"""Avtomatik javobni soha bo'yicha yoqish/o'chirish."""
import logging
from datetime import datetime
from aiogram import F

logger = logging.getLogger(__name__)
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.app.keyboards import section_names_uz
from src.config.settings import settings
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import admin_router


def build_ai_sections_page(db_session: DBSession) -> tuple[str, InlineKeyboardMarkup]:
    from src.models.ai_answer import AiSectionSetting
    rows = {r.section_name: r for r in db_session.exec(select(AiSectionSetting)).all()}
    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(section_names_uz):
        enabled = rows.get(name).enabled if rows.get(name) else True
        builder.button(text=f"{'✅' if enabled else '❌'} {name.strip()}", callback_data=f"admin:ai_sec:{idx}")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)
    text = (
        "<b>🤖 Avtomatik javob sohalari</b><br/><br/>"
        "✅ — oddiy savollarga avtomatik javob beriladi (nazoratchi tasdiqlasa).<br/>"
        "❌ — bu sohadagi barcha savollar to'g'ridan-to'g'ri huquqshunoslarga yuboriladi.<br/><br/>"
        f"Hozir umumiy holat: <b>{'yoqilgan' if settings.AI_CITIZEN_ANSWERS else 'o‘chirilgan (.env: AI_CITIZEN_ANSWERS)'}</b>"
    )
    return text, builder.as_markup()

@admin_router.callback_query(F.data == "admin:ai_sections", is_private_message)
async def admin_ai_sections_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)
    text, markup = build_ai_sections_page(db_session)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:ai_sec:"), is_private_message)
async def admin_ai_section_toggle(query: CallbackQuery, db_session: DBSession):
    from src.models.ai_answer import AiSectionSetting
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)
    try:
        name = section_names_uz[int(query.data.split(":")[2])]
    except (ValueError, IndexError):
        return await query.answer()
    row = db_session.exec(select(AiSectionSetting).where(AiSectionSetting.section_name == name)).first()
    if row is None:
        row = AiSectionSetting(section_name=name, enabled=False)
    else:
        row.enabled = not row.enabled
    row.updated_by = query.from_user.id
    row.updated_at = datetime.now()
    db_session.add(row)
    db_session.commit()
    logger.info("Avtomatik javob sohasi %s: %s (admin %s)", name, row.enabled, query.from_user.id)
    text, markup = build_ai_sections_page(db_session)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer("Saqlandi")


# ---------------------------------------------------------------------------------------------
# Biriktirishlar paneli: kimda nechta ochiq murojaat, kim qancha kutyapti, biriktirilmaganlar
# ---------------------------------------------------------------------------------------------
