import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, CallbackQuery, User as TgUser, Chat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from src.app.generate_staff_report import parse_date_range_string
from src.routes.aiogram.admin import (
    get_admin_menu_keyboard,
    admin_report_command,
    admin_report_custom_range_received,
    admin_report_menu_callback,
    AdminReportCustomState,
)
from src.config.settings import Settings


def test_parse_date_range_string_hashtag():
    # 01.08.2026#01.10.2026
    start_dt, end_dt, period_name, suffix = parse_date_range_string("01.08.2026#01.10.2026")
    assert start_dt == datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end_dt == datetime(2026, 10, 1, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert period_name == "01.08.2026 – 01.10.2026"
    assert suffix == "20260801_20261001"


def test_parse_date_range_string_with_command_prefix():
    # /report 01.08.2026#01.10.2026
    start_dt, end_dt, period_name, suffix = parse_date_range_string("/report 01.08.2026#01.10.2026")
    assert start_dt.year == 2026 and start_dt.month == 8 and start_dt.day == 1
    assert end_dt.year == 2026 and end_dt.month == 10 and end_dt.day == 1
    assert period_name == "01.08.2026 – 01.10.2026"


def test_parse_date_range_string_delimiters():
    # Hyphen with spaces
    s, e, p, _ = parse_date_range_string("01.08.2026 - 30.09.2026")
    assert p == "01.08.2026 – 30.09.2026"

    # Space separated
    s, e, p, _ = parse_date_range_string("01.08.2026 30.09.2026")
    assert p == "01.08.2026 – 30.09.2026"

    # Presets
    s, e, p, _ = parse_date_range_string("month")
    assert "Joriy oy" in p

    s, e, p, _ = parse_date_range_string("all")
    assert s is None and e is None
    assert p == "Barcha davr uchun"


def test_parse_date_range_invalid():
    with pytest.raises(ValueError):
        parse_date_range_string("30.09.2026#01.08.2026")  # start > end

    with pytest.raises(ValueError):
        parse_date_range_string("not_a_date#also_not")


def test_admin_menu_keyboard_has_report_button():
    kb = get_admin_menu_keyboard(blocked_count=1, channels_count=2, benefits_count=112)
    found = False
    for row in kb.inline_keyboard:
        for btn in row:
            if btn.callback_data == "admin:report_menu":
                found = True
                assert "Tahliliy hisobot" in btn.text
    assert found, "Tahliliy hisobot button not found in admin menu keyboard"


@pytest.mark.asyncio
async def test_admin_report_command_with_args():
    admin_id = 123456
    with patch.object(Settings, "is_admin", return_value=True):
        message = MagicMock(spec=Message)
        message.from_user = TgUser(id=admin_id, is_bot=False, first_name="Admin")
        message.chat = Chat(id=admin_id, type="private")
        message.text = "/report 01.08.2026#01.10.2026"
        message.answer = AsyncMock()

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_document = AsyncMock()

        storage = MemoryStorage()
        state = FSMContext(
            storage=storage,
            key=StorageKey(bot_id=1, chat_id=admin_id, user_id=admin_id)
        )

        with patch("src.routes.aiogram.admin.reports.generate_comprehensive_report") as mock_gen:
            mock_gen.return_value = ("/tmp/mock_report.xlsx", {
                "period": "01.08.2026 – 01.10.2026",
                "total_inquiries": 10,
                "total_answered": 8,
                "resolution_rate": 80.0,
                "total_rated": 5,
                "avg_rating": 4.5,
                "satisfaction_rate": 90.0,
                "avg_response_str": "5 daqiqa",
                "total_appointments": 3,
                "completed_appointments": 2,
                "remote_appointments": 2,
                "in_person_appointments": 1,
                "avg_app_rating": 4.8,
                "top_regions": [("Toshkent", {"total": 10})],
                "top_sections": [("Mehnat", {"total": 10})],
                "top_specialist": None,
            })
            with patch("os.path.exists", return_value=True):
                with patch("shutil.copy2"):
                    with patch("os.remove"):
                        await admin_report_command(message, state, bot)

        # Must send confirmation / document
        assert message.answer.called
        assert bot.send_document.called or bot.send_message.called


@pytest.mark.asyncio
async def test_admin_report_custom_range_received():
    admin_id = 123456
    with patch.object(Settings, "is_admin", return_value=True):
        message = MagicMock(spec=Message)
        message.from_user = TgUser(id=admin_id, is_bot=False, first_name="Admin")
        message.chat = Chat(id=admin_id, type="private")
        message.text = "01.08.2026#01.10.2026"
        message.answer = AsyncMock()

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_document = AsyncMock()

        storage = MemoryStorage()
        state = FSMContext(
            storage=storage,
            key=StorageKey(bot_id=1, chat_id=admin_id, user_id=admin_id)
        )
        await state.set_state(AdminReportCustomState.waiting_for_date_range)

        with patch("src.routes.aiogram.admin.reports.generate_comprehensive_report") as mock_gen:
            mock_gen.return_value = ("/tmp/mock_report.xlsx", {
                "period": "01.08.2026 – 01.10.2026",
                "total_inquiries": 10,
                "total_answered": 8,
                "resolution_rate": 80.0,
                "total_rated": 5,
                "avg_rating": 4.5,
                "satisfaction_rate": 90.0,
                "avg_response_str": "5 daqiqa",
                "total_appointments": 3,
                "completed_appointments": 2,
                "remote_appointments": 2,
                "in_person_appointments": 1,
                "avg_app_rating": 4.8,
                "top_regions": [],
                "top_sections": [],
                "top_specialist": None,
            })
            with patch("os.path.exists", return_value=True):
                with patch("shutil.copy2"):
                    with patch("os.remove"):
                        await admin_report_custom_range_received(message, state, bot)

        # State should be cleared
        current_state = await state.get_state()
        assert current_state is None
        assert message.answer.called
        assert bot.send_document.called or bot.send_message.called
