from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.keyboards import get_role_menu, inquiry_sections, inquiry_main_menu, inquiry_sections_uz
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.models.user import User
from src.app.inquiry_card import payload_from_message, payload_from_state
from src.app.question_delivery import deliver_citizen_question
from src.routes.deps.db_session import DBSession

auto_inquiry_router = Router(name="auto_inquiry")


class AutoInquiryState(StatesGroup):
    confirming = State()
    selecting_section = State()


MENU_BUTTONS_LIST = [
    t("menu_profile", "uz"), t("menu_profile", "oz"), t("menu_profile", "ru"), "🪪 Profil", "🪪 Профил", "🪪 Профиль",
    t("menu_benefits", "uz"), t("menu_benefits", "oz"), t("menu_benefits", "ru"), "Imtiyozlarim", "Имтиёзларим", "Мои льготы",
    t("menu_inquiry", "uz"), t("menu_inquiry", "oz"), t("menu_inquiry", "ru"), "📩 Savol yuborish", "📩 Савол юбориш", "📩 Задать вопрос",
    t("menu_appointment", "uz"), t("menu_appointment", "oz"), t("menu_appointment", "ru"), "✍️ Yurist qabuliga yozilish", "✍️ Юрист қабулига ёзилиш", "✍️ Запись на прием к юристу", "✍️ Запись к юристу",
    t("menu_my_inquiries", "uz"), t("menu_my_inquiries", "oz"), t("menu_my_inquiries", "ru"), "📋 Mening murojaatlarim", "🗂 Мурожаатларим архиви", "📋 Мои обращения", "🗂 Murojaatlarim arxivi",
    t("menu_about_us", "uz"), t("menu_about_us", "oz"), t("menu_about_us", "ru"), "ℹ️ Biz haqimizda", "ℹ️ Биз ҳақимизда", "ℹ️ О нас",
    t("menu_help", "uz"), t("menu_help", "oz"), t("menu_help", "ru"), "⁉️ Texnik yordam", "⁉️ Техник ёрдам", "⁉️ Техподдержка", "⁉️ Техническая помощь",
    t("menu_ai", "uz"), t("menu_ai", "oz"), t("menu_ai", "ru"), "🤖 AI yordamchi", "🤖 AI ёрдамчи", "🤖 ИИ-помощник",
    t("btn_new_ai_chat", "uz"), t("btn_new_ai_chat", "oz"), t("btn_new_ai_chat", "ru"), "🔄 Yangi suhbat", "🔄 Янги суҳбат", "🔄 Новый диалог",
    t("btn_change_lang", "uz"), t("btn_change_lang", "oz"), t("btn_change_lang", "ru"), "🌐 Tilni o'zgartirish", "🌐 Тилни ўзгартириш", "🌐 Сменить язык", "🌐 Изменить язык",
    t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена",
    t("btn_back_main", "uz"), t("btn_back_main", "oz"), t("btn_back_main", "ru"), "⬅️ Asosiy menyu", "⬅️ Асосий меню", "⬅️ Главное меню",
]


def get_auto_inquiry_confirm_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    from src.app.rag_client import rag_client
    keyboard = [
        [
            InlineKeyboardButton(text=t("btn_auto_inquiry_yes", lang), callback_data="auto_inquiry:confirm"),
            InlineKeyboardButton(text=t("btn_auto_inquiry_no", lang), callback_data="auto_inquiry:cancel"),
        ]
    ]
    if settings.AI_CITIZEN_ENABLED and rag_client.is_enabled():
        keyboard.append([
            InlineKeyboardButton(text=t("btn_auto_inquiry_ai", lang), callback_data="auto_inquiry:ai")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def extract_message_payload(message: Message) -> dict | None:
    """Tasdiqlashgacha FSM'da saqlanadigan murojaat mazmuni (payload_from_state bilan qayta o'qiladi)."""
    payload = payload_from_message(message)
    if payload is None:
        return None
    return {
        "private_msg_id": message.message_id,
        "media_type": payload.media_type.value,
        "text": payload.text,
        "file_id": payload.file_id,
        "caption": payload.caption,
        "file_name": payload.file_name,
        "media_data": payload.media_json,
    }


@auto_inquiry_router.callback_query(F.data == "auto_inquiry:cancel", is_private_message)
async def handle_cancel_auto_inquiry(query: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer("Bekor qilindi", show_alert=False)


@auto_inquiry_router.callback_query(F.data == "auto_inquiry:ai", is_private_message)
async def handle_auto_inquiry_ai(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        await query.answer()
        return await query.message.answer(t("ai_unavailable", lang))
    data = await state.get_data()
    text = data.get("text")
    if not text:
        await query.answer(t("review_only_text", lang), show_alert=True)
        return
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()

    from src.routes.aiogram.ai_assistant import AiChatState, process_ai_query
    from src.app.keyboards import get_ai_chat_menu
    await state.set_state(AiChatState.chatting)
    await state.update_data(last_question=text, conversation_id=None)
    await query.message.answer(
        t("ai_intro", lang),
        reply_markup=get_ai_chat_menu(lang),
    )
    await process_ai_query(
        message=query.message,
        text=text,
        user=user,
        state=state,
        bot=bot,
        user_id=query.from_user.id,
        question_msg_id=data.get("private_msg_id"),
    )


@auto_inquiry_router.callback_query(F.data == "auto_inquiry:confirm", is_private_message)
async def handle_confirm_auto_inquiry(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    if not user:
        await state.clear()
        return await query.answer("Foydalanuvchi topilmadi!", show_alert=True)

    lang = user.language or LANG_UZ
    data = await state.get_data()
    media_type_str = data.get("media_type")

    if not media_type_str:
        await state.clear()
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.answer("Murojaat ma'lumotlari topilmadi. Qaytadan yuboring.", show_alert=True)

    await state.set_state(AutoInquiryState.selecting_section)
    try:
        await query.message.delete()
    except Exception:
        pass

    prompt_text = t("auto_choose_section", lang)
    await query.message.answer(
        prompt_text,
        reply_markup=inquiry_main_menu(lang),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@auto_inquiry_router.message(
    AutoInquiryState.selecting_section,
    F.text.in_([
        t("btn_back_main", "uz"), t("btn_back_main", "oz"), t("btn_back_main", "ru"),
        t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"),
        "⬅️ Asosiy menyu", "⬅️ Асосий меню", "⬅️ Главное меню",
        "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"
    ]),
    is_private_message
)
async def auto_inquiry_cancel_at_section(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@auto_inquiry_router.message(AutoInquiryState.selecting_section, is_private_message)
async def auto_inquiry_section_chosen(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    if not user:
        await state.clear()
        return await message.answer(t("user_not_found", "uz"), reply_markup=get_role_menu(message.from_user.id, "uz", db_session))

    lang = user.language or LANG_UZ
    section_text = message.text

    if not section_text or section_text not in inquiry_sections:
        prompt = t("auto_choose_section_again", lang)
        return await message.answer(prompt, reply_markup=inquiry_main_menu(lang), parse_mode=SULGUK_PARSE_MODE)

    data = await state.get_data()
    media_type_str = data.get("media_type")
    private_msg_id = data.get("private_msg_id") or message.message_id

    if not media_type_str:
        await state.clear()
        return await message.answer("Murojaat ma'lumotlari topilmadi. Qaytadan yuboring.", reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    # Resolve target group based on section
    sec_id = inquiry_sections.get(section_text)
    id_to_latin = {v: k for k, v in inquiry_sections_uz.items()}
    latin_sec_name = id_to_latin.get(sec_id, section_text)

    inquiry_groups = settings.get_inquiry_groups()
    group_id = inquiry_groups.get(latin_sec_name) or inquiry_groups.get("Boshqa") or settings.LAWYER_APPOINTMENT_GROUP_ID

    payload = payload_from_state(data)
    if payload is None:
        await state.clear()
        return await message.answer("Noma'lum format.", reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    await state.clear()
    await deliver_citizen_question(bot, message, db_session, user, section_text, group_id, payload, private_msg_id)


@auto_inquiry_router.message(AutoInquiryState.confirming, is_private_message)
async def handle_msg_in_confirming(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    # If user pressed a main menu button or command, cancel auto inquiry and restore menu
    if message.text and (message.text.startswith("/") or message.text in MENU_BUTTONS_LIST or message.text in inquiry_sections.keys()):
        await state.clear()
        if message.text in [t("menu_inquiry", "uz"), t("menu_inquiry", "ru"), "📩 Savol yuborish", "📩 Задать вопрос"]:
            from src.routes.aiogram.inquiry import start_inquiry
            return await start_inquiry(message, state, db_session)
        return await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    # User sent another message: update state with latest message
    payload = extract_message_payload(message)
    if not payload:
        return await message.answer(t("inquiry_type_prompt", lang))

    await state.update_data(**payload)
    await message.reply(
        t("auto_inquiry_confirm_prompt", lang),
        reply_markup=get_auto_inquiry_confirm_keyboard(lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@auto_inquiry_router.message(is_private_message)
async def handle_unsolicited_message(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    # Only handle messages when user has no active state
    current_state = await state.get_state()
    if current_state is not None:
        return

    # Ignore commands
    if message.text and message.text.strip().startswith("/"):
        return

    # Ignore main menu buttons
    if message.text and (message.text in MENU_BUTTONS_LIST or message.text in inquiry_sections.keys()):
        return

    user = User.get_by_user_id(message.from_user.id, db_session)
    if not user:
        from src.routes.aiogram.registration import RegistrationState
        from src.app.keyboards import get_language_keyboard
        await state.set_state(RegistrationState.language)
        return await message.answer(t("choose_language", "uz"), reply_markup=get_language_keyboard())

    lang = user.language or LANG_UZ
    if user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    payload = extract_message_payload(message)
    if not payload:
        return await message.answer(t("inquiry_type_prompt", lang))

    await state.set_state(AutoInquiryState.confirming)
    await state.update_data(**payload)

    await message.reply(
        t("auto_inquiry_confirm_prompt", lang),
        reply_markup=get_auto_inquiry_confirm_keyboard(lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
