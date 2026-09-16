import re
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, CallbackQuery
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.generate_report import generate_report
from src.app.keyboards import (
    get_main_menu,
    get_agreement_keyboard,
    get_language_keyboard,
)
from src.app.translations import t, get_about_us_text
from src.models.user import User
from aiogram.filters import Command, CommandObject
from src.routes.aiogram.inquiry import inquiry_router
from src.routes.aiogram.inquiry_archive import inquiry_archive_router
from src.routes.aiogram.registration import RegistrationState, registration_router
from src.routes.aiogram.volunteer_reg import volunteer_reg_router, start_volunteer_registration
from src.config.settings import settings
from src.routes.deps.db_session import DBSession

router = Router()
router.include_routers(registration_router, inquiry_router, inquiry_archive_router, volunteer_reg_router)


@router.message(Command("start"), is_private_message)
async def start_command(message: Message, command: CommandObject, state: FSMContext, db_session: DBSession):
    await state.clear()

    # Check if referral/deep link is for volunteer registration
    if command.args and command.args.strip().lower() == settings.VOLUNTEER_REG_KEY.lower():
        return await start_volunteer_registration(message, state, db_session)

    user = User.get_by_user_id(message.from_user.id, db_session)
    if not user:
        await state.set_state(RegistrationState.language)
        await message.answer(
            t("choose_language", "uz"),
            reply_markup=get_language_keyboard(),
        )
    else:
        lang = user.language or "uz"
        if user.is_blocked:
            await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)
            return
        await message.answer(t("already_registered", lang), reply_markup=get_main_menu(lang))


@router.callback_query(F.data.startswith("set_lang:"), is_private_message)
async def language_selected(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    selected_lang = query.data.split(":")[1]
    if selected_lang not in ["uz", "ru"]:
        selected_lang = "uz"

    user = User.get_by_user_id(query.from_user.id, db_session)
    if user:
        user.language = selected_lang
        db_session.add(user)
        db_session.commit()
        await query.answer()
        await query.message.delete()
        await query.message.answer(
            t("lang_changed", selected_lang),
            reply_markup=get_main_menu(selected_lang),
        )
    else:
        await state.update_data(language=selected_lang)
        await state.set_state(RegistrationState.agreement)
        await query.answer()
        await query.message.delete()
        await query.message.answer(
            get_about_us_text(selected_lang, settings.BOT_NAME),
            reply_markup=get_agreement_keyboard("understood_for_registration", selected_lang),
            parse_mode=SULGUK_PARSE_MODE,
        )


@router.message(F.text.in_([t("btn_change_lang", "uz"), t("btn_change_lang", "ru"), "🌐 Tilni o'zgartirish", "🌐 Сменить язык"]), is_private_message)
async def change_language_handler(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    await message.answer(
        t("choose_language", lang),
        reply_markup=get_language_keyboard(),
    )


@router.message(F.text.in_([t("menu_about_us", "uz"), t("menu_about_us", "ru"), "ℹ️ Biz haqimizda", "ℹ️ О нас"]), is_private_message)
async def about_us_handler(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    await message.answer(
        get_about_us_text(lang, settings.BOT_NAME),
        reply_markup=get_agreement_keyboard("understood_about_us", lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@router.callback_query(F.data == "understood_about_us")
async def understood_about_us_handler(query: CallbackQuery):
    await query.message.delete()


@router.message(Command("report"), is_private_message)
async def menu_command(message: Message):
    date_pattern = r"(\d{2}/\d{2}/\d{2})-(\d{2}/\d{2}/\d{2})"
    match = re.search(date_pattern, message.text)
    if '-' not in message.text:
        return

    try:
        start_date, end_date = match.groups()
        start_date = datetime.strptime(start_date, "%d/%m/%y")
        end_date = datetime.strptime(end_date, "%d/%m/%y")
        end_date = end_date + timedelta(days=1)
    except Exception as e:
        print(e)
        return await message.answer("Iltimos sanalarni to'g'ri kiriting. Masalan: 01/08/24-30/08/24")

    filename = generate_report((start_date, end_date))
    file = FSInputFile(filename)
    await message.answer_document(document=file)
