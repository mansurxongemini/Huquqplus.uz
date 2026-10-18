"""Biriktirishlar paneli."""
import html
import logging
from datetime import datetime
from aiogram import F

logger = logging.getLogger(__name__)
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.volunteer import Volunteer
from src.routes.deps.db_session import DBSession
from src.app.link_utils import build_group_message_link

from src.routes.aiogram.admin.common import admin_router


def _wait_str(since: datetime | None) -> str:
    if not since:
        return "—"
    hours = int((datetime.now() - since).total_seconds() // 3600)
    return f"{hours // 24} kun {hours % 24} soat" if hours >= 24 else f"{hours} soat"

def _inquiry_link(inq: Inquiry) -> str:
    link = build_group_message_link(inq.group_id, inq.group_question_id)
    return f'<a href="{link}">№{inq.id}</a>' if link else f"№{inq.id}"

def build_assignments_panel(db_session: DBSession) -> tuple[str, InlineKeyboardMarkup]:
    from src.models.assignment import AssignmentStatus, InquiryAssignment
    open_rows = db_session.exec(
        select(InquiryAssignment).where(InquiryAssignment.status.in_(AssignmentStatus.OPEN))
    ).all()
    per_vol: dict[int, list] = {}
    for row in open_rows:
        per_vol.setdefault(row.volunteer_user_id, []).append(row)
    unassigned = db_session.exec(
        select(Inquiry).where(Inquiry.status == InquiryStatus.active, Inquiry.assigned_volunteer_id == None)  # noqa: E711
        .order_by(Inquiry.created_at)
    ).all()
    lines = ["<b>📋 Biriktirishlar paneli</b><br/>"]
    lines.append(f"🟡 <b>Biriktirilmagan faol murojaatlar:</b> {len(unassigned)} ta")
    if unassigned:
        lines.append("Eng uzoq kutayotganlar: " + ", ".join(
            f"{_inquiry_link(i)} ({_wait_str(i.created_at)})" for i in unassigned[:8]))
    lines.append("<br/>👥 <b>Volontyorlardagi ochiq murojaatlar:</b>")
    builder = InlineKeyboardBuilder()
    if not per_vol:
        lines.append("<i>Ochiq biriktirish yo'q</i>")
    for vol_user_id, rows in sorted(per_vol.items(), key=lambda kv: min(r.assigned_at or datetime.now() for r in kv[1])):
        vol = Volunteer.get_by_user_id(vol_user_id, db_session)
        name = vol.full_name if vol else str(vol_user_id)
        oldest = min((r.assigned_at for r in rows if r.assigned_at), default=None)
        lines.append(f"• {html.escape(name)}: <b>{len(rows)}</b> ta, eng uzog'i {_wait_str(oldest)}")
        builder.button(text=f"{name[:24]} ({len(rows)})", callback_data=f"admin:asg_vol:{vol_user_id}")
    builder.button(text="🔄 Yangilash", callback_data="admin:asg_panel")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)
    lines.append("<br/><i>Qayta biriktirish: murojaat havolasini oching va kartadagi «🔗 Biriktirish» tugmasini bosing.</i>")
    return "<br/>".join(lines), builder.as_markup()

@admin_router.callback_query(F.data == "admin:asg_panel", is_private_message)
async def admin_assignments_panel(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)
    text, markup = build_assignments_panel(db_session)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE,
                                  link_preview_options=LinkPreviewOptions(is_disabled=True))
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:asg_vol:"), is_private_message)
async def admin_assignments_of_volunteer(query: CallbackQuery, db_session: DBSession):
    from src.models.assignment import AssignmentStatus, InquiryAssignment
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)
    try:
        vol_user_id = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        return await query.answer()
    rows = db_session.exec(
        select(InquiryAssignment).where(
            InquiryAssignment.volunteer_user_id == vol_user_id,
            InquiryAssignment.status.in_(AssignmentStatus.OPEN),
        ).order_by(InquiryAssignment.assigned_at)
    ).all()
    vol = Volunteer.get_by_user_id(vol_user_id, db_session)
    lines = [f"<b>👤 {html.escape(vol.full_name if vol else str(vol_user_id))}</b> — ochiq murojaatlar ({len(rows)} ta):<br/>"]
    for row in rows[:30]:
        inq = db_session.get(Inquiry, row.inquiry_id)
        if not inq:
            continue
        review = {"passed": "✅ tasdiqlangan", "failed": "❌ rad etilgan", "needs_admin": "⏳ admin ko'rigida"}.get(
            row.review_status or "", "tekshirilmagan")
        lines.append(f"• {_inquiry_link(inq)} — {html.escape((inq.section_name or '').strip())}, "
                     f"kutmoqda {_wait_str(row.assigned_at)}, javob: {review}")
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Panelga qaytish", callback_data="admin:asg_panel")
    await query.message.edit_text("<br/>".join(lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE,
                                  link_preview_options=LinkPreviewOptions(is_disabled=True))
    await query.answer()
