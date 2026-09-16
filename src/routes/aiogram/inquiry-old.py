from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, LinkPreviewOptions
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from pydantic import BaseModel
from src.app.enums import create_user_info
from src.app.filters import is_private_message
from src.app.keyboards import inquiry_main_menu, inquiry_sections, get_main_menu
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.post import Post
from src.models.user import User
from src.routes.deps.db_session import DBSession
from sulguk import SULGUK_PARSE_MODE

inquiry_router = Router(name="inquiry")
# inquiry_groups = {
#     '🛡  Ijtimoiy himoya': "@hqplus_boshqa",
#     '👨🏻‍🎓 Ta’lim': "@hqplus_talim",
#     '👩🏻‍💼 Mehnat': "@hqplus_mehnat",
#     '🏘  Uy-joy': "@hqplus_boshqa",
#     '🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya': "@hqplus_boshqa",
#     'Boshqa': "@hqplus_boshqa"
# }

inquiry_groups = {
    '🛡  Ijtimoiy himoya': "@huquqplus_ijtimoiyhimoya",
    '👨🏻‍🎓 Ta’lim': "@huquqplus_talim",
    '👩🏻‍💼 Mehnat': "@huquqplus_mehnat",
    '🏘  Uy-joy': "@huquqplus_uyjoy",
    '🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya': "@huquqplus_tibbiy",
    'Boshqa': "@huquqplus_boshqa"
}


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


def fix_charset(text: str) -> str:
    return text.encode('latin-1', errors='replace').decode('utf-8', errors='replace')


@inquiry_router.message(InquiryState.custom_question, F.text == "📁 Boʻlimlar")
async def return_to_inquiry(message: Message, state: FSMContext):
    await state.set_state(InquiryState.section)
    await message.answer("Quyidagilardan sizni qiziqtirgan savol tegishli bo'lgan bo'limni tanlang!",
                         reply_markup=inquiry_main_menu())


@inquiry_router.message(InquiryState.section, F.text == "⬅️ Asosiy menyu")
@inquiry_router.message(InquiryState.custom_question, F.text == "⬅️ Asosiy menyu")
@inquiry_router.message(InquiryState.custom_question, F.text == "❌ Bekor qilish")
async def return_to_main(message: Message, state: FSMContext):
    await state.clear()
    return await message.answer("Asosiy Menyu", reply_markup=get_main_menu())


@inquiry_router.message(InquiryState.received_answer, F.text == "✅ Ha")
async def was_useful(message: Message, state: FSMContext, db_session: DBSession):
    data = InquiryStateData.model_validate(await state.get_data())
    if data.inquiry_id and (inquiry := Inquiry.get_by_id(data.inquiry_id, db_session)):
        inquiry.close(False, db_session)

    await state.clear()
    return await message.answer("Sizga yordam bera olganimizdan xursandmiz!", reply_markup=get_main_menu())


@inquiry_router.message(InquiryState.received_answer, F.text == "❌ Yoʻq")
async def not_useful(message: Message, state: FSMContext, db_session: DBSession):
    data = InquiryStateData.model_validate(await state.get_data())
    await state.set_state(InquiryState.custom_question)
    if data.inquiry_id and (inquiry := Inquiry.get_by_id(data.inquiry_id, db_session)):
        inquiry.close(False, db_session)

    return await message.answer(
        "❓Unda o‘z savolingizni matn, ovozli yoki video xabar ko‘rinishida yuboring.",
        reply_markup=ReplyKeyboardRemove())


@inquiry_router.message(F.text == "📩 Savol yuborish", is_private_message)
async def start_inquiry(message: Message, state: FSMContext):
    await state.set_state(InquiryState.section)
    await message.answer("👇 Quyidagi tugmalar orqali o‘zingizga kerakli bo‘limni tanlang va o‘z savolingizni "
                         "yuboring", reply_markup=inquiry_main_menu())


@inquiry_router.message(InquiryState.section)
async def select_section(message: Message, state: FSMContext, db_session: DBSession):
    if message.text not in inquiry_sections.keys():
        return await message.answer(
            "Iltimos quyida ko'rsatilgan bo'limlardan birini tanlang", reply_markup=inquiry_main_menu())

    category = inquiry_sections[message.text]
    await state.update_data(section=category, section_name=message.text)
    await state.set_state(InquiryState.custom_question)
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Bekor qilish")
    await message.answer(
        "❓O‘z savolingizni matn, ovozli yoki video xabar ko‘rinishida yuboring.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )


@inquiry_router.message(InquiryState.custom_question)
async def send_custom_question(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    data = InquiryStateData.model_validate(await state.get_data())
    group_id = inquiry_groups[data.section_name] if data.section_name in inquiry_groups else inquiry_groups["Boshqa"]
    user = User.get_by_user_id(message.from_user.id, db_session)
    if not user:
        await state.clear()
        await message.answer(
            "Siz haqingizda ma'lumot topilmadi. Iltimos, botni qayta ishga tushirish uchun /start buyrug'ini bosing.",
            reply_markup=get_main_menu()
        )
        return
    user_context = create_user_info(user)

    if message.text:
        media_data = None
        media_type = InquiryMediaType.text
        message_content = message.text
        sending_message = f"<p><blockquote>{message.text}</blockquote></p>{user_context}"
        group_message = await bot.send_message(
            chat_id=group_id, text=sending_message,
            parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))
    elif message.voice:
        media_data = message.voice.json()
        media_type = InquiryMediaType.voice
        message_content = message.voice.file_id
        group_message = await bot.send_voice(
            chat_id=group_id,
            voice=message.voice.file_id,
            caption=user_context,
            parse_mode=SULGUK_PARSE_MODE
        )
    elif message.video_note:
        media_data = message.video_note.model_dump_json()
        media_type = InquiryMediaType.video_note
        message_content = message.video_note.file_id
        await bot.send_video_note(chat_id=group_id, video_note=message_content)
        group_message = await bot.send_message(
            chat_id=group_id,
            text=f"<b>Yuqoridagi video xabarga javob yuborish uchun ushbu xabarni tanlang.</b><br/> {user_context}",
            parse_mode=SULGUK_PARSE_MODE)
    elif message.video:
        media_data = message.video.model_dump_json()
        media_type = InquiryMediaType.video
        message_content = message.video.file_id
        group_message = await bot.send_video(
            chat_id=group_id,
            video=message_content,
            caption=user_context,
            parse_mode=SULGUK_PARSE_MODE)
    else:
        return await message.answer("Iltimos savolingizni matn, video yoki ovozli xabar ko'rinishida yuboring")

    inquiry = Inquiry(
        section_name=data.section_name,
        question=message_content,
        question_mediatype=media_type,
        question_media=media_data,
        private_question_id=message.message_id,
        group_question_id=group_message.message_id,
        group_id=group_id,
        bot_id=bot.id,
        user_id=message.from_user.id)

    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)

    await state.set_state(InquiryState.awaiting_response)
    await state.update_data(inquiry_id=inquiry.id, group_question_id=group_message.message_id)

    markup = ReplyKeyboardBuilder()
    markup.button(text="❌ Bekor qilish")
    await message.answer(
        """
        <p>✅ Savolingiz muvaffaqiyatli qabul qilindi. Iltimos yuristlarimiz javobini kuting. </p>
<p>⏳Odatda 1-2 ish kunida javob berishga harakat qilamiz.</p>
<p>Telegram kanalimizga obuna boʻlishni unutmang:</p>
<p>👉 https://t.me/huquqplus</p>
""",
        reply_markup=markup.as_markup(resize_keyboard=True), parse_mode=SULGUK_PARSE_MODE)


@inquiry_router.message(InquiryState.awaiting_response, F.text == "❌ Bekor qilish")
async def awaiting_response(message: Message, state: FSMContext):
    await state.set_state(InquiryState.confirm_cancellation)
    markup = ReplyKeyboardBuilder()
    markup.button(text="Yoʻq")
    markup.button(text="Ha")
    return await message.answer(
        "Amaldagi murojaatingiz o'chirib yuborildai va ko'rib chiqilmaydi. Ishonchingiz komilmi?",
        reply_markup=markup.adjust(2).as_markup(resize_keyboard=True))


@inquiry_router.message(InquiryState.confirm_cancellation)
async def confirm_cancellation(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    if message.text == "Ha":
        data = await state.get_data()
        chat_id = inquiry_groups[data["section_name"]]

        if inquiry := Inquiry.get_by_message_id(chat_id, data['group_question_id'], bot.id, db_session):
            inquiry.status = InquiryStatus.cancelled
            inquiry.updated_at = str(datetime.now())

            db_session.add(inquiry)
            db_session.commit()
            try:
                await bot.delete_message(
                    chat_id=chat_id,
                    message_id=inquiry.group_question_id)
            except Exception as e:
                print("Failed to delete message in group: ", e)

        await state.clear()
        return await message.answer("Murojaatingiz muvofaqiyatli bekor qilindi!", reply_markup=get_main_menu())
    else:
        await state.set_state(InquiryState.awaiting_response)
        markup = ReplyKeyboardBuilder()
        markup.button(text="❌ Bekor qilish")
        return await message.answer(
            "Savolingiz javob kutmoqda!", reply_markup=markup.as_markup(resize_keyboard=True))
