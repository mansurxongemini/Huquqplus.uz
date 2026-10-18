"""B/C/D bosqich sarg'ish testlari: sukunat soati, eslatma tanlash, xesh, darvoza, media rad."""
from datetime import datetime, timedelta

from src.app.assign_helpers import (
    cb_within_limit,
    decide_answer_gate,
    is_quiet_hour,
    is_text_review,
    normalize_review_text,
    reminder_applies,
    reminder_due,
    review_draft_hash,
    review_hashes_match,
    vol_assigns_cb,
)
from src.app.translations import t

ENFORCE = datetime(2026, 10, 20)


def _gate(**kw):
    base = dict(
        enforce_from=ENFORCE,
        inquiry_created_at=ENFORCE + timedelta(days=1),
        inquiry_status="active",
        assigned_volunteer_id=100,
        replier_id=100,
        is_admin=False,
        is_lawyer=False,
        review_row_exists=True,
        review_passed=True,
        hashes_match=True,
        has_text=True,
    )
    base.update(kw)
    return decide_answer_gate(**base)


def test_quiet_hour_wrap_around():
    assert is_quiet_hour(22) is True
    assert is_quiet_hour(0) is True
    assert is_quiet_hour(5) is True
    assert is_quiet_hour(6) is False
    assert is_quiet_hour(21) is False
    assert is_quiet_hour(12) is False


def test_quiet_hour_custom_range():
    assert is_quiet_hour(23, 23, 7) is True
    assert is_quiet_hour(7, 23, 7) is False
    assert is_quiet_hour(10, 8, 20) is True
    assert is_quiet_hour(21, 8, 20) is False


def test_reminder_due_first():
    now = datetime(2026, 10, 25, 12, 0)
    assert reminder_due(now - timedelta(hours=25), None, None, now) == "first"
    assert reminder_due(now - timedelta(hours=23), None, None, now) is None
    assert reminder_due(now - timedelta(hours=24), None, None, now) == "first"
    assert reminder_due(None, None, None, now) is None


def test_reminder_due_followup():
    now = datetime(2026, 10, 25, 12, 0)
    assigned = now - timedelta(days=3)
    first = now - timedelta(hours=7)
    assert reminder_due(assigned, first, first, now) == "followup"
    assert reminder_due(assigned, first, now - timedelta(hours=5), now) is None
    assert reminder_due(assigned, first, now - timedelta(hours=6), now) == "followup"


def test_reminder_applies_enforce():
    assert reminder_applies(ENFORCE + timedelta(hours=1), ENFORCE) is True
    assert reminder_applies(ENFORCE - timedelta(hours=1), ENFORCE) is False
    assert reminder_applies(ENFORCE - timedelta(days=30), None) is True


def test_review_hash_normalization():
    h1 = review_draft_hash("  Salom   dunyo ")
    h2 = review_draft_hash("Salom dunyo")
    assert h1 == h2
    assert review_hashes_match("Salom dunyo!", h1) is False
    assert review_hashes_match("Salom dunyo", h1) is True
    assert review_hashes_match("", h1) is False
    assert review_hashes_match("Salom dunyo", None) is False
    assert normalize_review_text("a\r\nb") == normalize_review_text("a\nb")


def test_gate_admin_lawyer_free():
    assert _gate(is_admin=True, review_passed=False, hashes_match=False) == "allow_admin"
    assert _gate(is_lawyer=True, review_passed=False, hashes_match=False) == "allow_lawyer"


def test_gate_foreign_denied():
    assert _gate(replier_id=200) == "deny_foreign"


def test_gate_unassigned_waits():
    assert _gate(assigned_volunteer_id=None) == "wait_unassigned"


def test_gate_review_branches():
    assert _gate(review_passed=False) == "deny_no_review"
    assert _gate(hashes_match=False) == "deny_changed"
    assert _gate() == "allow_pass"


def test_gate_media_without_text_passes_when_approved():
    assert _gate(has_text=False, hashes_match=False) == "allow_pass"
    assert _gate(has_text=False, hashes_match=False, review_passed=False) == "deny_no_review"


def test_gate_old_inquiries_unchanged():
    assert _gate(enforce_from=None) == "allow_old"
    assert _gate(inquiry_created_at=ENFORCE - timedelta(seconds=1)) == "allow_old"
    assert _gate(inquiry_created_at=None) == "allow_old"
    assert _gate(inquiry_status="replied") == "allow_old"
    assert _gate(review_row_exists=False) == "allow_old"


def test_review_text_predicate_rejects_media():
    assert is_text_review("javob matni") is True
    assert is_text_review("   ") is False
    assert is_text_review("") is False
    assert is_text_review(None) is False


def test_review_unavailable_is_tech_error_text():
    assert "10 daqiqa" in t("review_unavailable", "uz")
    assert "10 дақиқа" in t("review_unavailable", "oz")
    assert "10 минут" in t("review_unavailable", "ru")


def test_vol_assigns_callback_within_limit():
    assert cb_within_limit(vol_assigns_cb(12345))
    assert vol_assigns_cb(3) == "volas:3"


def test_bcd_translations_present():
    keys = (
        "assign_remind_first", "assign_remind_follow", "assign_remind_blocked_admin",
        "menu_vol_result", "menu_vol_assigns", "menu_vol_review",
        "vol_assigns_title", "vol_assigns_empty", "vol_assigns_row",
        "review_ask", "review_no_assign", "review_only_text", "review_unavailable",
        "review_rejected", "review_approved", "review_hint",
        "review_needs_admin", "review_admin_escalation",
        "review_error_admin", "review_error_admin_pending",
        "gate_foreign", "gate_unassigned", "gate_need_review", "gate_changed",
    )
    for key in keys:
        for lang in ("uz", "oz", "ru"):
            assert t(key, lang) != key, (key, lang)


def test_quiet_day_setting():
    from src.app.assign_helpers import is_quiet_day
    assert is_quiet_day(6, "6") and is_quiet_day(5, "5, 6")
    assert not is_quiet_day(0, "5,6") and not is_quiet_day(6, "")
