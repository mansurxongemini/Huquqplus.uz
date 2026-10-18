"""Foydalanuvchilarni bloklash va blokdan chiqarish."""
import logging
from datetime import datetime
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.app.translations import t
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.user import User
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import AdminBlockState, PAGE_SIZE, admin_router


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
        logger.warning("Failed to clear FSM on block: %s", e)

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
        logger.warning("Failed to cancel inquiries on block: %s", e)

    # 3. Notify user
    user_lang = target_user.language or "uz"
    try:
        msg = t("user_blocked_notification", user_lang)
        if reason:
            reason_label = t("block_reason_label", user_lang)
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
