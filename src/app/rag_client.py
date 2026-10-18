import asyncio
import ipaddress
import logging
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RagError(Exception):
    def __init__(
        self,
        code: str,
        status: int = 500,
        retry_after: int | None = None,
        message: str = "",
    ):
        super().__init__(message or code)
        self.code = code
        self.status = status
        self.retry_after = retry_after
        self.message = message

    def __str__(self) -> str:
        return f"RagError(code={self.code}, status={self.status}, retry_after={self.retry_after})"


def normalize_language(lang: str | None) -> str:
    if not lang:
        return "uz"
    l = lang.lower().strip()
    if l == "ru":
        return "ru"
    if l in ("uz", "oz"):
        return "uz"
    if l == "auto":
        return "auto"
    return "uz"


REVIEW_VERDICTS = ("approve", "reject", "needs_admin")
REVIEW_SCORE_KEYS = ("legal_accuracy", "citation_basis", "completeness", "tone")
REVIEW_ISSUE_KEYS = ("type", "quote", "problem", "fix")


def _is_score(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 5


def validate_review_response(data: Any) -> dict[str, Any]:
    """YANGI /assistant/review javob sxemasini tekshirish (fail-closed).

    Mos kelmasa RagError(code='review_parse_error', status=502) ko'taradi.
    """
    def bad() -> RagError:
        return RagError(code="review_parse_error", status=502, message="Review response schema mismatch")

    if not isinstance(data, dict):
        raise bad()
    if data.get("verdict") not in REVIEW_VERDICTS:
        raise bad()
    scores = data.get("scores")
    if not isinstance(scores, dict) or any(k not in scores or not _is_score(scores[k]) for k in REVIEW_SCORE_KEYS):
        raise bad()
    issues = data.get("issues")
    if not isinstance(issues, list):
        raise bad()
    norm_issues = []
    for item in issues:
        if not isinstance(item, dict):
            raise bad()
        if any(k not in item or not isinstance(item[k], str) for k in REVIEW_ISSUE_KEYS):
            raise bad()
        norm_issues.append({k: item[k] for k in REVIEW_ISSUE_KEYS})
    if not isinstance(data.get("summary"), str):
        raise bad()
    hint = data.get("delivery_hint")
    if hint is not None and not isinstance(hint, str):
        raise bad()
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise bad()
    if not isinstance(data.get("rubric_version"), str) or not isinstance(data.get("model"), str):
        raise bad()
    if not isinstance(data.get("retrieved"), list):
        raise bad()
    return {
        "verdict": data["verdict"],
        "scores": {k: scores[k] for k in REVIEW_SCORE_KEYS},
        "issues": norm_issues,
        "summary": data["summary"],
        "delivery_hint": hint.strip() if hint and hint.strip() else None,
        "confidence": confidence,
        "rubric_version": data["rubric_version"],
        "model": data["model"],
        "retrieved": data["retrieved"],
    }


def is_safe_api_url(url: str) -> bool:
    """The key is sent on every request, so plain http is allowed only inside the host/private network
    (loopback, private IP, or a single-label Docker service name such as http://rag:8000)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if not host or parts.username or parts.password:
        return False
    if parts.scheme == "https":
        return True
    if parts.scheme != "http":
        return False
    if host == "localhost" or "." not in host:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


class RagClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._unsafe_url_logged = False

    def is_configured(self) -> bool:
        """Ichki AI uchun ulanish tekshiruvi (AI_ASSISTANT_ENABLED bayrog'isiz)."""
        if not (settings.RAG_API_URL and settings.RAG_API_KEY):
            return False
        if not is_safe_api_url(settings.RAG_API_URL):
            if not self._unsafe_url_logged:
                logger.error("RAG_API_URL must be https (plain http only for localhost/private network); AI disabled")
                self._unsafe_url_logged = True
            return False
        return True

    def is_enabled(self) -> bool:
        if not settings.AI_ASSISTANT_ENABLED:
            return False
        return self.is_configured()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _build_headers(self) -> dict[str, str]:
        # Explicitly do NOT include Origin header: server key + Origin returns 403
        return {
            "Authorization": f"Bearer {settings.RAG_API_KEY}",
            "Content-Type": "application/json",
        }

    async def _handle_error_response(self, resp: aiohttp.ClientResponse):
        retry_after = None
        ra_header = resp.headers.get("Retry-After")
        if ra_header:
            try:
                retry_after = int(ra_header)
            except ValueError:
                pass

        err_code = "error"
        err_msg = ""
        try:
            data = await resp.json()
            if isinstance(data, dict):
                err_obj = data.get("error", {})
                if isinstance(err_obj, dict):
                    err_code = err_obj.get("code", "error")
                    err_msg = err_obj.get("message", "")
        except Exception:
            pass

        if resp.status == 429:
            err_code = err_code if err_code != "error" else "rate_limited"
        elif resp.status == 404:
            err_code = err_code if err_code != "error" else "conversation_not_found"
        elif resp.status in (401, 403):
            err_code = err_code if err_code != "error" else "auth_error"
        elif resp.status == 503:
            err_code = err_code if err_code != "error" else "service_unavailable"
        elif resp.status == 500:
            err_code = err_code if err_code != "error" else "server_error"

        # Log status, error code and retry_after ONLY (never question or key)
        logger.warning(
            "RAG API error: status=%s, code=%s, retry_after=%s",
            resp.status,
            err_code,
            retry_after,
        )
        raise RagError(
            code=err_code,
            status=resp.status,
            retry_after=retry_after,
            message=err_msg,
        )

    async def ask(
        self,
        question: str,
        user_id: str | int,
        conversation_id: str | None = None,
        language: str = "uz",
        internal: bool = False,
    ) -> dict[str, Any]:
        ready = self.is_configured() if internal else self.is_enabled()
        if not ready:
            raise RagError(code="disabled", status=503, message="AI assistant is not enabled")

        url = f"{settings.RAG_API_URL.rstrip('/')}/api/v1/assistant/ask"
        payload = {
            "question": str(question),
            "user_id": str(user_id),
            "conversation_id": conversation_id,
            "language": normalize_language(language),
            "format": "telegram_html",
        }
        headers = self._build_headers()
        timeout = aiohttp.ClientTimeout(total=float(settings.RAG_TIMEOUT_SECONDS))

        session = self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout, allow_redirects=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info("RAG ask success: status=200, latency_ms=%s", data.get("latency_ms"))
                    return data

                # Check if 404 (conversation_not_found): retry once with conversation_id=None
                if resp.status == 404 and conversation_id is not None:
                    should_retry = True
                    try:
                        err_data = await resp.json()
                        if isinstance(err_data, dict):
                            code = err_data.get("error", {}).get("code")
                            if code and code != "conversation_not_found":
                                should_retry = False
                    except Exception:
                        pass

                    if should_retry:
                        logger.info("RAG ask returned 404. Retrying once without conversation_id.")
                        retry_payload = dict(payload)
                        retry_payload["conversation_id"] = None
                        async with session.post(
                            url, json=retry_payload, headers=headers, timeout=timeout, allow_redirects=False
                        ) as retry_resp:
                            if retry_resp.status == 200:
                                retry_data = await retry_resp.json()
                                logger.info(
                                    "RAG ask retry success: status=200, latency_ms=%s",
                                    retry_data.get("latency_ms"),
                                )
                                return retry_data
                            await self._handle_error_response(retry_resp)

                await self._handle_error_response(resp)

        except RagError:
            raise
        except asyncio.TimeoutError:
            logger.warning("RAG request timeout (timeout=%s)", settings.RAG_TIMEOUT_SECONDS)
            raise RagError(code="timeout", status=504, message="RAG request timed out")
        except aiohttp.ClientError as e:
            logger.warning("RAG client network error: %s", type(e).__name__)
            raise RagError(code="network_error", status=503, message="Network error connecting to RAG")

    async def status(self) -> dict[str, Any]:
        """LLM xizmati holati va balans (GET /api/v1/assistant/status)."""
        if not self.is_configured():
            raise RagError(code="disabled", status=503, message="RAG is not configured")
        url = f"{settings.RAG_API_URL.rstrip('/')}/api/v1/assistant/status"
        timeout = aiohttp.ClientTimeout(total=20)
        session = self._get_session()
        async with session.get(url, headers=self._build_headers(), timeout=timeout, allow_redirects=False) as resp:
            if resp.status == 200:
                return await resp.json()
            await self._handle_error_response(resp)
        return {}

    async def review(
        self,
        question: str | None,
        section: str | None,
        answer: str,
        disability_state: str | None,
        request_id: str,
    ) -> dict[str, Any]:
        """YANGI maxsus endpoint: POST /api/v1/assistant/review.

        Ichki AI nazoratchi uchun — rag_client.is_enabled()/AI_ASSISTANT_ENABLED
        ga BOG'LIQ EMAS, faqat is_configured() tekshiriladi.
        Sxema buzilsa RagError(code='review_parse_error'), vaqt tugasa
        RagError(code='review_timeout') ko'taradi.
        """
        if not self.is_configured():
            raise RagError(code="disabled", status=503, message="AI reviewer is not configured")

        url = f"{settings.RAG_API_URL.rstrip('/')}/api/v1/assistant/review"
        payload = {
            "question": str(question or ""),
            "section": str(section or ""),
            "answer": str(answer or ""),
            "language": "uz",
            "disability_state": disability_state,
            "request_id": str(request_id),
        }
        headers = self._build_headers()
        timeout = aiohttp.ClientTimeout(total=float(settings.RAG_REVIEW_TIMEOUT_SECONDS))

        session = self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout, allow_redirects=False) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                    except Exception:
                        raise RagError(code="review_parse_error", status=502, message="Review response is not valid JSON")
                    result = validate_review_response(data)
                    logger.info("RAG review success: verdict=%s", result["verdict"])
                    return result
                await self._handle_error_response(resp)

        except RagError:
            raise
        except asyncio.TimeoutError:
            logger.warning("RAG review timeout (timeout=%s)", settings.RAG_REVIEW_TIMEOUT_SECONDS)
            raise RagError(code="review_timeout", status=504, message="Review request timed out")
        except aiohttp.ClientError:
            logger.warning("RAG review network error")
            raise RagError(code="network_error", status=503, message="Network error connecting to RAG")
        raise RagError(code="error", status=500, message="Unexpected review failure")

    async def feedback(self, answer_id: str, rating: str, comment: str = "") -> bool:
        if not self.is_configured():
            return False

        url = f"{settings.RAG_API_URL.rstrip('/')}/api/v1/assistant/feedback"
        payload = {
            "answer_id": str(answer_id),
            "rating": rating,
            "comment": comment,
        }
        headers = self._build_headers()
        timeout = aiohttp.ClientTimeout(total=float(settings.RAG_TIMEOUT_SECONDS))

        session = self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout, allow_redirects=False) as resp:
                logger.info("RAG feedback status=%s", resp.status)
                return resp.status == 200
        except Exception as e:
            logger.warning("RAG feedback error: %s", type(e).__name__)
            return False

    async def delete_conversation(self, conversation_id: str, user_id: str | int) -> bool:
        if not self.is_enabled():
            return False

        url = f"{settings.RAG_API_URL.rstrip('/')}/api/v1/assistant/conversations/{conversation_id}/delete"
        payload = {"user_id": str(user_id)}
        headers = self._build_headers()
        timeout = aiohttp.ClientTimeout(total=float(settings.RAG_TIMEOUT_SECONDS))

        session = self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout, allow_redirects=False) as resp:
                logger.info("RAG delete_conversation status=%s", resp.status)
                return resp.status == 200
        except Exception as e:
            logger.warning("RAG delete_conversation error: %s", type(e).__name__)
            return False


rag_client = RagClient()
