import os
import json
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select, Session
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.translations import t
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.broadcast import Broadcast, BroadcastStatus
from src.models.volunteer import Volunteer
from src.models.user import User
from src.routes.deps.db_session import DBSession
from src.app.generate_staff_report import generate_staff_kpi_report
from src.app.volunteer_analytics import calculate_volunteer_stats, get_month_date_range, get_top_volunteers_with_ties
from src.database.redisdb import get_redis
from src.database.mysql import engine

admin_router = Router(name="admin")

PAGE_SIZE = 5


class AdminBlockState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()


class AdminAddLawyerState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_name = State()
    waiting_for_details = State()


class AdminCrmState(StatesGroup):
    waiting_for_link = State()
    waiting_for_cancel_reason = State()


class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()


def get_admin_menu_keyboard(blocked_count: int = 0):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📢 Ommaviy xabar (Broadcast)",
        callback_data="admin:broadcast_menu"
    )
    builder.button(
        text="📅 Qabullar CRM va Taqvimi",
        callback_data="admin:crm_appointments"
    )
    builder.button(
        text="📊 Mutaxassislar statistikasi & KPI",
        callback_data="admin:staff_stats"
    )
    builder.button(
        text="👨‍⚖️ yurist boshqaruvi",
        callback_data="admin:lawyers_list"
    )
    builder.button(
        text=f"🚫 Bloklanganlar ro'yxati ({blocked_count})",
        callback_data="admin:blocked_page:1"
    )
    builder.button(
        text="➕ Foydalanuvchini bloklash (ID orqali)",
        callback_data="admin:block_start"
    )
    builder.adjust(1)
    return builder.as_markup()


def build_blocked_page(blocked_users: list[User], page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    total_users = len(blocked_users)
    if total_users == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
        return (
            "<b>🚫 Bloklangan foydalanuvchilar:</b><br/><br/>"
            "Hozirda bloklangan foydalanuvchilar mavjud emas.",
            builder.as_markup()
        )

    total_pages = (total_users + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_users)
    users_on_page = blocked_users[start_idx:end_idx]

    text_lines = [
        f"<b>🚫 Bloklangan foydalanuvchilar ro'yxati</b> (Jami: {total_users} ta, Sahifa: {page}/{total_pages}):<br/>"
    ]

    builder = InlineKeyboardBuilder()

    for idx, u in enumerate(users_on_page, start=start_idx + 1):
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or f"User {u.user_id}"
        uname = f"@{u.username}" if u.username else "mavjud emas"
        phone = u.phone or "noma'lum"
        blocked_time = u.blocked_at.strftime('%Y-%m-%d %H:%M') if u.blocked_at else "noma'lum"
        reason = u.block_reason or "ko'rsatilmadi"
        blocked_by = f"<code>{u.blocked_by}</code>" if u.blocked_by else "admin"

        text_lines.append(
            f"{idx}. <b>{name}</b><br/>"
            f"   ID: <code>{u.user_id}</code> | Username: {uname}<br/>"
            f"   Tel: {phone}<br/>"
            f"   Vaqti: {blocked_time}<br/>"
            f"   Sabab: <i>{reason}</i> (Admin: {blocked_by})<br/>"
        )

        builder.button(
            text=f"🔓 {name[:20]} - Blokdan chiqarish",
            callback_data=f"admin:unblock:{u.user_id}:{page}"
        )

    text_lines.append("<br/><i>Blokdan chiqarish uchun pastdagi tegishli tugmani bosing:</i>")

    # Pagination navigation buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:blocked_page:{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin:noop"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:blocked_page:{page + 1}"))

    builder.adjust(1)
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Admin menyu", callback_data="admin:main"))

    return "<br/>".join(text_lines), builder.as_markup()


async def execute_block_user(user_id: int, admin_id: int, reason: str | None, db_session: DBSession, bot: Bot) -> tuple[bool, str]:
    target_user = User.get_by_user_id(user_id, db_session)
    if not target_user:
        target_user = User(
            user_id=user_id,
            first_name="Foydalanuvchi",
            is_blocked=True
        )
        db_session.add(target_user)
        db_session.commit()
        db_session.refresh(target_user)

    target_user.block(blocked_by=admin_id, reason=reason, session=db_session)

    # 1. Clear FSM state
    try:
        storage_key = StorageKey(user_id=user_id, chat_id=user_id, bot_id=bot.id)
        user_state = FSMContext(telegram_storage, storage_key)
        await user_state.clear()
    except Exception as e:
        print("Failed to clear FSM on block:", e)

    # 2. Cancel active inquiries
    try:
        active_inquiries = db_session.exec(
            select(Inquiry).where(
                Inquiry.user_id == user_id,
                Inquiry.status.in_([InquiryStatus.active, InquiryStatus.replied])
            )
        ).all()
        for inq in active_inquiries:
            inq.status = InquiryStatus.cancelled
            inq.updated_at = datetime.now()
            db_session.add(inq)
        db_session.commit()
    except Exception as e:
        print("Failed to cancel inquiries on block:", e)

    # 3. Notify user
    user_lang = target_user.language or "uz"
    try:
        msg = t("user_blocked_notification", user_lang)
        if reason:
            reason_label = "<b>Sabab:</b>" if user_lang == "uz" else "<b>Причина:</b>"
            msg += f"<br/><br/>{reason_label} <i>{reason}</i>"
        await bot.send_message(chat_id=user_id, text=msg, parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass

    name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or str(user_id)
    return True, name


async def execute_unblock_user(user_id: int, db_session: DBSession, bot: Bot) -> tuple[bool, str]:
    target_user = User.get_by_user_id(user_id, db_session)
    if not target_user:
        return False, "Foydalanuvchi topilmadi"

    target_user.unblock(db_session)

    # Notify user
    user_lang = target_user.language or "uz"
    try:
        await bot.send_message(
            chat_id=user_id,
            text=t("user_unblocked_notification", user_lang),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception:
        pass

    name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or str(user_id)
    return True, name


# --------------------- HANDLERS ---------------------


@admin_router.message(Command("admin"), is_private_message)
async def admin_panel_start(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")

    await state.clear()
    blocked_users = User.get_blocked_users(db_session)
    count = len(blocked_users)

    await message.answer(
        "<b>👑 HuquqPlus Admin Panel</b><br/><br/>"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_menu_keyboard(count),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.callback_query(F.data == "admin:main", is_private_message)
async def admin_main_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    blocked_users = User.get_blocked_users(db_session)
    count = len(blocked_users)

    await query.message.edit_text(
        "<b>👑 HuquqPlus Admin Panel</b><br/><br/>"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_menu_keyboard(count),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:blocked_page:"), is_private_message)
async def admin_blocked_page_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    page = int(query.data.split(":")[2])
    blocked_users = User.get_blocked_users(db_session)

    text, markup = build_blocked_page(blocked_users, page=page)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data == "admin:blocked_list", is_private_message)
async def admin_blocked_list_redirect(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    blocked_users = User.get_blocked_users(db_session)
    text, markup = build_blocked_page(blocked_users, page=1)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data == "admin:noop")
async def admin_noop_callback(query: CallbackQuery):
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:unblock:"), is_private_message)
async def admin_unblock_user_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    user_id = int(parts[2])
    current_page = int(parts[3]) if len(parts) > 3 else 1

    success, name = await execute_unblock_user(user_id, db_session, bot)
    if success:
        await query.answer(f"✅ {name} muvaffaqiyatli blokdan chiqarildi!", show_alert=True)
    else:
        await query.answer(f"Xatolik: {name}", show_alert=True)

    # Refresh page
    blocked_users = User.get_blocked_users(db_session)
    text, markup = build_blocked_page(blocked_users, page=current_page)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)


# --- Interactive FSM Block flow ---


@admin_router.callback_query(F.data == "admin:block_start", is_private_message)
async def admin_block_start_callback(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminBlockState.waiting_for_user_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:main")

    await query.message.edit_text(
        "<b>🚫 Foydalanuvchini bloklash</b><br/><br/>"
        "Bloklamoqchi bo'lgan foydalanuvchining <b>Telegram ID</b> raqamini kiriting:<br/>"
        "<i>(Masalan: 123456789)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@admin_router.message(AdminBlockState.waiting_for_user_id, is_private_message)
async def admin_block_user_id_entered(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        return await message.answer(
            "⚠️ Noto'g'ri format. Iltimos, faqat raqamlardan iborat Telegram ID kiriting:\n(Bekor qilish uchun /admin yozing)"
        )

    target_user_id = int(text)
    if settings.is_admin(target_user_id):
        return await message.answer("⚠️ Admin hisobini bloklash mumkin emas!")

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminBlockState.waiting_for_reason)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:main")

    await message.answer(
        f"Foydalanuvchi ID: <code>{target_user_id}</code> qabul qilindi.<br/><br/>"
        "Iltimos, <b>bloklash sababini</b> kiriting:<br/>"
        "<i>(Agar sabab kiritmoqchi bo'lmasangiz, shunchaki <b>-</b> belgisini yuboring)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.message(AdminBlockState.waiting_for_reason, is_private_message)
async def admin_block_reason_entered(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        return await message.answer("Xatolik yuz berdi. Iltimos qaytadan /admin buyrug'ini bering.")

    reason = message.text.strip()
    if reason == "-":
        reason = None

    await state.clear()
    success, name = await execute_block_user(target_user_id, message.from_user.id, reason, db_session, bot)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")

    await message.answer(
        f"✅ <b>Foydalanuvchi muvaffaqiyatli bloklandi!</b><br/><br/>"
        f"Foydalanuvchi: <b>{name}</b><br/>"
        f"ID: <code>{target_user_id}</code><br/>"
        f"Sabab: <i>{reason or 'kiritilmadi'}</i><br/>"
        f"Bloklagan admin: <code>{message.from_user.id}</code>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


# --- Direct command handlers: /block and /unblock ---


@admin_router.message(Command("block"), is_private_message)
async def command_block_user(message: Message, db_session: DBSession, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")

    args = message.text.split(maxsplit=2)
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer(
            "<b>Format:</b> <code>/block &lt;user_id&gt; [sabab]</code><br/>"
            "<b>Misol:</b> <code>/block 123456789 Qoidabuzarlik va spam uchun</code>",
            parse_mode=SULGUK_PARSE_MODE
        )

    target_user_id = int(args[1])
    if settings.is_admin(target_user_id):
        return await message.answer("⚠️ Admin hisobini bloklash mumkin emas!")

    reason = args[2].strip() if len(args) > 2 else None

    success, name = await execute_block_user(target_user_id, message.from_user.id, reason, db_session, bot)

    await message.answer(
        f"🚫 <b>Foydalanuvchi bloklandi!</b><br/><br/>"
        f"Foydalanuvchi: <b>{name}</b><br/>"
        f"ID: <code>{target_user_id}</code><br/>"
        f"Sabab: <i>{reason or 'kiritilmadi'}</i>",
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.message(Command("unblock"), is_private_message)
async def command_unblock_user(message: Message, db_session: DBSession, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer(
            "<b>Format:</b> <code>/unblock &lt;user_id&gt;</code><br/>"
            "<b>Misol:</b> <code>/unblock 123456789</code>",
            parse_mode=SULGUK_PARSE_MODE
        )

    target_user_id = int(args[1])
    success, name = await execute_unblock_user(target_user_id, db_session, bot)

    if success:
        await message.answer(
            f"🔓 <b>Foydalanuvchi blokdan chiqarildi!</b><br/><br/>"
            f"Foydalanuvchi: <b>{name}</b><br/>"
            f"ID: <code>{target_user_id}</code>",
            parse_mode=SULGUK_PARSE_MODE
        )
    else:
        await message.answer(f"⚠️ {name} (ID: <code>{target_user_id}</code>)", parse_mode=SULGUK_PARSE_MODE)


# --- Mutaxassislar (Volontyor va Yuristlar) Statistikasi & Excel ---


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
<b>📩 Murojaatlar (Inquiries):</b><br/>
• Jami murojaatlar: <b>{total_inquiries}</b> ta<br/>
• Javob berilgan: <b>{total_answered}</b> ta<br/>
• Fuqarolar baholagan: <b>{total_rated_inq}</b> ta<br/>
• O'rtacha baho: <b>⭐ {avg_inq_rating:.2f} / 5.0</b><br/>
• Ijobiy baholar (4-5 ⭐): <b>{pos_inq}</b> ta<br/>
• Qoniqarsiz baholar (1-2 ⭐): <b>{neg_inq}</b> ta<br/><br/>
<b>✍️ Yurist qabullari (Appointments):</b><br/>
• Jami arizalar: <b>{total_appointments}</b> ta<br/>
• O'tkazilgan va yakunlangan: <b>{total_completed}</b> ta<br/>
• Baholangan suhbatlar: <b>{total_rated_app}</b> ta<br/>
• Suhbatlarning o'rtacha bahosi: <b>⭐ {avg_app_rating:.2f} / 5.0</b><br/><br/>
<b>🏆 Eng yuqori KPI to'plagan mutaxassislar (Top 3):</b><br/>
{top_specs_text}
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Joriy oy Leaderboard", callback_data="admin:vol_leaderboard:month")
    builder.button(text="🌟 Barcha davr Leaderboard", callback_data="admin:vol_leaderboard:all")
    builder.button(text="🔗 Volontyorlik taklif havolasi", callback_data="admin:vol_invite_link")
    builder.button(text="👥 Volontyorlar ro'yxati", callback_data="admin:vol_list")
    builder.button(text="📥 Excel hisobotni yuklab olish (.xlsx)", callback_data="admin:export_staff_excel")
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
                f"• 🎯 KPI Ball: <b>{v['kpi_score']}</b> | 📩 Javoblar: <b>{v['inquiries_count']}</b> ta<br/>"
                f"• ⭐️ Baho: <b>{rating_str}</b> | ⚡️ Tezlik: <b>{v['avg_response_str']}</b><br/>"
            )
        body = "<br/>".join(lines)

    text = f"{title}<br/>━━━━━━━━━━━━━━━━━━━━━<br/>{body}"

    builder = InlineKeyboardBuilder()
    if mode == "month":
        builder.button(text="🌟 Barcha davr bo'yicha", callback_data="admin:vol_leaderboard:all")
    else:
        builder.button(text="🏆 Joriy oy bo'yicha", callback_data="admin:vol_leaderboard:month")
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data == "admin:vol_invite_link", is_private_message)
async def admin_vol_invite_link_callback(query: CallbackQuery, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    bot_info = await bot.get_me()
    bot_user = bot_info.username or settings.BOT_NAME.replace("@", "")
    invite_url = f"https://t.me/{bot_user}?start=volunteer"

    text = f"""
🔗 <b>Volontyorlarni ro'yxatdan o'tkazish havolasi:</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
<code>{invite_url}</code><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
💡 <b>Ko'rsatma:</b><br/>
Ushbu umumiy taklif havolasini yangi volontyorlarga yuboring. Ular havola orqali botga kirib, quyidagi ma'lumotlarni to'ldiradilar:<br/>
1. Ism<br/>
2. Familiya<br/>
3. O'qish yoki ish joyi<br/>
4. Tug'ilgan yili<br/>
5. Telefon raqami<br/><br/>
Ro'yxatdan o'tgach, ular darhol faol volontyorga aylanadi va guruhda fuqarolarning savollariga bemalol javob bera oladi.
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data == "admin:vol_list", is_private_message)
async def admin_vol_list_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    volunteers = db_session.exec(select(Volunteer).order_by(Volunteer.created_at.desc())).all()
    if not volunteers:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Taklif havolasini olish", callback_data="admin:vol_invite_link")
        builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
        builder.adjust(1)
        return await query.message.edit_text(
            "<i>Hozircha tizimda birorta ham rasmiy volontyor ro'yxatdan o'tmagan.</i>",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    lines = []
    builder = InlineKeyboardBuilder()
    for idx, v in enumerate(volunteers[:15], start=1):
        status_icon = "🟢" if v.is_active else "🔴"
        reg_date = v.created_at.strftime('%d.%m.%Y') if v.created_at else ""
        lines.append(
            f"{idx}. {status_icon} <b>{v.full_name}</b> (<code>{v.user_id}</code>)<br/>"
            f"• 🎓 {v.study_or_work} | 📱 {v.phone_number}<br/>"
            f"• 📅 Tug'ilgan: {v.birth_year} | Ro'yxatdan o'tgan: {reg_date}<br/>"
        )
        toggle_text = f"🛑 Bloklash: {v.first_name}" if v.is_active else f"✅ Faollashtirish: {v.first_name}"
        builder.button(text=toggle_text, callback_data=f"admin:vol_toggle:{v.id}")

    builder.button(text="🔗 Taklif havolasini olish", callback_data="admin:vol_invite_link")
    builder.button(text="⬅️ Mutaxassislar statistikasi", callback_data="admin:staff_stats")
    builder.adjust(1)

    text = f"👥 <b>Ro'yxatdan o'tgan volontyorlar ({len(volunteers)} ta):</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>" + "<br/>".join(lines)
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:vol_toggle:"), is_private_message)
async def admin_vol_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    vol_id = int(query.data.split(":")[3])
    vol = db_session.get(Volunteer, vol_id)
    if vol:
        vol.is_active = not vol.is_active
        db_session.add(vol)
        db_session.commit()
        msg = "Volontyor faollashtirildi." if vol.is_active else "Volontyor faoliyati to'xtatildi."
        await query.answer(msg, show_alert=False)

    await admin_vol_list_callback(query, db_session)


@admin_router.callback_query(F.data == "admin:export_staff_excel", is_private_message)
async def admin_export_staff_excel_callback(query: CallbackQuery, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await query.answer("⏳ Excel hisobot tayyorlanmoqda, iltimos kuting...", show_alert=False)

    try:
        file_path = generate_staff_kpi_report()
        filename = f"HuquqPlus_Mutaxassislar_KPI_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        document = FSInputFile(path=file_path, filename=filename)

        caption = (
            "📊 <b>HuquqPlus — Mutaxassislar (Volontyor va Yuristlar) KPI hisoboti</b><br/><br/>"
            "Ushbu tahliliy Excel jadvalda:<br/>"
            "1-varaq: <b>Mutaxassislar KPI reytingi</b> (javoblar soni, 1-5 baholar taqsimoti, o'rtacha ball)<br/>"
            "2-varaq: <b>Murojaatlar tafsiloti</b> (har bir savol-javob, mutaxassis va fuqaro bahosi hamda fikri)<br/>"
            "3-varaq: <b>Yurist qabullari</b> (arizalar, suhbat o'tkazgan yurist va fuqaro bahosi)"
        )

        await bot.send_document(
            chat_id=query.from_user.id,
            document=document,
            caption=caption,
            parse_mode=SULGUK_PARSE_MODE
        )

        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print("Excel export error:", e)
        await query.message.answer(f"⚠️ Excel hisobot yaratishda xatolik yuz berdi: {e}")


# --- yuristlar Boshqaruvi ---


@admin_router.callback_query(F.data == "admin:lawyers_list", is_private_message)
async def admin_lawyers_list_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    lawyers = db_session.exec(select(OfficialLawyer)).all()
    builder = InlineKeyboardBuilder()

    text_lines = ["<b>👨‍⚖️ Yuristlar ro'yxati:</b><br/>"]
    if not lawyers:
        text_lines.append("<i>Hozirda ro'yxatdan o'tgan yuristlar mavjud emas.</i>")
    else:
        for idx, l in enumerate(lawyers, start=1):
            status = "🟢 Faol" if l.is_active else "🔴 Nofaol"
            phone_str = f" | Tel: {l.phone}" if l.phone else ""
            spec_str = f" ({l.specialization})" if l.specialization else ""
            text_lines.append(f"{idx}. <b>{l.full_name}</b>{spec_str} — {status}<br/>   ID: <code>{l.user_id}</code>{phone_str}")

            icon = "🟢" if l.is_active else "🔴"
            builder.button(
                text=f"{icon} {l.full_name[:20]}",
                callback_data=f"admin:lawyer_view:{l.id}"
            )

    builder.button(text="➕ Yangi yurist qo'shish", callback_data="admin:lawyer_add")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:lawyer_view:"), is_private_message)
async def admin_lawyer_view_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    status_str = "🟢 Faol" if lawyer.is_active else "🔴 Nofaol"
    toggle_btn_text = "🔴 Faolsizlantirish" if lawyer.is_active else "🟢 Faollashtirish"

    text = f"""
<b>👨‍⚖️ Yurist ma'lumotlari:</b><br/><br/>
• Ism-familiya: <b>{lawyer.full_name}</b><br/>
• Telegram ID: <code>{lawyer.user_id}</code><br/>
• Telefon: <b>{lawyer.phone or "kiritilmagan"}</b><br/>
• Soha/Mutaxassislik: <b>{lawyer.specialization or "kiritilmagan"}</b><br/>
• Holati: <b>{status_str}</b><br/>
• Qo'shilgan sana: <b>{lawyer.created_at.strftime('%Y-%m-%d %H:%M')}</b>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=toggle_btn_text, callback_data=f"admin:lawyer_toggle:{lawyer.id}")
    builder.button(text="🗑 O'chirish", callback_data=f"admin:lawyer_delete:{lawyer.id}")
    builder.button(text="⬅️ Yuristlar ro'yxatiga", callback_data="admin:lawyers_list")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:lawyer_toggle:"), is_private_message)
async def admin_lawyer_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    lawyer.is_active = not lawyer.is_active
    db_session.add(lawyer)
    db_session.commit()

    action_text = "faollashtirildi" if lawyer.is_active else "faolsizlantirildi"
    await query.answer(f"Yurist muvaffaqiyatli {action_text}!", show_alert=True)

    status_str = "🟢 Faol" if lawyer.is_active else "🔴 Nofaol"
    toggle_btn_text = "🔴 Faolsizlantirish" if lawyer.is_active else "🟢 Faollashtirish"

    text = f"""
<b>👨‍⚖️ Yurist ma'lumotlari:</b><br/><br/>
• Ism-familiya: <b>{lawyer.full_name}</b><br/>
• Telegram ID: <code>{lawyer.user_id}</code><br/>
• Telefon: <b>{lawyer.phone or "kiritilmagan"}</b><br/>
• Soha/Mutaxassislik: <b>{lawyer.specialization or "kiritilmagan"}</b><br/>
• Holati: <b>{status_str}</b><br/>
• Qo'shilgan sana: <b>{lawyer.created_at.strftime('%Y-%m-%d %H:%M')}</b>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=toggle_btn_text, callback_data=f"admin:lawyer_toggle:{lawyer.id}")
    builder.button(text="🗑 O'chirish", callback_data=f"admin:lawyer_delete:{lawyer.id}")
    builder.button(text="⬅️ Yuristlar ro'yxatiga", callback_data="admin:lawyers_list")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


@admin_router.callback_query(F.data.startswith("admin:lawyer_delete:"), is_private_message)
async def admin_lawyer_delete_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    db_session.delete(lawyer)
    db_session.commit()

    await query.answer("Yurist muvaffaqiyatli o'chirildi!", show_alert=True)

    lawyers = db_session.exec(select(OfficialLawyer)).all()
    builder = InlineKeyboardBuilder()

    text_lines = ["<b>👨‍⚖️ yuristlar ro'yxati:</b><br/>"]
    if not lawyers:
        text_lines.append("<i>Hozirda ro'yxatdan o'tgan yuristlar mavjud emas.</i>")
    else:
        for idx, l in enumerate(lawyers, start=1):
            status = "🟢 Faol" if l.is_active else "🔴 Nofaol"
            phone_str = f" | Tel: {l.phone}" if l.phone else ""
            spec_str = f" ({l.specialization})" if l.specialization else ""
            text_lines.append(f"{idx}. <b>{l.full_name}</b>{spec_str} — {status}<br/>   ID: <code>{l.user_id}</code>{phone_str}")
            icon = "🟢" if l.is_active else "🔴"
            builder.button(
                text=f"{icon} {l.full_name[:20]}",
                callback_data=f"admin:lawyer_view:{l.id}"
            )

    builder.button(text="➕ Yangi yurist qo'shish", callback_data="admin:lawyer_add")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


# --- Add Lawyer FSM Handlers ---


@admin_router.callback_query(F.data == "admin:lawyer_add", is_private_message)
async def admin_lawyer_add_start(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminAddLawyerState.waiting_for_user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await query.message.edit_text(
        "<b>➕ Yangi yurist qo'shish</b><br/><br/>"
        "Yuristning <b>Telegram ID</b> raqamini kiriting:<br/>"
        "<i>(Masalan: 123456789)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@admin_router.message(AdminAddLawyerState.waiting_for_user_id, is_private_message)
async def admin_lawyer_id_received(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        return await message.answer("⚠️ Iltimos, faqat raqamlardan iborat to'g'ri Telegram ID kiriting:")

    lawyer_uid = int(text)
    existing = OfficialLawyer.get_by_user_id(lawyer_uid, db_session)
    if existing:
        return await message.answer(f"⚠️ Bu foydalanuvchi ({existing.full_name}) allaqachon yuristlar ro'yxatida mavjud!")

    await state.update_data(lawyer_user_id=lawyer_uid)
    await state.set_state(AdminAddLawyerState.waiting_for_name)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await message.answer(
        f"Telegram ID: <code>{lawyer_uid}</code> qabul qilindi.<br/><br/>"
        "Endi yuristning <b>to'liq ism-familiyasini</b> kiriting:<br/>"
        "<i>(Masalan: Alisher Qodirov)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.message(AdminAddLawyerState.waiting_for_name, is_private_message)
async def admin_lawyer_name_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    name = message.text.strip()
    if len(name) < 3:
        return await message.answer("⚠️ Iltimos, ism-familiyani to'liqroq kiriting:")

    await state.update_data(lawyer_name=name)
    await state.set_state(AdminAddLawyerState.waiting_for_details)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await message.answer(
        f"Ism: <b>{name}</b> qabul qilindi.<br/><br/>"
        "Endi yuristning <b>sohasi/mutaxassisligi</b> yoki telefon raqamini kiriting:<br/>"
        "<i>(Agar kiritishni istamasangiz, shunchaki <b>-</b> belgisini yuboring)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.message(AdminAddLawyerState.waiting_for_details, is_private_message)
async def admin_lawyer_details_received(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    lawyer_uid = data.get("lawyer_user_id")
    lawyer_name = data.get("lawyer_name")

    details = message.text.strip()
    spec = None if details == "-" else details

    new_lawyer = OfficialLawyer(
        user_id=lawyer_uid,
        full_name=lawyer_name,
        specialization=spec,
        is_active=True
    )
    db_session.add(new_lawyer)
    db_session.commit()
    db_session.refresh(new_lawyer)

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍⚖️ Yuristlar ro'yxatiga qaytish", callback_data="admin:lawyers_list")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await message.answer(
        f"✅ <b>Yangi yurist muvaffaqiyatli qo'shildi!</b><br/><br/>"
        f"• Ism: <b>{new_lawyer.full_name}</b><br/>"
        f"• ID: <code>{new_lawyer.user_id}</code><br/>"
        f"• Soha: <b>{new_lawyer.specialization or 'kiritilmagan'}</b><br/>"
        f"• Holat: 🟢 Faol",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


# =====================================================================
# --- Yurist Qabullari CRM va Taqvimi ---
# =====================================================================


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
<b>📅 Qabullar CRM va Smart Taqvimi</b><br/><br/>
Hozirgi holat bo'yicha ko'rsatkichlar:<br/>
• <b>Bugungi qabullar:</b> {len(today_apps)} ta<br/>
• <b>Kutilayotgan rejalashtirilgan qabullar:</b> {len(upcoming_apps)} ta<br/>
• <b>Yurist biriktirilmagan arizalar:</b> {len(pending_apps)} ta<br/>
• <b>Jami qabullar tarixi:</b> {len(all_apps)} ta<br/><br/>
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
            f"• Vaqt: <b>{time_str}</b> | Fuqaro: {c_name}<br/>"
            f"• Yurist: {l_name}<br/>"
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

    c_user = User.get_by_user_id(app.user_id, db_session)
    c_name = f"{c_user.first_name} {c_user.last_name or ''}".strip() if c_user else f"ID: {app.user_id}"
    c_phone = c_user.phone if c_user else "Noma'lum"

    lawyer = OfficialLawyer.get_by_user_id(app.lawyer_id, db_session) if app.lawyer_id else None
    lawyer_name = lawyer.full_name if lawyer else "Hali biriktirilmagan"

    time_str = app.scheduled_at.strftime('%Y-%m-%d %H:%M') if app.scheduled_at else "Belgilanmagan"
    app_type_str = "Masofaviy (Online)" if app.appointment_type == "remote_appointment" else "Yuzma-yuz (Ofis)"

    media_info = "Yo'q (faqat matn)"
    if app.media_type and app.media_type != "text":
        media_info = f"{app.media_type.upper()} ({app.media_name or 'fayl'})"

    rating_str = f"{app.rating} ⭐" if app.rating else "Baholanmagan"

    card = f"""
<b>📋 Qabul arizasi tafsilotlari (№{app.id}):</b>
━━━━━━━━━━━━━━━━━━━━━
🏢 <b>Qabul shakli:</b> {app_type_str}
👤 <b>Fuqaro:</b> {c_name} (ID: <code>{app.user_id}</code>)
📞 <b>Telefon:</b> {c_phone}
👨‍⚖️ <b>Yurist:</b> {lawyer_name}
📅 <b>Belgilangan vaqt:</b> <b>{time_str}</b>
📊 <b>Holati:</b> <b>{app.status.upper()}</b>
📎 <b>Ilova:</b> {media_info}
🔗 <b>Uchrashuv havolasi:</b> {app.meeting_link or "Kiritilmagan"}
⭐ <b>Fuqaro bahosi:</b> {rating_str}
📝 <b>Muammo matni:</b>
<blockquote>{app.problem_description}</blockquote>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()

    if app.media_file_id:
        builder.button(text="📎 Biriktirilgan faylni ko'rish", callback_data=f"admin:crm_media:{app.id}")

    builder.button(text="🔗 Havola kiritish/yangilash", callback_data=f"admin:crm_set_link:{app.id}:{filter_type}:{page}")
    builder.button(text="👨‍⚖️ Yuristni biriktirish", callback_data=f"admin:crm_assign:{app.id}:{filter_type}:{page}")

    if app.status != AppointmentStatus.cancelled:
        builder.button(text="❌ Arizani bekor qilish", callback_data=f"admin:crm_cancel:{app.id}:{filter_type}:{page}")

    builder.button(text="⬅️ Ro'yxatga qaytish", callback_data=f"admin:crm_list:{filter_type}:{page}")
    builder.adjust(1)

    await query.message.edit_text(card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
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
        app.lawyer_id = lawyer_uid
        app.status = AppointmentStatus.accepted
        app.updated_at = datetime.now()
        db_session.add(app)
        db_session.commit()

        # Notify citizen
        try:
            await bot.send_message(
                chat_id=app.user_id,
                text=t("appointment_claimed_citizen", "uz", lawyer_name=lawyer.full_name),
                parse_mode=SULGUK_PARSE_MODE
            )
        except Exception:
            pass

        # Notify lawyer
        try:
            await bot.send_message(
                chat_id=lawyer_uid,
                text=f"🔔 <b>Sizga yangi qabul arizasi biriktirildi (Ariza №{app.id}):</b><br/>Vaqti: {app.scheduled_at}",
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
        app.status = AppointmentStatus.cancelled
        app.cancellation_reason = reason
        app.updated_at = datetime.now()
        db_session.add(app)
        db_session.commit()

        # Notify citizen
        try:
            await bot.send_message(
                chat_id=app.user_id,
                text=f"⚠️ <b>Hurmatli fuqaro!</b> Sizning yurist qabuliga arizangiz (№{app.id}) bekor qilindi.<br/><b>Sabab:</b> <i>{reason}</i>",
                parse_mode=SULGUK_PARSE_MODE
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


@admin_router.callback_query(F.data == "admin:broadcast_menu", is_private_message)
async def admin_broadcast_menu_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    running = Broadcast.get_running_broadcast(db_session)

    builder = InlineKeyboardBuilder()

    if running:
        builder.button(text="⚡️ Hozirgi jonli broadcast holati", callback_data=f"admin:broadcast:live:{running.id}")

    builder.button(text="➕ Yangi broadcast yaratish", callback_data="admin:broadcast:start")
    builder.button(text="📊 Broadcastlar tarixi", callback_data="admin:broadcast:history:1")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    running_text = ""
    if running:
        running_text = f"<br/>🔥 <b>DIQQAT: Ayni paytda Broadcast №{running.id} yuborilmoqda!</b><br/>"

    text = f"""
<b>📢 Ommaviy xabar (Broadcast) bo'limi</b><br/>{running_text}
Ushbu bo'lim orqali siz barcha yoki tanlangan toifadagi foydalanuvchilarga xabar (matn, rasm, video, audio, PDF) yuborishingiz mumkin.<br/><br/>
<i>Tezlik: ~25-28 xabar/soniya (Telegram limitlariga 100% mos va xavfsiz).</i>
"""
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data == "admin:broadcast:start", is_private_message)
async def admin_broadcast_start(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminBroadcastState.waiting_for_message)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    prompt = """
📢 <b>Ommaviy yuboriladigan xabarni yuboring:</b><br/><br/>
Siz quyidagi formatlarda yuborishingiz mumkin:<br/>
• Formatlangan oddiy matn<br/>
• Rasm (tagida matni bilan yoki alohida)<br/>
• Video yoki video-xabar<br/>
• Ovozli xabar<br/>
• PDF yoki Word hujjat<br/>
• Boshqa kanaldan forward qilingan post<br/><br/>
<i>(Xabar siz qanday yuborsangiz, barcha foydalanuvchilarga xuddi shunday yetkaziladi)</i>
"""
    await query.message.edit_text(prompt, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.message(AdminBroadcastState.waiting_for_message, is_private_message)
async def admin_broadcast_message_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    # Store message_id and chat_id
    await state.update_data(
        broadcast_from_chat_id=message.chat.id,
        broadcast_message_id=message.message_id
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Ha, havola tugmasi qo'shish", callback_data="admin:broadcast:add_btn:yes")
    builder.button(text="⏭ Yo'q, tugmasiz davom etish", callback_data="admin:broadcast:add_btn:no")
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    await message.answer(
        "✅ <b>Xabar qabul qilindi!</b><br/><br/>"
        "Ushbu xabar ostiga havola beruvchi <b>Inline tugma</b> (masalan: <i>Batafsil ma'lumot</i>) qo'shishni xohlaysizmi?",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.callback_query(F.data == "admin:broadcast:add_btn:yes", is_private_message)
async def admin_broadcast_add_btn_start(query: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcastState.waiting_for_button_text)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    await query.message.edit_text(
        "🔘 <b>Tugma ustida ko'rinadigan matnni kiriting:</b><br/>"
        "<i>(Masalan: 👉 Batafsil ma'lumot)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@admin_router.message(AdminBroadcastState.waiting_for_button_text, is_private_message)
async def admin_broadcast_btn_text_received(message: Message, state: FSMContext):
    btn_text = message.text.strip()
    await state.update_data(broadcast_btn_text=btn_text)
    await state.set_state(AdminBroadcastState.waiting_for_button_url)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    await message.answer(
        f"Tugma matni: <b>{btn_text}</b><br/><br/>"
        "Endi tugma bosilganda ochiladigan <b>URL manzilni</b> kiriting:<br/>"
        "<i>(Masalan: https://t.me/huquqplus yoki https://huquqplus.uz)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.message(AdminBroadcastState.waiting_for_button_url, is_private_message)
async def admin_broadcast_btn_url_received(message: Message, state: FSMContext, db_session: DBSession):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/")):
        return await message.answer("⚠️ Iltimos, haqiqiy URL manzil kiriting (https:// bilan boshlanishi kerak):")

    await state.update_data(broadcast_btn_url=url)
    await show_audience_selection(message, state, db_session)


@admin_router.callback_query(F.data == "admin:broadcast:add_btn:no", is_private_message)
async def admin_broadcast_no_btn(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await state.update_data(broadcast_btn_text=None, broadcast_btn_url=None)
    await query.message.delete()
    await show_audience_selection(query.message, state, db_session)
    await query.answer()


async def show_audience_selection(message: Message, state: FSMContext, db_session: DBSession):
    total_users = len(db_session.exec(select(User).where(User.is_blocked == False)).all())
    uz_users = len(db_session.exec(select(User).where(User.is_blocked == False, User.language == "uz")).all())
    ru_users = len(db_session.exec(select(User).where(User.is_blocked == False, User.language == "ru")).all())

    builder = InlineKeyboardBuilder()
    builder.button(text=f"👥 Barcha foydalanuvchilar ({total_users} ta)", callback_data="admin:broadcast:target:all")
    builder.button(text=f"🇺🇿 O'zbek tili ({uz_users} ta)", callback_data="admin:broadcast:target:lang_uz")
    builder.button(text=f"🇷🇺 Rus tili ({ru_users} ta)", callback_data="admin:broadcast:target:lang_ru")
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    await message.answer(
        "🎯 <b>Xabar qaysi auditoriyaga yuborilsin?</b><br/>"
        "Quyidagi toifalardan birini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


@admin_router.callback_query(F.data.startswith("admin:broadcast:target:"), is_private_message)
async def admin_broadcast_target_chosen(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    target_filter = query.data.replace("admin:broadcast:target:", "")
    data = await state.get_data()

    from_chat_id = data.get("broadcast_from_chat_id")
    message_id = data.get("broadcast_message_id")
    btn_text = data.get("broadcast_btn_text")
    btn_url = data.get("broadcast_btn_url")

    # Count matching users
    q = select(User).where(User.is_blocked == False)
    filter_label = "Barcha foydalanuvchilar"
    if target_filter == "lang_uz":
        q = q.where(User.language == "uz")
        filter_label = "O'zbek tili foydalanuvchilari"
    elif target_filter == "lang_ru":
        q = q.where(User.language == "ru")
        filter_label = "Rus tili foydalanuvchilari"

    matched_users = len(db_session.exec(q).all())

    # Create Broadcast entry
    bc = Broadcast(
        admin_id=query.from_user.id,
        from_chat_id=from_chat_id,
        message_id=message_id,
        target_filter=target_filter,
        button_text=btn_text,
        button_url=btn_url,
        total_target=matched_users,
        status=BroadcastStatus.pending
    )
    db_session.add(bc)
    db_session.commit()
    db_session.refresh(bc)

    await state.clear()
    await query.message.delete()

    # Send exact copy of message to admin as preview
    test_markup = None
    if btn_text and btn_url:
        test_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn_text, url=btn_url)]]
        )

    try:
        await bot.copy_message(
            chat_id=query.from_user.id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            reply_markup=test_markup
        )
    except Exception as e:
        print("Test copy failed:", e)

    # Estimate time (at 28 msg/sec)
    eta_sec = int(matched_users / 28) if matched_users else 0
    eta_min = eta_sec // 60
    eta_rem = eta_sec % 60
    eta_str = f"~{eta_min} daqiqa {eta_rem} soniya" if eta_min > 0 else f"~{eta_sec} soniya"

    btn_display = f"'{btn_text}' ({btn_url})" if btn_text else "Mavjud emas"

    confirm_card = f"""
📢 <b>BROADCASTNI TASDIQLANG:</b>
━━━━━━━━━━━━━━━━━━━━━
🎯 <b>Auditoriya:</b> {filter_label} (<b>{matched_users}</b> ta foydalanuvchi)
🔘 <b>Tugma:</b> {btn_display}
⏱ <b>Taxminiy yuborish vaqti:</b> {eta_str}
━━━━━━━━━━━━━━━━━━━━━
<i>Yuqoridagi xabar nusxasi to'g'rimi? Barcha foydalanuvchilarga yuborishni tasdiqlaysizmi?</i>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Xabarni barchaga yuborish", callback_data=f"admin:broadcast:launch:{bc.id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"admin:broadcast:cancel_draft:{bc.id}")
    builder.adjust(1)

    await query.message.answer(confirm_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:broadcast:launch:"), is_private_message)
async def admin_broadcast_launch(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    bc = db_session.get(Broadcast, bc_id)
    if not bc:
        return await query.answer("Broadcast topilmadi!", show_alert=True)

    if bc.status == BroadcastStatus.running:
        return await query.answer("Ushbu broadcast allaqachon ishga tushirilgan!", show_alert=True)

    # Dispatch Celery background task
    from src.tasks.broadcast import execute_broadcast
    execute_broadcast.delay(bc.id)

    await query.answer("🚀 Broadcast ishga tushirildi!", show_alert=True)
    await show_live_progress(query, bc.id)


@admin_router.callback_query(F.data.startswith("admin:broadcast:cancel_draft:"), is_private_message)
async def admin_broadcast_cancel_draft(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    bc = db_session.get(Broadcast, bc_id)
    if bc and bc.status == BroadcastStatus.pending:
        bc.status = BroadcastStatus.cancelled
        db_session.add(bc)
        db_session.commit()

    await query.answer("Broadcast bekor qilindi.", show_alert=False)
    await admin_broadcast_menu_callback(query, None, db_session)


@admin_router.callback_query(F.data.startswith("admin:broadcast:live:"), is_private_message)
async def admin_broadcast_live_callback(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    await show_live_progress(query, bc_id, db_session)


async def show_live_progress(query: CallbackQuery, broadcast_id: int, db_session: DBSession | None = None):
    redis_client = get_redis(is_async=True)

    if db_session:
        bc = db_session.get(Broadcast, broadcast_id)
    else:
        with Session(engine) as session:
            bc = session.get(Broadcast, broadcast_id)

    if not bc:
        return await query.answer("Broadcast topilmadi!", show_alert=True)

    live_stats = None
    try:
        live_stats = await redis_client.hgetall(f"broadcast:{broadcast_id}:live")
    except Exception:
        pass

    sent = int(live_stats.get("sent", bc.sent_count)) if live_stats else bc.sent_count
    blocked = int(live_stats.get("blocked", bc.blocked_count)) if live_stats else bc.blocked_count
    failed = int(live_stats.get("failed", bc.failed_count)) if live_stats else bc.failed_count
    total = int(live_stats.get("total", bc.total_target)) if live_stats else bc.total_target

    processed = sent + blocked + failed
    pct = (processed / total * 100) if total > 0 else 0.0

    filled = int(pct // 10)
    bar = "█" * filled + "░" * (10 - filled)

    status_icon = "⚡️ Jarayonda..." if bc.status == BroadcastStatus.running else ("✅ Yakunlandi" if bc.status == BroadcastStatus.completed else f"❌ {bc.status}")

    card = f"""
<b>📊 Broadcast holati (№{bc.id}):</b>
━━━━━━━━━━━━━━━━━━━━━
Holati: <b>{status_icon}</b><br/>
Progress: <code>[{bar}]</code> <b>{pct:.1f}%</b><br/><br/>
• 🎯 Jami: <b>{total}</b> ta<br/>
• ✅ Muvaffaqiyatli: <b>{sent}</b> ta<br/>
• 🚫 Botni bloklagan: <b>{blocked}</b> ta<br/>
• ⚠️ Xatolik: <b>{failed}</b> ta<br/>
• 📤 Qayta ishlangan: <b>{processed} / {total}</b>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Yangilash", callback_data=f"admin:broadcast:live:{bc.id}")

    if bc.status == BroadcastStatus.running:
        builder.button(text="🛑 Yuborishni to'xtatish", callback_data=f"admin:broadcast:stop:{bc.id}")

    builder.button(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    try:
        await query.message.edit_text(card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass
    await query.answer()


@admin_router.callback_query(F.data.startswith("admin:broadcast:stop:"), is_private_message)
async def admin_broadcast_stop(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    redis_client = get_redis(is_async=True)

    try:
        await redis_client.set(f"broadcast:{bc_id}:cancel", 1)
        await query.answer("🛑 To'xtatish buyrug'i yuborildi. Jarayon to'xtatilmoqda...", show_alert=True)
    except Exception as e:
        await query.answer(f"Xatolik: {e}", show_alert=True)

    await show_live_progress(query, bc_id, db_session)


@admin_router.callback_query(F.data.startswith("admin:broadcast:history:"), is_private_message)
async def admin_broadcast_history(query: CallbackQuery, db_session: DBSession):
    page = int(query.data.split(":")[3])
    all_bc = db_session.exec(select(Broadcast).order_by(Broadcast.created_at.desc())).all()

    total = len(all_bc)
    if total == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu")
        return await query.message.edit_text("<i>Hozircha ommaviy xabarlar tarixi mavjud emas.</i>", reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total)
    page_bcs = all_bc[start_idx:end_idx]

    text_lines = [f"<b>📊 Ommaviy xabarlar tarixi</b> (Sahifa: {page}/{total_pages}):<br/>"]
    builder = InlineKeyboardBuilder()

    status_icons = {
        BroadcastStatus.completed: "✅",
        BroadcastStatus.running: "⚡️",
        BroadcastStatus.cancelled: "❌",
        BroadcastStatus.pending: "⏳"
    }

    for b in page_bcs:
        icon = status_icons.get(b.status, "ℹ️")
        dt_str = b.created_at.strftime("%d.%m.%Y %H:%M")
        text_lines.append(
            f"{icon} <b>Broadcast №{b.id}</b> ({dt_str})<br/>"
            f"• Holat: {b.status.upper()}<br/>"
            f"• Yetkazildi: {b.sent_count} / {b.total_target} ta (Bloklagan: {b.blocked_count})<br/>"
        )
        builder.button(text=f"🔍 №{b.id} tafsilotlari", callback_data=f"admin:broadcast:live:{b.id}")

    builder.adjust(1)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:broadcast:history:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:broadcast:history:{page + 1}"))

    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu"))

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()



