import logging
import re
from datetime import datetime, timedelta
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, CallbackQuery
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.generate_report import generate_report
from src.app.keyboards import (
    get_role_menu,
    get_main_menu,
    get_volunteer_menu,
    is_volunteer_menu_user,
    get_agreement_keyboard,
    get_language_keyboard,
)
from src.app.translations import t, get_about_us_text
from src.models.user import User
from aiogram.filters import Command, CommandObject
from src.routes.aiogram.benefits import benefits_router
from src.routes.aiogram.inquiry import inquiry_router
from src.routes.aiogram.inquiry_archive import inquiry_archive_router
from src.routes.aiogram.registration import RegistrationState, registration_router
from src.routes.aiogram.volunteer_reg import volunteer_reg_router, start_volunteer_registration
from src.routes.aiogram.volunteer_result import volunteer_result_router
from src.routes.aiogram.volunteer_assign import volunteer_assign_router
from src.routes.aiogram.ai_answer import ai_answer_router
from src.routes.aiogram.volunteer_sections import volunteer_sections_router
from src.config.settings import settings
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

router = Router()
router.include_routers(
    registration_router,
    benefits_router,
    inquiry_router,
    inquiry_archive_router,
    volunteer_reg_router,
    volunteer_result_router,
    volunteer_assign_router,
    ai_answer_router,
    volunteer_sections_router,
)


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
        await message.answer(t("already_registered", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@router.callback_query(F.data.startswith("set_lang:"), is_private_message)
async def language_selected(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    selected_lang = query.data.split(":")[1]
    if selected_lang not in ["uz", "ru", "oz"]:
        selected_lang = "uz"

    from src.models.required_channel import RequiredChannel
    from src.app.subscription_utils import check_user_channels, build_subscription_keyboard, get_subscription_prompt_text
    from src.database.redisdb import get_redis

    redis = get_redis(is_async=True)
    # Invalidate cached subscription state across all languages for this user
    try:
        await redis.delete(f"user_sub_ok:{query.from_user.id}")
        await redis.delete(f"user_sub_ok:{query.from_user.id}:uz")
        await redis.delete(f"user_sub_ok:{query.from_user.id}:oz")
        await redis.delete(f"user_sub_ok:{query.from_user.id}:ru")
    except Exception:
        pass

    user = User.get_by_user_id(query.from_user.id, db_session)
    if user:
        user.language = selected_lang
        db_session.add(user)
        db_session.commit()
        await query.answer()

        # Check if user needs to subscribe to new channels for the newly chosen language
        channels = RequiredChannel.get_active_channels_for_lang(selected_lang, db_session)
        is_all_sub, unsubscribed = await check_user_channels(bot, query.from_user.id, channels)
        if not is_all_sub and unsubscribed:
            try:
                await query.message.delete()
            except Exception:
                pass
            prompt_text = get_subscription_prompt_text(selected_lang)
            markup = build_subscription_keyboard(unsubscribed, selected_lang)
            return await query.message.answer(prompt_text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)

        try:
            await redis.set(f"user_sub_ok:{query.from_user.id}:{selected_lang}", "1", ex=60)
        except Exception:
            pass

        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.answer(
            t("lang_changed", selected_lang),
            reply_markup=get_role_menu(query.from_user.id, selected_lang, db_session),
        )
    else:
        await state.update_data(language=selected_lang)
        await query.answer()

        # Check subscription for new user with selected language
        channels = RequiredChannel.get_active_channels_for_lang(selected_lang, db_session)
        is_all_sub, unsubscribed = await check_user_channels(bot, query.from_user.id, channels)
        if not is_all_sub and unsubscribed:
            try:
                await query.message.delete()
            except Exception:
                pass
            prompt_text = get_subscription_prompt_text(selected_lang)
            markup = build_subscription_keyboard(unsubscribed, selected_lang)
            return await query.message.answer(prompt_text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)

        try:
            await redis.set(f"user_sub_ok:{query.from_user.id}:{selected_lang}", "1", ex=60)
        except Exception:
            pass

        await state.set_state(RegistrationState.agreement)
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.answer(
            get_about_us_text(selected_lang, settings.BOT_NAME),
            reply_markup=get_agreement_keyboard("understood_for_registration", selected_lang),
            parse_mode=SULGUK_PARSE_MODE,
        )


@router.message(F.text.in_([t("btn_change_lang", "uz"), t("btn_change_lang", "ru"), t("btn_change_lang", "oz"), "🌐 Tilni o'zgartirish", "🌐 Тилни ўзгартириш", "🌐 Сменить язык", "🌐 Изменить язык"]), is_private_message)
async def change_language_handler(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    await message.answer(
        t("choose_language", lang),
        reply_markup=get_language_keyboard(),
    )


@router.message(F.text.in_([t("menu_about_us", "uz"), t("menu_about_us", "ru"), t("menu_about_us", "oz"), "ℹ️ Biz haqimizda", "ℹ️ Биз ҳақимизда", "ℹ️ О нас"]), is_private_message)
async def about_us_handler(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    await message.answer(
        get_about_us_text(lang, settings.BOT_NAME),
        reply_markup=get_agreement_keyboard("understood_about_us", lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


def _texts(key: str) -> list[str]:
    return [t(key, "uz"), t(key, "oz"), t(key, "ru")]


@router.message(F.text.in_(_texts("btn_back_main")), is_private_message)
async def back_to_main_handler(message: Message, state: FSMContext, db_session: DBSession):
    await state.clear()
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@router.message(F.text.in_(_texts("menu_vol_citizen")), is_private_message)
async def volunteer_to_citizen_menu(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    is_vol = is_volunteer_menu_user(message.from_user.id, db_session)
    await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang, show_volunteer_panel=is_vol))


@router.message(Command("panel"), is_private_message)
@router.message(F.text.in_(_texts("menu_vol_panel")), is_private_message)
async def open_volunteer_panel(message: Message, state: FSMContext, db_session: DBSession):
    await state.clear()
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else "uz"
    if not is_volunteer_menu_user(message.from_user.id, db_session):
        return await message.answer(t("vol_panel_not_volunteer", lang), reply_markup=get_main_menu(lang))
    await message.answer(t("vol_panel_opened", lang), reply_markup=get_volunteer_menu(lang))


@router.callback_query(F.data == "understood_about_us")
async def understood_about_us_handler(query: CallbackQuery):
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass


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
        logger.warning("%s", e)
        return await message.answer("Iltimos sanalarni to'g'ri kiriting. Masalan: 01/08/24-30/08/24")

    filename = generate_report((start_date, end_date))
    file = FSInputFile(filename)
    await message.answer_document(document=file)


@router.callback_query(F.data == "check_sub", is_private_message)
async def check_subscription_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    from src.models.required_channel import RequiredChannel
    from src.app.subscription_utils import check_user_channels, build_subscription_keyboard
    from src.database.redisdb import get_redis

    user_id = query.from_user.id
    user = User.get_by_user_id(user_id, db_session)
    state_data = await state.get_data()
    user_lang = user.language if (user and user.language) else state_data.get("language", "uz")

    channels = RequiredChannel.get_active_channels_for_lang(user_lang, db_session)
    if not channels:
        await query.answer(t("sub_verified_success", user_lang), show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        if user:
            return await query.message.answer(t("already_registered", user_lang), reply_markup=get_role_menu(user_id, user_lang, db_session))
        else:
            await state.set_state(RegistrationState.agreement)
            return await query.message.answer(
                get_about_us_text(user_lang, settings.BOT_NAME),
                reply_markup=get_agreement_keyboard("understood_for_registration", user_lang),
                parse_mode=SULGUK_PARSE_MODE,
            )

    is_all_sub, unsubscribed = await check_user_channels(bot, user_id, channels)

    if is_all_sub:
        try:
            redis = get_redis(is_async=True)
            await redis.set(f"user_sub_ok:{user_id}:{user_lang}", "1", ex=60)
        except Exception:
            pass

        await query.answer(t("sub_verified_success", user_lang), show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass

        if user:
            await query.message.answer(t("already_registered", user_lang), reply_markup=get_role_menu(user_id, user_lang, db_session))
        else:
            await state.set_state(RegistrationState.agreement)
            await query.message.answer(
                get_about_us_text(user_lang, settings.BOT_NAME),
                reply_markup=get_agreement_keyboard("understood_for_registration", user_lang),
                parse_mode=SULGUK_PARSE_MODE,
            )
    else:
        await query.answer(t("sub_not_verified", user_lang), show_alert=True)
        try:
            new_markup = build_subscription_keyboard(unsubscribed, user_lang)
            await query.message.edit_reply_markup(reply_markup=new_markup)
        except Exception:
            pass
