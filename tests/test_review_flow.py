"""AI nazoratchi review oqimi (YANGI /assistant/review endpoint).

RAG klient mock bilan: approve/reject/needs_admin yo'llari, RagError/timeout/
parse xatosida volontyor matni + admin DM + tasdiq berilmasligi, dedupe
(5 daqiqa), sirlar xabarda yo'qligi.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.app.rag_client import RagClient, RagError, validate_review_response
from src.config.settings import settings
from src.models.inquiry import InquiryStatus
from src.routes.aiogram import volunteer_assign as va
from src.routes.aiogram.volunteer_assign import (
    _review_error_dedupe,
    format_review_issues,
    review_error_info,
    review_error_key,
    sanitize_admin_error_text,
)


def _ok_payload(**kw):
    base = {
        "verdict": "approve",
        "scores": {"legal_accuracy": 5, "citation_basis": 4, "completeness": 5, "tone": 5},
        "issues": [],
        "summary": "Javob to'liq va asosli.",
        "delivery_hint": None,
        "confidence": 0.92,
        "rubric_version": "v1",
        "model": "rag-review-1",
        "retrieved": [],
    }
    base.update(kw)
    return base


def _reject_payload():
    return _ok_payload(
        verdict="reject",
        issues=[
            {"type": "citation", "quote": "Qonunga ko'ra", "problem": "Modda ko'rsatilmagan", "fix": "FK 123-moddasini yozing"},
            {"type": "completeness", "quote": "qisqa javob", "problem": "Asos yetarli emas", "fix": "Havola qo'shing"},
        ],
        summary="Kamchiliklar bor.",
    )


# --- Sxema validatsiyasi ---

def test_validate_review_ok():
    out = validate_review_response(_ok_payload())
    assert out["verdict"] == "approve"
    assert out["delivery_hint"] is None
    out2 = validate_review_response(_ok_payload(verdict="needs_admin", delivery_hint="  "))
    assert out2["verdict"] == "needs_admin" and out2["delivery_hint"] is None


def test_validate_review_bad_verdict():
    with pytest.raises(RagError) as e:
        validate_review_response(_ok_payload(verdict="maybe"))
    assert e.value.code == "review_parse_error"


def test_validate_review_bad_scores():
    bad = _ok_payload()
    del bad["scores"]["tone"]
    with pytest.raises(RagError):
        validate_review_response(bad)
    with pytest.raises(RagError):
        validate_review_response(_ok_payload(scores={"legal_accuracy": 6, "citation_basis": 0, "completeness": 0, "tone": 0}))
    with pytest.raises(RagError):
        validate_review_response(_ok_payload(scores={"legal_accuracy": True, "citation_basis": 0, "completeness": 0, "tone": 0}))


def test_validate_review_bad_issues():
    with pytest.raises(RagError):
        validate_review_response(_ok_payload(issues="xato"))
    with pytest.raises(RagError):
        validate_review_response(_ok_payload(issues=[{"type": "x", "quote": "q", "problem": "p"}]))


def test_validate_review_missing_fields():
    for key in ("summary", "confidence", "rubric_version", "model", "retrieved"):
        bad = _ok_payload()
        del bad[key]
        with pytest.raises(RagError):
            validate_review_response(bad)
    with pytest.raises(RagError):
        validate_review_response("oddiy matn")
    with pytest.raises(RagError):
        validate_review_response(None)


# --- review() klienti (soxta transport) ---

class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeSession:
    closed = False

    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc
        self.seen = {}

    def post(self, url, json=None, headers=None, timeout=None, allow_redirects=False):
        self.seen = {"url": url, "json": json, "headers": headers, "timeout": timeout}
        if self._exc is not None:
            raise self._exc
        return self._resp


def _configured(monkeypatch):
    monkeypatch.setattr(settings, "RAG_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "RAG_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_review_success_payload(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(settings, "AI_ASSISTANT_ENABLED", False)  # review() bunga bog'liq emas
    client = RagClient()
    client._session = _FakeSession(_FakeResp(200, _ok_payload()))
    out = await client.review(
        question="Savol", section="Mehnat", answer="Qoralama",
        disability_state="vision", request_id="inquiry:5",
    )
    assert out["verdict"] == "approve"
    seen = client._session.seen
    assert seen["url"].endswith("/api/v1/assistant/review")
    assert seen["json"] == {
        "question": "Savol", "section": "Mehnat", "answer": "Qoralama",
        "language": "uz", "disability_state": "vision", "request_id": "inquiry:5",
    }
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["timeout"].total == float(settings.RAG_REVIEW_TIMEOUT_SECONDS)


def test_review_timeout_default_90():
    assert settings.RAG_REVIEW_TIMEOUT_SECONDS == 90.0


@pytest.mark.asyncio
async def test_review_disabled_config(monkeypatch):
    monkeypatch.setattr(settings, "RAG_API_URL", "")
    client = RagClient()
    with pytest.raises(RagError) as e:
        await client.review(question="s", section="m", answer="a", disability_state=None, request_id="inquiry:1")
    assert e.value.code == "disabled"


@pytest.mark.asyncio
async def test_review_http_error_code(monkeypatch):
    _configured(monkeypatch)
    client = RagClient()
    client._session = _FakeSession(_FakeResp(500, {"error": {"code": "review_llm_error", "message": "boom"}}))
    with pytest.raises(RagError) as e:
        await client.review(question="s", section="m", answer="a", disability_state=None, request_id="inquiry:1")
    assert e.value.code == "review_llm_error" and e.value.status == 500


@pytest.mark.asyncio
async def test_review_timeout(monkeypatch):
    _configured(monkeypatch)
    client = RagClient()
    client._session = _FakeSession(exc=asyncio.TimeoutError())
    with pytest.raises(RagError) as e:
        await client.review(question="s", section="m", answer="a", disability_state=None, request_id="inquiry:1")
    assert e.value.code == "review_timeout"


@pytest.mark.asyncio
async def test_review_schema_mismatch_is_parse_error(monkeypatch):
    _configured(monkeypatch)
    client = RagClient()
    client._session = _FakeSession(_FakeResp(200, {"verdict": "approve"}))
    with pytest.raises(RagError) as e:
        await client.review(question="s", section="m", answer="a", disability_state=None, request_id="inquiry:1")
    assert e.value.code == "review_parse_error"


@pytest.mark.asyncio
async def test_review_bad_json_is_parse_error(monkeypatch):
    _configured(monkeypatch)
    client = RagClient()
    client._session = _FakeSession(_FakeResp(200, ValueError("no json")))
    with pytest.raises(RagError) as e:
        await client.review(question="s", section="m", answer="a", disability_state=None, request_id="inquiry:1")
    assert e.value.code == "review_parse_error"


# --- Handler oqimi (soxta DB/xabar/bot) ---

class FakeDB:
    def __init__(self, inquiry, assignment):
        self.inquiry = inquiry
        self.assignment = assignment
        self.committed = False

    def get(self, model, _id):
        return self.inquiry if model.__name__ == "Inquiry" else self.assignment

    def add(self, obj):
        pass

    def commit(self):
        self.committed = True


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key) or 0) + 1)
        return int(self.store[key])

    async def expire(self, key, ttl):
        return True

    async def delete(self, key):
        self.store.pop(key, None)
        return 1


class Ctx:
    def __init__(self, redis=None, disability_state=None):
        user = SimpleNamespace(disability_state=disability_state) if disability_state else None
        self.inquiry = SimpleNamespace(
            id=5, status=InquiryStatus.active, question="Savol matni",
            section_name="Mehnat", user=user, group_id="-100123", group_question_id=10,
        )
        self.assignment = SimpleNamespace(
            id=9,
            volunteer_user_id=777, inquiry_id=5, status="assigned",
            review_status="none", review_draft_hash=None,
            review_passed_at=None, review_json=None,
        )
        self.db = FakeDB(self.inquiry, self.assignment)
        from_user = SimpleNamespace(id=777, first_name="Ali", last_name="Valiyev", username="ali")
        self.message = SimpleNamespace(text="Tayyor javob matni", from_user=from_user, answer=AsyncMock())
        self.state = SimpleNamespace(
            get_data=AsyncMock(return_value={"review_inquiry_id": 5, "review_assignment_id": 9}),
            clear=AsyncMock(),
        )
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.redis = redis if redis is not None else FakeRedis()

    async def run(self, review_result=None, review_exc=None):
        review_mock = AsyncMock()
        if review_exc is not None:
            review_mock.side_effect = review_exc
        else:
            review_mock.return_value = review_result
        with (
            patch.object(va, "_active_volunteer", return_value=SimpleNamespace(user_id=777)),
            patch.object(va, "_vol_lang", return_value="uz"),
            patch.object(va.rag_client, "review", review_mock),
            patch.object(va.settings, "ADMIN_IDS", "111,222"),
            patch.object(va, "_get_redis_client", return_value=self.redis),
        ):
            await va.vol_review_draft_handler(self.message, self.state, self.db, self.bot)
        return review_mock


def _vol_text(ctx):
    return ctx.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_approve_sets_passed():
    ctx = Ctx()
    await ctx.run(review_result=_ok_payload(delivery_hint="Ovozli qo'shing"))
    assert ctx.assignment.review_status == "passed"
    assert ctx.assignment.review_passed_at is not None
    assert json.loads(ctx.assignment.review_json)["verdict"] == "approve"
    assert ctx.db.committed is True
    text = _vol_text(ctx)
    assert "tasdiqlandi" in text and "Ovozli qo" in text and "Tavsiya" in text
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_reject_lists_issues_and_no_approval():
    ctx = Ctx()
    await ctx.run(review_result=_reject_payload())
    assert ctx.assignment.review_status == "failed"
    assert ctx.assignment.review_passed_at is None
    text = _vol_text(ctx)
    assert "tasdiqlanmadi" in text and "qaytadan yozib chiqing" in text
    assert "Modda ko" in text and "FK 123-moddasini yozing" in text
    assert "Asos yetarli emas" in text
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_needs_admin_notifies_and_waits():
    ctx = Ctx()
    await ctx.run(review_result=_ok_payload(verdict="needs_admin", summary="Murakkab holat."))
    assert ctx.assignment.review_status == "needs_admin"
    assert ctx.assignment.review_passed_at is None
    assert "adminga" in _vol_text(ctx)
    assert ctx.bot.send_message.call_count == 2
    admin_text = ctx.bot.send_message.call_args[1]["text"]
    assert "Murakkab holat" in admin_text and "№5" in admin_text


@pytest.mark.asyncio
async def test_error_ragerror_volunteer_text_admin_dm_no_approval():
    ctx = Ctx()
    await ctx.run(review_exc=RagError(code="review_llm_error", status=500, message="boom"))
    text = _vol_text(ctx)
    assert "Texnik xatolik" in text and "10 daqiqa" in text
    assert ctx.assignment.review_status == "none"
    assert ctx.assignment.review_passed_at is None
    assert ctx.db.committed is False
    assert ctx.bot.send_message.call_count == 2
    kwargs = ctx.bot.send_message.call_args[1]
    admin_text = kwargs.get("text", "")
    assert "review_llm_error" in admin_text and "№5" in admin_text
    assert "10 daqiqa" in admin_text


@pytest.mark.asyncio
async def test_error_timeout_and_unexpected():
    for exc in (asyncio.TimeoutError(), ValueError("kutilmagan")):
        ctx = Ctx()
        await ctx.run(review_exc=exc)
        text = _vol_text(ctx)
        assert "Texnik xatolik" in text and "10 daqiqa" in text
        assert ctx.assignment.review_status == "none"
        assert ctx.assignment.review_passed_at is None
        assert ctx.bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_error_admin_text_hides_secrets():
    ctx = Ctx()
    await ctx.run(review_exc=RagError(
        code="review_llm_error", status=500,
        message="boom Bearer abc123 RAG_API_KEY=xyz http://u:pw@host/x",
    ))
    kwargs = ctx.bot.send_message.call_args[1]
    admin_text = kwargs.get("text", "")
    assert "abc123" not in admin_text
    assert "xyz" not in admin_text
    assert ":pw@" not in admin_text
    assert "***" in admin_text


@pytest.mark.asyncio
async def test_error_dedupe_and_aggregation():
    redis = FakeRedis()
    ctx1 = Ctx(redis=redis)
    await ctx1.run(review_exc=RagError(code="review_timeout", status=504, message="t"))
    assert ctx1.bot.send_message.call_count == 2
    ctx2 = Ctx(redis=redis)
    await ctx2.run(review_exc=RagError(code="review_timeout", status=504, message="t"))
    assert ctx2.bot.send_message.call_count == 0  # 5 daqiqada 2-xabar yo'q
    assert "Texnik xatolik" in ctx2.message.answer.call_args[0][0]  # volontyor baribir ogohlantiriladi
    ctx3 = Ctx(redis=redis)
    await ctx3.run(review_exc=RagError(code="review_llm_error", status=500, message="boshqa"))
    assert ctx3.bot.send_message.call_count == 2  # boshqa kalit — yuboriladi
    redis.store.pop("review_err:RagError:review_timeout:lock", None)
    ctx4 = Ctx(redis=redis)
    await ctx4.run(review_exc=RagError(code="review_timeout", status=504, message="t"))
    assert ctx4.bot.send_message.call_count == 2
    kwargs = ctx4.bot.send_message.call_args[1]
    assert "yana 1 ta" in kwargs.get("text", "")


@pytest.mark.asyncio
async def test_error_redis_down_still_sends():
    ctx = Ctx(redis=None)
    ctx.redis = None
    review_mock = AsyncMock(side_effect=RagError(code="review_timeout", status=504, message="t"))
    with (
        patch.object(va, "_active_volunteer", return_value=SimpleNamespace(user_id=777)),
        patch.object(va, "_vol_lang", return_value="uz"),
        patch.object(va.rag_client, "review", review_mock),
        patch.object(va.settings, "ADMIN_IDS", "111"),
        patch.object(va, "_get_redis_client", return_value=None),
    ):
        await va.vol_review_draft_handler(ctx.message, ctx.state, ctx.db, ctx.bot)
    assert ctx.bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_review_sends_disability_state_and_request_id():
    ctx = Ctx(disability_state="vision")
    review_mock = await ctx.run(review_result=_ok_payload())
    assert review_mock.call_args.kwargs["disability_state"] == "vision"
    assert review_mock.call_args.kwargs["request_id"] == "inquiry:5"


@pytest.mark.asyncio
async def test_dedupe_helper_directly():
    redis = FakeRedis()
    assert await _review_error_dedupe(redis, "k1") == (True, 0)
    assert await _review_error_dedupe(redis, "k1") == (False, 0)
    assert await _review_error_dedupe(None, "k1") == (True, 0)


def test_format_review_issues():
    out = format_review_issues([
        {"type": "t", "quote": "q" * 500, "problem": "p", "fix": "f"},
    ])
    assert "…" in out and "q" * 500 not in out
    assert format_review_issues([]) == "—"
    assert format_review_issues(None) == "—"


def test_error_info_and_key():
    assert review_error_info(RagError(code="review_timeout", status=504)) == ("RagError", "review_timeout")
    assert review_error_info(asyncio.TimeoutError()) == ("TimeoutError", "review_timeout")
    assert review_error_info(ValueError("x")) == ("ValueError", "exception")
    assert review_error_key("RagError", "review_llm_error") == "review_err:RagError:review_llm_error"


def test_sanitize_hides_secrets():
    out = sanitize_admin_error_text("err RAG_API_KEY=abc123 done")
    assert "abc123" not in out and "***" in out
    out2 = sanitize_admin_error_text("x http://user:pw@host/y")
    assert "pw@" not in out2
