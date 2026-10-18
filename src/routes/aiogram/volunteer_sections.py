"""Volontyor o'zi soha a'zoligini so'raydi, admin tasdiqlaydi yoki rad etadi."""
import html
import logging

from aiogram import F, Bot, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.keyboards import section_names_uz
from src.app.translations import t
from src.config.settings import settings
from src.database.redisdb import get_redis
from src.models.assignment import VolunteerSection
from src.models.user import User
from src.models.volunteer import Volunteer
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

volunteer_sections_router = Router(name="volunteer_sections")
REQUEST_TTL = 30 * 86400


def _lang(user_id: int, db_session: DBSession) -> str:
    user = User.get_by_user_id(user_id, db_session)
    return (user.language if user else None) or "uz"


def _pending_key(vol_user_id: int, idx: int) -> str:
    return f"vol_section_request:{vol_user_id}:{idx}"


def _sections_markup(vol_user_id: int, db_session: DBSession) -> InlineKeyboardMarkup:
    member = {row.section_name for row in VolunteerSection.get_user_sections(vol_user_id, db_session)}
    r = get_redis(is_async=False)
    rows = []
    for idx, name in enumerate(section_names_uz):
        if name in member:
            mark, cb = "✅", "volsec:noop"
        elif r.exists(_pending_key(vol_user_id, idx)):
            mark, cb = "⏳", "volsec:noop"
        else:
            mark, cb = "➕", f"volsec:req:{idx}"
        rows.append([InlineKeyboardButton(text=f"{mark} {name.strip()}", callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@volunteer_sections_router.message(
    F.text.in_([t("menu_vol_sections", "uz"), t("menu_vol_sections", "oz"), t("menu_vol_sections", "ru")]),
    is_private_message,
)
async def vol_sections_menu(message: Message, db_session: DBSession):
    lang = _lang(message.from_user.id, db_session)
    vol = Volunteer.get_by_user_id(message.from_user.id, db_session)
    if not vol or not vol.is_active:
        return await message.answer(t("vol_panel_not_volunteer", lang))
    await message.answer(t("vol_sections_title", lang), reply_markup=_sections_markup(vol.user_id, db_session),
                         parse_mode=SULGUK_PARSE_MODE)


@volunteer_sections_router.callback_query(F.data == "volsec:noop")
async def vol_sections_noop(query: CallbackQuery):
    await query.answer()


@volunteer_sections_router.callback_query(F.data.startswith("volsec:req:"), is_private_message)
async def vol_section_request(query: CallbackQuery, db_session: DBSession, bot: Bot):
    lang = _lang(query.from_user.id, db_session)
    vol = Volunteer.get_by_user_id(query.from_user.id, db_session)
    try:
        idx = int(query.data.split(":")[2])
        section = section_names_uz[idx]
    except (ValueError, IndexError):
        return await query.answer()
    if not vol or not vol.is_active:
        return await query.answer(t("vol_panel_not_volunteer", lang), show_alert=True)
    if not get_redis(is_async=False).set(_pending_key(vol.user_id, idx), "1", ex=REQUEST_TTL, nx=True):
        return await query.answer(t("vol_section_requested", lang))

    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"secreq:ok:{vol.user_id}:{idx}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"secreq:no:{vol.user_id}:{idx}"),
    ]])
    text = (f"🗂 <b>Soha a'zoligi so'rovi</b><br/>Volontyor: "
            f'<a href="tg://user?id={vol.user_id}">{html.escape(vol.full_name)}</a><br/>Soha: <b>{html.escape(section.strip())}</b>')
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(chat_id=admin_id, text=text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
        except Exception as e:
            logger.info("Soha so'rovi admin %s ga yetmadi: %s", admin_id, type(e).__name__)
    await query.answer(t("vol_section_requested", lang))
    try:
        await query.message.edit_reply_markup(reply_markup=_sections_markup(vol.user_id, db_session))
    except Exception:
        pass


@volunteer_sections_router.callback_query(F.data.startswith("secreq:"), is_private_message)
async def admin_section_request_decision(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Bu amal faqat adminlar uchun.", show_alert=True)
    try:
        _, decision, vol_id_s, idx_s = query.data.split(":")
        vol_user_id, idx = int(vol_id_s), int(idx_s)
        section = section_names_uz[idx]
    except (ValueError, IndexError):
        return await query.answer()
    r = get_redis(is_async=False)
    if not r.delete(_pending_key(vol_user_id, idx)):
        await query.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    vol_lang = _lang(vol_user_id, db_session)
    if decision == "ok":
        exists = db_session.exec(select(VolunteerSection).where(
            VolunteerSection.volunteer_user_id == vol_user_id, VolunteerSection.section_name == section)).first()
        if not exists:
            db_session.add(VolunteerSection(volunteer_user_id=vol_user_id, section_name=section, added_by=query.from_user.id))
            db_session.commit()
        notice, badge = t("vol_section_approved", vol_lang, section=section.strip()), "✅ Tasdiqlandi"
    else:
        notice, badge = t("vol_section_rejected", vol_lang, section=section.strip()), "❌ Rad etildi"
    logger.info("Soha so'rovi %s: volontyor %s, soha %s, admin %s", decision, vol_user_id, section, query.from_user.id)
    try:
        await bot.send_message(chat_id=vol_user_id, text=notice)
    except Exception:
        pass
    admin_name = html.escape(query.from_user.first_name or str(query.from_user.id))
    try:
        await query.message.edit_text(f"{query.message.html_text}\n\n<b>{badge}</b> — {admin_name}", parse_mode="HTML")
    except Exception:
        pass
    await query.answer(badge)
