import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from aiogram.types import Message, Chat, User as TgUser
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.routes.aiogram.group_router import (
    send_answer_to_citizen,
    is_inquiry_already_edited,
    edit_message,
    replied_context,
)


@pytest.mark.asyncio
async def test_send_answer_to_citizen_success():
    handler = AsyncMock(return_value="sent_message_mock")
    args = {"chat_id": 12345, "text": "Huquqiy javob", "reply_to_message_id": 99}

    ok, reason, res = await send_answer_to_citizen(handler, args, max_retries=3, initial_delay=0.01)

    assert ok is True
    assert reason == "success"
    assert res == "sent_message_mock"
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_send_answer_to_citizen_retry_on_network_error():
    handler = AsyncMock(side_effect=[
        TelegramNetworkError(method="sendMessage", message="Connection reset"),
        "sent_message_ok"
    ])
    args = {"chat_id": 12345, "text": "Huquqiy javob", "reply_to_message_id": 99}

    ok, reason, res = await send_answer_to_citizen(handler, args, max_retries=3, initial_delay=0.01)

    assert ok is True
    assert reason == "success"
    assert res == "sent_message_ok"
    assert handler.call_count == 2


@pytest.mark.asyncio
async def test_send_answer_to_citizen_fails_after_max_retries():
    handler = AsyncMock(side_effect=TelegramNetworkError(method="sendMessage", message="Timeout"))
    args = {"chat_id": 12345, "text": "Huquqiy javob"}

    ok, reason, res = await send_answer_to_citizen(handler, args, max_retries=3, initial_delay=0.01)

    assert ok is False
    assert "network_error" in reason
    assert handler.call_count == 3


@pytest.mark.asyncio
async def test_send_answer_to_citizen_blocked_by_user():
    handler = AsyncMock(side_effect=TelegramForbiddenError(method="sendMessage", message="Forbidden: bot was blocked by the user"))
    args = {"chat_id": 12345, "text": "Huquqiy javob"}

    ok, reason, res = await send_answer_to_citizen(handler, args, max_retries=3, initial_delay=0.01)

    assert ok is False
    assert reason == "blocked"
    assert handler.call_count == 1  # No pointless retries for blocked users


@pytest.mark.asyncio
async def test_send_answer_to_citizen_restricted_format():
    handler = AsyncMock(side_effect=TelegramBadRequest(method="sendVoice", message="Bad Request: user restricted incoming voice messages"))
    args = {"chat_id": 12345, "voice": "file_id_123"}

    ok, reason, res = await send_answer_to_citizen(handler, args, max_retries=3, initial_delay=0.01)

    assert ok is False
    assert reason == "restricted"
    assert handler.call_count == 1


def test_is_inquiry_already_edited():
    inquiry = Inquiry(
        id=555,
        section_name="mehnat",
        question="Savol matni",
        private_question_id=10,
        group_question_id=200,
        group_id="-100999",
        bot_id=123,
        status=InquiryStatus.active,
    )

    # 1. Message does not have "Murojaatga javob berildi"
    msg_unedited = MagicMock(spec=Message)
    msg_unedited.message_id = 200
    msg_unedited.text = "<blockquote>Savol matni</blockquote>"
    msg_unedited.caption = None

    reply_msg = MagicMock(spec=Message)
    reply_msg.reply_to_message = msg_unedited

    with patch("src.routes.aiogram.group_router.get_redis") as mock_redis:
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_redis.return_value = mock_r

        assert is_inquiry_already_edited(reply_msg, inquiry) is False

    # 2. Message has "Murojaatga javob berildi"
    msg_edited = MagicMock(spec=Message)
    msg_edited.message_id = 200
    msg_edited.text = "<blockquote>Savol matni</blockquote><br/><b>✅ Murojaatga javob berildi:</b>"
    msg_edited.caption = None
    reply_msg.reply_to_message = msg_edited

    assert is_inquiry_already_edited(reply_msg, inquiry) is True


@pytest.mark.asyncio
async def test_edit_message_fallback_and_handling():
    inquiry = Inquiry(
        id=777,
        section_name="ijtimoiy",
        question="Nogironlik nafaqasi qancha?",
        private_question_id=11,
        group_question_id=300,
        group_id="-100888",
        bot_id=123,
        status=InquiryStatus.active,
        question_mediatype=InquiryMediaType.text,
    )

    lawyer_tg = TgUser(id=999, is_bot=False, first_name="Alisher", last_name="Yurist")
    lawyer_chat = Chat(id=-100888, type="supergroup", username="yuristlar_guruhi")
    lawyer_msg = MagicMock(spec=Message)
    lawyer_msg.message_id = 450
    lawyer_msg.chat = lawyer_chat
    lawyer_msg.from_user = lawyer_tg
    lawyer_msg.date = datetime.now()

    bot = AsyncMock()
    # bot.edit_message_text succeeds
    bot.edit_message_text = AsyncMock(return_value=True)

    result = await edit_message(inquiry, lawyer_msg, bot)
    assert result is True
    bot.edit_message_text.assert_called_once()
