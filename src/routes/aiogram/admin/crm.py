"""Yurist qabullari CRM va taqvimi."""
import json
import logging
from datetime import datetime
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.routes.deps.db_session import DBSession
from src.app.appointment_card import (
    render_appointment_card,
    get_appointment_markup,
    notify_citizen_appointment_update,
)

from src.routes.aiogram.admin.common import AdminCrmState, PAGE_SIZE, admin_router


@admin_router.callback_query(F.data == "admin:crm_appointments", is_private_message)
async def admin_crm_dashboard(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)

    all_apps = db_session.exec(select(Appointment)).all()
    today_apps = [a for a in all_apps if a.scheduled_at and today_start <= a.scheduled_at <= today_end]
    upcoming_apps = [a for a in all_apps if a.scheduled_at and a.scheduled_at >= now and a.status in [AppointmentStatus.pending, AppointmentStatus.accepted]]
    pending_apps = [a for a in all_apps if a.status == AppointmentStatus.pending]

    dashboard_text = f"""
<b>📅 Yurist qabuli</b><br/><br/>
Hozirgi holat bo'yicha ko'rsatkichlar:<br/>
<b>Bugungi qabullar:</b> {len(today_apps)} ta<br/>
<b>Kutilayotgan rejalashtirilgan qabullar:</b> {len(upcoming_apps)} ta<br/>
<b>Yurist biriktirilmagan arizalar:</b> {len(pending_apps)} ta<br/>
<b>Jami qabullar tarixi:</b> {len(all_apps)} ta<br/><br/>
<i>Kerakli bo'limni tanlang:</i>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"📅 Bugungi qabullar ({len(today_apps)})", callback_data="admin:crm_list:today:1")
    builder.button(text=f"⏳ Kutilayotgan qabullar ({len(upcoming_apps)})", callback_data="admin:crm_list:upcoming:1")
    builder.button(text=f"📁 Barcha qabullar tarixi ({len(all_apps)})", callback_data="admin:crm_list:all:1")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text(dashboard_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:crm_list:"), is_private_message)
async def admin_crm_list_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    parts = query.data.split(":")
    filter_type = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 1

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)

    all_apps = db_session.exec(select(Appointment).order_by(Appointment.scheduled_at.desc())).all()

    if filter_type == "today":
        filtered_apps = [a for a in all_apps if a.scheduled_at and today_start <= a.scheduled_at <= today_end]
        title = "📅 <b>Bugungi qabullar</b>"
    elif filter_type == "upcoming":
        filtered_apps = [a for a in all_apps if a.scheduled_at and a.scheduled_at >= now and a.status in [AppointmentStatus.pending, AppointmentStatus.accepted]]
        title = "⏳ <b>Kutilayotgan rejalashtirilgan qabullar</b>"
    else:
        filtered_apps = all_apps
        title = "📁 <b>Barcha qabullar ro'yxati</b>"

    total = len(filtered_apps)
    if total == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ CRM menyuga qaytish", callback_data="admin:crm_appointments")
        return await query.message.edit_text(
            f"{title}<br/><br/><i>Ushbu bo'limda hozircha qabullar mavjud emas.</i>",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total)
    current_page_apps = filtered_apps[start_idx:end_idx]

    lawyers = {l.user_id: l.full_name for l in db_session.exec(select(OfficialLawyer)).all()}
    users = {u.user_id: u for u in db_session.exec(select(User)).all()}

    text_lines = [f"{title} (Jami: {total} ta, Sahifa: {page}/{total_pages}):<br/>"]
    builder = InlineKeyboardBuilder()

    status_icons = {
        AppointmentStatus.pending: "⏳ Kutilmoqda",
        AppointmentStatus.accepted: "🔵 Biriktirilgan",
        AppointmentStatus.completed: "✅ Yakunlangan",
        AppointmentStatus.cancelled: "❌ Bekor qilingan"
    }

    for a in current_page_apps:
        c_user = users.get(a.user_id)
        c_name = f"{c_user.first_name} {c_user.last_name or ''}".strip() if c_user else f"User {a.user_id}"
        l_name = lawyers.get(a.lawyer_id, "Biriktirilmagan")
        time_str = a.scheduled_at.strftime('%d.%m %H:%M') if a.scheduled_at else "Vaqtsiz"
        st_text = status_icons.get(a.status, str(a.status))

        text_lines.append(
            f"<b>Ariza №{a.id}</b> | {st_text}<br/>"
            f"Vaqt: <b>{time_str}</b> | Fuqaro: {c_name}<br/>"
            f"Yurist: {l_name}<br/>"
        )

        builder.button(
            text=f"🔍 Ariza №{a.id} ({time_str})",
            callback_data=f"admin:crm_view:{a.id}:{filter_type}:{page}"
        )

    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:crm_list:{filter_type}:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin:noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:crm_list:{filter_type}:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ CRM bosh sahifasi", callback_data="admin:crm_appointments"))

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:crm_view:"), is_private_message)
async def admin_crm_view_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    app_id = int(parts[2])
    filter_type = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    app = db_session.get(Appointment, app_id)
    if not app:
        return await query.answer("Ariza topilmadi!", show_alert=True)

    card = render_appointment_card(app, db_session)

    extra_rows = []
    if app.media_file_id or app.media_meta:
        extra_rows.append([
            InlineKeyboardButton(text="📎 Biriktirilgan fayllarni ko'rish", callback_data=f"admin:crm_media:{app.id}")
        ])
    extra_rows.append([
        InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=f"admin:crm_list:{filter_type}:{page}")
    ])

    markup = get_appointment_markup(app, extra_rows=extra_rows)
    await query.message.edit_text(card, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:crm_media:"), is_private_message)
async def admin_crm_media_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    app = db_session.get(Appointment, app_id)
    if not app or (not app.media_file_id and not app.media_meta):
        return await query.answer("Fayl topilmadi!", show_alert=True)

    await query.answer("Fayllar yuklanmoqda...", show_alert=False)

    media_items = []
    if app.media_meta:
        try:
            media_items = json.loads(app.media_meta)
        except Exception:
            pass

    if not media_items and app.media_file_id:
        media_items = [{
            "type": app.media_type or "document",
            "file_id": app.media_file_id,
            "name": app.media_name or "Fayl"
        }]

    total_files = len(media_items)
    for idx, item in enumerate(media_items, 1):
        m_type = item.get("type")
        m_fid = item.get("file_id")
        m_name = item.get("name", "Fayl")
        caption = f"📎 Ariza №{app.id} ga ilova qilingan fayl ({idx}/{total_files}): {m_name}"

        try:
            if m_type == "document":
                await bot.send_document(chat_id=query.from_user.id, document=m_fid, caption=caption)
            elif m_type == "voice":
                await bot.send_voice(chat_id=query.from_user.id, voice=m_fid, caption=caption)
            elif m_type == "video":
                await bot.send_video(chat_id=query.from_user.id, video=m_fid, caption=caption)
            elif m_type == "photo":
                await bot.send_photo(chat_id=query.from_user.id, photo=m_fid, caption=caption)
            elif m_type == "video_note":
                await bot.send_video_note(chat_id=query.from_user.id, video_note=m_fid)
        except Exception as e:
            await query.message.answer(f"⚠️ Faylni ({m_name}) yuborishda xatolik: {e}")


# --- Link Setting by Admin ---

@admin_router.callback_query(F.data.startswith("admin:crm_set_link:"), is_private_message)
async def admin_crm_set_link_start(query: CallbackQuery, state: FSMContext):
    parts = query.data.split(":")
    app_id = int(parts[2])
    filter_type = parts[3]
    page = int(parts[4])

    await state.set_state(AdminCrmState.waiting_for_link)
    await state.update_data(crm_app_id=app_id, crm_filter=filter_type, crm_page=page)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")

    await query.message.edit_text(
        f"🔗 <b>Ariza №{app_id} uchun online suhbat havolasini kiriting:</b><br/><br/>"
        "<i>(Google Meet, Zoom yoki Telegram call havolasini yuboring. Masalan: https://meet.google.com/abc-defg)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminCrmState.waiting_for_link, is_private_message)
async def admin_crm_link_received(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    link = message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://") or link.startswith("t.me/")):
        return await message.answer("⚠️ Iltimos, haqiqiy URL havola yuboring (https:// bilan boshlanishi kerak):")

    data = await state.get_data()
    app_id = data.get("crm_app_id")
    filter_type = data.get("crm_filter", "all")
    page = data.get("crm_page", 1)

    app = db_session.get(Appointment, app_id)
    if app:
        app.meeting_link = link
        app.updated_at = datetime.now()
        db_session.add(app)
        db_session.commit()

        # Notify citizen
        try:
            citizen_msg = (
                f"🔗 <b>Online suhbat havolasi taqdim etildi! (Ariza №{app.id})</b><br/><br/>"
                f"Suhbat havolasi:<br/>👉 <a href=\"{link}\">{link}</a><br/><br/>"
                "Iltimos, belgilangan vaqtda ushbu havola orqali ulaning."
            )
            await bot.send_message(chat_id=app.user_id, text=citizen_msg, parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Arizaga qaytish", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")

    await message.answer(f"✅ Havola saqlandi va fuqaroga yetkazildi!\n🔗 {link}", reply_markup=builder.as_markup())


# --- Assign Lawyer by Admin ---

@admin_router.callback_query(F.data.startswith("admin:crm_assign:"), is_private_message)
async def admin_crm_assign_start(query: CallbackQuery, db_session: DBSession):
    parts = query.data.split(":")
    app_id = int(parts[2])
    filter_type = parts[3]
    page = int(parts[4])

    lawyers = OfficialLawyer.get_active_lawyers(db_session)
    builder = InlineKeyboardBuilder()

    for l in lawyers:
        spec = f" ({l.specialization})" if l.specialization else ""
        builder.button(
            text=f"👨‍⚖️ {l.full_name}{spec}",
            callback_data=f"admin:crm_do_assign:{app_id}:{l.user_id}:{filter_type}:{page}"
        )

    builder.button(text="⬅️ Ortga", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")
    builder.adjust(1)

    await query.message.edit_text(
        f"👨‍⚖️ <b>Ariza №{app_id} ga qaysi yuristni biriktirmoqchisiz?</b>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:crm_do_assign:"), is_private_message)
async def admin_crm_do_assign(query: CallbackQuery, db_session: DBSession, bot: Bot):
    parts = query.data.split(":")
    app_id = int(parts[2])
    lawyer_uid = int(parts[3])
    filter_type = parts[4]
    page = int(parts[5])

    app = db_session.get(Appointment, app_id)
    lawyer = OfficialLawyer.get_by_user_id(lawyer_uid, db_session)

    if app and lawyer:
        old_lawyer_id = app.lawyer_id
        is_reassign = old_lawyer_id is not None and old_lawyer_id != lawyer_uid
        app.lawyer_id = lawyer_uid
        if app.scheduled_at:
            app.status = AppointmentStatus.accepted
        else:
            app.status = AppointmentStatus.pending
        app.updated_at = datetime.now()
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        logger.info(
            "admin_crm_assigned_lawyer",
            extra={
                "admin_id": query.from_user.id,
                "appointment_id": app.id,
                "old_lawyer_id": old_lawyer_id,
                "new_lawyer_id": lawyer_uid,
            }
        )

        # Notify citizen
        kind = "lawyer_changed" if is_reassign else "lawyer_assigned"
        await notify_citizen_appointment_update(bot, app, db_session, kind=kind)

        # Update card in lawyer group if exists
        if app.group_message_id and settings.LAWYER_APPOINTMENT_GROUP_ID:
            try:
                card_text = render_appointment_card(app, db_session)
                markup = get_appointment_markup(app)
                await bot.edit_message_caption(
                    chat_id=settings.LAWYER_APPOINTMENT_GROUP_ID,
                    message_id=app.group_message_id,
                    caption=card_text,
                    reply_markup=markup,
                    parse_mode=SULGUK_PARSE_MODE,
                )
            except Exception:
                try:
                    await bot.edit_message_text(
                        chat_id=settings.LAWYER_APPOINTMENT_GROUP_ID,
                        message_id=app.group_message_id,
                        text=card_text,
                        reply_markup=markup,
                        parse_mode=SULGUK_PARSE_MODE,
                    )
                except Exception:
                    pass

        # Notify lawyer
        try:
            await bot.send_message(
                chat_id=lawyer_uid,
                text=f"🔔 <b>Sizga yangi qabul arizasi biriktirildi (Ariza №{app.id}):</b><br/>Vaqti: {app.scheduled_at or 'Belgilanmagan'}",
                parse_mode=SULGUK_PARSE_MODE
            )
        except Exception:
            pass

        await query.answer(f"Ariza {lawyer.full_name} ga muvaffaqiyatli biriktirildi!", show_alert=True)

    # Redirect back to view
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Arizani ko'rish", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")
    await query.message.edit_text(f"✅ <b>Ariza №{app_id}</b> yurist <b>{lawyer.full_name}</b> ga biriktirildi.", reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


# --- Cancel Appointment by Admin ---

@admin_router.callback_query(F.data.startswith("admin:crm_cancel:"), is_private_message)
async def admin_crm_cancel_start(query: CallbackQuery, state: FSMContext):
    parts = query.data.split(":")
    app_id = int(parts[2])
    filter_type = parts[3]
    page = int(parts[4])

    await state.set_state(AdminCrmState.waiting_for_cancel_reason)
    await state.update_data(crm_cancel_id=app_id, crm_filter=filter_type, crm_page=page)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Ortga", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")

    await query.message.edit_text(
        f"❌ <b>Ariza №{app_id} ni bekor qilish sababini kiriting:</b><br/>"
        "<i>(Ushbu sabab fuqaroga bildirishnoma sifatida yuboriladi)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminCrmState.waiting_for_cancel_reason, is_private_message)
async def admin_crm_cancel_reason_received(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    reason = message.text.strip()
    data = await state.get_data()
    app_id = data.get("crm_cancel_id")
    filter_type = data.get("crm_filter", "all")
    page = data.get("crm_page", 1)

    app = db_session.get(Appointment, app_id)
    if app:
        old_status = app.status
        app.status = AppointmentStatus.cancelled
        app.cancellation_reason = reason
        app.updated_at = datetime.now()
        db_session.add(app)
        db_session.commit()
        db_session.refresh(app)

        logger.info(
            "admin_crm_cancelled_appointment",
            extra={
                "admin_id": message.from_user.id,
                "appointment_id": app.id,
                "old_status": old_status,
                "reason": reason,
            }
        )

        # Notify citizen
        await notify_citizen_appointment_update(bot, app, db_session, kind="cancelled")

        # Update card in lawyer group if exists
        if app.group_message_id and settings.LAWYER_APPOINTMENT_GROUP_ID:
            try:
                card_text = render_appointment_card(app, db_session)
                markup = get_appointment_markup(app)
                await bot.edit_message_caption(
                    chat_id=settings.LAWYER_APPOINTMENT_GROUP_ID,
                    message_id=app.group_message_id,
                    caption=card_text,
                    reply_markup=markup,
                    parse_mode=SULGUK_PARSE_MODE,
                )
            except Exception:
                try:
                    await bot.edit_message_text(
                        chat_id=settings.LAWYER_APPOINTMENT_GROUP_ID,
                        message_id=app.group_message_id,
                        text=card_text,
                        reply_markup=markup,
                        parse_mode=SULGUK_PARSE_MODE,
                    )
                except Exception:
                    pass

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Arizaga qaytish", callback_data=f"admin:crm_view:{app_id}:{filter_type}:{page}")
    await message.answer(f"✅ Ariza №{app_id} bekor qilindi va fuqaroga sababi yuborildi.", reply_markup=builder.as_markup())


# =====================================================================
# --- Ommaviy Xabar (Broadcast) Boshqaruvi ---
# =====================================================================
