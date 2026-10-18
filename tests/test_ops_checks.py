from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramMigrateToChat

from src.app import ops_checks
from src.config.settings import settings


def test_error_digest_groups_same_errors():
    entries = [{"type": "KeyError", "msg": "x"}] * 3 + [{"type": "ValueError", "msg": "y"}]
    text = ops_checks.build_error_digest(entries, "18.10.2026")
    assert "jami 4 ta" in text and "3 ×  KeyError: x" in text
    assert ops_checks.build_error_digest([], "18.10.2026") is None


@pytest.mark.asyncio
async def test_config_check_reports_basic_group_missing_rights_and_migration(monkeypatch):
    monkeypatch.setattr(ops_checks, "_configured_groups", lambda: {"-5350260753": "Eski", "-100111": "Mehnat", "-100222": "Ta'lim"})

    async def get_chat(gid):
        if gid == "-5350260753":
            raise TelegramMigrateToChat(method=MagicMock(), message="upgraded", migrate_to_chat_id=-1004291925995)
        return SimpleNamespace(type="supergroup")

    async def get_chat_member(gid, uid):
        if gid == "-100111":
            return SimpleNamespace(status="member")
        return SimpleNamespace(status="administrator", can_delete_messages=True)

    bot = MagicMock(id=1, get_chat=get_chat, get_chat_member=get_chat_member)
    with patch("src.app.rag_client.rag_client.is_configured", return_value=True):
        issues = await ops_checks.collect_config_issues(bot)
    assert len(issues) == 2
    assert "-1004291925995" in issues[0] and "admin emas" in issues[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("status, alerted", [
    ({"ok": True, "credits_remaining": 10.0}, False),
    ({"ok": True, "credits_remaining": 1.0}, True),
    ({"ok": False, "credits_remaining": -0.2, "error": "insufficient_credits"}, True),
])
async def test_balance_alert(monkeypatch, status, alerted):
    monkeypatch.setattr(settings, "AI_BALANCE_ALERT_USD", 2.0)
    with patch("src.app.rag_client.rag_client.is_configured", return_value=True), \
         patch("src.app.rag_client.rag_client.status", AsyncMock(return_value={"llm": status})), \
         patch.object(ops_checks, "notify_super_admins", AsyncMock()) as notify:
        await ops_checks.check_llm_balance(MagicMock())
    assert notify.await_count == (1 if alerted else 0)


def test_gate_summary_groups_by_volunteer():
    counts = {"5|no_review": 3, "5|foreign": 1, "7|unassigned": 1}
    text = ops_checks.build_gate_summary(counts, {"5": "Ali Valiyev"}, "2026w42")
    assert text.index("Ali Valiyev") < text.index('id=7')  # eng ko'p buzgan birinchi
    assert "4 ta (tekshiruvsiz — 3, boshqaga biriktirilgan murojaatga — 1)" in text
    assert ops_checks.build_gate_summary({}, {}, "2026w42") is None
