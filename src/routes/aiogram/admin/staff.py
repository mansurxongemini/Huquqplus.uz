"""Mutaxassislar statistikasi, volontyorlar ro'yxati, profili va sohalari."""
import logging
from datetime import datetime
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.app.keyboards import normalize_section_name, section_names_uz
from src.app.review_quality import format_quality_block, review_quality
from src.app.translations import t
from src.models.assignment import VolunteerSection
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.appointment import Appointment, AppointmentStatus
from src.models.volunteer import Volunteer
from src.models.user import User
from src.routes.deps.db_session import DBSession
from src.app.volunteer_analytics import calculate_volunteer_stats, get_month_date_range, get_top_volunteers_with_ties, dispatch_weekly_volunteer_digest
from src.app.link_utils import build_group_message_link
from src.app.split_message import truncate_string

from src.routes.aiogram.admin.common import admin_router


@admin_router.callback_query(F.data == "admin:staff_stats", is_private_message)
async def admin_staff_stats_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    all_inquiries = db_session.exec(select(Inquiry)).all()
    total_inquiries = len(all_inquiries)
    answered_inquiries = [i for i in all_inquiries if i.status in [InquiryStatus.replied, InquiryStatus.closed]]
    total_answered = len(answered_inquiries)

    rated_inquiries = [i for i in all_inquiries if i.rating is not None]
    total_rated_inq = len(rated_inquiries)
    avg_inq_rating = (sum(i.rating for i in rated_inquiries) / total_rated_inq) if total_rated_inq > 0 else 0.0
    pos_inq = sum(1 for i in rated_inquiries if i.rating >= 4)
    neg_inq = sum(1 for i in rated_inquiries if i.rating <= 2)

    all_appointments = db_session.exec(select(Appointment)).all()
    total_appointments = len(all_appointments)
    completed_appointments = [a for a in all_appointments if a.status == AppointmentStatus.completed]
    total_completed = len(completed_appointments)

    rated_appointments = [a for a in all_appointments if a.rating is not None]
    total_rated_app = len(rated_appointments)
    avg_app_rating = (sum(a.rating for a in rated_appointments) / total_rated_app) if total_rated_app > 0 else 0.0

    # Group specialists and compute KPI using volunteer analytics
    all_specs_stats = calculate_volunteer_stats(date_range=None)
    top_specs = all_specs_stats[:3]
    top_specs_lines = []
    if top_specs:
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
        for idx, s in enumerate(top_specs, 1):
            r_str = f"⭐ {s['avg_rating']}" if s['avg_rating'] > 0 else "baho yo'q"
            top_specs_lines.append(f"{rank_emojis.get(idx, '🎖')} <b>{s['name']}</b> ({s['role']}): 🎯 {s['kpi_score']} ball | {s['inquiries_count']} ta javob ({r_str}, ⚡️ {s['avg_response_str']})")
        top_specs_text = "<br/>".join(top_specs_lines)
    else:
        top_specs_text = "<i>Hozircha javoblar mavjud emas</i>"

    stats_html = f"""
<b>📊 Mutaxassislar (Volontyor va Yuristlar) faoliyati statistikasi</b><br/><br/>
<b>📩 Murojaatlar:</b><br/>
Jami murojaatlar: <b>{total_inquiries}</b> ta<br/>
Javob berilgan: <b>{total_answered}</b> ta<br/>
Fuqarolar baholagan: <b>{total_rated_inq}</b> ta<br/>
O'rtacha baho: <b>⭐ {avg_inq_rating:.2f} / 5.0</b><br/>
Ijobiy baholar (4-5 ⭐): <b>{pos_inq}</b> ta<br/>
Qoniqarsiz baholar (1-2 ⭐): <b>{neg_inq}</b> ta<br/><br/>
<b>✍️ Yurist qabullari:</b><br/>
Jami arizalar: <b>{total_appointments}</b> ta<br/>
O'tkazilgan va yakunlangan: <b>{total_completed}</b> ta<br/>
Baholangan suhbatlar: <b>{total_rated_app}</b> ta<br/>
Suhbatlarning o'rtacha bahosi: <b>⭐ {avg_app_rating:.2f} / 5.0</b><br/><br/>
<b>🏆 Eng yuqori KPI to'plagan mutaxassislar (Top 3):</b><br/>
{top_specs_text}
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Joriy oy Leaderboard", callback_data="admin:vol_leaderboard:month")
    builder.button(text="🌟 Barcha davr Leaderboard", callback_data="admin:vol_leaderboard:all")
    builder.button(text="📨 Haftalik hisobotni volontyorlarga yuborish", callback_data="admin:send_weekly_rankings_confirm")
    builder.button(text="🔗 Volontyorlik taklif havolasi", callback_data="admin:vol_invite_link")
    builder.button(text="👥 Volontyorlar ro'yxati", callback_data="admin:vol_list")
    builder.button(text="📊 Tahliliy hisobotni yuklab olish (.xlsx)", callback_data="admin:report_menu")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text(stats_html, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:vol_leaderboard:"), is_private_message)
async def admin_vol_leaderboard_callback(query: CallbackQuery):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    mode = query.data.split(":")[2]  # 'month' or 'all'
    now = datetime.now()

    if mode == "month":
        start_date, _ = get_month_date_range(now)
        date_range = (start_date, now)
        title = f"🏆 <b>Joriy oy Leaderboard ({now.strftime('%m.%Y')})</b>"
    else:
        date_range = None
        title = "🌟 <b>Barcha davr uchun Volontyorlar Leaderboard</b>"

    stats = calculate_volunteer_stats(date_range=date_range, volunteers_only=True)
    active = [s for s in stats if s["inquiries_count"] > 0]
    top10 = get_top_volunteers_with_ties(active, top_limit=10)

    if not top10:
        body = "<i>Tanlangan davrda volontyorlar faoliyati hali qayd etilmagan.</i>"
    else:
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🎖", 5: "🎖", 6: "🎖", 7: "🎖", 8: "🎖", 9: "🎖", 10: "🎖"}
        lines = []
        for v in top10:
            rank = v.get("rank", 1)
            emoji = rank_emojis.get(rank, "🎖")
            rating_str = f"⭐ {v['avg_rating']}" if v['avg_rating'] > 0 else "baho yo'q"
            lines.append(
                f"{emoji} <b>{rank}-o'rin: {v['name']}</b> (<code>{v['user_id']}</code>)<br/>"
                f"🎯 KPI Ball: <b>{v['kpi_score']}</b> | 📩 Javoblar: <b>{v['inquiries_count']}</b> ta<br/>"
                f"⭐️ Baho: <b>{rating_str}</b> | ⚡️ Tezlik: <b>{v['avg_response_str']}</b><br/>"
            )
        body = "<br/>".join(lines)

    text = f"{title}<br/>━━━━━━━━━━━━━━━━━━━━━<br/>{body}"

    builder = InlineKeyboardBuilder()
    if mode == "month":
        builder.button(text="🌟 Barcha davr bo'yicha", callback_data="admin:vol_leaderboard:all")
    else:
        builder.button(text="🏆 Joriy oy bo'yicha", callback_data="admin:vol_leaderboard:month")
    builder.button(text="📨 Haftalik hisobotni volontyorlarga yuborish", callback_data="admin:send_weekly_rankings_confirm")
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data == "admin:send_weekly_rankings_confirm", is_private_message)
async def admin_send_weekly_rankings_confirm_callback(query: CallbackQuery):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    confirm_text = """
<b>📨 Haftalik shaxsiy hisobotni volontyorlarga yuborish</b><br/><br/>
Siz haqiqatdan ham joriy hafta (dushanbadan bugungacha) yakunlari va KPI o'zgarishlari bo'yicha barcha faol volontyorlarga shaxsiy hisobot xabarini yubormoqchimisiz?<br/><br/>
ℹ️ <i>Har bir volontyorga o'zining javob bergan murojaatlari soni, o'tgan haftaga nisbatan KPI ballining o'sishi yoki kamayishi hamda shaxsiy ko'rsatkichlari shaxsiydan (DM) yuboriladi.</i>
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, barchaga yuborilsin", callback_data="admin:send_weekly_rankings_execute")
    builder.button(text="❌ Bekor qilish", callback_data="admin:staff_stats")
    builder.adjust(1)
    await query.message.edit_text(confirm_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data == "admin:send_weekly_rankings_execute", is_private_message)
async def admin_send_weekly_rankings_execute_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await query.answer("Yuborish jarayoni boshlandi...", show_alert=False)
    await query.message.edit_text("⏳ <i>Haftalik shaxsiy hisobotlar volontyorlarga yuborilmoqda, iltimos kuting...</i>", parse_mode=SULGUK_PARSE_MODE)

    sent_count, failed_count = await dispatch_weekly_volunteer_digest(bot, db_session, is_manual=True)

    result_text = f"""
<b>✅ Haftalik shaxsiy hisobotlar muvaffaqiyatli yuborildi!</b><br/><br/>
• Muvaffaqiyatli yuborildi: <b>{sent_count}</b> nafar volontyorga<br/>
• Yetib bormadi (bloklagan / xatolik): <b>{failed_count}</b> ta<br/><br/>
<i>Barcha faol volontyorlar o'zlarining shaxsiy ko'rsatkichlari va KPI dinamikasidan xabardor qilindi.</i>
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    builder.adjust(1)
    await query.message.edit_text(result_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)

@admin_router.callback_query(F.data == "admin:vol_invite_link", is_private_message)
async def admin_vol_invite_link_callback(query: CallbackQuery, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    bot_info = await bot.get_me()
    bot_user = bot_info.username or settings.BOT_NAME.replace("@", "")
    invite_url = f"https://t.me/{bot_user}?start=volunteer"

    text = f"""
🔗 <b>Volontyorlarni ro'yxatdan o'tkazish havolasi:</b><br/>
<code>{invite_url}</code><br/>
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


VOL_PAGE_SIZE = 6
INQ_PAGE_SIZE = 5

@admin_router.callback_query(F.data.startswith("admin:vol_list"), is_private_message)
async def admin_vol_list_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    # Barcha volontyorlar statistikasini KPI bo'yicha saralangan holda olamiz
    vol_stats = calculate_volunteer_stats(date_range=None, volunteers_only=True)
    all_volunteers = db_session.exec(select(Volunteer)).all()
    vol_obj_map = {v.user_id: v for v in all_volunteers}

    # Agar hali savolga javob bermagan volontyorlar bo'lsa, ularni ham ro'yxat oxiriga qo'shamiz
    stats_user_ids = {s["user_id"] for s in vol_stats}
    for v in all_volunteers:
        if v.user_id not in stats_user_ids:
            vol_stats.append({
                "user_id": v.user_id,
                "name": v.full_name,
                "role": "Volontyor",
                "phone": v.phone_number,
                "study_work": v.study_or_work,
                "birth_year": v.birth_year,
                "inquiries_count": 0,
                "ratings": [],
                "five_star_count": 0,
                "four_star_count": 0,
                "negative_count": 0,
                "response_times_minutes": [],
                "fast_responses_count": 0,
                "avg_rating": 0.0,
                "avg_response_minutes": 0.0,
                "avg_response_str": "Mavjud emas",
                "kpi_score": 0,
                "rank": len(vol_stats) + 1
            })

    total_count = len(vol_stats)
    if total_count == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Taklif havolasini olish", callback_data="admin:vol_invite_link")
        builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
        builder.adjust(1)
        return await query.message.edit_text(
            "<i>Hozircha tizimda birorta ham rasmiy volontyor ro'yxatdan o'tmagan.</i>",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    total_pages = (total_count + VOL_PAGE_SIZE - 1) // VOL_PAGE_SIZE
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * VOL_PAGE_SIZE
    page_items = vol_stats[start_idx:start_idx + VOL_PAGE_SIZE]

    lines = []
    builder = InlineKeyboardBuilder()

    rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    for idx_in_list, s in enumerate(page_items, start=start_idx + 1):
        v_obj = vol_obj_map.get(s["user_id"])
        vol_id = v_obj.id if v_obj else 0
        is_active = v_obj.is_active if v_obj else True
        status_icon = "🟢" if is_active else "🔴"
        medal = rank_emojis.get(s.get("rank", idx_in_list), f"{s.get('rank', idx_in_list)}.")
        r_str = f"⭐ {s['avg_rating']}" if s['avg_rating'] > 0 else "baho yo'q"

        lines.append(
            f"{medal} {status_icon} <b>{s['name']}</b><br/>"
            f"   🎯 KPI: <b>{s['kpi_score']} ball</b> | 📩 {s['inquiries_count']} ta javob ({r_str})"
        )
        btn_title = f"{medal} {s['name']} (🎯 {s['kpi_score']})"
        builder.button(text=btn_title, callback_data=f"admin:vol_view:{vol_id}:{page}")

    builder.adjust(1)

    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin:vol_list:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin:noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin:vol_list:{page + 1}"))
    builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔗 Taklif havolasini olish", callback_data="admin:vol_invite_link"))
    builder.row(InlineKeyboardButton(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats"))

    text = (
        f"👥 <b>Volontyor huquqshunoslar reytingi ({total_count} ta):</b><br/>"
        + "<br/><br/>".join(lines)
    )

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:vol_view:"), is_private_message)
async def admin_vol_view_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2])
    source_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Volontyor topilmadi!", show_alert=True)

    all_stats = calculate_volunteer_stats(date_range=None, volunteers_only=True)
    v_stat = next((s for s in all_stats if s["user_id"] == vol.user_id), None)
    if not v_stat:
        v_stat = {
            "inquiries_count": 0,
            "avg_rating": 0.0,
            "five_star_count": 0,
            "four_star_count": 0,
            "negative_count": 0,
            "fast_responses_count": 0,
            "avg_response_str": "Mavjud emas",
            "kpi_score": 0,
            "rank": "-"
        }

    feedbacks_inqs = db_session.exec(
        select(Inquiry).where(
            Inquiry.responder_id == vol.user_id,
            Inquiry.feedback != None
        )
    ).all()
    fb_total = len(feedbacks_inqs)

    status_str = "🟢 Faol" if vol.is_active else "🔴 Faoliyati to'xtatilgan"
    reg_date = vol.created_at.strftime('%d.%m.%Y') if vol.created_at else "Noma'lum"

    text = f"""
👤 <b>Volontyor: {vol.full_name}</b> ({status_str})<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
🆔 <b>Telegram ID:</b> <code>{vol.user_id}</code><br/>
📱 <b>Telefon:</b> {vol.phone_number}<br/>
🎓 <b>O'qish / Ish joyi:</b> {vol.study_or_work}<br/>
📅 <b>Tug'ilgan yili:</b> {vol.birth_year}<br/>
🗓 <b>A'zo bo'lgan sana:</b> {reg_date}<br/><br/>
📊 <b>Faoliyat ko'rsatkichlari (KPI):</b><br/>
🎯 <b>Umumiy KPI bali:</b> {v_stat['kpi_score']} ball (🏆 Reyting: {v_stat['rank']}-o'rin)<br/>
📩 <b>Jami javob bergan murojaatlari:</b> {v_stat['inquiries_count']} ta<br/>
⭐ <b>O'rtacha bahosi:</b> {v_stat['avg_rating']} / 5.0<br/>
🌟 5 yulduzli baholar: <b>{v_stat['five_star_count']}</b> ta<br/>
👍 4 yulduzli baholar: <b>{v_stat['four_star_count']}</b> ta<br/>
⚠️ Qoniqarsiz baholar (1-2 ⭐): <b>{v_stat['negative_count']}</b> ta<br/>
⚡️ Tezkor javoblar (&lt; 1 soat): <b>{v_stat['fast_responses_count']}</b> ta<br/>
⏱ O'rtacha javob vaqti: <b>{v_stat['avg_response_str']}</b><br/>
💬 Fuqarolar qoldirgan izohlar: <b>{fb_total}</b> ta<br/><br/>
{format_quality_block(review_quality(db_session, vol.user_id))}
"""

    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗂 Volontyor sohalari",
        callback_data=f"admin:vol_secs:{vol.id}:{source_page}"
    )
    builder.button(
        text=f"📋 Barcha javoblari ({v_stat['inquiries_count']})",
        callback_data=f"admin:vol_inqs:{vol.id}:1:{source_page}"
    )
    builder.button(
        text=f"💬 Fuqarolar izohlari ({fb_total})",
        callback_data=f"admin:vol_fbs:{vol.id}:1:{source_page}"
    )
    toggle_text = "🛑 Faoliyatini to'xtatish" if vol.is_active else "✅ Faoliyatini tiklash"
    builder.button(
        text=toggle_text,
        callback_data=f"admin:vol_toggle:{vol.id}:{source_page}"
    )
    builder.button(
        text="⬅️ Volontyorlar ro'yxatiga qaytish",
        callback_data=f"admin:vol_list:{source_page}"
    )
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:vol_secs:"), is_private_message)
async def admin_vol_sections_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2])
    source_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Volontyor topilmadi!", show_alert=True)

    member = {normalize_section_name(s.section_name) for s in VolunteerSection.get_user_sections(vol.user_id, db_session)}

    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(section_names_uz):
        mark = "✅" if name in member else "⬜"
        builder.button(text=f"{mark} {name}", callback_data=f"admin:vol_sec_tg:{vol.id}:{idx}:{source_page}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Profilga qaytish", callback_data=f"admin:vol_view:{vol.id}:{source_page}"))

    await query.message.edit_text(
        t("vol_sections_title", "uz", name=vol.full_name),
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:vol_sec_tg:"), is_private_message)
async def admin_vol_section_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2])
    sec_idx = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else -1
    source_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if not vol or sec_idx < 0 or sec_idx >= len(section_names_uz):
        return await query.answer("Volontyor topilmadi!", show_alert=True)

    section = normalize_section_name(section_names_uz[sec_idx])
    existing = db_session.exec(
        select(VolunteerSection).where(
            VolunteerSection.volunteer_user_id == vol.user_id,
            VolunteerSection.section_name == section,
        )
    ).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
        await query.answer(f"❌ {section} dan olindi", show_alert=False)
    else:
        db_session.add(VolunteerSection(volunteer_user_id=vol.user_id, section_name=section, added_by=query.from_user.id))
        db_session.commit()
        await query.answer(f"✅ {section} ga qo'shildi", show_alert=False)

    query.data = f"admin:vol_secs:{vol_id}:{source_page}"
    await admin_vol_sections_callback(query, db_session)

@admin_router.callback_query(F.data.startswith("admin:vol_toggle:"), is_private_message)
async def admin_vol_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2]) if len(parts) == 3 else int(parts[2])
    source_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if vol:
        vol.is_active = not vol.is_active
        db_session.add(vol)
        db_session.commit()
        msg = "Volontyor faollashtirildi." if vol.is_active else "Volontyor faoliyati to'xtatildi."
        await query.answer(msg, show_alert=False)

    query.data = f"admin:vol_view:{vol_id}:{source_page}"
    await admin_vol_view_callback(query, db_session)

@admin_router.callback_query(F.data.startswith("admin:vol_inqs:"), is_private_message)
async def admin_vol_inquiries_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2])
    inq_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
    source_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Volontyor topilmadi!", show_alert=True)

    inquiries = db_session.exec(
        select(Inquiry).where(Inquiry.responder_id == vol.user_id).order_by(Inquiry.created_at.desc())
    ).all()

    total_inqs = len(inquiries)
    if total_inqs == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Profilga qaytish", callback_data=f"admin:vol_view:{vol.id}:{source_page}")
        return await query.message.edit_text(
            f"<b>{vol.full_name}</b> hali birorta ham murojaatga javob bermagan.",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    total_pages = (total_inqs + INQ_PAGE_SIZE - 1) // INQ_PAGE_SIZE
    inq_page = max(1, min(inq_page, total_pages))
    start_idx = (inq_page - 1) * INQ_PAGE_SIZE
    page_inqs = inquiries[start_idx:start_idx + INQ_PAGE_SIZE]

    lines = []
    builder = InlineKeyboardBuilder()

    for idx, inq in enumerate(page_inqs, start=start_idx + 1):
        r_str = f"{inq.rating} ⭐" if inq.rating else "baholanmagan"
        snippet = truncate_string(inq.question or "Savol", 60)
        lines.append(f"<b>{idx}. Ariza №{inq.id}</b> ({inq.section_name})<br/>Baho: <b>{r_str}</b><br/>Savol: <i>{snippet}</i>")
        builder.button(
            text=f"№{inq.id} | {snippet[:25]}...",
            callback_data=f"admin:inq_view:{inq.id}:inqs:{vol_id}:{inq_page}:{source_page}"
        )

    builder.adjust(1)

    nav = []
    if inq_page > 1:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin:vol_inqs:{vol_id}:{inq_page - 1}:{source_page}"))
    nav.append(InlineKeyboardButton(text=f"📄 {inq_page}/{total_pages}", callback_data="admin:noop"))
    if inq_page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin:vol_inqs:{vol_id}:{inq_page + 1}:{source_page}"))
    builder.row(*nav)

    builder.row(InlineKeyboardButton(text="⬅️ Volontyor profiliga qaytish", callback_data=f"admin:vol_view:{vol.id}:{source_page}"))

    text = (
        f"📋 <b>{vol.full_name} javob bergan murojaatlar ({total_inqs} ta):</b><br/>"
        + "<br/><br/>".join(lines)
    )

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:vol_fbs:"), is_private_message)
async def admin_vol_feedbacks_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    vol_id = int(parts[2])
    fb_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
    source_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Volontyor topilmadi!", show_alert=True)

    inquiries = db_session.exec(
        select(Inquiry).where(
            Inquiry.responder_id == vol.user_id,
            Inquiry.feedback != None
        ).order_by(Inquiry.rated_at.desc())
    ).all()

    total_fbs = len(inquiries)
    if total_fbs == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Profilga qaytish", callback_data=f"admin:vol_view:{vol.id}:{source_page}")
        return await query.message.edit_text(
            f"<b>{vol.full_name}</b> uchun hali fuqarolar tomonidan yozma izoh qoldirilmagan.",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    total_pages = (total_fbs + INQ_PAGE_SIZE - 1) // INQ_PAGE_SIZE
    fb_page = max(1, min(fb_page, total_pages))
    start_idx = (fb_page - 1) * INQ_PAGE_SIZE
    page_inqs = inquiries[start_idx:start_idx + INQ_PAGE_SIZE]

    lines = []
    builder = InlineKeyboardBuilder()

    for idx, inq in enumerate(page_inqs, start=start_idx + 1):
        stars = "⭐" * (inq.rating or 0)
        snippet_fb = truncate_string(inq.feedback or "", 70)
        lines.append(f"<b>{idx}. Ariza №{inq.id}</b> ({stars})<br/>💬 <i>«{snippet_fb}»</i>")
        builder.button(
            text=f"№{inq.id} | ⭐ {inq.rating} | «{snippet_fb[:20]}...»",
            callback_data=f"admin:inq_view:{inq.id}:fbs:{vol_id}:{fb_page}:{source_page}"
        )

    builder.adjust(1)

    nav = []
    if fb_page > 1:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin:vol_fbs:{vol_id}:{fb_page - 1}:{source_page}"))
    nav.append(InlineKeyboardButton(text=f"📄 {fb_page}/{total_pages}", callback_data="admin:noop"))
    if fb_page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin:vol_fbs:{vol_id}:{fb_page + 1}:{source_page}"))
    builder.row(*nav)

    builder.row(InlineKeyboardButton(text="⬅️ Volontyor profiliga qaytish", callback_data=f"admin:vol_view:{vol.id}:{source_page}"))

    text = (
        f"💬 <b>{vol.full_name} olgan fuqarolar izohlari ({total_fbs} ta):</b><br/>"
        "━━━━━━━━━━━━━━━━━━━━━<br/>"
        + "<br/><br/>".join(lines)
        + "<br/>━━━━━━━━━━━━━━━━━━━━━<br/>"
        "<i>To'liq tafsilotlarni o'qish uchun ariza tugmasini bosing:</i>"
    )

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:inq_view:"), is_private_message)
async def admin_inquiry_detail_view_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    # admin:inq_view:{inq.id}:{origin}:{vol_id}:{current_page}:{source_page}
    inq_id = int(parts[2])
    origin = parts[3]  # 'inqs' or 'fbs'
    vol_id = int(parts[4])
    current_page = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 1
    source_page = int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 1

    inquiry = db_session.get(Inquiry, inq_id)
    if not inquiry:
        return await query.answer("Murojaat topilmadi!", show_alert=True)

    vol = db_session.get(Volunteer, vol_id)
    citizen = User.get_by_user_id(inquiry.user_id, db_session) if inquiry.user_id else None
    citizen_name = f"{citizen.first_name or ''} {citizen.last_name or ''}".strip() if citizen else f"ID: {inquiry.user_id}"

    created_str = inquiry.created_at.strftime('%d.%m.%Y %H:%M') if inquiry.created_at else "Noma'lum"
    replied_str = inquiry.replied_at.strftime('%d.%m.%Y %H:%M') if inquiry.replied_at else "Javob berilmagan"

    spent_str = "Mavjud emas"
    if inquiry.created_at and inquiry.replied_at:
        try:
            diff_sec = (inquiry.replied_at - inquiry.created_at).total_seconds()
            if diff_sec >= 0:
                mins = int(diff_sec // 60)
                if mins < 60:
                    spent_str = f"{mins} daqiqa"
                else:
                    spent_str = f"{mins // 60} soat {mins % 60} daqiqa"
        except Exception:
            pass

    if inquiry.rating:
        stars_str = f"{'⭐' * inquiry.rating} ({inquiry.rating} / 5)"
    else:
        stars_str = "Baholanmagan"

    feedback_text = inquiry.feedback if inquiry.feedback else "<i>Fuqaro yozma izoh qoldirmagan</i>"
    question_text = inquiry.question if inquiry.question else "<i>Matnsiz savol</i>"
    answer_text = inquiry.answer if inquiry.answer else "<i>Javob matni mavjud emas</i>"

    link = build_group_message_link(inquiry.group_id, inquiry.group_question_id)

    vol_name = vol.full_name if vol else "Noma'lum"

    card_text = f"""
📩 <b>Murojaat №{inquiry.id}</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
📂 <b>Yo'nalish:</b> {inquiry.section_name}<br/>
👤 <b>Fuqaro:</b> {citizen_name} (<code>{inquiry.user_id}</code>)<br/>
📅 <b>Savol vaqti:</b> {created_str}<br/><br/>
❓ <b>Fuqaroning savoli:</b><br/>
<blockquote>{question_text}</blockquote><br/>
👨‍⚖️ <b>Volontyor ({vol_name}) javobi:</b><br/>
<blockquote>{answer_text}</blockquote><br/>
⏱ <b>Javob berilgan vaqt:</b> {replied_str} (Ketgan vaqt: <b>{spent_str}</b>)<br/>
⭐ <b>Fuqaro bahosi:</b> {stars_str}<br/>
💬 <b>Fuqaro izohi:</b><br/>
<blockquote>{feedback_text}</blockquote>
"""

    builder = InlineKeyboardBuilder()
    if link:
        builder.row(InlineKeyboardButton(text="🔗 Guruhdagi asl xabarni ochish", url=link))

    back_callback = f"admin:vol_{origin}:{vol_id}:{current_page}:{source_page}"
    builder.row(InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=back_callback))

    await query.message.edit_text(card_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()
