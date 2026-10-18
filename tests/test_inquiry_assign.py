"""A/E bosqich sarg'ish testi: normalizatsiya, callback limiti, sahifalash, tavsiya tartibi, bayroqlar."""
from src.app.assign_helpers import (
    assign_list_cb,
    assign_pick_cb,
    assign_retry_cb,
    parse_assign_pair,
    cb_within_limit,
    paginate,
    rank_section_candidates,
)
from src.app.keyboards import inquiry_sections_oz, inquiry_sections_ru, normalize_section_name
from src.app.translations import t
from src.config.settings import settings
from src.routes.aiogram.inquiry_assign import classify_dm_error


def test_normalize_section_uz_passthrough():
    assert normalize_section_name("🏘  Uy-joy") == "🏘  Uy-joy"
    assert normalize_section_name(None) is None
    assert normalize_section_name("Noma'lum soha") == "Noma'lum soha"


def test_normalize_section_oz_ru_to_uz():
    oz_name = next(iter(inquiry_sections_oz.keys()))
    ru_name = next(iter(inquiry_sections_ru.keys()))
    oz_id = inquiry_sections_oz[oz_name]
    ru_id = inquiry_sections_ru[ru_name]
    from src.app.keyboards import inquiry_sections_uz
    uz_by_id = {v: k for k, v in inquiry_sections_uz.items()}
    assert normalize_section_name(oz_name) == uz_by_id[oz_id]
    assert normalize_section_name(ru_name) == uz_by_id[ru_id]


def test_assign_callbacks_within_64_bytes():
    big_inq, big_vol = 99999999, 9999999999
    for cb in (assign_list_cb(big_inq, 12), assign_pick_cb(big_inq, big_vol), assign_retry_cb(big_inq, big_vol)):
        assert cb_within_limit(cb), cb


def test_paginate_five_per_page():
    items = list(range(12))
    page1, total, p = paginate(items, 1)
    assert (page1, total, p) == ([0, 1, 2, 3, 4], 3, 1)
    page3, total, p = paginate(items, 9)
    assert (page3, total, p) == ([10, 11], 3, 3)


def test_rank_section_candidates_order():
    rows = [
        {"user_id": 1, "last_assigned_at": "2026-10-10", "open_count": 0, "recent_replies": 0},
        {"user_id": 2, "last_assigned_at": None, "open_count": 5, "recent_replies": 0},
        {"user_id": 3, "last_assigned_at": "2026-10-01", "open_count": 9, "recent_replies": 1},
        {"user_id": 4, "last_assigned_at": "2026-10-01", "open_count": 1, "recent_replies": 7},
    ]
    assert [r["user_id"] for r in rank_section_candidates(rows)] == [2, 4, 3, 1]


def test_leaderboard_public_off_by_default():
    assert settings.VOLUNTEER_LEADERBOARD_PUBLIC is False
    # .env da sozlangan bo'lishi mumkin: kod defaulti None bo'lishi kerak
    assert type(settings).model_fields["ASSIGN_ENFORCE_FROM"].default is None


def test_classify_dm_error():
    assert classify_dm_error("blocked", Exception("bot was blocked by the user")) == "blocked"
    assert classify_dm_error("blocked", Exception("chat not found")) == "nostart"
    assert classify_dm_error("network_error: x", Exception("timeout")) == "other"


def test_assign_translations_present():
    for key in ("assign_only_admins", "assign_dm_text", "assign_moved_dm", "assign_group_done",
                "assign_retry_btn", "assign_list_title", "vol_sections_title"):
        for lang in ("uz", "oz", "ru"):
            assert t(key, lang) != key, (key, lang)


def test_assign_pair_callback_roundtrip():
    assert parse_assign_pair(assign_pick_cb(7, 8954778334)) == (7, 8954778334)
    assert parse_assign_pair(assign_retry_cb(123, 99)) == (123, 99)
