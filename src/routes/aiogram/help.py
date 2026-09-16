from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.keyboards import get_main_menu
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.models.user import User
from src.routes.deps.db_session import DBSession

help_router = Router(name="help")


class HelpState(StatesGroup):
    waiting_for_phone_number = State()
    waiting_for_help_message = State()


@help_router.message(
    F.text.in_([t("menu_help", "uz"), t("menu_help", "ru"), "⁉️ Texnik yordam", "⁉️ Техническая помощь"]),
    is_private_message,
)
async def start_help_request(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        return await message.answer(t("user_not_found", lang), reply_markup=get_main_menu(lang))

    if user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(HelpState.waiting_for_phone_number)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("reg_send_phone_btn", lang), request_contact=True)
    kb.button(text=t("btn_cancel", lang))
    kb.adjust(1)
    await message.answer(
        t("help_start_text", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@help_router.message(
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Отмена"]),
    F.state.in_({HelpState.waiting_for_phone_number, HelpState.waiting_for_help_message}),
)
async def cancel_help_request(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))


@help_router.message(HelpState.waiting_for_phone_number, is_private_message)
async def process_phone_number(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    phone_number = ""
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text:
        phone_number = message.text

    await state.update_data(phone_number=phone_number)
    await state.set_state(HelpState.waiting_for_help_message)

    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await message.answer(
        t("help_problem_prompt", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@help_router.message(HelpState.waiting_for_help_message, is_private_message)
async def process_help_message(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        await state.clear()
        return await message.answer(t("user_not_found", lang), reply_markup=get_main_menu(lang))

    if user.is_blocked:
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    data = await state.get_data()
    phone_number = data.get('phone_number', user.phone or 'Noma\'lum')

    user_info = (
        f"<b>Yordam so'rovi (Texnik yordam):</b><br/>"
        f"<b>Foydalanuvchi:</b> {user.first_name} {user.last_name}<br/>"
        f"<b>Username:</b> @{user.username}<br/>"
        f"<b>ID:</b> <code>{user.user_id}</code><br/>"
        f"<b>Telefon:</b> {phone_number}<br/>"
        f"<b>Til:</b> {'Oʻzbekcha' if lang == 'uz' else 'Русский'}<br/><br/>"
        f"<b>Xabar:</b> {message.text}"
    )

    await bot.send_message(
        chat_id=settings.get_help_group_id(),
        text=user_info,
        parse_mode=SULGUK_PARSE_MODE,
    )

    await state.clear()
    await message.answer(
        t("help_success", lang),
        reply_markup=get_main_menu(lang),
    )
