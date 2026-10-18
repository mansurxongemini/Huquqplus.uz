"""
tests/test_appointment_streamlined.py
Unit tests verifying the streamlined appointment flow:
- Removal of lawyer selection and date/time selection states
- Direct transition from appointment type selection to entering_problem_and_media
- Confirmation card contains only appointment type, attached files, and problem description
- Appointment created with pending status, None lawyer_id, None scheduled_at
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message, User as TgUser, Chat

from src.routes.aiogram.appointment import (
    AppointmentState,
    process_appointment_type,
    render_confirmation_card,
    execute_appointment_submission,
)
from src.models.appointment import Appointment, AppointmentStatus
from src.models.user import User


def test_appointment_states_streamlined():
    """Verify choosing_lawyer, choosing_date, and choosing_time_slot are eliminated."""
    state_names = [s.state for s in AppointmentState.__all_states__]
    assert "AppointmentState:choosing_appointment_type" in state_names
    assert "AppointmentState:entering_problem_and_media" in state_names
    assert "AppointmentState:confirming_booking" in state_names

    # Must NOT contain obsolete states
    assert "AppointmentState:choosing_lawyer" not in state_names
    assert "AppointmentState:choosing_date" not in state_names
    assert "AppointmentState:choosing_time_slot" not in state_names


@pytest.mark.asyncio
async def test_appointment_type_transitions_directly_to_problem_media():
    """Selecting remote or in-person appointment type must directly transition to entering_problem_and_media."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=456, user_id=789)
    fsm_context = FSMContext(storage=storage, key=key)
    await fsm_context.set_state(AppointmentState.choosing_appointment_type)

    tg_user = TgUser(id=789, is_bot=False, first_name="Test Citizen")
    tg_chat = Chat(id=456, type="private")
    mock_msg = AsyncMock(spec=Message)
    mock_msg.delete = AsyncMock()
    mock_msg.answer = AsyncMock()

    mock_query = AsyncMock(spec=CallbackQuery)
    mock_query.from_user = tg_user
    mock_query.data = "remote_appointment"
    mock_query.message = mock_msg
    mock_query.answer = AsyncMock()

    # Mock DB session where user exists and has no active appointments
    db_session = MagicMock()
    mock_db_user = User(user_id=789, first_name="Test Citizen", language="uz")
    db_session.exec.return_value.first.return_value = None  # No existing active appointment

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(User, "get_by_user_id", lambda uid, sess: mock_db_user)
        await process_appointment_type(mock_query, fsm_context, db_session)

    # State must be entering_problem_and_media
    current_state = await fsm_context.get_state()
    assert current_state == AppointmentState.entering_problem_and_media.state

    # Prompt message sent to user must contain the expected instruction
    mock_msg.answer.assert_called_once()
    sent_text = mock_msg.answer.call_args[0][0]
    assert "Muammoingizni bayon qiling va zarur hujjatlarni ilova qiling:" in sent_text


@pytest.mark.asyncio
async def test_render_confirmation_card_has_no_lawyer_or_datetime():
    """Confirmation card must not display lawyer or scheduled datetime."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=456, user_id=789)
    fsm_context = FSMContext(storage=storage, key=key)
    await fsm_context.update_data(
        appointment_type="remote_appointment",
        problem_description="Mening aliment bo'yicha masalam bor edi."
    )

    mock_msg = AsyncMock(spec=Message)
    mock_msg.answer = AsyncMock()

    await render_confirmation_card(mock_msg, fsm_context, lang="uz")

    assert mock_msg.answer.call_count >= 1
    preview_card = mock_msg.answer.call_args_list[0][0][0]

    assert "Qabul ma'lumotlarini tasdiqlang" in preview_card
    assert "Masofaviy qabul" in preview_card
    assert "Mening aliment" in preview_card
    assert "masalam bor edi" in preview_card
    # Must NOT have lawyer or date/time headers
    assert "Yurist:" not in preview_card
    assert "Sana va vaqt:" not in preview_card


@pytest.mark.asyncio
async def test_execute_appointment_submission_creates_pending_unassigned():
    """Submitting appointment sets lawyer_id=None, scheduled_at=None, and status=pending."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=456, user_id=789)
    fsm_context = FSMContext(storage=storage, key=key)
    await fsm_context.update_data(
        appointment_type="in_person_appointment",
        problem_description="Nogironlik nafaqasi to'xtatilgan."
    )

    db_session = MagicMock()
    # No duplicate active
    db_session.exec.return_value.first.return_value = None

    created_app = None
    def mock_add(obj):
        nonlocal created_app
        if isinstance(obj, Appointment):
            created_app = obj
            obj.id = 999

    db_session.add = MagicMock(side_effect=mock_add)
    db_session.commit = MagicMock()
    db_session.refresh = MagicMock()

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = MagicMock(message_id=12345)

    mock_target = AsyncMock(spec=Message)
    mock_target.answer = AsyncMock()

    mock_user = User(user_id=789, first_name="Ali", last_name="Valiyev", phone="+998901234567", language="uz")

    await execute_appointment_submission(
        user=mock_user,
        lang="uz",
        state=fsm_context,
        db_session=db_session,
        bot=mock_bot,
        message_target=mock_target
    )

    assert created_app is not None
    assert created_app.lawyer_id is None
    assert created_app.scheduled_at is None
    assert created_app.status == AppointmentStatus.pending
    assert created_app.appointment_type == "in_person_appointment"

    # Verify group notification sent with claim button
    mock_bot.send_message.assert_called()
    group_call = mock_bot.send_message.call_args_list[0]
    group_caption = group_call.kwargs.get("text") or group_call.args[1]
    assert "YURIST QABULIGA ARIZA" in group_caption
    assert "Yuzma-yuz" in group_caption

    # Verify citizen confirmation response
    mock_target.answer.assert_called_once()
    citizen_reply = mock_target.answer.call_args[0][0]
    assert "Arizangiz qabul qilindi" in citizen_reply
