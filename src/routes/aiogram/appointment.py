import html
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LinkPreviewOptions,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE

from src.app.html_utils import escape_multiline
from src.app.appointment_card import (
    CARD_DESC_LIMIT,
    render_appointment_card,
    get_appointment_markup,
    get_appointment_type_display,
)
from src.app.calendar_utils import format_uz_date
from src.app.keyboards import get_role_menu
from src.app.translations import t, get_appointment_text, LANG_UZ
from src.config.settings import settings
from sqlalchemy import or_
from sqlmodel import select
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.routes.deps.db_session import DBSession
import logging

logger = logging.getLogger(__name__)

appointment_router = Router(name="appointment")


class AppointmentState(StatesGroup):
    choosing_appointment_type = State()
    entering_problem_and_media = State()
    confirming_booking = State()


class AppointmentFeedbackState(StatesGroup):
    waiting_for_feedback = State()


def find_active_appointment(db_session: DBSession, user_id: int, app_type: str) -> Appointment | None:
    """Fuqaroning shu turdagi faol arizasi. Vaqti bir kundan ko'proq o'tib ketgan, lekin yakunlanmay
    qolgan ariza hisobga olinmaydi — aks holda u yangi arizaga abadiy to'siq bo'lib qoladi."""
    stale_before = datetime.now() - timedelta(days=1)
    return db_session.exec(
        select(Appointment).where(
            Appointment.user_id == user_id,
            Appointment.appointment_type == app_type,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted]),
            or_(Appointment.scheduled_at.is_(None), Appointment.scheduled_at >= stale_before),
        )
    ).first()


# --- Step 1: Start Appointment & Choose Type ---


@appointment_router.message(
    F.text.in_([t("menu_appointment", "uz"), t("menu_appointment", "oz"), t("menu_appointment", "ru"), "✍️ Yurist qabuliga yozilish", "✍️ Юрист қабулига ёзилиш", "✍️ Запись к юристу"])
)
async def start_appointment(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        return await message.answer(t("user_not_found", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    if user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    await state.clear()
    await state.set_state(AppointmentState.choosing_appointment_type)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("appointment_remote_btn", lang), callback_data="remote_appointment")],
            [InlineKeyboardButton(text=t("appointment_in_person_btn", lang), callback_data="in_person_appointment")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="app_cancel")]
        ]
    )
    await message.answer(
        get_appointment_text(lang),
        reply_markup=kb,
        disable_web_page_preview=True,
        parse_mode=SULGUK_PARSE_MODE,
    )


# --- Step 2: Choose Lawyer (or directly Date if in-person) ---


@appointment_router.callback_query(
    AppointmentState.choosing_appointment_type,
    F.data.in_(["remote_appointment", "in_person_appointment", "app_cancel"])
)
async def process_appointment_type(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if query.data == "app_cancel":
        await state.clear()
        user = User.get_by_user_id(query.from_user.id, db_session)
        lang = user.language if user else LANG_UZ
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(query.from_user.id, lang, db_session))

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    app_type = query.data

    # Check if user already has an active appointment of this type
    active_app = find_active_appointment(db_session, user.user_id, app_type)

    if active_app:
        await state.clear()
        if app_type == "in_person_appointment":
            lawyer_display = t("app_lawyer_office", lang)
        else:
            lawyer_obj = OfficialLawyer.get_by_user_id(active_app.lawyer_id, db_session) if active_app.lawyer_id else None
            lawyer_display = lawyer_obj.full_name if lawyer_obj else t("app_lawyer_any", lang)
        warning_card = t(
            "app_active_warning", lang,
            id=active_app.id,
            app_type=get_appointment_type_display(app_type, lang),
            time=format_uz_date(active_app.scheduled_at) if active_app.scheduled_at else t("app_time_not_set", lang),
            lawyer=html.escape(lawyer_display),
            status=t("app_status_pending" if active_app.status == AppointmentStatus.pending else "app_status_accepted", lang),
        )

        builder = InlineKeyboardBuilder()
        builder.button(
            text=t("btn_app_cancel_mine", lang),
            callback_data=f"app_user_cancel_prompt:{active_app.id}"
        )
        builder.button(
            text=t("btn_back_main", lang),
            callback_data="app_cancel"
        )
        builder.adjust(1)

        await query.message.edit_text(warning_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        return await query.answer()

    await state.update_data(appointment_type=app_type)
    await state.set_state(AppointmentState.entering_problem_and_media)

    send_btn_label = t("btn_send", lang)
    action_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=send_btn_label),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )

    prompt = t("app_problem_prompt", lang)

    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(prompt, reply_markup=action_kb, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# --- Step 6: Capture Problem Description / Media and Show Confirmation Card ---


async def render_confirmation_card(target_message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")
    problem_text = data.get("problem_description", "")

    media_items = list(data.get("media_items", []))
    if not media_items and data.get("media_file_id"):
        media_items = [{
            "type": data.get("media_type", "document"),
            "file_id": data.get("media_file_id"),
            "name": data.get("media_name", "Fayl"),
            "caption": ""
        }]

    if not media_items:
        media_display = t("app_media_text_only", lang)
    elif len(media_items) == 1:
        media_display = f"📄 {html.escape(media_items[0]['name'])}"
    else:
        media_display = t("app_media_count", lang, n=len(media_items),
                          names=html.escape(", ".join(item["name"] for item in media_items)))
    desc_display = problem_text.strip() if problem_text and problem_text.strip() else t("app_desc_by_media", lang)
    preview_card = t(
        "app_preview", lang,
        app_type=get_appointment_type_display(app_type, lang),
        media=media_display,
        desc=escape_multiline(desc_display[:350]),
    )

    btn_confirm_label = t("btn_app_confirm", lang)
    builder = InlineKeyboardBuilder()
    builder.button(text=btn_confirm_label, callback_data="app_confirm:yes")
    builder.button(text=t("btn_cancel", lang), callback_data="app_cancel")
    builder.adjust(1)

    confirm_reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=btn_confirm_label),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )

    await target_message.answer(preview_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    confirm_prompt = t("app_confirm_prompt", lang)
    await target_message.answer(
        confirm_prompt,
        reply_markup=confirm_reply_kb,
        parse_mode=SULGUK_PARSE_MODE
    )


MEDIA_ICONS = {"voice": "🎤", "video_note": "📹", "video": "📹", "photo": "📷", "document": "📄"}


def appointment_media_item(message: Message, lang: str) -> dict | None:
    """Qabul arizasiga biriktiriladigan fayl tavsifi (nomi fuqaro tilida)."""
    if message.voice:
        kind, file_id, name = "voice", message.voice.file_id, t("media_voice", lang)
    elif message.video_note:
        kind, file_id, name = "video_note", message.video_note.file_id, t("media_video_note", lang)
    elif message.video:
        kind, file_id, name = "video", message.video.file_id, t("media_video", lang)
    elif message.document:
        kind, file_id, name = "document", message.document.file_id, message.document.file_name or t("media_document", lang)
    elif message.photo:
        kind, file_id, name = "photo", message.photo[-1].file_id, t("media_photo", lang)
    else:
        return None
    return {"type": kind, "file_id": file_id, "name": name, "caption": message.caption or f"{MEDIA_ICONS[kind]} {name}"}


def _append_text(current: str, extra: str | None) -> str:
    if not extra:
        return current
    return f"{current}\n{extra}".strip() if current else extra


_user_appointment_locks: dict[int, asyncio.Lock] = {}
_pending_media_ack_tasks: dict[int, asyncio.Task] = {}


def get_appointment_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_appointment_locks:
        _user_appointment_locks[user_id] = asyncio.Lock()
    return _user_appointment_locks[user_id]


@appointment_router.message(
    AppointmentState.entering_problem_and_media,
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"]),
)
async def cancel_at_media_step(message: Message, state: FSMContext, db_session: DBSession):
    user_id = message.from_user.id
    if user_id in _pending_media_ack_tasks:
        _pending_media_ack_tasks[user_id].cancel()
        _pending_media_ack_tasks.pop(user_id, None)

    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@appointment_router.message(AppointmentState.entering_problem_and_media)
async def handle_appointment_media_input(message: Message, state: FSMContext, db_session: DBSession):
    user_id = message.from_user.id
    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        if user_id in _pending_media_ack_tasks:
            _pending_media_ack_tasks[user_id].cancel()
            _pending_media_ack_tasks.pop(user_id, None)
        await state.clear()
        return await message.answer(t("user_not_found", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    if user.is_blocked:
        if user_id in _pending_media_ack_tasks:
            _pending_media_ack_tasks[user_id].cancel()
            _pending_media_ack_tasks.pop(user_id, None)
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    # Check if user pressed "📤 Yuborish" / "📩 Yuborish"
    is_submit = (
        message.text in [
            "📤 Yuborish", "📤 Юбориш", "📤 Отправить",
            "📩 Yuborish", "📩 Юбориш", "📩 Отправить",
            "✅ Yuborish", "✅ Юбориш", "✅ Отправить",
            "Yuborish", "Юбориш", "Отправить",
            "✅ Qabulni tasdiqlash", "✅ Қабулни тасдиқлаш", "✅ Подтвердить прием"
        ]
        # matnda "yuborish" so'zi bo'lishi tugma bosilgani emas: fuqaro "ariza yuborish kerakmi?" deb yozishi mumkin
    )
    if is_submit:
        if user_id in _pending_media_ack_tasks:
            _pending_media_ack_tasks[user_id].cancel()
            _pending_media_ack_tasks.pop(user_id, None)

        async with get_appointment_user_lock(user_id):
            data = await state.get_data()
            if not data.get("problem_description") and not data.get("media_items") and not data.get("media_file_id"):
                warning_text = t("app_nothing_to_send", lang)
                return await message.answer(warning_text, parse_mode=SULGUK_PARSE_MODE)

            await state.set_state(AppointmentState.confirming_booking)
            return await render_confirmation_card(message, state, lang)

    # Atomically read and update media/problem description under per-user lock
    async with get_appointment_user_lock(user_id):
        data = await state.get_data()
        current_desc = data.get("problem_description", "")
        media_items = list(data.get("media_items", []))

        is_media_msg = bool(message.voice or message.video_note or message.video or message.document or message.photo)
        if is_media_msg and len(media_items) >= 10:
            limit_err = t("appointment_media_limit_reached", lang)
            return await message.answer(limit_err, parse_mode=SULGUK_PARSE_MODE)

        if message.text:
            current_desc = _append_text(current_desc, message.text)
        else:
            item = appointment_media_item(message, lang)
            if item is None:
                return await message.answer(t("app_unsupported_media", lang))
            media_items.append(item)
            current_desc = _append_text(current_desc, message.caption)
        latest_media = media_items[-1] if media_items else None
        await state.update_data(
            media_items=media_items,
            media_type=latest_media["type"] if latest_media else "text",
            media_file_id=latest_media["file_id"] if latest_media else None,
            media_name=latest_media["name"] if latest_media else None,
            problem_description=current_desc
        )

    # Cancel previous ack task if one was scheduled
    if user_id in _pending_media_ack_tasks:
        _pending_media_ack_tasks[user_id].cancel()

    # Schedule debounced acknowledgement (0.7s) to combine album updates or rapid multi-file uploads into 1 clean reply
    bot = message.bot
    chat_id = message.chat.id

    async def _send_debounced_ack():
        try:
            await asyncio.sleep(0.7)
            async with get_appointment_user_lock(user_id):
                current_state = await state.get_state()
                if current_state != AppointmentState.entering_problem_and_media:
                    return

                d = await state.get_data()
                cur_media = list(d.get("media_items", []))
                send_btn_label = t("btn_send", lang)
                action_kb = ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text=send_btn_label),
                            KeyboardButton(text=t("btn_cancel", lang)),
                        ]
                    ],
                    resize_keyboard=True,
                )

                items_info = ""
                if cur_media:
                    items_info = t("app_files_received", lang, n=len(cur_media),
                                   names=html.escape(", ".join(it["name"] for it in cur_media)))
                ack_prompt = t("app_info_received", lang, files=items_info)

                await bot.send_message(
                    chat_id=chat_id,
                    text=ack_prompt,
                    reply_markup=action_kb,
                    parse_mode=SULGUK_PARSE_MODE
                )
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning("Failed to send debounced appointment media ack: %s", ex)
        finally:
            _pending_media_ack_tasks.pop(user_id, None)

    _pending_media_ack_tasks[user_id] = asyncio.create_task(_send_debounced_ack())


# --- Step 7: Confirm Booking & Dispatch to Lawyer Group ---


async def execute_appointment_submission(user: User, lang: str, state: FSMContext, db_session: DBSession, bot: Bot, message_target: Message, is_callback: bool = False, query: CallbackQuery | None = None):
    if user.user_id in _pending_media_ack_tasks:
        _pending_media_ack_tasks[user.user_id].cancel()
        _pending_media_ack_tasks.pop(user.user_id, None)

    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")
    problem_description = data.get("problem_description", "")

    media_items = list(data.get("media_items", []))
    if not media_items and data.get("media_file_id"):
        media_items = [{
            "type": data.get("media_type", "document"),
            "file_id": data.get("media_file_id"),
            "name": data.get("media_name", "Fayl"),
            "caption": ""
        }]

    # Guard against duplicate active appointment of same type
    existing_active = find_active_appointment(db_session, user.user_id, app_type)
    if existing_active:
        msg = t("app_already_active_short", lang, id=existing_active.id)
        await state.clear()
        if is_callback and query:
            await query.answer(msg, show_alert=True)
        else:
            await message_target.answer(msg, reply_markup=get_role_menu(user.user_id, lang, db_session))
        return

    # Create Appointment record
    latest_media = media_items[-1] if media_items else None
    primary_type = latest_media["type"] if latest_media else "text"
    primary_fid = latest_media["file_id"] if latest_media else None
    primary_name = latest_media["name"] if latest_media else None
    media_meta_json = json.dumps(media_items, ensure_ascii=False) if media_items else None

    desc_cleaned = problem_description.strip() if problem_description and problem_description.strip() else "(Muammo audio/video/fayl orqali bayon etilgan)"

    app = Appointment(
        user_id=user.user_id,
        appointment_type=app_type,
        problem_description=desc_cleaned,
        lawyer_id=None,
        scheduled_at=None,
        media_type=primary_type,
        media_file_id=primary_fid,
        media_name=primary_name,
        media_meta=media_meta_json,
        status=AppointmentStatus.pending,
        reminder_sent=False
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    # kartada matnning boshi ko'rinadi, qolgani davom xabarida (hech narsa tushib qolmasin)
    desc_part2 = desc_cleaned[CARD_DESC_LIMIT:].strip() if len(desc_cleaned) > CARD_DESC_LIMIT else ""

    group_caption = render_appointment_card(app, db_session)
    group_markup = get_appointment_markup(app)

    group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
    group_msg = None

    try:
        group_msg = await bot.send_message(
            chat_id=group_id,
            text=group_caption,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        logger.info("Dispatched appointment %s to lawyer group %s", app.id, group_id)
    except Exception as e:
        logger.error("Failed to dispatch appointment to lawyer group: %s", e)

    if group_msg:
        app.group_message_id = group_msg.message_id
        db_session.add(app)
        db_session.commit()

        if desc_part2:
            try:
                await bot.send_message(
                    chat_id=group_id,
                    text=f"📌 <b>Ariza №{app.id} — Muammo tavsifining davomi:</b><br/><p><blockquote>{escape_multiline(desc_part2)}</blockquote></p>",
                    reply_to_message_id=group_msg.message_id,
                    parse_mode=SULGUK_PARSE_MODE,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            except Exception as e:
                logger.warning("Failed to send appointment problem continuation: %s", e)

        # Send all attached media items (voice, video, note, doc, photo) as threaded replies to group_msg
        media_count = len(media_items)
        for idx, item in enumerate(media_items, 1):
            await asyncio.sleep(0.15)
            m_type = item.get("type")
            m_fid = item.get("file_id")
            m_name = item.get("name", "Fayl")
            caption_note = f"📎 Ariza №{app.id} ilovasi ({idx}/{media_count}): {m_name}"
            try:
                if m_type == "voice":
                    await bot.send_voice(
                        chat_id=group_id,
                        voice=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "video_note":
                    await bot.send_video_note(
                        chat_id=group_id,
                        video_note=m_fid,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "video":
                    await bot.send_video(
                        chat_id=group_id,
                        video=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "document":
                    await bot.send_document(
                        chat_id=group_id,
                        document=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "photo":
                    await bot.send_photo(
                        chat_id=group_id,
                        photo=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
            except Exception as me:
                logger.warning("Failed to send attached media %d (%s) to lawyer group: %s", idx, m_type, me)

    await state.clear()

    if is_callback and query:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.answer()

    app_type_text = get_appointment_type_display(app.appointment_type, lang)

    success_msg = t("app_submitted", lang, id=app.id, app_type=app_type_text)

    await message_target.answer(success_msg, reply_markup=get_role_menu(user.user_id, lang, db_session), parse_mode=SULGUK_PARSE_MODE)


@appointment_router.callback_query(AppointmentState.confirming_booking, F.data == "app_confirm:yes")
async def confirm_booking_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await execute_appointment_submission(user, lang, state, db_session, bot, message_target=query.message, is_callback=True, query=query)


@appointment_router.message(
    AppointmentState.confirming_booking,
    F.text.in_([
        "✅ Qabulni tasdiqlash", "✅ Подтвердить прием", "✅ Қабулни тасдиқлаш",
        "✅ Tasdiqlash", "✅ Тасдиқлаш",
        "📤 Yuborish", "📤 Отправить", "📤 Юбориш",
        "✅ Ha", "✅ Да", "✅ Ҳа"
    ])
)
async def confirm_booking_text_message(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await execute_appointment_submission(user, lang, state, db_session, bot, message_target=message, is_callback=False)


@appointment_router.message(
    AppointmentState.confirming_booking,
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "ru"), t("btn_cancel", "oz"), "❌ Bekor qilish", "❌ Отмена", "❌ Бекор қилиш"])
)
async def cancel_booking_text_message(message: Message, state: FSMContext, db_session: DBSession):
    user_id = message.from_user.id
    if user_id in _pending_media_ack_tasks:
        _pending_media_ack_tasks[user_id].cancel()
        _pending_media_ack_tasks.pop(user_id, None)

    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@appointment_router.message(AppointmentState.confirming_booking)
async def extra_media_in_confirming(message: Message, state: FSMContext, db_session: DBSession):
    user_id = message.from_user.id
    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ

    async with get_appointment_user_lock(user_id):
        data = await state.get_data()
        current_desc = data.get("problem_description", "")
        media_items = list(data.get("media_items", []))

        is_media_msg = bool(message.voice or message.video_note or message.video or message.document or message.photo)
        if is_media_msg and len(media_items) >= 10:
            limit_err = t("appointment_media_limit_reached", lang)
            return await message.answer(limit_err, parse_mode=SULGUK_PARSE_MODE)

        if message.text:
            current_desc = _append_text(current_desc, message.text)
        else:
            item = appointment_media_item(message, lang)
            if item is None:
                return
            media_items.append(item)
            current_desc = _append_text(current_desc, message.caption)
        latest_media = media_items[-1] if media_items else None
        await state.update_data(
            media_items=media_items,
            media_type=latest_media["type"] if latest_media else "text",
            media_file_id=latest_media["file_id"] if latest_media else None,
            media_name=latest_media["name"] if latest_media else None,
            problem_description=current_desc
        )
        await render_confirmation_card(message, state, lang)


@appointment_router.callback_query(F.data == "app_cancel", StateFilter("*"))
async def cancel_appointment_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user_id = query.from_user.id
    if user_id in _pending_media_ack_tasks:
        _pending_media_ack_tasks[user_id].cancel()
        _pending_media_ack_tasks.pop(user_id, None)

    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(query.from_user.id, lang, db_session))
    try:
        await query.answer()
    except Exception:
        pass


# --- Appointment Rating Handlers ---


@appointment_router.callback_query(F.data.startswith("rate:appointment:"))
async def handle_appointment_rating(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    parts = query.data.split(":")
    app_id = int(parts[2])
    stars = int(parts[3])

    app = Appointment.get_by_id(app_id, db_session)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if app:
        app.rating = stars
        app.rated_at = datetime.now()
        db_session.add(app)
        db_session.commit()

    await query.answer(f"Bahoyingiz: {stars} ⭐", show_alert=False)

    text = f"{t('rate_received_thanks', lang)}<br/><br/>{t('rate_leave_feedback', lang)}"
    await query.message.edit_text(text, parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(AppointmentFeedbackState.waiting_for_feedback)
    await state.update_data(rating_appointment_id=app_id)


@appointment_router.message(AppointmentFeedbackState.waiting_for_feedback)
async def handle_appointment_feedback_message(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text in [
        t("menu_profile", "uz"), t("menu_profile", "ru"),
        t("menu_benefits", "uz"), t("menu_benefits", "ru"),
        t("menu_inquiry", "uz"), t("menu_inquiry", "ru"),
        t("menu_appointment", "uz"), t("menu_appointment", "ru"),
        t("menu_about_us", "uz"), t("menu_about_us", "ru"),
        t("menu_help", "uz"), t("menu_help", "ru"),
        t("btn_change_lang", "uz"), t("btn_change_lang", "ru"),
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
    ]:
        await state.clear()
        return

    data = await state.get_data()
    app_id = data.get("rating_appointment_id")
    if app_id:
        app = Appointment.get_by_id(app_id, db_session)
        if app and message.text:
            app.feedback = message.text.strip()
            db_session.add(app)
            db_session.commit()

    await state.clear()
    await message.answer(t("feedback_recorded", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


# --- User-initiated Appointment Cancellation ---


@appointment_router.callback_query(F.data.startswith("app_user_cancel_prompt:"), StateFilter("*"))
async def app_user_cancel_prompt_handler(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await state.clear()
    app_id = int(query.data.split(":")[1])
    app = db_session.get(Appointment, app_id)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not app or app.user_id != query.from_user.id:
        return await query.answer(t("app_not_found", lang), show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_app_cancel_yes", lang), callback_data=f"app_user_cancel_confirm:{app_id}")
    builder.button(text=t("btn_app_cancel_no", lang), callback_data="app_cancel")
    builder.adjust(1)
    confirm_text = t("app_cancel_confirm", lang, id=app_id)
    await query.message.edit_text(confirm_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@appointment_router.callback_query(F.data.startswith("app_user_cancel_confirm:"), StateFilter("*"))
async def app_user_cancel_confirm_handler(query: CallbackQuery, db_session: DBSession, bot: Bot, state: FSMContext):
    await state.clear()
    app_id = int(query.data.split(":")[1])
    app = db_session.get(Appointment, app_id)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not app or app.user_id != query.from_user.id:
        return await query.answer(t("app_not_found", lang), show_alert=True)

    if app.status in [AppointmentStatus.completed, AppointmentStatus.cancelled]:
        alert_msg = t("app_already_closed", lang)
        await query.answer(alert_msg, show_alert=True)
        return await query.message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(query.from_user.id, lang, db_session))

    app.status = AppointmentStatus.cancelled
    app.cancellation_reason = "Foydalanuvchi tomonidan bekor qilindi"
    app.updated_at = datetime.now()
    db_session.add(app)
    db_session.commit()
    logger.info("Appointment %s cancelled by citizen %s", app.id, query.from_user.id)

    # If message was posted in lawyer group, notify group and update card
    if app.group_message_id:
        group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
        try:
            card_text = render_appointment_card(app, db_session)
            card_markup = get_appointment_markup(app)
            await bot.edit_message_text(
                chat_id=group_id,
                message_id=app.group_message_id,
                text=card_text,
                reply_markup=card_markup,
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception as e:
            logger.warning("Failed to update group card on cancel: %s", e)

        try:
            await bot.send_message(
                chat_id=group_id,
                text=f"⚠️ <b>Ariza №{app.id}</b> fuqaro tomonidan bekor qilindi.",
                reply_to_message_id=app.group_message_id,
                parse_mode=SULGUK_PARSE_MODE
            )
        except Exception as e:
            logger.warning("Failed to notify group of user cancellation: %s", e)

    await query.answer(t("app_cancelled_short", lang))
    success_text = t("app_cancelled_by_citizen", lang, id=app.id)
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(success_text, reply_markup=get_role_menu(query.from_user.id, lang, db_session), parse_mode=SULGUK_PARSE_MODE)


@appointment_router.callback_query(F.data.startswith("app_att:"), StateFilter("*"))
async def appointment_attendance_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    """Fuqaro qabulga tayyorligini tasdiqlaydi yoki boshqa vaqt kerakligini bildiradi."""
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = (user.language if user else None) or LANG_UZ
    try:
        _, app_id_s, answer = query.data.split(":")
        app = db_session.get(Appointment, int(app_id_s))
    except (ValueError, IndexError):
        app, answer = None, ""
    if not app or app.user_id != query.from_user.id or answer not in ("yes", "no"):
        return await query.answer(t("app_not_found", lang), show_alert=True)
    if app.status not in (AppointmentStatus.pending, AppointmentStatus.accepted):
        await query.answer(t("app_already_closed", lang), show_alert=True)
        return await query.message.edit_reply_markup(reply_markup=None)

    app.citizen_confirmation = answer
    app.updated_at = datetime.now()
    db_session.add(app)
    db_session.commit()
    logger.info("Appointment %s: citizen attendance=%s", app.id, answer)
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.answer(t("app_attend_yes_reply" if answer == "yes" else "app_attend_no_reply", lang))

    if app.group_message_id:
        group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
        try:
            await bot.edit_message_text(
                chat_id=group_id, message_id=app.group_message_id,
                text=render_appointment_card(app, db_session), reply_markup=get_appointment_markup(app),
                parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.info("Appointment %s card not refreshed: %s", app.id, e)
        if answer == "no":
            try:
                await bot.send_message(
                    chat_id=group_id,
                    text=f"⚠️ <b>Ariza №{app.id}:</b> fuqaro belgilangan vaqtda qatnasha olmasligini bildirdi — yangi vaqt belgilang.",
                    reply_to_message_id=app.group_message_id,
                    parse_mode=SULGUK_PARSE_MODE,
                )
            except Exception as e:
                logger.info("Appointment %s group notice failed: %s", app.id, e)
