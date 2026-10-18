"""
tests/test_appointment_media_concurrency.py
Tests verifying that multiple concurrent media files (albums/burst uploads)
in lawyer appointment booking are:
1. Not dropped by ThrottlingMiddleware
2. Correctly collected in FSM without race conditions
3. Acknowledged with a single debounced message
4. Dispatched to the lawyer group with rate limit delays
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram import Bot
from aiogram.types import Message, Chat, User as TgUser, PhotoSize, Voice, Document

from src.app.middlewares import ThrottlingMiddleware
from src.routes.aiogram.appointment import (
    AppointmentState,
    handle_appointment_media_input,
    execute_appointment_submission,
    _pending_media_ack_tasks,
    _user_appointment_locks,
)
from src.models.user import User
from src.models.appointment import Appointment


@pytest.mark.asyncio
async def test_throttling_middleware_exempts_media_and_albums():
    """Verify ThrottlingMiddleware does not drop media groups or media files."""
    middleware = ThrottlingMiddleware(rate_limit=0.5)
    handler = AsyncMock(return_value="handled")

    tg_user = TgUser(id=999111, is_bot=False, first_name="Ali")
    chat = Chat(id=999111, type="private")

    # 1. Rapid text messages: 1st passes, 2nd should be throttled
    msg1 = AsyncMock(spec=Message)
    msg1.from_user = tg_user
    msg1.chat = chat
    msg1.media_group_id = None
    msg1.photo = None
    msg1.document = None
    msg1.video = None
    msg1.voice = None
    msg1.video_note = None
    msg1.text = "Birinchi xabar"

    res1 = await middleware(handler, msg1, {})
    assert res1 == "handled"

    msg2 = AsyncMock(spec=Message)
    msg2.from_user = tg_user
    msg2.chat = chat
    msg2.media_group_id = None
    msg2.photo = None
    msg2.document = None
    msg2.video = None
    msg2.voice = None
    msg2.video_note = None
    msg2.text = "Ikkinchi tez xabar"
    msg2.answer = AsyncMock()

    res2 = await middleware(handler, msg2, {})
    # Second fast text message is throttled
    assert res2 is None
    msg2.answer.assert_called_once()
    assert "juda tez xabar yuborildi" in msg2.answer.call_args[0][0]

    # 2. Media group (album) message: must NOT be throttled even immediately after
    album_msg = AsyncMock(spec=Message)
    album_msg.from_user = tg_user
    album_msg.chat = chat
    album_msg.media_group_id = "album_12345"
    album_msg.photo = [PhotoSize(file_id="p1", file_unique_id="pu1", width=100, height=100)]
    album_msg.document = None
    album_msg.video = None
    album_msg.voice = None
    album_msg.video_note = None

    handler.reset_mock()
    res_album = await middleware(handler, album_msg, {})
    assert res_album == "handled"
    handler.assert_called_once()

    # 3. Individual photo in private chat: must NOT be throttled
    photo_msg = AsyncMock(spec=Message)
    photo_msg.from_user = tg_user
    photo_msg.chat = chat
    photo_msg.media_group_id = None
    photo_msg.photo = [PhotoSize(file_id="p2", file_unique_id="pu2", width=100, height=100)]
    photo_msg.document = None
    photo_msg.video = None
    photo_msg.voice = None
    photo_msg.video_note = None

    handler.reset_mock()
    res_photo = await middleware(handler, photo_msg, {})
    assert res_photo == "handled"
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_album_photos_accumulated_safely():
    """Verify that 5 concurrent photo updates are all safely appended to media_items."""
    storage = MemoryStorage()
    user_id = 777222
    key = StorageKey(bot_id=123, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(AppointmentState.entering_problem_and_media)

    db_session = MagicMock()
    mock_user = User(user_id=user_id, first_name="Nodir", language="uz")
    db_session.get.return_value = mock_user

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    # Create 5 concurrent photo messages simulating Telegram album burst
    messages = []
    for i in range(1, 6):
        msg = AsyncMock(spec=Message)
        msg.from_user = TgUser(id=user_id, is_bot=False, first_name="Nodir")
        msg.chat = Chat(id=user_id, type="private")
        msg.text = None
        msg.caption = f"Hujjat rasmi {i}" if i == 1 else None
        msg.voice = None
        msg.video_note = None
        msg.video = None
        msg.document = None
        msg.photo = [PhotoSize(file_id=f"photo_fid_{i}", file_unique_id=f"u_{i}", width=100, height=100)]
        msg.media_group_id = "album_concurrent_99"
        msg.bot = mock_bot
        msg.answer = AsyncMock()
        messages.append(msg)

    with patch("src.routes.aiogram.appointment.User.get_by_user_id", return_value=mock_user):
        # Fire all 5 simultaneously
        await asyncio.gather(*[
            handle_appointment_media_input(msg, state, db_session)
            for msg in messages
        ])

        # Verify state immediately has all 5 media items
        data = await state.get_data()
        media_items = data.get("media_items", [])
        assert len(media_items) == 5, f"Expected 5 items, found {len(media_items)}"
        fids = [item["file_id"] for item in media_items]
        assert fids == [f"photo_fid_{i}" for i in range(1, 6)]

        # Wait for debounce task (0.7s sleep + small margin)
        await asyncio.sleep(0.85)

        # Verify bot sent exactly ONE debounced acknowledgement message
        assert mock_bot.send_message.call_count == 1
        sent_text = mock_bot.send_message.call_args[1]["text"]
        assert "Qabul qilindi." in sent_text
        assert "5 ta" in sent_text


@pytest.mark.asyncio
async def test_submit_after_album_cancels_pending_ack_and_records_all():
    """Verify clicking submit immediately after album cancels debounce and proceeds with all items."""
    storage = MemoryStorage()
    user_id = 888333
    key = StorageKey(bot_id=123, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(AppointmentState.entering_problem_and_media)

    db_session = MagicMock()
    mock_user = User(user_id=user_id, first_name="Malika", language="uz")

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    # User sends 2 photos
    messages = []
    for i in range(1, 3):
        msg = AsyncMock(spec=Message)
        msg.from_user = TgUser(id=user_id, is_bot=False, first_name="Malika")
        msg.chat = Chat(id=user_id, type="private")
        msg.text = None
        msg.caption = None
        msg.voice = None
        msg.video_note = None
        msg.video = None
        msg.document = None
        msg.photo = [PhotoSize(file_id=f"malika_photo_{i}", file_unique_id=f"u_{i}", width=100, height=100)]
        msg.media_group_id = "album_malika"
        msg.bot = mock_bot
        msg.answer = AsyncMock()
        messages.append(msg)

    with patch("src.routes.aiogram.appointment.User.get_by_user_id", return_value=mock_user):
        await asyncio.gather(*[
            handle_appointment_media_input(msg, state, db_session)
            for msg in messages
        ])

        # Immediately user presses "📤 Yuborish"
        submit_msg = AsyncMock(spec=Message)
        submit_msg.from_user = TgUser(id=user_id, is_bot=False, first_name="Malika")
        submit_msg.chat = Chat(id=user_id, type="private")
        submit_msg.text = "📤 Yuborish"
        submit_msg.caption = None
        submit_msg.voice = None
        submit_msg.video_note = None
        submit_msg.video = None
        submit_msg.document = None
        submit_msg.photo = None
        submit_msg.media_group_id = None
        submit_msg.bot = mock_bot
        submit_msg.answer = AsyncMock()

        await handle_appointment_media_input(submit_msg, state, db_session)

        # State should now be confirming_booking
        curr_state = await state.get_state()
        assert curr_state == AppointmentState.confirming_booking.state

        # Debounced ack should have been cancelled
        await asyncio.sleep(0.85)
        # mock_bot.send_message should NOT have been called for debounce ack
        assert mock_bot.send_message.call_count == 0

        # And confirmation card should show 2 files
        submit_msg.answer.assert_called()
        confirm_card = submit_msg.answer.call_args_list[0][0][0]
        assert "2 ta fayl" in confirm_card
