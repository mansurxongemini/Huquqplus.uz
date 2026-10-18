from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.appointment import Appointment, AppointmentStatus
from src.models.inquiry import Inquiry, InquiryMediaType, InquiryStatus
from src.routes.aiogram.inquiry_archive import format_inquiry_detail_card


def _inq(**kw):
    base = dict(id=7, user_id=10, section_name="Mehnat", question="Savol <b>1</b>\n2-qator",
                question_mediatype=InquiryMediaType.text, group_id="-100", group_question_id=1,
                status=InquiryStatus.active, created_at=datetime(2026, 10, 18, 10, 0))
    base.update(kw)
    return Inquiry(**base)


def test_archive_shows_assignment_and_escapes_question():
    card = format_inquiry_detail_card(_inq(assigned_at=datetime(2026, 10, 18, 12, 30)), "uz")
    assert "Mas'ul mutaxassis biriktirilgan" in card and "18.10.2026 12:30" in card
    assert "Savol &lt;b&gt;1&lt;/b&gt;<br/>2-qator" in card


def test_archive_waiting_for_assignment_ru():
    card = format_inquiry_detail_card(_inq(), "ru")
    assert "будет назначен" in card and "ОБРАЩЕНИЕ №7" in card


def test_appointment_card_shows_citizen_attendance():
    from src.app.appointment_card import render_appointment_card
    app = Appointment(id=3, user_id=10, problem_description="x", status=AppointmentStatus.accepted,
                      scheduled_at=datetime(2026, 10, 20, 10, 0), citizen_confirmation="no")
    db = MagicMock()
    db.exec.return_value.first.return_value = None
    db.get.return_value = None
    with patch("src.app.appointment_card.User.get_by_user_id", return_value=None):
        assert "qatnasha olmaydi" in render_appointment_card(app, db)


@pytest.mark.asyncio
async def test_attendance_no_notifies_group():
    from src.routes.aiogram import appointment as ap
    app = Appointment(id=3, user_id=10, problem_description="x", status=AppointmentStatus.accepted, group_message_id=55)
    db = MagicMock()
    db.get.return_value = app
    query = AsyncMock()
    query.data = "app_att:3:no"
    query.from_user.id = 10
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock()
    with patch.object(ap.User, "get_by_user_id", return_value=None), \
         patch.object(ap, "render_appointment_card", return_value="card"):
        await ap.appointment_attendance_callback(query, db, bot)
    assert app.citizen_confirmation == "no"
    assert bot.send_message.await_args.kwargs["reply_to_message_id"] == 55
