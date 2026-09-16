import html
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    LinkPreviewOptions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from pydantic import BaseModel
from sulguk import SULGUK_PARSE_MODE

from src.app.enums import create_user_info
from src.app.filters import is_private_message
from src.app.keyboards import (
    inquiry_main_menu,
    inquiry_sections,
    get_main_menu,
    get_low_rating_action_keyboard,
    get_inquiry_followup_cancel_keyboard,
)
from src.routes.aiogram.inquiry_archive import InquiryFollowupState
from src.app.translations import t, LANG_UZ, LANG_RU
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.user import User
from src.config.settings import settings
from src.routes.deps.db_session import DBSession

inquiry_router = Router(name="inquiry")


class InquiryState(StatesGroup):
    inquiry_id = State()
    section_name = State()
    group_question_id = State()

    section = State()
    custom_question = State()
    awaiting_response = State()
    confirm_cancellation = State()
    received_answer = State()


class InquiryStateData(BaseModel):
    section_name: str | None = None
    group_question_id: int | None = None
    inquiry_id: int | None = None
    section: int | None = None


def get_block_button_markup(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block_user:{user_id}")]
        ]
    )


@inquiry_router.message(
    InquiryState.custom_question,
    F.text.in_([t("inquiry_sections_btn", "uz"), t("inquiry_sections_btn", "ru"), "📁 Boʻlimlar", "📁 Разделы"]),
)
async def return_to_inquiry(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.set_state(InquiryState.section)
    await message.answer(
        t("inquiry_select_section", lang),
        reply_markup=inquiry_main_menu(lang),
    )


@inquiry_router.message(
    InquiryState.section,
    F.text.in_([t("btn_back_main", "uz"), t("btn_back_main", "ru"), "⬅️ Asosiy menyu", "⬅️ Главное меню"]),
)
@inquiry_router.message(
    InquiryState.custom_question,
    F.text.in_([
        t("btn_back_main", "uz"), t("btn_back_main", "ru"),
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
        "⬅️ Asosiy menyu", "⬅️ Главное меню", "❌ Bekor qilish", "❌ Отмена"
    ]),
)
async def return_to_main(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    return await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))


class InquiryFeedbackState(StatesGroup):
    waiting_for_feedback = State()


@inquiry_router.callback_query(F.data.startswith("rate:inquiry:"))
async def handle_inquiry_rating(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    parts = query.data.split(":")
    inquiry_id = int(parts[2])
    stars = int(parts[3])

    inquiry = Inquiry.get_by_id(inquiry_id, db_session)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if inquiry:
        inquiry.rating = stars
        inquiry.rated_at = datetime.now()
        inquiry.status = InquiryStatus.closed
        db_session.add(inquiry)
        db_session.commit()

    await query.answer(f"Bahoyingiz: {stars} ⭐", show_alert=False)

    if stars <= 2:
        text = f"{t('rate_received_thanks', lang)}<br/><br/>{t('rate_low_ask_again', lang)}"
        await query.message.edit_text(
            text,
            reply_markup=get_low_rating_action_keyboard(inquiry_id, lang),
            parse_mode=SULGUK_PARSE_MODE
        )
    else:
        text = f"{t('rate_received_thanks', lang)}<br/><br/>{t('rate_leave_feedback', lang)}"
        await query.message.edit_text(text, parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(InquiryFeedbackState.waiting_for_feedback)
    await state.update_data(rating_inquiry_id=inquiry_id)


@inquiry_router.callback_query(F.data == "inquiry:ask_again")
async def handle_ask_again_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    data = await state.get_data()
    inquiry_id = data.get("rating_inquiry_id")
    if inquiry_id:
        inquiry = db_session.get(Inquiry, inquiry_id)
        if inquiry:
            await state.set_state(InquiryFollowupState.waiting_for_message)
            await state.update_data(parent_id=inquiry.id, section_name=inquiry.section_name)
            prompt = t("follow_up_prompt", lang).format(id=inquiry.id)
            return await query.message.edit_text(
                prompt,
                reply_markup=get_inquiry_followup_cancel_keyboard(inquiry.id, lang),
                parse_mode=SULGUK_PARSE_MODE
            )

    await state.clear()
    await state.set_state(InquiryState.section)
    await query.message.delete()
    await query.message.answer(
        t("inquiry_select_section", lang),
        reply_markup=inquiry_main_menu(lang),
    )


@inquiry_router.message(InquiryFeedbackState.waiting_for_feedback, is_private_message)
async def handle_feedback_message(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text in [
        t("menu_profile", "uz"), t("menu_profile", "ru"),
        t("menu_inquiry", "uz"), t("menu_inquiry", "ru"),
        t("menu_appointment", "uz"), t("menu_appointment", "ru"),
        t("menu_about_us", "uz"), t("menu_about_us", "ru"),
        t("menu_help", "uz"), t("menu_help", "ru"),
        t("btn_change_lang", "uz"), t("btn_change_lang", "ru"),
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
    ]:
        await state.clear()
        return

    data = await state.get_data()
    inquiry_id = data.get("rating_inquiry_id")
    if inquiry_id:
        inquiry = Inquiry.get_by_id(inquiry_id, db_session)
        if inquiry and message.text:
            inquiry.feedback = message.text.strip()
            db_session.add(inquiry)
            db_session.commit()

    await state.clear()
    await message.answer(t("feedback_recorded", lang), reply_markup=get_main_menu(lang))


@inquiry_router.message(
    InquiryState.received_answer,
    F.text.in_([t("btn_yes", "uz"), t("btn_yes", "ru"), "✅ Ha", "✅ Да"]),
)
async def was_useful(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    data = InquiryStateData.model_validate(await state.get_data())
    if data.inquiry_id and (inquiry := Inquiry.get_by_id(data.inquiry_id, db_session)):
        inquiry.close(False, db_session)

    await state.clear()
    return await message.answer(t("rate_received_thanks", lang), reply_markup=get_main_menu(lang))


@inquiry_router.message(
    InquiryState.received_answer,
    F.text.in_([t("btn_no", "uz"), t("btn_no", "ru"), "❌ Yoʻq", "❌ Нет"]),
)
async def not_useful(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    data = InquiryStateData.model_validate(await state.get_data())
    await state.set_state(InquiryState.custom_question)
    if data.inquiry_id and (inquiry := Inquiry.get_by_id(data.inquiry_id, db_session)):
        inquiry.close(False, db_session)

    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    return await message.answer(
        t("inquiry_send_prompt", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@inquiry_router.message(
    F.text.in_([t("menu_inquiry", "uz"), t("menu_inquiry", "ru"), "📩 Savol yuborish", "📩 Задать вопрос"]),
    is_private_message,
)
async def start_inquiry(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    if not user:
        return await message.answer(
            t("user_not_found", "uz"),
            reply_markup=get_main_menu(),
        )

    lang = user.language or LANG_UZ
    if user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(InquiryState.section)
    await message.answer(
        t("inquiry_select_section", lang),
        reply_markup=inquiry_main_menu(lang),
    )


@inquiry_router.message(InquiryState.section)
async def select_section(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text not in inquiry_sections.keys():
        return await message.answer(
            t("inquiry_select_section", lang),
            reply_markup=inquiry_main_menu(lang),
        )

    category = inquiry_sections[message.text]
    await state.update_data(section=category, section_name=message.text)
    await state.set_state(InquiryState.custom_question)
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_cancel", lang))
    await message.answer(
        t("inquiry_send_prompt", lang),
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@inquiry_router.message(InquiryState.custom_question)
async def send_custom_question(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        await state.clear()
        return await message.answer(
            t("user_not_found", lang),
            reply_markup=get_main_menu(lang),
        )

    if user.is_blocked:
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    data = InquiryStateData.model_validate(await state.get_data())
    inquiry_groups = settings.get_inquiry_groups()
    group_id = inquiry_groups.get(data.section_name) or inquiry_groups.get("Boshqa") or settings.LAWYER_APPOINTMENT_GROUP_ID

    user_context = create_user_info(user, with_link=True, lang=lang)

    if message.text:
        media_data = None
        media_type = InquiryMediaType.text
        message_content = message.text
        sending_message = f"<p><blockquote>{html.escape(message.text)}</blockquote></p>{user_context}"
        group_message = await bot.send_message(
            chat_id=group_id,
            text=sending_message,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    elif message.voice:
        media_data = message.voice.model_dump_json()
        media_type = InquiryMediaType.voice
        message_content = message.voice.file_id
        group_message = await bot.send_voice(
            chat_id=group_id,
            voice=message.voice.file_id,
            caption=user_context,
            parse_mode=SULGUK_PARSE_MODE,
        )
    elif message.video_note:
        media_data = message.video_note.model_dump_json()
        media_type = InquiryMediaType.video_note
        message_content = message.video_note.file_id
        await bot.send_video_note(chat_id=group_id, video_note=message_content)
        group_message = await bot.send_message(
            chat_id=group_id,
            text=f"<b>Yuqoridagi video xabarga javob yuborish uchun ushbu xabarni tanlang.</b><br/> {user_context}",
            parse_mode=SULGUK_PARSE_MODE,
        )
    elif message.video:
        media_data = message.video.model_dump_json()
        media_type = InquiryMediaType.video
        message_content = message.video.file_id
        group_message = await bot.send_video(
            chat_id=group_id,
            video=message_content,
            caption=user_context,
            parse_mode=SULGUK_PARSE_MODE,
        )
    elif message.document:
        media_data = message.document.model_dump_json()
        media_type = InquiryMediaType.document
        doc_caption = f"📄 <b>Ilova qilingan hujjat:</b> {html.escape(message.document.file_name or 'Hujjat')}"
        if message.caption:
            doc_caption += f"<br/><blockquote>{html.escape(message.caption)}</blockquote>"
        message_content = doc_caption
        group_message = await bot.send_document(
            chat_id=group_id,
            document=message.document.file_id,
            caption=f"{doc_caption}<br/>{user_context}",
            parse_mode=SULGUK_PARSE_MODE,
        )
    elif message.photo:
        photo = message.photo[-1]
        media_data = photo.model_dump_json()
        media_type = InquiryMediaType.photo
        photo_caption = "📷 <b>Ilova qilingan fotohujjat</b>"
        if message.caption:
            photo_caption += f"<br/><blockquote>{html.escape(message.caption)}</blockquote>"
        message_content = photo_caption
        group_message = await bot.send_photo(
            chat_id=group_id,
            photo=photo.file_id,
            caption=f"{photo_caption}<br/>{user_context}",
            parse_mode=SULGUK_PARSE_MODE,
        )
    else:
        return await message.answer(t("inquiry_type_prompt", lang))

    inquiry = Inquiry(
        section_name=data.section_name,
        question=message_content,
        question_mediatype=media_type,
        question_media=media_data,
        private_question_id=message.message_id,
        group_question_id=group_message.message_id,
        group_id=group_id,
        bot_id=bot.id,
        user_id=message.from_user.id,
    )

    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)

    await state.clear()

    await message.answer(
        t("inquiry_received", lang),
        reply_markup=get_main_menu(lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@inquiry_router.message(
    InquiryState.awaiting_response,
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Отмена"]),
)
async def awaiting_response(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.set_state(InquiryState.confirm_cancellation)
    markup = ReplyKeyboardBuilder()
    markup.button(text=t("btn_no", lang))
    markup.button(text=t("btn_yes", lang))
    return await message.answer(
        t("inquiry_cancel_confirm", lang),
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
    )


@inquiry_router.message(InquiryState.confirm_cancellation)
async def confirm_cancellation(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text in [t("btn_yes", "uz"), t("btn_yes", "ru"), "Ha", "✅ Ha", "Да", "✅ Да"]:
        data = await state.get_data()
        inquiry_groups = settings.get_inquiry_groups()
        section_name = data.get("section_name", "Boshqa")
        chat_id = inquiry_groups.get(section_name) or inquiry_groups.get("Boshqa") or settings.LAWYER_APPOINTMENT_GROUP_ID

        if inquiry := Inquiry.get_by_message_id(chat_id, data.get('group_question_id'), bot.id, db_session):
            inquiry.status = InquiryStatus.cancelled
            inquiry.updated_at = str(datetime.now())

            db_session.add(inquiry)
            db_session.commit()
            try:
                await bot.delete_message(chat_id=chat_id, message_id=inquiry.group_question_id)
            except Exception as e:
                print("Failed to delete message in group: ", e)

        await state.clear()
        return await message.answer(t("inquiry_cancelled", lang), reply_markup=get_main_menu(lang))
    else:
        await state.set_state(InquiryState.awaiting_response)
        markup = ReplyKeyboardBuilder()
        markup.button(text=t("btn_cancel", lang))
        return await message.answer(
            t("inquiry_waiting", lang),
            reply_markup=markup.as_markup(resize_keyboard=True),
        )
