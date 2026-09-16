from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, LinkPreviewOptions
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE
from src.app.enums import create_user_info
from src.app.filters import is_group_message, reply_to_my_message
from src.app.keyboards import inquiry_sections
from src.app.timeutils import tz
from src.config.redis_queue import telegram_storage
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.routes.aiogram.inquiry import InquiryState
from src.routes.deps.db_session import DBSession
from aiogram.exceptions import TelegramBadRequest
router = Router(name="group")


async def try_with_reply(handler, reply_to_message_id: int, **kwargs):
    try:
        return await handler(reply_to_message_id=reply_to_message_id,**kwargs)
    except TelegramBadRequest as e:
        if "message to be replied not found" in e.message:
            return await handler(**kwargs)
        else:
            raise e


@router.message(is_group_message, reply_to_my_message)
async def handle_response(message: Message, db_session: DBSession, bot: Bot):
    group_id = "@" + message.chat.username
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=message.reply_to_message.message_id,
        bot_id=bot.id,
        session=db_session)

    if not inquiry or inquiry.status in [InquiryStatus.closed, InquiryStatus.cancelled]:
        return

    if message.text:
        inquiry.answer_mediatype = InquiryMediaType.text
        inquiry.answer = message.text
        handler = bot.send_message
        args = dict(
            chat_id=inquiry.user_id,
            text=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.voice:
        inquiry.answer_media = message.voice.json()
        inquiry.answer_mediatype = InquiryMediaType.voice
        inquiry.answer = message.voice.file_id
        handler = bot.send_voice
        args = dict(
            chat_id=inquiry.user_id,
            voice=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.video_note:
        inquiry.answer_media = message.video_note.json()
        inquiry.answer_mediatype = InquiryMediaType.video_note
        inquiry.answer = message.video_note.file_id
        handler = bot.send_video_note
        args = dict(
            chat_id=inquiry.user_id,
            video_note=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.video:
        inquiry.answer_media = message.video.json()
        inquiry.answer_mediatype = InquiryMediaType.video
        inquiry.answer = message.video.file_id
        handler = bot.send_video
        args = dict(
            chat_id=inquiry.user_id,
            video=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    else:
        return await message.answer("Bunday turdagi xabarlar qabul qilinmaydi.")

    try:
        await edit_message(inquiry, message, bot)

        storage_key = StorageKey(user_id=inquiry.user_id, chat_id=inquiry.user_id, bot_id=bot.id)
        user_state = FSMContext(telegram_storage, storage_key)

        await user_state.set_state(InquiryState.received_answer)
        await user_state.update_data(
            inquiry_id=inquiry.id,
            section_name=inquiry.section_name,
            group_question_id=message.reply_to_message.message_id,
            section=inquiry_sections[inquiry.section_name]
        )

        inquiry.group_answer_id = message.message_id
        inquiry.responder_id = message.from_user.id
        inquiry.replied_at = inquiry.updated_at = str(datetime.now())
        inquiry.status = InquiryStatus.replied
        db_session.add(inquiry)
        db_session.commit()

        await try_with_reply(handler, **args)

        markup = ReplyKeyboardBuilder()
        markup.button(text="❌ Yoʻq")
        markup.button(text="✅ Ha")
        reply_markup = markup.adjust(2).as_markup(resize_keyboard=True)

        await bot.send_message(
            chat_id=inquiry.user_id,
            text="<p>❓Yurist javobi sizni qoniqtirdimi?</p><p>Agar qoniqmagan bo‘lsangiz ❌ Yo‘q tugmasini "
                 "bosib qayta savol yuborishingiz mumkin...</p>",
            reply_markup=reply_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    except TelegramBadRequest as e:
        if "restricted" in e.message:
            await message.reply(
                "Foydalanuvchi bu formatdagi xabarlarni ta'qiqlagan. Iltimos javobingizni boshqa formatda yuboring.")
            return await bot.send_message(
                chat_id=inquiry.user_id,
                text="Sizning xafsizlik sozlamalaringiz ovozli/video xabarlar ta'qiqlanganligi sababli huquqshunos "
                     "javobini yubora olmadik. Iltimos huquqshunosimiz boshqa formatda xabar yuborishini kuting yoki "
                     "sozlamalaringizni o'zgartiring."
            )
        else:
            raise e


async def edit_message(inquiry: Inquiry, message: Message, bot: Bot):
    group_id = "@" + message.chat.username
    user_context = create_user_info(inquiry.user)
    if message.reply_to_message.text:
        sending_message = f"<p><blockquote>{inquiry.question}</blockquote></p>{user_context}"
        await bot.edit_message_text(
            chat_id=group_id,
            text=sending_message + replied_context(message),
            message_id=message.reply_to_message.message_id,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(url=f"https://t.me/{message.chat.username}/{message.message_id}")
        )
    elif message.reply_to_message.voice or message.reply_to_message.video:
        await bot.edit_message_caption(
            chat_id=group_id,
            caption=user_context + replied_context(message),
            message_id=message.reply_to_message.message_id,
            parse_mode=SULGUK_PARSE_MODE
        )


def replied_context(message: Message):
    return f"""
        <hr/>
        <b>✅ Murojaatga javob berildi:</b><br/>
        <b>Javob Vaqti: </b>{message.date.astimezone(tz)}<br/>
        <b>Xabar: </b><a href="https://t.me/{message.chat.username}/{message.message_id}">Javobga havola</a><br/>
        <b>Muallif: </b><a href="tg://user?id={message.from_user.id}">{message.from_user.first_name} {message.from_user.last_name}</a>
    """
