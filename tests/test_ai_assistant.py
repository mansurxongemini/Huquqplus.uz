import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from src.app.keyboards import get_main_menu
from src.app.rag_client import RagClient, RagError
from src.app.translations import t
from src.config.settings import settings
from src.routes.aiogram.ai_assistant import (
    enter_ai_assistant_mode,
    get_ai_response_inline_keyboard,
    process_ai_query,
    send_ai_part,
    send_lawyer_ai_draft,
    strip_html_tags,
)
from src.routes.aiogram.auto_inquiry import get_auto_inquiry_confirm_keyboard


class MockResponse:
    def __init__(self, status=200, json_data=None, headers=None):
        self.status = status
        self._json_data = json_data or {}
        self.headers = headers or {}

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_client_success():
    client = RagClient()
    mock_data = {
        "answer_id": "ans-100",
        "conversation_id": "conv-200",
        "answer": "Test answer",
        "parts": ["<b>Part 1</b>", "Part 2"],
        "disclaimer": "Huquqiy maslahat emas",
        "is_refusal": False,
        "latency_ms": 150,
    }

    mock_session = MagicMock()
    mock_session.closed = False
    captured_kwargs = {}

    def mock_post(url, **kwargs):
        captured_kwargs["url"] = url
        captured_kwargs.update(kwargs)
        return MockResponse(status=200, json_data=mock_data)

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):

        result = await client.ask(
            question="Pensiya yoshi qancha?",
            user_id="12345678",
            conversation_id="conv-old",
            language="uz",
        )

        assert result["answer_id"] == "ans-100"
        assert result["conversation_id"] == "conv-200"
        assert len(result["parts"]) == 2

        # Check headers and payload
        headers = captured_kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-secret-key"
        assert "Origin" not in headers

        payload = captured_kwargs["json"]
        assert payload["question"] == "Pensiya yoshi qancha?"
        assert payload["user_id"] == "12345678"
        assert payload["conversation_id"] == "conv-old"
        assert payload["language"] == "uz"
        assert payload["format"] == "telegram_html"


@pytest.mark.asyncio
async def test_client_429_rate_limited():
    client = RagClient()
    mock_session = MagicMock()
    mock_session.closed = False

    def mock_post(url, **kwargs):
        return MockResponse(
            status=429,
            json_data={"error": {"code": "user_rate_limited", "message": "Juda ko'p so'rov"}},
            headers={"Retry-After": "45"},
        )

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):

        with pytest.raises(RagError) as exc_info:
            await client.ask("Savol", user_id="123")

        err = exc_info.value
        assert err.status == 429
        assert err.retry_after == 45
        assert err.code == "user_rate_limited"


@pytest.mark.asyncio
async def test_client_503_service_unavailable():
    client = RagClient()
    mock_session = MagicMock()
    mock_session.closed = False

    def mock_post(url, **kwargs):
        return MockResponse(
            status=503,
            json_data={"error": {"code": "service_unavailable", "message": "Model band"}},
        )

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):

        with pytest.raises(RagError) as exc_info:
            await client.ask("Savol", user_id="123")

        err = exc_info.value
        assert err.status == 503
        assert err.code == "service_unavailable"


@pytest.mark.asyncio
async def test_client_404_retry_without_conversation_id():
    client = RagClient()
    mock_session = MagicMock()
    mock_session.closed = False

    call_count = 0
    captured_payloads = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        captured_payloads.append(kwargs.get("json", {}))
        if call_count == 1:
            return MockResponse(
                status=404,
                json_data={"error": {"code": "conversation_not_found", "message": "Suhbat topilmadi"}},
            )
        return MockResponse(
            status=200,
            json_data={"answer_id": "ans-retry", "conversation_id": "conv-fresh", "parts": ["Yangi javob"]},
        )

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):

        result = await client.ask("Savol", user_id="123", conversation_id="expired-conv-id")

        assert call_count == 2
        assert captured_payloads[0]["conversation_id"] == "expired-conv-id"
        assert captured_payloads[1]["conversation_id"] is None
        assert result["answer_id"] == "ans-retry"
        assert result["conversation_id"] == "conv-fresh"


@pytest.mark.asyncio
async def test_client_key_and_question_not_in_logs(caplog):
    client = RagClient()
    mock_session = MagicMock()
    mock_session.closed = False

    secret_key = "MY_ULTRA_SECRET_TOKEN_98765"
    secret_question = "MAXFIY_SAVOL_FUQARO_123456"

    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"answer_id": "ans-1", "parts": ["Ok"], "latency_ms": 100})

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", secret_key), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True), \
         caplog.at_level(logging.DEBUG):

        await client.ask(question=secret_question, user_id="12345")

        log_text = caplog.text
        assert secret_key not in log_text
        assert secret_question not in log_text


def test_is_enabled_false_when_empty_settings_and_no_menu_button():
    client = RagClient()

    # Empty URL
    with patch.object(settings, "RAG_API_URL", ""), \
         patch.object(settings, "RAG_API_KEY", "key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):
        assert client.is_enabled() is False

    # Empty KEY
    with patch.object(settings, "RAG_API_URL", "http://localhost"), \
         patch.object(settings, "RAG_API_KEY", ""), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):
        assert client.is_enabled() is False

    # Disabled flag
    with patch.object(settings, "RAG_API_URL", "http://localhost"), \
         patch.object(settings, "RAG_API_KEY", "key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", False):
        assert client.is_enabled() is False

    # Fuqaro menyusida AI tugmasi hech qachon chiqmaydi (RAG holatidan qat'i nazar)
    with patch("src.app.rag_client.rag_client.is_enabled", return_value=False):
        for lang in ("uz", "oz", "ru"):
            menu = get_main_menu(lang)
            buttons = [b.text for row in menu.keyboard for b in row]
            assert "🤖 AI yordamchi" not in buttons
            assert "🤖 AI ёрдамчи" not in buttons
            assert "🤖 ИИ-помощник" not in buttons

    with patch("src.app.rag_client.rag_client.is_enabled", return_value=True):
        for lang in ("uz", "oz", "ru"):
            menu = get_main_menu(lang)
            buttons = [b.text for row in menu.keyboard for b in row]
            assert "🤖 AI yordamchi" not in buttons
            assert "🤖 AI ёрдамчи" not in buttons
            assert "🤖 ИИ-помощник" not in buttons

    # Auto-inquiry dagi "AI javobi" tugmasi faqat rollback bayrog'i True bo'lganda chiqadi
    with patch("src.app.rag_client.rag_client.is_enabled", return_value=True), \
         patch.object(settings, "AI_CITIZEN_ENABLED", False):
        confirm_kb = get_auto_inquiry_confirm_keyboard("uz")
        confirm_buttons = [b.text for row in confirm_kb.inline_keyboard for b in row]
        assert "🤖 AI javobi" not in confirm_buttons

    with patch("src.app.rag_client.rag_client.is_enabled", return_value=True), \
         patch.object(settings, "AI_CITIZEN_ENABLED", True):
        confirm_kb = get_auto_inquiry_confirm_keyboard("uz")
        confirm_buttons = [b.text for row in confirm_kb.inline_keyboard for b in row]
        assert "🤖 AI javobi" in confirm_buttons


def test_callback_data_under_64_bytes():
    # Test standard UUID answer_id
    uuid_answer_id = "550e8400-e29b-41d4-a716-446655440000"
    kb = get_ai_response_inline_keyboard(uuid_answer_id, "uz")
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64

    # Test excessively long answer_id
    long_answer_id = "a" * 120
    kb_long = get_ai_response_inline_keyboard(long_answer_id, "uz")
    for row in kb_long.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64

    # Auto inquiry AI callback
    assert len("auto_inquiry:ai".encode("utf-8")) <= 64
    assert len("ai_to_lawyer".encode("utf-8")) <= 64


@pytest.mark.asyncio
async def test_parse_error_fallback_to_plain_text():
    mock_bot = MagicMock()
    call_modes = []

    async def mock_send_message(chat_id, text, **kwargs):
        pm = kwargs.get("parse_mode")
        call_modes.append(pm)
        if pm == ParseMode.HTML:
            raise TelegramBadRequest(
                method=MagicMock(),
                message="Bad Request: can't parse entities in message text",
            )
        return MagicMock(message_id=123, text=text)

    mock_bot.send_message = mock_send_message

    html_text = "<b>Qalin matn</b> va <i>kursiv</i>"
    result = await send_ai_part(bot=mock_bot, chat_id=12345, text=html_text)

    # First attempt HTML, then fallback with None
    assert call_modes == [ParseMode.HTML, None]
    assert result.message_id == 123
    assert strip_html_tags(html_text) == "Qalin matn va kursiv"


@pytest.mark.asyncio
async def test_lawyer_draft_redis_mapping():
    mock_bot = MagicMock()
    mock_msg = MagicMock(message_id=999, chat=MagicMock(id=-1001999999))
    mock_bot.send_message = AsyncMock(return_value=mock_msg)

    mock_redis = AsyncMock()

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_LAWYER_DRAFTS", True), \
         patch("src.app.rag_client.rag_client.ask", new_callable=AsyncMock) as mock_ask, \
         patch("src.routes.aiogram.ai_assistant.get_redis", return_value=mock_redis):

        mock_ask.return_value = {
            "is_refusal": False,
            "parts": ["Yurist uchun AI tavsiyasi loyihasi"],
        }

        await send_lawyer_ai_draft(
            bot=mock_bot,
            inquiry_id=88,
            user_id=12345,
            group_id=-1001999999,
            reply_to_message_id=500,
            question_text="Mehnat ta'tili masalasi",
            user_lang="uz",
        )

        assert mock_bot.send_message.called
        # Verify Redis key: inquiry_cont:{group_id}:{draft_message_id} -> "88"
        mock_redis.set.assert_any_call(
            "inquiry_cont:-1001999999:999",
            "88",
            ex=86400 * 30,
        )

        # Ensure inquiry_cont_msg was NOT touched
        for call_args in mock_redis.set.call_args_list:
            key = call_args[0][0]
            assert not key.startswith("inquiry_cont_msg:")


@pytest.mark.asyncio
async def test_lawyer_draft_not_sent_on_refusal():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_LAWYER_DRAFTS", True), \
         patch("src.app.rag_client.rag_client.ask", new_callable=AsyncMock) as mock_ask:

        mock_ask.return_value = {
            "is_refusal": True,
            "parts": ["Ushbu savolga javob berish imkonsiz"],
        }

        await send_lawyer_ai_draft(
            bot=mock_bot,
            inquiry_id=89,
            user_id=12345,
            group_id=-1001999999,
            reply_to_message_id=500,
            question_text="Qoidabuzarlik",
            user_lang="uz",
        )

        # send_message must NOT be called when is_refusal is True
        assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_client_feedback_and_delete():
    client = RagClient()
    mock_session = MagicMock()
    mock_session.closed = False

    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"ok": True})

    mock_session.post = mock_post
    client._session = mock_session

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", True):

        fb_res = await client.feedback("ans-1", "up", "Yaxshi javob")
        assert fb_res is True

        del_res = await client.delete_conversation("conv-1", "123")
        assert del_res is True


def test_ai_unavailable_translations():
    from src.app.translations import TRANSLATIONS, LANG_OZ, LANG_RU, LANG_UZ
    entry = TRANSLATIONS.get("ai_unavailable")
    assert entry is not None
    for lang in (LANG_UZ, LANG_OZ, LANG_RU):
        assert entry.get(lang), f"ai_unavailable missing for lang {lang}"


@pytest.mark.asyncio
async def test_citizen_ai_entry_denied_when_flag_false():
    message = MagicMock()
    message.from_user.id = 12345
    message.answer = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()

    mock_user = MagicMock()
    mock_user.language = "uz"
    mock_user.is_blocked = False

    with patch.object(settings, "AI_CITIZEN_ENABLED", False), \
         patch("src.routes.aiogram.ai_assistant.User.get_by_user_id", return_value=mock_user):
        await enter_ai_assistant_mode(message, state, MagicMock())

    message.answer.assert_called_once_with(t("ai_unavailable", "uz"))
    state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_process_ai_query_denied_when_flag_false():
    message = MagicMock()
    message.answer = AsyncMock()
    mock_user = MagicMock()
    mock_user.language = "oz"

    with patch.object(settings, "AI_CITIZEN_ENABLED", False), \
         patch("src.app.rag_client.rag_client.ask", new_callable=AsyncMock) as mock_ask:
        await process_ai_query(
            message=message,
            text="Savol matni",
            user=mock_user,
            state=MagicMock(),
            bot=MagicMock(),
            user_id=12345,
        )

    message.answer.assert_called_once_with(t("ai_unavailable", "oz"))
    mock_ask.assert_not_called()


@pytest.mark.asyncio
async def test_lawyer_draft_works_when_citizen_and_assistant_flags_off():
    """Ichki AI fuqaro bayrog'i va AI_ASSISTANT_ENABLED dan mustaqil ishlaydi."""
    mock_bot = MagicMock()
    mock_msg = MagicMock(message_id=777, chat=MagicMock(id=-1001999999))
    mock_bot.send_message = AsyncMock(return_value=mock_msg)
    mock_redis = AsyncMock()

    with patch.object(settings, "RAG_API_URL", "http://localhost:8000"), \
         patch.object(settings, "RAG_API_KEY", "test-secret-key"), \
         patch.object(settings, "AI_ASSISTANT_ENABLED", False), \
         patch.object(settings, "AI_CITIZEN_ENABLED", False), \
         patch.object(settings, "AI_LAWYER_DRAFTS", True), \
         patch("src.app.rag_client.rag_client.ask", new_callable=AsyncMock) as mock_ask, \
         patch("src.routes.aiogram.ai_assistant.get_redis", return_value=mock_redis):
        mock_ask.return_value = {
            "is_refusal": False,
            "parts": ["Yurist uchun AI tavsiyasi loyihasi"],
        }

        await send_lawyer_ai_draft(
            bot=mock_bot,
            inquiry_id=90,
            user_id=12345,
            group_id=-1001999999,
            reply_to_message_id=500,
            question_text="Mehnat ta'tili masalasi",
            user_lang="uz",
        )

    assert mock_bot.send_message.called
    mock_ask.assert_called_once()
    assert mock_ask.call_args.kwargs.get("internal") is True
