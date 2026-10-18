import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.rag_client import RagClient, is_safe_api_url
from src.config.settings import settings
from src.routes.aiogram import ai_assistant
from src.routes.aiogram.ai_assistant import get_ai_response_inline_keyboard, process_ai_query


def _rag_settings(url="http://127.0.0.1:8000"):
    return (patch.object(settings, "RAG_API_URL", url),
            patch.object(settings, "RAG_API_KEY", "hpk_live_secret"),
            patch.object(settings, "AI_ASSISTANT_ENABLED", True))


@pytest.mark.parametrize("url, ok", [
    ("https://ai.huquqplus.uz", True),
    ("http://127.0.0.1:8000", True),
    ("http://localhost:8000", True),
    ("http://rag:8000", True),               # Docker service name on the same host
    ("http://10.0.0.5:8000", True),
    ("http://ai.huquqplus.uz", False),        # key would travel in clear text over the internet
    ("http://8.8.8.8:8000", False),
    ("ftp://127.0.0.1", False),
    ("https://user:pw@ai.huquqplus.uz", False),
    ("", False),
])
def test_safe_api_url(url, ok):
    assert is_safe_api_url(url) is ok


def test_public_http_url_disables_ai():
    a, b, c = _rag_settings("http://ai.huquqplus.uz")
    with a, b, c:
        assert RagClient().is_enabled() is False
    a, b, c = _rag_settings("https://ai.huquqplus.uz")
    with a, b, c:
        assert RagClient().is_enabled() is True


@pytest.mark.asyncio
async def test_requests_never_follow_redirects():
    client = RagClient()
    calls = []

    class Resp:
        status = 200
        headers = {}

        async def json(self):
            return {"answer_id": "a", "conversation_id": "c", "parts": ["x"]}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    session = MagicMock()
    session.closed = False
    session.post = lambda url, **kw: calls.append(kw) or Resp()
    client._session = session
    a, b, c = _rag_settings()
    with a, b, c:
        await client.ask("savol", user_id=1)
        await client.feedback("a", "up")
        await client.delete_conversation("c", 1)
    assert len(calls) == 3
    assert all(kw.get("allow_redirects") is False for kw in calls)
    assert all("Origin" not in kw["headers"] for kw in calls)


@pytest.mark.asyncio
async def test_callback_path_sends_citizen_id_not_bot_id():
    """From an inline button, message.from_user is the bot: the citizen's id must be passed explicitly."""
    bot_message = MagicMock()
    bot_message.from_user = SimpleNamespace(id=999000)      # the bot
    bot_message.chat = SimpleNamespace(id=12345)
    bot_message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    ask = AsyncMock(return_value={"answer_id": "a", "conversation_id": "c", "parts": ["javob"], "disclaimer": ""})
    with patch.object(ai_assistant.rag_client, "ask", ask), \
         patch.object(ai_assistant, "send_ai_part", AsyncMock()), \
         patch.object(settings, "AI_CITIZEN_ENABLED", True):
        await process_ai_query(message=bot_message, text="savol", user=None, state=state, bot=bot,
                               user_id=12345, question_msg_id=77)
    assert ask.await_args.kwargs["user_id"] == "12345"
    state.update_data.assert_any_await(last_question="savol", last_question_msg_id=77, pending_media_payload=None)


@pytest.mark.asyncio
async def test_spawned_draft_task_is_kept_until_done():
    gate = asyncio.Event()

    async def fake_draft(**kwargs):
        await gate.wait()

    with patch.object(ai_assistant, "send_lawyer_ai_draft", fake_draft):
        task = ai_assistant.spawn_lawyer_ai_draft(bot=None)
        assert task in ai_assistant._background_tasks
        gate.set()
        await task
        await asyncio.sleep(0)
    assert task not in ai_assistant._background_tasks


def test_feedback_buttons_use_full_answer_id():
    kb = get_ai_response_inline_keyboard("Xy-_" * 5 + "ab", "uz")       # 22 chars, like token_urlsafe(16)
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "ai_fb:u:" + "Xy-_" * 5 + "ab" in data
    kb = get_ai_response_inline_keyboard("x" * 60, "uz")                 # too long: no truncated buttons
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert not any(d.startswith("ai_fb:") for d in data)
    assert all(len(d.encode()) <= 64 for d in data)
