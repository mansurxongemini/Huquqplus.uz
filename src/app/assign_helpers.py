"""Biriktirish (A bosqich) sof yordamchilari: DB/bot siz sinash mumkin."""

import hashlib
import unicodedata
from datetime import datetime, timedelta

ASSIGN_PAGE_SIZE = 5
VOL_ASSIGNS_PAGE_SIZE = 10
FIRST_REMINDER_AFTER = timedelta(hours=24)
FOLLOWUP_REMINDER_EVERY = timedelta(hours=6)


def assign_list_cb(inquiry_id: int, page: int) -> str:
    return f"inq_assign:{inquiry_id}:{page}"


def parse_assign_pair(data: str) -> tuple[int, int]:
    """'inq_assign_pick:{inquiry_id}:{volunteer_user_id}' (yoki retry) -> (inquiry_id, volunteer_user_id)."""
    _, inq_id_s, vol_id_s = data.split(":")
    return int(inq_id_s), int(vol_id_s)


def assign_pick_cb(inquiry_id: int, volunteer_user_id: int) -> str:
    return f"inq_assign_pick:{inquiry_id}:{volunteer_user_id}"


def assign_retry_cb(inquiry_id: int, volunteer_user_id: int) -> str:
    return f"inq_assign_retry:{inquiry_id}:{volunteer_user_id}"


def cb_within_limit(cb: str, limit: int = 64) -> bool:
    return len(cb.encode("utf-8")) <= limit


def paginate(items: list, page: int, per_page: int = ASSIGN_PAGE_SIZE) -> tuple[list, int, int]:
    total_pages = max((len(items) + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return items[start:start + per_page], total_pages, page


def rank_section_candidates(rows: list[dict]) -> list[dict]:
    """Soha kandidatlarini tavsiya tartibida saralash.

    Har bir row: {user_id, last_assigned_at|None, open_count, recent_replies}.
    Tartib: biriktirish olmagani (NULL) birinchi, keyin eng eski assigned_at,
    keyin ochiq ishlar kami, keyin oxirgi 30 kun javoblari ko'pi.
    """
    def key(r: dict):
        last = r.get("last_assigned_at")
        return (
            last is not None,
            last or "",
            r.get("open_count", 0),
            -(r.get("recent_replies", 0)),
            r.get("user_id", 0),
        )
    return sorted(rows, key=key)


def last_assigned_key(value) -> tuple:
    """Sinash uchun kalit: NULL birinchi."""
    return (value is not None, value or "")


def vol_assigns_cb(page: int) -> str:
    return f"volas:{page}"


def is_quiet_day(weekday: int, skip_weekdays: str) -> bool:
    """Eslatma yuborilmaydigan kunlar: "5,6" — shanba va yakshanba (0 — dushanba)."""
    days = {int(d) for d in (skip_weekdays or "").replace(" ", "").split(",") if d.isdigit()}
    return weekday in days


def is_quiet_hour(now_hour: int, start: int = 22, end: int = 6) -> bool:
    """Tungi sukunat (Toshkent): start<=soat<end; oraliq yarim tunni kesib o'tadi."""
    now_hour = int(now_hour) % 24
    start = int(start) % 24
    end = int(end) % 24
    if start == end:
        return False
    if start < end:
        return start <= now_hour < end
    return now_hour >= start or now_hour < end


def reminder_due(
    assigned_at: datetime | None,
    first_reminded_at: datetime | None,
    last_reminded_at: datetime | None,
    now: datetime,
) -> str | None:
    """Eslatma vaqti kelganmi: 'first' | 'followup' | None.

    Birinchi eslatma assigned_at+24h o'tgach; keyingilari oxirgi
    eslatmadan har 6 soatda. 'O'tgan' mantiq (tenglik emas).
    """
    if assigned_at is None:
        return None
    if first_reminded_at is None:
        if assigned_at + FIRST_REMINDER_AFTER <= now:
            return "first"
        return None
    last = last_reminded_at or first_reminded_at
    if last + FOLLOWUP_REMINDER_EVERY <= now:
        return "followup"
    return None


def reminder_applies(created_at: datetime | None, enforce_from: datetime | None) -> bool:
    """B eslatma shu murojaatga qo'llanadimi (chaqiruvchi assignment borligini tekshirgan).

    ASSIGN_ENFORCE_FROM None bo'lsa barcha biriktirilganlarga qo'llanadi.
    """
    if created_at is None:
        return True
    if enforce_from is None:
        return True
    return created_at >= enforce_from


def normalize_review_text(text: str) -> str:
    """Qoralama xesh uchun normalizatsiya: bir xil unicode (NFC), bosh/oxirgi
    bo'shliqlar olib tashlanadi, ichki bo'shliqlar yagona probelga yig'iladi."""
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(normalized.split())


def review_draft_hash(text: str) -> str:
    return hashlib.sha256(normalize_review_text(text).encode("utf-8")).hexdigest()


def review_hashes_match(sent_text: str | None, stored_hash: str | None) -> bool:
    if not sent_text or not stored_hash:
        return False
    return review_draft_hash(sent_text) == stored_hash


def is_text_review(text: str | None) -> bool:
    """AI nazoratchiga yaroqli kirishmi (faqat bo'sh bo'lmagan matn)."""
    return bool(text and text.strip())


def decide_answer_gate(
    *,
    enforce_from: datetime | None,
    inquiry_created_at: datetime | None,
    inquiry_status: str,
    assigned_volunteer_id: int | None,
    replier_id: int,
    is_admin: bool,
    is_lawyer: bool,
    review_row_exists: bool,
    review_passed: bool,
    hashes_match: bool,
    has_text: bool,
) -> str:
    """Javob darvozasi qarori (sof funksiya, group_router.handle_response ishlatadi).

    Qaytadi: allow_old | allow_admin | allow_lawyer | allow_pass |
    wait_unassigned | deny_foreign | deny_no_review | deny_changed.
    Darvoza faqat ASSIGN_ENFORCE_FROM sozlangan VA murojaat shundan keyin
    yaratilgan VA murojaat ochiq (active) bo'lganda yopiq; qolgan hamma holatda
    eski xulq (allow_old). Biriktirilmagan yangi murojaatga wait_unassigned.
    Tasdiq qatori (inquiry_assignments) topilmasa — tekshirib bo'lmaydi,
    eski xulq saqlanadi (allow_old).
    """
    if enforce_from is None:
        return "allow_old"
    if inquiry_created_at is None or inquiry_created_at < enforce_from:
        return "allow_old"
    if inquiry_status != "active":
        return "allow_old"
    if is_admin:
        return "allow_admin"
    if is_lawyer:
        return "allow_lawyer"
    if assigned_volunteer_id is None:
        return "wait_unassigned"
    if replier_id != assigned_volunteer_id:
        return "deny_foreign"
    if not review_row_exists:
        return "allow_old"
    if not review_passed:
        return "deny_no_review"
    if has_text and not hashes_match:
        return "deny_changed"
    return "allow_pass"
