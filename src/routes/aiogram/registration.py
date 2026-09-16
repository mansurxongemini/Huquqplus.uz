from datetime import datetime
from sulguk import SULGUK_PARSE_MODE
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from src.app.enums import (
    disability_types_uz,
    disability_types_ru,
    disability_states_uz,
    disability_states_ru,
    regions_uz,
    regions_ru,
    get_disability_types,
    get_disability_states,
    get_regions,
    create_user_info,
)
from src.app.filters import is_private_message
from src.app.keyboards import get_main_menu
from src.app.translations import t, LANG_UZ, LANG_RU
from src.models.user import GenderType, User, Region, DisabilityType, DisabilityState
from src.routes.deps.db_session import DBSession

registration_router = Router()


class RegistrationState(StatesGroup):
    language = State()
    agreement = State()
    first_name = State()
    last_name = State()
    gender = State()
    birth_year = State()
    phone = State()
    disability_type = State()
    disability_state = State()
    region = State()


def find_key_by_value(d_uz: dict, d_ru: dict, text: str) -> str | None:
    for k, v in d_uz.items():
        if v == text:
            return k
    for k, v in d_ru.items():
        if v == text:
            return k
    return None


@registration_router.callback_query(F.data == "understood_for_registration", RegistrationState.agreement)
async def agreement_understood(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)
    await query.message.delete()
    await state.set_state(RegistrationState.first_name)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await query.message.answer(
        t("reg_enter_first_name", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(
    F.text.in_([t("menu_profile", "uz"), t("menu_profile", "ru"), "🪪 Profil", "🪪 Профиль"]),
    is_private_message,
)
async def profile(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    if user is None:
        await message.answer(t("user_not_found", "uz"))
        return

    lang = user.language or LANG_UZ
    if user.is_blocked:
        await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)
        return

    user_info = create_user_info(user, False, lang=lang)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("profile_edit_btn", lang))
    kb.button(text=t("menu_my_inquiries", lang))
    kb.button(text=t("btn_back_main", lang))
    await message.answer(
        t("profile_title", lang) + user_info,
        reply_markup=kb.adjust(1, 2).as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(
    F.text.in_([
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
        t("btn_back_main", "uz"), t("btn_back_main", "ru"),
        "❌ Bekor qilish", "❌ Отмена", "⬅️ Asosiy menyu", "⬅️ Главное меню"
    ]),
    is_private_message,
)
async def cancel_or_main_menu(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    data = await state.get_data()
    lang = user.language if user else data.get("language", LANG_UZ)
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))


@registration_router.message(
    F.text.in_([t("profile_edit_btn", "uz"), t("profile_edit_btn", "ru"), "🪪 O‘zgartirish", "🪪 Изменить"]),
    is_private_message,
)
async def start_profile_edit(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.update_data(language=lang)
    await state.set_state(RegistrationState.first_name)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_enter_first_name", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(RegistrationState.first_name, is_private_message)
async def get_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)
    await state.update_data(first_name=message.text.strip())
    await state.set_state(RegistrationState.last_name)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_enter_last_name", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(RegistrationState.last_name, is_private_message)
async def get_last_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)
    await state.update_data(last_name=message.text.strip())
    await state.set_state(RegistrationState.gender)
    markup = ReplyKeyboardBuilder()
    markup.button(text="👦🏻 " + t("reg_gender_male", lang))
    markup.button(text="👧🏻 " + t("reg_gender_female", lang))
    markup.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_choose_gender", lang),
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
    )


@registration_router.message(RegistrationState.gender, is_private_message)
async def get_gender(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)
    valid_male = ["👦🏻 Erkak", "Erkak", "👦🏻 Мужской", "Мужской"]
    valid_female = ["👧🏻 Ayol", "Ayol", "👧🏻 Женский", "Женский"]

    if message.text in valid_male:
        selected_gender = GenderType.male
    elif message.text in valid_female:
        selected_gender = GenderType.female
    else:
        return await message.reply(t("reg_choose_gender", lang))

    await state.update_data(gender=selected_gender)
    await state.set_state(RegistrationState.birth_year)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_enter_birth_year", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(RegistrationState.birth_year, is_private_message)
async def get_age(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)
    if not message.text.isdigit() or int(message.text) < 1900 or int(message.text) > datetime.now().year:
        return await message.reply(t("reg_invalid_year", lang))

    await state.update_data(birth_year=int(message.text))
    await state.set_state(RegistrationState.phone)
    markup = ReplyKeyboardBuilder()
    markup.button(text=t("reg_send_phone_btn", lang), request_contact=True)
    markup.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_enter_phone", lang),
        reply_markup=markup.adjust(1).as_markup(resize_keyboard=True),
        parse_mode=SULGUK_PARSE_MODE,
    )


@registration_router.message(RegistrationState.phone, is_private_message)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)

    phone_number = None
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text and len(message.text.strip()) >= 7:
        phone_number = message.text.strip()

    if not phone_number:
        return await message.reply(t("reg_enter_phone", lang))

    await state.update_data(phone=phone_number)
    await state.set_state(RegistrationState.disability_type)

    d_types = get_disability_types(lang)
    markup = ReplyKeyboardBuilder()
    for value in d_types.values():
        markup.button(text=value)
    markup.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_choose_disability_type", lang),
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
    )


@registration_router.message(RegistrationState.disability_type, is_private_message)
async def get_disability_type(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)

    d_key = find_key_by_value(disability_types_uz, disability_types_ru, message.text)
    if not d_key:
        return await message.reply(t("reg_choose_disability_type", lang))

    await state.update_data(disability_type=DisabilityType(d_key))
    await state.set_state(RegistrationState.disability_state)

    d_states = get_disability_states(lang)
    markup = ReplyKeyboardBuilder()
    for value in d_states.values():
        markup.button(text=value)
    markup.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_choose_disability_state", lang),
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
    )


@registration_router.message(RegistrationState.disability_state, is_private_message)
async def get_disability_state(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)

    s_key = find_key_by_value(disability_states_uz, disability_states_ru, message.text)
    if not s_key:
        return await message.reply(t("reg_choose_disability_state", lang))

    await state.update_data(disability_state=DisabilityState(s_key))
    await state.set_state(RegistrationState.region)

    regs = get_regions(lang)
    markup = ReplyKeyboardBuilder()
    for value in regs.values():
        markup.button(text=value)
    markup.button(text=t("btn_cancel", lang))
    await message.answer(
        t("reg_choose_region", lang),
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
    )


@registration_router.message(RegistrationState.region, is_private_message)
async def get_region(message: Message, state: FSMContext, db_session: DBSession):
    data = await state.get_data()
    lang = data.get("language", LANG_UZ)

    r_key = find_key_by_value(regions_uz, regions_ru, message.text)
    if not r_key:
        return await message.reply(t("reg_choose_region", lang))

    chosen_region = Region[r_key]
    await state.update_data(region=chosen_region)
    collected = await state.get_data()

    existing_user = User.get_by_user_id(message.from_user.id, db_session)
    user_payload = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': collected.get('first_name'),
        'last_name': collected.get('last_name'),
        'gender': collected.get('gender'),
        'birth_year': collected.get('birth_year'),
        'phone': collected.get('phone'),
        'disability_type': collected.get('disability_type'),
        'disability_state': collected.get('disability_state'),
        'region': chosen_region,
        'language': lang,
    }

    if not existing_user:
        user = User.model_validate(user_payload)
    else:
        user = existing_user
        for key, val in user_payload.items():
            setattr(user, key, val)

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    await state.clear()
    await message.answer(
        t("reg_success", lang),
        reply_markup=get_main_menu(lang),
    )
