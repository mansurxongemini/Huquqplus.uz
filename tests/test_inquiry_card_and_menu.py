from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app import inquiry_card
from src.app.inquiry_card import InquiryPayload, post_inquiry_card, render_inquiry_card
from src.app.keyboards import get_role_menu, menu_button_texts
from src.app.middlewares import MenuButtonResetMiddleware
from src.app.translations import t
from src.models.inquiry import Inquiry, InquiryMediaType
from src.models.user import User


def _user():
    return User(user_id=10, first_name="Ali", last_name="Valiyev", language="uz", phone="+998901234567")


def _inquiry(**kw):
    base = dict(id=31, user_id=10, section_name="Mehnat", question="Ish haqi to'lanmayapti",
                question_mediatype=InquiryMediaType.text, group_id="-1002245081621", group_question_id=5003)
    base.update(kw)
    return Inquiry(**base)


def test_text_card_has_question_and_separate_user_lines():
    html_text, is_caption = render_inquiry_card(_inquiry(), None, user=_user())
    assert not is_caption
    assert "<blockquote>Ish haqi to&#x27;lanmayapti</blockquote>" in html_text
    # foydalanuvchi ma'lumotlari alohida qatorlarda (sulguk <br/>), bitta qatorga qo'shilib ketmaydi
    assert html_text.count("<br/>") >= 5


def test_responsible_line_rendered_from_db_not_from_old_message():
    vol = SimpleNamespace(full_name="Mansurxon Rustamov")
    with patch("src.models.volunteer.Volunteer.get_by_user_id", return_value=vol):
        html_text, _ = render_inquiry_card(_inquiry(assigned_volunteer_id=777), MagicMock(), user=_user())
    assert "Mas'ul volontyor" in html_text and "Mansurxon Rustamov" in html_text


def test_legacy_media_question_file_id_is_not_shown():
    inq = _inquiry(question="AwACAgIAAxkBAAIBQ2abcDEF1234567890", question_mediatype=InquiryMediaType.voice)
    html_text, is_caption = render_inquiry_card(inq, None, user=_user())
    assert is_caption
    assert "AwACAgIA" not in html_text


@pytest.mark.asyncio
async def test_post_text_inquiry_returns_full_question_and_continuation():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[SimpleNamespace(message_id=1), SimpleNamespace(message_id=2)])
    long_text = ("Gap. " * 700).strip()
    card, cont, question = await post_inquiry_card(bot, "-100123", _user(), InquiryPayload(InquiryMediaType.text, text=long_text))
    assert card.message_id == 1 and cont.message_id == 2
    assert question == long_text
    assert bot.send_message.await_args_list[1].kwargs["reply_to_message_id"] == 1


@pytest.mark.asyncio
async def test_post_photo_inquiry_keeps_caption_in_question():
    bot = MagicMock()
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=7))
    payload = InquiryPayload(InquiryMediaType.photo, file_id="PHOTO", caption="Hujjat rasmi")
    card, cont, question = await post_inquiry_card(bot, "-100123", _user(), payload)
    assert cont is None
    assert "Hujjat rasmi" in question
    assert bot.send_photo.await_args.kwargs["photo"] == "PHOTO"


def test_card_markup_has_only_assign_button():
    rows = inquiry_card.inquiry_card_markup(31).inline_keyboard
    assert [[b.callback_data for b in row] for row in rows] == [["inq_assign:31:1"]]


def test_volunteer_gets_volunteer_menu_with_citizen_toggle():
    with patch("src.app.keyboards.is_volunteer_menu_user", return_value=True):
        markup = get_role_menu(10, "uz", MagicMock())
    texts = [b.text for row in markup.keyboard for b in row]
    assert t("menu_vol_review", "uz") in texts and t("menu_vol_citizen", "uz") in texts
    assert t("menu_profile", "uz") not in texts


@pytest.mark.asyncio
@pytest.mark.parametrize("text, cleared", [
    (t("menu_profile", "ru"), True),
    (t("menu_vol_review", "oz"), True),
    ("Bu mening fikrim", False),
])
async def test_menu_button_resets_waiting_state(text, cleared):
    state = AsyncMock()
    data = {"raw_state": "FeedbackState:waiting", "state": state}
    message = MagicMock()
    message.__class__ = __import__("aiogram").types.Message
    message.chat.type = "private"
    message.text = text
    handler = AsyncMock()
    await MenuButtonResetMiddleware()(handler, message, data)
    assert (data["raw_state"] is None) is cleared
    assert state.clear.await_count == (1 if cleared else 0)
    handler.assert_awaited_once()


def test_menu_texts_cover_all_languages():
    texts = menu_button_texts()
    for lang in ("uz", "oz", "ru"):
        assert t("menu_inquiry", lang) in texts


@pytest.mark.asyncio
async def test_group_assign_message_has_no_missing_link_note():
    from src.routes.aiogram import inquiry_assign
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=9))
    basic_group = _inquiry(group_id="-5350260753", assigned_volunteer_id=777)
    await inquiry_assign._post_group_assign_message(bot, basic_group.group_id, basic_group, "Ali Valiyev", "ali_v")
    text = bot.send_message.await_args.kwargs["text"]
    assert "mavjud emas" not in text
    assert text.startswith("@ali_v<br/>")

    supergroup = _inquiry(assigned_volunteer_id=777)
    await inquiry_assign._post_group_assign_message(bot, supergroup.group_id, supergroup, "Ali Valiyev", None)
    assert "https://t.me/c/2245081621/5003" in bot.send_message.await_args.kwargs["text"]


def test_core_group_handlers_present():
    """Tahrirlashda asosiy handlerlar tasodifan o'chib ketmasligi uchun."""
    from src.routes.aiogram import group_router
    for name in ("handle_response", "handle_group_yurist_command", "claim_appointment_callback",
                 "escalate_restore_callback", "edit_message", "send_answer_to_citizen"):
        assert callable(getattr(group_router, name, None)), name


def test_multiline_citizen_text_keeps_line_breaks():
    html_text, _ = render_inquiry_card(_inquiry(question="1-qator\n2-qator"), None, user=_user())
    assert "1-qator<br/>2-qator" in html_text


def test_all_src_modules_import():
    """Ishlatilmaydigan importlarni tozalashdan keyin qayta-eksport sinmaganini tekshiradi."""
    import importlib
    import pkgutil

    import src
    failed = []
    for mod in pkgutil.walk_packages(src.__path__, "src."):
        if "-old" in mod.name or "alembic" in mod.name or mod.name in ("src.main", "src.run_polling"):
            continue
        try:
            importlib.import_module(mod.name)
        except SystemExit:
            pass
        except ModuleNotFoundError as e:
            if (e.name or "").startswith("src"):
                failed.append(f"{mod.name}: {e}")  # loyiha moduli yo'q; tashqi kutubxona (celery) bo'lmasa — o'tkazamiz
        except ImportError as e:
            failed.append(f"{mod.name}: {e}")
    assert not failed, failed


def test_admin_who_is_volunteer_can_use_panel():
    from src.routes.aiogram import volunteer_assign
    vol = SimpleNamespace(user_id=8904838656, is_active=True)
    from src.config.settings import Settings
    with patch.object(volunteer_assign.Volunteer, "get_by_user_id", return_value=vol), \
         patch.object(Settings, "is_admin", lambda self, uid: True):
        assert volunteer_assign._active_volunteer(8904838656, MagicMock()) is vol


@pytest.mark.asyncio
async def test_chat_migration_retries_with_new_id():
    from aiogram.exceptions import TelegramMigrateToChat
    from aiogram.methods import SendMessage
    from src.app.middlewares import ChatMigrationRequestMiddleware
    mw = ChatMigrationRequestMiddleware()
    mw.migrations.clear()
    calls = []

    async def make_request(bot, method):
        calls.append(method.chat_id)
        if method.chat_id == -5350260753:
            raise TelegramMigrateToChat(method=method, message="upgraded", migrate_to_chat_id=-1004291925995)
        return "ok"

    method = SendMessage(chat_id=-5350260753, text="x")
    assert await mw(make_request, MagicMock(), method) == "ok"
    assert calls == [-5350260753, -1004291925995]
    # keyingi so'rov darhol yangi ID ga ketadi
    calls.clear()
    assert await mw(make_request, MagicMock(), SendMessage(chat_id="-5350260753", text="y")) == "ok"
    assert calls == [-1004291925995]


def test_every_t_key_used_in_code_exists():
    """t("kalit") chaqiruvlari tarjimada bor: aks holda foydalanuvchi xom kalit nomini ko'radi."""
    import glob
    import re
    from src.app.translations import TRANSLATIONS
    missing = []
    for path in glob.glob("src/**/*.py", recursive=True):
        for m in re.finditer(r'\bt\(\s*"([^"]+)"', open(path, encoding="utf-8").read()):
            if m.group(1) not in TRANSLATIONS:
                missing.append(f"{path}: {m.group(1)}")
    assert not missing, missing


@pytest.mark.asyncio
async def test_review_offers_choice_when_several_assignments():
    from src.routes.aiogram import volunteer_assign
    pairs = [(SimpleNamespace(id=1), _inquiry(id=33)), (SimpleNamespace(id=2), _inquiry(id=34, section_name="Uy-joy"))]
    message, state = AsyncMock(), AsyncMock()
    with patch.object(volunteer_assign, "get_open_assignments", return_value=pairs):
        await volunteer_assign._start_review(message, state, SimpleNamespace(user_id=5), "uz", MagicMock())
    state.set_state.assert_not_awaited()
    kb = message.answer.await_args.kwargs["reply_markup"].inline_keyboard
    assert [row[0].callback_data for row in kb] == ["volrv:33", "volrv:34"]


@pytest.mark.asyncio
async def test_review_single_assignment_asks_directly():
    from src.routes.aiogram import volunteer_assign
    pairs = [(SimpleNamespace(id=1), _inquiry(id=33))]
    message, state = AsyncMock(), AsyncMock()
    with patch.object(volunteer_assign, "get_open_assignments", return_value=pairs):
        await volunteer_assign._start_review(message, state, SimpleNamespace(user_id=5), "uz", MagicMock())
    state.update_data.assert_awaited_with(review_inquiry_id=33, review_assignment_id=1)
    assert "Ish haqi" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_gate_notice_goes_private_and_removes_group_reply():
    from src.routes.aiogram import group_router
    bot = MagicMock()
    bot.send_message = AsyncMock()
    message = MagicMock()
    message.text = "Javob loyihasi"
    message.caption = None
    message.from_user.id = 77
    message.delete = AsyncMock()
    message.reply = AsyncMock()
    await group_router._gate_notice(message, bot, "⚠️ Avval tasdiqlating")
    assert bot.send_message.await_args.kwargs["chat_id"] == 77
    assert "Javob loyihasi" in bot.send_message.await_args.kwargs["text"]
    message.delete.assert_awaited_once()
    message.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_approved_answer_delivers_and_finalizes():
    import json as _json
    from src.app.assign_helpers import review_draft_hash
    from src.models.assignment import InquiryAssignment
    from src.routes.aiogram import group_router, volunteer_assign
    from src.models.inquiry import InquiryStatus

    text = "Mehnat kodeksining 427-moddasiga ko'ra ..."
    inquiry = _inquiry(id=40, status=InquiryStatus.active, assigned_volunteer_id=5, private_question_id=11)
    assignment = InquiryAssignment(id=9, inquiry_id=40, volunteer_user_id=5, assigned_by=1, status="notified",
                                   review_status="passed", review_draft_hash=review_draft_hash(text),
                                   review_json=_json.dumps({"verdict": "approve", "approved_text": text}))
    db = MagicMock()
    db.get.side_effect = lambda model, pk: assignment if model is InquiryAssignment else inquiry
    vol = SimpleNamespace(user_id=5, full_name="Ali Valiyev")
    query = AsyncMock()
    query.data = "volsend:9"
    query.from_user.id = 5
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=77))
    redis = MagicMock()
    redis.set.return_value = True
    with patch.object(volunteer_assign, "_active_volunteer", return_value=vol), \
         patch("src.database.redisdb.get_redis", return_value=redis), \
         patch.object(group_router, "send_answer_to_citizen", AsyncMock(return_value=(True, "success", None))) as send, \
         patch.object(group_router, "finalize_inquiry_answer", AsyncMock()) as fin, \
         patch("src.app.inquiry_card.refresh_inquiry_card", AsyncMock(return_value=True)):
        await volunteer_assign.vol_send_approved_callback(query, db, bot)
    assert send.await_args.args[1]["text"] == text and send.await_args.args[1]["chat_id"] == 10
    assert bot.send_message.await_args.kwargs["reply_to_message_id"] == 5003  # guruhdagi kartaga reply
    fin.assert_awaited_once()
    assert inquiry.answer == text
