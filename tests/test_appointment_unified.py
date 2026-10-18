"""
tests/test_appointment_unified.py
Comprehensive test suite verifying unified appointment system:
1. Unified card formatting (render_appointment_card & render_escalated_appointment_card).
2. Unified inline markups across all lifecycle states (pending, accepted, cancelled, completed).
3. Callback data length invariant (<= 64 bytes).
4. Restore handler permission enforcement (only settings.is_admin) & expired time reset.
5. Media limit enforcement (maximum 10 media files, 11th rejected with localized warning).
6. Citizen notifications deleting previous notice (notify_citizen_appointment_update).
7. Removal of block buttons from inquiry and appointment cards.
"""

import json
from datetime import datetime, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery, User as TgUser, Chat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from src.models.appointment import Appointment, AppointmentStatus
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.user import User
from src.models.lawyer import OfficialLawyer
from src.app.appointment_card import (
    render_appointment_card,
    render_escalated_appointment_card,
    get_appointment_markup,
    get_appointment_type_display,
    notify_citizen_appointment_update,
)
from src.routes.aiogram.inquiry import get_inquiry_card_markup
from src.routes.aiogram.group_router import escalate_restore_callback
from src.routes.aiogram.appointment import (
    AppointmentState,
    handle_appointment_media_input,
    extra_media_in_confirming,
)


# ---------------------------------------------------------------------------
# 1. Unified Card Formatting Tests
# ---------------------------------------------------------------------------

def test_unified_card_rendering_citizen_and_escalated():
    """Verify render_appointment_card produces consistent structure for citizen & escalated appointments."""
    db_session = MagicMock()
    mock_user = User(
        user_id=111222,
        first_name="Mansur",
        last_name="Aliyev",
        phone="+998901234567"
    )
    mock_lawyer = OfficialLawyer(
        user_id=999888,
        full_name="Temur Huquqshunos",
        specialization="Fuqarolik huquqi"
    )

    future_time = datetime(2026, 12, 1, 14, 0)
    app = Appointment(
        id=77,
        user_id=111222,
        appointment_type="remote_appointment",
        problem_description="Mening aliment masalam bo'yicha maslahat kerak & iltimos yordam bering <tezroq>.",
        lawyer_id=999888,
        scheduled_at=future_time,
        status=AppointmentStatus.accepted,
        meeting_link="https://meet.google.com/abc-defg-hij?auth=1&user=2",
        media_meta=json.dumps([{"type": "photo", "file_id": "f1"}, {"type": "document", "file_id": "f2"}])
    )

    with patch("src.models.user.User.get_by_user_id", return_value=mock_user), \
         patch("src.models.lawyer.OfficialLawyer.get_by_user_id", return_value=mock_lawyer):
        card = render_appointment_card(app, db_session)

    # 1. Check title & headers
    assert "YURIST QABULIGA ARIZA (№77)" in card
    assert "FUQARO MA'LUMOTLARI:" in card
    assert "Mansur Aliyev" in card
    assert "+998901234567" in card

    # 2. Dynamic appointment type (never hardcoded static "Masofaviy")
    assert "Masofaviy" in card

    # 3. Media files count
    assert "2 ta fayl" in card

    # 4. Lawyer name
    assert "Temur Huquqshunos" in card

    # 5. Scheduled time formatted
    assert "14:00" in card

    # 6. Meeting link HTML escaped
    assert "https://meet.google.com/abc-defg-hij?auth=1&amp;user=2" in card

    # 7. Problem description HTML escaped
    assert "&amp; iltimos yordam bering &lt;tezroq&gt;" in card

    # 8. Test alias compatibility with escalated inquiry
    inquiry = Inquiry(
        id=55,
        user_id=111222,
        section_name="Ijtimoiy himoya",
        question="Inquiry question"
    )
    with patch("src.models.user.User.get_by_user_id", return_value=mock_user), \
         patch("src.models.lawyer.OfficialLawyer.get_by_user_id", return_value=mock_lawyer):
        escalated_card = render_escalated_appointment_card(app, db_session, inquiry=inquiry)
    assert "Ijtimoiy himoya" in escalated_card
    assert "YURIST QABULIGA ARIZA (№77)" in escalated_card


def test_appointment_type_display_multilingual():
    """Verify get_appointment_type_display localized values."""
    assert "Masofaviy" in get_appointment_type_display("remote_appointment", "uz")
    assert "Yuzma-yuz" in get_appointment_type_display("in_person_appointment", "uz")
    assert "Масофавий" in get_appointment_type_display("remote_appointment", "oz")
    assert "Юзма-юз" in get_appointment_type_display("in_person_appointment", "oz")
    assert "Дистанционный" in get_appointment_type_display("remote_appointment", "ru")
    assert "Очный" in get_appointment_type_display("in_person_appointment", "ru")


# ---------------------------------------------------------------------------
# 2. Unified Markup States & Callback Length Invariant
# ---------------------------------------------------------------------------

def test_unified_markup_states_and_callback_data_length():
    """Verify get_appointment_markup buttons across pending, accepted, cancelled, and callback limits."""
    # State A: Pending unassigned
    app_pending = Appointment(
        id=12345,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.pending,
        lawyer_id=None,
        scheduled_at=None,
    )
    markup_pending = get_appointment_markup(app_pending)
    callbacks_pending = [btn.callback_data for row in markup_pending.inline_keyboard for btn in row]

    assert f"appointment:claim:{app_pending.id}" in callbacks_pending
    assert f"app_escalate:assign:{app_pending.id}" in callbacks_pending
    assert f"app_escalate:date:{app_pending.id}" in callbacks_pending
    assert f"appointment:cancel:{app_pending.id}" in callbacks_pending

    # State B: Accepted fully scheduled
    app_accepted = Appointment(
        id=12345,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.accepted,
        lawyer_id=200,
        scheduled_at=datetime(2026, 11, 20, 10, 0),
    )
    markup_accepted = get_appointment_markup(app_accepted)
    callbacks_accepted = [btn.callback_data for row in markup_accepted.inline_keyboard for btn in row]

    assert f"appointment:add_link:{app_accepted.id}" in callbacks_accepted
    assert f"appointment:complete:{app_accepted.id}" in callbacks_accepted
    assert f"appointment:cancel:{app_accepted.id}" in callbacks_accepted
    assert f"app_escalate:manage:{app_accepted.id}" in callbacks_accepted

    # State C: Cancelled (must have restore button)
    app_cancelled = Appointment(
        id=12345,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.cancelled,
    )
    markup_cancelled = get_appointment_markup(app_cancelled)
    callbacks_cancelled = [btn.callback_data for row in markup_cancelled.inline_keyboard for btn in row]

    assert [f"app_escalate:restore:{app_cancelled.id}"] == callbacks_cancelled

    # State D: Completed (must have no action buttons)
    app_completed = Appointment(
        id=12345,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.completed,
    )
    markup_completed = get_appointment_markup(app_completed)
    assert len(markup_completed.inline_keyboard) == 0

    # Invariant: Every callback_data must be <= 64 bytes (Telegram API strict limit)
    all_callbacks = callbacks_pending + callbacks_accepted + callbacks_cancelled
    for cb in all_callbacks:
        assert len(cb.encode("utf-8")) <= 64, f"Callback {cb} exceeds 64 bytes!"


from src.config.settings import Settings


# ---------------------------------------------------------------------------
# 3. Restore Handler Permission & Expiration Check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_callback_non_admin_forbidden():
    """Non-admin user cannot restore a cancelled appointment."""
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=999999, is_bot=False, first_name="Ordinary User")
    query.data = "app_escalate:restore:10"
    query.answer = AsyncMock()

    db_session = MagicMock()
    mock_bot = AsyncMock()

    with patch.object(Settings, "is_admin", lambda self, uid: False):
        await escalate_restore_callback(query, db_session, mock_bot)

    query.answer.assert_called_once_with("⛔️ Qabulni qayta tiklash faqat adminlar uchun!", show_alert=True)
    db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_restore_callback_admin_with_expired_time_resets_schedule():
    """Restoring an appointment with expired scheduled_at resets scheduled_at to None and status to pending."""
    past_time = datetime.now() - timedelta(days=2)
    app = Appointment(
        id=88,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.cancelled,
        cancellation_reason="Foydalanuvchi iltimosiga binoan",
        lawyer_id=300,
        scheduled_at=past_time,
        reminder_sent=True,
    )

    db_session = MagicMock()
    db_session.get.return_value = app

    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=111, is_bot=False, first_name="Super Admin")
    query.data = "app_escalate:restore:88"
    query.answer = AsyncMock()
    query.message = AsyncMock()
    query.message.edit_text = AsyncMock()

    mock_bot = AsyncMock()

    with patch.object(Settings, "is_admin", lambda self, uid: True), \
         patch("src.routes.aiogram.group_router.Appointment.get_by_id", return_value=app), \
         patch("src.routes.aiogram.group_router.notify_citizen_appointment_update", new_callable=AsyncMock):
        await escalate_restore_callback(query, db_session, mock_bot)

    # scheduled_at must be reset because it was in the past
    assert app.scheduled_at is None
    assert app.status == AppointmentStatus.pending
    assert app.cancellation_reason is None
    assert app.reminder_sent is False
    db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_restore_callback_admin_with_future_time_becomes_accepted():
    """Restoring an appointment with valid future time and lawyer sets status to accepted."""
    future_time = datetime.now() + timedelta(days=3)
    app = Appointment(
        id=89,
        user_id=10,
        appointment_type="remote_appointment",
        status=AppointmentStatus.cancelled,
        cancellation_reason="Xatolik tufayli",
        lawyer_id=300,
        scheduled_at=future_time,
        reminder_sent=True,
    )

    db_session = MagicMock()
    db_session.get.return_value = app
    db_session.exec.return_value.first.return_value = None  # shu soatda boshqa qabul yo'q

    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=111, is_bot=False, first_name="Super Admin")
    query.data = "app_escalate:restore:89"
    query.answer = AsyncMock()
    query.message = AsyncMock()
    query.message.edit_text = AsyncMock()

    mock_bot = AsyncMock()

    with patch.object(Settings, "is_admin", lambda self, uid: True), \
         patch("src.routes.aiogram.group_router.Appointment.get_by_id", return_value=app), \
         patch("src.routes.aiogram.group_router.notify_citizen_appointment_update", new_callable=AsyncMock):
        await escalate_restore_callback(query, db_session, mock_bot)

    assert app.scheduled_at == future_time
    assert app.status == AppointmentStatus.accepted
    assert app.cancellation_reason is None
    assert app.reminder_sent is False
    db_session.commit.assert_called()


# ---------------------------------------------------------------------------
# 4. Media Limit (10 Files Strict Boundary)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_media_limit_rejection_at_10_files():
    """When a user attempts to upload an 11th media item, it must be rejected with warning."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=10, user_id=10)
    fsm = FSMContext(storage=storage, key=key)

    # Prepopulate with 10 files
    existing_10 = [{"type": "photo", "file_id": f"fid_{i}"} for i in range(10)]
    await fsm.set_state(AppointmentState.entering_problem_and_media)
    await fsm.update_data(media_items=existing_10)

    # 11th media attempt via Message
    mock_msg = AsyncMock(spec=Message)
    mock_msg.from_user = TgUser(id=10, is_bot=False, first_name="User")
    mock_msg.chat = Chat(id=10, type="private")
    mock_msg.photo = [MagicMock(file_id="photo_11")]
    mock_msg.video = None
    mock_msg.document = None
    mock_msg.voice = None
    mock_msg.video_note = None
    mock_msg.text = None
    mock_msg.caption = None
    mock_msg.media_group_id = None
    mock_msg.answer = AsyncMock()

    mock_user = User(user_id=10, language="uz", is_blocked=False)
    db_session = MagicMock()

    with patch("src.models.user.User.get_by_user_id", return_value=mock_user):
        await handle_appointment_media_input(mock_msg, fsm, db_session)

    # Data must still contain exactly 10 items
    data = await fsm.get_data()
    assert len(data.get("media_items", [])) == 10

    # User must have received localized limit alert
    mock_msg.answer.assert_called_once()
    alert_text = mock_msg.answer.call_args[0][0]
    assert "10" in alert_text
    assert "ko'pi bilan 10 ta" in alert_text or "Ko'pi bilan 10 ta" in alert_text


# ---------------------------------------------------------------------------
# 5. Citizen Notifications Deleting Previous Notice
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_citizen_deletes_previous_notice_and_saves_new_id():
    """notify_citizen_appointment_update must delete previous message ID and store new message ID."""
    app = Appointment(
        id=42,
        user_id=777,
        appointment_type="remote_appointment",
        status=AppointmentStatus.accepted,
        lawyer_id=500,
        scheduled_at=datetime(2026, 12, 10, 15, 0),
        citizen_notice_message_id=98765,
    )
    mock_lawyer = OfficialLawyer(user_id=500, full_name="Sherzod Yurist")
    mock_user = User(user_id=777, language="uz")

    db_session = MagicMock()

    mock_bot = AsyncMock()
    mock_bot.delete_message = AsyncMock()
    new_sent_msg = MagicMock()
    new_sent_msg.message_id = 99999
    mock_bot.send_message = AsyncMock(return_value=new_sent_msg)

    with patch("src.models.user.User.get_by_user_id", return_value=mock_user), \
         patch("src.models.lawyer.OfficialLawyer.get_by_user_id", return_value=mock_lawyer):
        await notify_citizen_appointment_update(
            bot=mock_bot,
            appointment=app,
            db_session=db_session,
            kind="time_set"
        )

    # 1. Previous notice was deleted
    mock_bot.delete_message.assert_called_once_with(chat_id=777, message_id=98765)

    # 2. New message sent
    mock_bot.send_message.assert_called_once()
    sent_text = mock_bot.send_message.call_args.kwargs.get("text") or mock_bot.send_message.call_args.args[1]
    assert "15:00" in sent_text
    assert "Sherzod Yurist" in sent_text

    # 3. New message ID recorded in appointment and committed to DB
    assert app.citizen_notice_message_id == 99999
    db_session.add.assert_called_with(app)
    db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_notify_citizen_silent_if_delete_message_fails():
    """If bot.delete_message raises TelegramBadRequest, notification still succeeds."""
    app = Appointment(
        id=43,
        user_id=777,
        appointment_type="remote_appointment",
        status=AppointmentStatus.cancelled,
        cancellation_reason="Vaqt to'g'ri kelmadi",
        citizen_notice_message_id=12345,
    )

    db_session = MagicMock()
    mock_user = User(user_id=777, language="uz")

    mock_bot = AsyncMock()
    mock_bot.delete_message = AsyncMock(side_effect=Exception("Message to delete not found"))
    new_sent_msg = MagicMock()
    new_sent_msg.message_id = 54321
    mock_bot.send_message = AsyncMock(return_value=new_sent_msg)

    with patch("src.models.user.User.get_by_user_id", return_value=mock_user):
        await notify_citizen_appointment_update(
            bot=mock_bot,
            appointment=app,
            db_session=db_session,
            kind="cancelled"
        )

    mock_bot.send_message.assert_called_once()
    assert app.citizen_notice_message_id == 54321
    db_session.commit.assert_called()


# ---------------------------------------------------------------------------
# 6. Removal of Block Buttons from Inquiry & Appointment Cards
# ---------------------------------------------------------------------------

def test_removal_of_block_buttons():
    """Inquiry card and appointment card must NOT contain block buttons."""
    # Inquiry card markup
    inquiry_markup = get_inquiry_card_markup(inquiry_id=100)
    inquiry_callbacks = [btn.callback_data for row in inquiry_markup.inline_keyboard for btn in row]
    assert "inq_assign:100:1" in inquiry_callbacks
    for cb in inquiry_callbacks:
        assert "block" not in cb.lower(), "Inquiry card must not contain block button!"

    # Appointment cards in all statuses
    for status in [AppointmentStatus.pending, AppointmentStatus.accepted, AppointmentStatus.cancelled]:
        app = Appointment(id=1, user_id=2, status=status)
        markup = get_appointment_markup(app)
        for row in markup.inline_keyboard:
            for btn in row:
                assert "blok" not in btn.text.lower()
                assert "block" not in btn.callback_data.lower()


@pytest.mark.asyncio
async def test_restore_callback_clears_time_when_slot_taken_meanwhile():
    """Bekor qilingan paytda yurist shu soatga boshqa qabul olgan bo'lsa, vaqt qayta so'raladi."""
    future_time = datetime.now() + timedelta(days=3)
    app = Appointment(id=90, user_id=10, appointment_type="remote_appointment",
                      status=AppointmentStatus.cancelled, lawyer_id=300, scheduled_at=future_time)
    db_session = MagicMock()
    clash = Appointment(id=91, user_id=11, lawyer_id=300, scheduled_at=future_time, status=AppointmentStatus.accepted)
    # 1-chaqiruv: to'qnashuv so'rovi; keyingilari (karta chizish) uchun ma'lumot yo'q
    db_session.exec.return_value.first.side_effect = [clash] + [None] * 10
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=111, is_bot=False, first_name="Super Admin")
    query.data = "app_escalate:restore:90"
    query.answer = AsyncMock()
    query.message = AsyncMock()
    with patch.object(Settings, "is_admin", lambda self, uid: True), \
         patch("src.routes.aiogram.group_router.Appointment.get_by_id", return_value=app), \
         patch("src.routes.aiogram.group_router.notify_citizen_appointment_update", new_callable=AsyncMock):
        await escalate_restore_callback(query, db_session, AsyncMock())
    assert app.scheduled_at is None
    assert app.status == AppointmentStatus.pending
