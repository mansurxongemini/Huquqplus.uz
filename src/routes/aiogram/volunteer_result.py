import html
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.app.review_quality import format_quality_block, review_quality
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.volunteer_analytics import (
    calculate_volunteer_stats,
    get_week_date_range,
)
from src.config.settings import settings
from src.models.inquiry import Inquiry
from src.models.volunteer import Volunteer
from src.routes.deps.db_session import DBSession

volunteer_result_router = Router(name="volunteer_result")

FEEDBACKS_PER_PAGE = 5


def get_volunteer_result_view(vol: Volunteer, db_session: DBSession) -> tuple[str, InlineKeyboardMarkup]:
    """Generates the volunteer's personal performance card and action keyboard."""
    now = datetime.now()
    start_current, _ = get_week_date_range(now)

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
            "rank": "-",
        }

    # Rank prior to the current week
    prev_overall = calculate_volunteer_stats(date_range=(None, start_current), volunteers_only=True)
    prev_stat = next((s for s in prev_overall if s["user_id"] == vol.user_id), None)

    current_rank = v_stat.get("rank", "-")
    prev_rank = prev_stat.get("rank", "-") if prev_stat else "-"
    total_vols = len(all_stats)

    if current_rank != "-" and prev_rank != "-":
        diff = prev_rank - current_rank
        if diff > 0:
            rank_change_str = f"📈 <b>{diff} pog‘ona yuqorilagan</b> (o‘tgan haftada {prev_rank}-o‘rinda edi)"
        elif diff < 0:
            rank_change_str = f"📉 <b>{abs(diff)} pog‘ona pasaygan</b> (o‘tgan haftada {prev_rank}-o‘rinda edi)"
        else:
            rank_change_str = f"➖ <b>O‘zgarmagan</b> (o‘tgan haftadagi kabi {current_rank}-o‘rinda)"
    elif current_rank != "-":
        rank_change_str = "🆕 <b>Yangi</b> (ushbu haftada ilk bor reytingga kirdi)"
    else:
        rank_change_str = "—"

    # Inquiries and feedbacks
    all_fbs = db_session.exec(
        select(Inquiry).where(
            Inquiry.responder_id == vol.user_id,
            Inquiry.rating != None
        ).order_by(Inquiry.rated_at.desc(), Inquiry.id.desc())
    ).all()
    written_fbs = [i for i in all_fbs if i.feedback and i.feedback.strip()]
    total_fbs = len(written_fbs)

    if written_fbs:
        comm_lines = ["<b>💬 Fuqarolar qoldirgan so‘nggi izohlar:</b>"]
        for idx, inq in enumerate(written_fbs[:3], start=1):
            stars = "⭐" * (inq.rating or 0)
            date_str = inq.rated_at.strftime("%d.%m.%Y") if inq.rated_at else ""
            d_str = f" ({date_str})" if date_str else ""
            fb_text = html.escape(inq.feedback.strip())
            if len(fb_text) > 100:
                fb_text = fb_text[:97] + "..."
            comm_lines.append(f"{idx}. {stars}{d_str}<br/><i>«{fb_text}»</i>")
        comments_block = "<br/>".join(comm_lines)
    else:
        comments_block = "<i>Hozircha fuqarolar tomonidan yozma izoh qoldirilmagan.</i>"

    safe_name = html.escape(vol.full_name)

    text = f"""
👤 <b>Volontyor: {safe_name}</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
🏆 <b>Barcha volontyorlar ichidagi o‘rningiz:</b> <b>{current_rank}-o‘rin</b> (jami {total_vols} ta volontyor ichida)<br/>
📊 <b>O‘tgan haftaga nisbatan:</b> {rank_change_str}<br/>
🎯 <b>Umumiy KPI ballingiz:</b> <b>{v_stat['kpi_score']}</b> ball<br/><br/>

⚡️ <b>O‘rtacha javob berish tezligi:</b> <b>{v_stat['avg_response_str']}</b><br/>
📩 <b>Jami javob berilgan murojaatlar:</b> <b>{v_stat['inquiries_count']}</b> ta<br/>
⭐️ <b>O‘rtacha baho:</b> <b>⭐ {v_stat['avg_rating']} / 5.0</b><br/>
• 🌟 5 yulduzli baholar: <b>{v_stat['five_star_count']}</b> ta<br/>
• 👍 4 yulduzli baholar: <b>{v_stat['four_star_count']}</b> ta<br/>
• ⚠️ 1-2 yulduzli baholar: <b>{v_stat['negative_count']}</b> ta<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
{format_quality_block(review_quality(db_session, vol.user_id))}<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
{comments_block}
"""

    builder = InlineKeyboardBuilder()
    if total_fbs > 0:
        builder.button(text=f"💬 Barcha izohlarni ko‘rish ({total_fbs} ta)", callback_data="vol_result:fbs:1")
    builder.button(text="🔄 Yangilash", callback_data="vol_result:refresh")
    builder.button(text="❌ Yopish", callback_data="vol_result:close")
    builder.adjust(1)

    return text.strip(), builder.as_markup()


def get_volunteer_feedbacks_page(vol: Volunteer, db_session: DBSession, page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    """Renders paginated citizen feedbacks for the volunteer."""
    inquiries = db_session.exec(
        select(Inquiry).where(
            Inquiry.responder_id == vol.user_id,
            Inquiry.feedback != None
        ).order_by(Inquiry.rated_at.desc(), Inquiry.id.desc())
    ).all()

    written_fbs = [i for i in inquiries if i.feedback and i.feedback.strip()]
    total_fbs = len(written_fbs)

    if total_fbs == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Natijalarimga qaytish", callback_data="vol_result:back")
        return "<i>Sizga fuqarolar tomonidan hali yozma izoh qoldirilmagan.</i>", builder.as_markup()

    total_pages = (total_fbs + FEEDBACKS_PER_PAGE - 1) // FEEDBACKS_PER_PAGE
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * FEEDBACKS_PER_PAGE
    page_items = written_fbs[start_idx:start_idx + FEEDBACKS_PER_PAGE]

    lines = []
    for idx, inq in enumerate(page_items, start=start_idx + 1):
        stars = "⭐" * (inq.rating or 0)
        date_str = inq.rated_at.strftime("%d.%m.%Y") if inq.rated_at else ""
        d_part = f" ({date_str})" if date_str else ""
        safe_fb = html.escape(inq.feedback.strip())
        lines.append(f"<b>{idx}. Ariza №{inq.id}</b> {stars}{d_part}<br/>💬 <i>«{safe_fb}»</i>")

    body = "<br/><br/>".join(lines)
    header = f"💬 <b>Sizning javoblaringizga fuqarolar qoldirgan izohlar ({total_fbs} ta):</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>"
    footer = "<br/>━━━━━━━━━━━━━━━━━━━━━"

    text = f"{header}{body}{footer}".strip()

    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"vol_result:fbs:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"vol_result:fbs:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Natijalarimga qaytish", callback_data="vol_result:back"))
    return text, builder.as_markup()


@volunteer_result_router.message(Command("myresult"), is_private_message)
async def myresult_command_handler(message: Message, db_session: DBSession):
    user_id = message.from_user.id
    vol = Volunteer.get_by_user_id(user_id, db_session)
    is_admin = settings.is_admin(user_id)

    # Volontyor yoki admin bo'lmagan foydalanuvchilar ushbu buyruqni yuborsa bot hech qanday javob bermasin!
    if not vol and not is_admin:
        return

    # Agar admin bo'lsa va volontyorlar ro'yxatida bo'lmasa:
    if is_admin and (not vol or not vol.is_active):
        all_stats = calculate_volunteer_stats(date_range=None, volunteers_only=True)
        active_count = len([s for s in all_stats if s["inquiries_count"] > 0])
        return await message.answer(
            f"👑 <b>Administrator paneli</b><br/><br/>"
            f"Siz administrator hisoblanasiz (sizda volontyorlik profili faol emas).<br/>"
            f"Jami ro‘yxatdan o‘tgan volontyorlar: <b>{len(all_stats)}</b> ta (faollari: <b>{active_count}</b> ta).<br/><br/>"
            f"Barcha mutaxassislar statistikasi va reytingini ko‘rish uchun: /admin",
            parse_mode=SULGUK_PARSE_MODE
        )

    if not vol.is_active:
        return

    text, reply_markup = get_volunteer_result_view(vol, db_session)
    await message.answer(text, reply_markup=reply_markup, parse_mode=SULGUK_PARSE_MODE)


@volunteer_result_router.callback_query(F.data.startswith("vol_result:fbs:"), is_private_message)
async def volunteer_feedbacks_page_callback(query: CallbackQuery, db_session: DBSession):
    user_id = query.from_user.id
    vol = Volunteer.get_by_user_id(user_id, db_session)
    is_admin = settings.is_admin(user_id)

    if not vol and not is_admin:
        return await query.answer()

    if not vol:
        return await query.answer("Volontyor profili topilmadi!", show_alert=True)

    page = int(query.data.split(":")[2])
    text, reply_markup = get_volunteer_feedbacks_page(vol, db_session, page=page)
    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@volunteer_result_router.callback_query(F.data == "vol_result:back", is_private_message)
async def volunteer_result_back_callback(query: CallbackQuery, db_session: DBSession):
    user_id = query.from_user.id
    vol = Volunteer.get_by_user_id(user_id, db_session)
    is_admin = settings.is_admin(user_id)

    if not vol and not is_admin:
        return await query.answer()

    if not vol:
        return await query.answer("Volontyor profili topilmadi!", show_alert=True)

    text, reply_markup = get_volunteer_result_view(vol, db_session)
    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@volunteer_result_router.callback_query(F.data == "vol_result:refresh", is_private_message)
async def volunteer_result_refresh_callback(query: CallbackQuery, db_session: DBSession):
    user_id = query.from_user.id
    vol = Volunteer.get_by_user_id(user_id, db_session)
    is_admin = settings.is_admin(user_id)

    if not vol and not is_admin:
        return await query.answer()

    if not vol:
        return await query.answer("Volontyor profili topilmadi!", show_alert=True)

    text, reply_markup = get_volunteer_result_view(vol, db_session)
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass
    await query.answer("Ko‘rsatkichlar yangilandi! 🔄")


@volunteer_result_router.callback_query(F.data == "vol_result:close", is_private_message)
async def volunteer_result_close_callback(query: CallbackQuery):
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()
