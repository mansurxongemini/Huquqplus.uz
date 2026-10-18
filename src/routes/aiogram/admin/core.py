"""/admin buyrug'i va bosh menyu."""
import logging
from aiogram import F

logger = logging.getLogger(__name__)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.user import User
from src.models.required_channel import RequiredChannel
from src.models.benefit import Benefit
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import admin_router, get_admin_menu_keyboard


@admin_router.message(Command("admin"), is_private_message)
async def admin_panel_start(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")

    await state.clear()
    blocked_users = User.get_blocked_users(db_session)
    count = len(blocked_users)
    channels_count = len(RequiredChannel.get_all(db_session))
    benefits_count = len(db_session.exec(select(Benefit.id)).all())

    await message.answer(
        "<b>👑 Admin Panel</b><br/><br/>"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_menu_keyboard(count, channels_count, benefits_count),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data == "admin:main", is_private_message)
async def admin_main_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    blocked_users = User.get_blocked_users(db_session)
    count = len(blocked_users)
    channels_count = len(RequiredChannel.get_all(db_session))
    benefits_count = len(db_session.exec(select(Benefit.id)).all())

    await query.message.edit_text(
        "<b>👑 Admin Panel</b><br/><br/>"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_menu_keyboard(count, channels_count, benefits_count),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.callback_query(F.data == "admin:noop")
async def admin_noop_callback(query: CallbackQuery):
    await query.answer()
