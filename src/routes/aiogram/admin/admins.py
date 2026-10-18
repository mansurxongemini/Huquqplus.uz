"""Adminlarni Telegram ID orqali qo'shish va o'chirish."""
import html
import logging
from datetime import datetime
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.user import User
from src.models.bot_admin import BotAdmin
from src.app.admin_registry import invalidate_cache as invalidate_admin_cache
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import AdminManageState, admin_router


def _admin_label(user_id: int, db_session: DBSession) -> str:
    user = User.get_by_user_id(user_id, db_session)
    if not user:
        return f"ID <code>{user_id}</code>"
    name = " ".join(x for x in (user.first_name, user.last_name) if x) or "—"
    uname = f" (@{html.escape(user.username)})" if user.username else ""
    return f"{html.escape(name)}{uname} • <code>{user_id}</code>"

def _parse_telegram_id(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw.isdigit() or not (5 <= len(raw) <= 15):
        return None
    value = int(raw)
    return value if value > 0 else None

def build_admins_page(db_session: DBSession, viewer_is_super: bool) -> tuple[str, InlineKeyboardMarkup]:
    supers = settings.super_admin_ids_list
    db_admins = BotAdmin.get_active(db_session)
    lines = ["<b>👥 Adminlar boshqaruvi</b><br/>"]
    lines.append("<b>🔒 Asosiy adminlar</b> (serverda belgilangan, o'chirib bo'lmaydi):")
    for uid in supers:
        lines.append(f"• {_admin_label(uid, db_session)}")
    lines.append("<br/><b>👤 Panel orqali qo'shilgan adminlar:</b>")
    if db_admins:
        for a in db_admins:
            when = a.added_at.strftime("%d.%m.%Y") if a.added_at else ""
            lines.append(f"• {_admin_label(a.user_id, db_session)} <i>({when})</i>")
    else:
        lines.append("<i>Hozircha yo'q</i>")
    if not viewer_is_super:
        lines.append("<br/><i>Adminlarni qo'shish va o'chirish faqat asosiy adminlarga ruxsat etilgan.</i>")

    builder = InlineKeyboardBuilder()
    if viewer_is_super:
        builder.button(text="➕ Admin qo'shish (Telegram ID)", callback_data="admin:adm_add")
        for a in db_admins:
            user = User.get_by_user_id(a.user_id, db_session)
            name = (user.first_name if user and user.first_name else None) or str(a.user_id)
            builder.button(text=f"🗑 {name[:24]} ({a.user_id})", callback_data=f"admin:adm_rm:{a.user_id}")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)
    return "<br/>".join(lines), builder.as_markup()

async def _deny_non_super(query: CallbackQuery) -> bool:
    if not settings.is_super_admin(query.from_user.id):
        await query.answer("Bu amal faqat asosiy adminlar uchun.", show_alert=True)
        return True
    return False

@admin_router.callback_query(F.data == "admin:admins_list", is_private_message)
async def admin_admins_list_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)
    await state.clear()
    text, markup = build_admins_page(db_session, settings.is_super_admin(query.from_user.id))
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data == "admin:adm_add", is_private_message)
async def admin_adm_add_callback(query: CallbackQuery, state: FSMContext):
    if await _deny_non_super(query):
        return
    await state.set_state(AdminManageState.waiting_for_admin_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:admins_list")
    await query.message.edit_text(
        "<b>➕ Yangi admin qo'shish</b><br/><br/>"
        "Yangi adminning <b>Telegram ID</b> raqamini yuboring (faqat raqamlar, masalan <code>123456789</code>).<br/><br/>"
        "<i>ID ni bilmasangiz, u kishi @userinfobot ga /start yuborsa ID ni ko'radi.</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()

@admin_router.message(AdminManageState.waiting_for_admin_id, is_private_message)
async def admin_adm_id_input(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_super_admin(message.from_user.id):
        return
    if message.text and message.text.strip().lower() in ("/cancel", "bekor qilish"):
        await state.clear()
        text, markup = build_admins_page(db_session, True)
        return await message.answer(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)

    new_id = _parse_telegram_id(message.text or "")
    if new_id is None:
        return await message.answer("⚠️ Noto'g'ri ID. Faqat raqamlardan iborat Telegram ID yuboring (masalan <code>123456789</code>).", parse_mode=SULGUK_PARSE_MODE)

    if settings.is_admin(new_id):
        await state.clear()
        text, markup = build_admins_page(db_session, True)
        return await message.answer(f"ℹ️ {_admin_label(new_id, db_session)} allaqachon admin.<br/><br/>{text}", reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)

    known = User.get_by_user_id(new_id, db_session) is not None
    warn = "" if known else (
        "<br/><br/>⚠️ Bu foydalanuvchi botni hali ishga tushirmagan (/start). "
        "Admin bo'ladi, lekin bot unga xabar yubora olmaydi, panelga kirish uchun u botga /start yuborishi kerak."
    )
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, admin qilish", callback_data=f"admin:adm_ok:{new_id}")
    builder.button(text="❌ Bekor qilish", callback_data="admin:admins_list")
    builder.adjust(1)
    await message.answer(
        f"<b>Admin qilish tasdig'i</b><br/><br/>{_admin_label(new_id, db_session)}{warn}<br/><br/>"
        "Bu shaxs barcha admin huquqlarini (biriktirish, hisobotlar, bloklash, broadcast) oladi. Tasdiqlaysizmi?",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE,
    )

@admin_router.callback_query(F.data.startswith("admin:adm_ok:"), is_private_message)
async def admin_adm_confirm_add(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if await _deny_non_super(query):
        return
    try:
        new_id = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        return await query.answer("Noto'g'ri so'rov.", show_alert=True)
    if _parse_telegram_id(str(new_id)) is None:
        return await query.answer("Noto'g'ri ID.", show_alert=True)

    row = BotAdmin.get_by_user_id(new_id, db_session)
    if row and row.is_active:
        return await query.answer("Bu foydalanuvchi allaqachon admin.", show_alert=True)
    if row:
        row.is_active = True
        row.added_by = query.from_user.id
        row.added_at = datetime.now()
        row.removed_by = None
        row.removed_at = None
    else:
        row = BotAdmin(user_id=new_id, added_by=query.from_user.id)
    db_session.add(row)
    db_session.commit()
    invalidate_admin_cache()
    logger.info("Admin added: %s by %s", new_id, query.from_user.id)

    notice = ""
    try:
        await bot.send_message(new_id, "👑 Siz Huquq+ botida admin etib tayinlandingiz. Admin panelni ochish uchun /admin buyrug'ini yuboring.")
    except Exception as e:  # noqa: BLE001
        logger.info("New admin %s not notified: %s", new_id, type(e).__name__)
        notice = "<br/><br/>⚠️ Yangi adminga xabar yuborib bo'lmadi (u botni ishga tushirmagan yoki bloklagan)."

    text, markup = build_admins_page(db_session, True)
    await query.message.edit_text(f"✅ {_admin_label(new_id, db_session)} admin qilindi.{notice}<br/><br/>{text}", reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:adm_rm:"), is_private_message)
async def admin_adm_remove_ask(query: CallbackQuery, db_session: DBSession):
    if await _deny_non_super(query):
        return
    try:
        target = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        return await query.answer("Noto'g'ri so'rov.", show_alert=True)
    row = BotAdmin.get_by_user_id(target, db_session)
    if not row or not row.is_active:
        return await query.answer("Bu admin ro'yxatda yo'q.", show_alert=True)
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, olib tashlash", callback_data=f"admin:adm_rm_ok:{target}")
    builder.button(text="❌ Bekor qilish", callback_data="admin:admins_list")
    builder.adjust(1)
    await query.message.edit_text(
        f"<b>Adminlikdan olib tashlash</b><br/><br/>{_admin_label(target, db_session)}<br/><br/>Tasdiqlaysizmi?",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:adm_rm_ok:"), is_private_message)
async def admin_adm_remove_confirm(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if await _deny_non_super(query):
        return
    try:
        target = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        return await query.answer("Noto'g'ri so'rov.", show_alert=True)
    if settings.is_super_admin(target):
        return await query.answer("Asosiy adminni o'chirib bo'lmaydi.", show_alert=True)
    row = BotAdmin.get_by_user_id(target, db_session)
    if not row or not row.is_active:
        return await query.answer("Bu admin ro'yxatda yo'q.", show_alert=True)
    row.is_active = False
    row.removed_by = query.from_user.id
    row.removed_at = datetime.now()
    db_session.add(row)
    db_session.commit()
    invalidate_admin_cache()
    logger.info("Admin removed: %s by %s", target, query.from_user.id)
    try:
        await bot.send_message(target, "ℹ️ Sizning Huquq+ botidagi admin huquqlaringiz bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass
    text, markup = build_admins_page(db_session, True)
    await query.message.edit_text(f"✅ Adminlikdan olib tashlandi.<br/><br/>{text}", reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# ---------------------------------------------------------------------------------------------
# Avtomatik javob: soha bo'yicha yoqish/o'chirish (yozuv bo'lmasa — yoqilgan)
# ---------------------------------------------------------------------------------------------
