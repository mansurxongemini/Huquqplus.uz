import json
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    LinkPreviewOptions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlmodel import select, func
from sulguk import SULGUK_PARSE_MODE

from src.app.enums import create_user_info
from src.app.filters import is_private_message
from src.app.keyboards import (
    get_main_menu,
    get_inquiries_archive_keyboard,
    get_inquiry_detail_keyboard,
    get_inquiry_followup_cancel_keyboard,
)
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.user import User
from src.routes.deps.db_session import DBSession

inquiry_archive_router = Router(name="inquiry_archive")

PAGE_SIZE = 5


class InquiryFollowupState(StatesGroup):
    waiting_for_message = State()


def get_status_label(status: str, lang: str = "uz") -> str:
    labels = {
        "active": t("archive_status_active", lang),
        "replied": t("archive_status_replied", lang),
        "closed": t("archive_status_closed", lang),
        "cancelled": t("archive_status_cancelled", lang),
    }
    return labels.get(status, status)


def format_inquiry_detail_card(inquiry: Inquiry, lang: str = "uz") -> str:
    status_text = get_status_label(inquiry.status.value if hasattr(inquiry.status, "value") else str(inquiry.status), lang)
    date_str = inquiry.created_at.strftime("%d.%m.%Y %H:%M") if inquiry.created_at else "-"

    parent_info = ""
    if inquiry.parent_id:
        parent_info = f"🔗 <i>№{inquiry.parent_id}-sonli murojaat bo'yicha qo'shimcha savol</i><br/><br/>" if lang == "uz" else f"🔗 <i>Уточняющий вопрос по обращению №{inquiry.parent_id}</i><br/><br/>"

    # Format user's question
    q_type_icon = {
        InquiryMediaType.voice: "🎤 Ovozli xabar",
        InquiryMediaType.video: "📹 Video",
        InquiryMediaType.video_note: "📹 Video xabar",
        InquiryMediaType.document: "📄 Hujjat",
        InquiryMediaType.photo: "📷 Fotosurat",
    }.get(inquiry.question_mediatype, "")

    q_text = inquiry.question or ""
    if q_type_icon and q_type_icon not in q_text:
        q_text = f"{q_type_icon}<br/>{q_text}"

    # Format specialist answer
    if inquiry.status == InquiryStatus.replied and inquiry.answer:
        a_date = inquiry.replied_at.strftime("%d.%m.%Y %H:%M") if inquiry.replied_at and hasattr(inquiry.replied_at, "strftime") else (str(inquiry.replied_at)[:16] if inquiry.replied_at else "")
        a_date_str = f" <i>({a_date})</i>" if a_date else ""

        ans_type_icon = {
            InquiryMediaType.voice: "🎤 <i>Ovozli xabar orqali javob berildi</i>",
            InquiryMediaType.video: "📹 <i>Video xabar orqali javob berildi</i>",
            InquiryMediaType.video_note: "📹 <i>Video xabar orqali javob berildi</i>",
        }.get(inquiry.answer_mediatype, "")

        if ans_type_icon:
            answer_block = f"<blockquote>{ans_type_icon}</blockquote>"
        else:
            answer_block = f"<blockquote>{inquiry.answer}</blockquote>"

        ans_section = (
            f"<b>💬 Mutaxassis javobi{a_date_str}:</b><br/>"
            f"{answer_block}"
        ) if lang == "uz" else (
            f"<b>💬 Ответ специалиста{a_date_str}:</b><br/>"
            f"{answer_block}"
        )
    elif inquiry.status == InquiryStatus.active:
        ans_section = (
            "<b>💬 Mutaxassis javobi:</b><br/>"
            "<blockquote>⏳ <i>Savolingiz qabul qilingan va mutaxassislar tomonidan ko'rib chiqilmoqda. Tez orada javob taqdim etiladi.</i></blockquote>"
        ) if lang == "uz" else (
            "<b>💬 Ответ специалиста:</b><br/>"
            "<blockquote>⏳ <i>Ваш вопрос принят и находится на рассмотрении. Ответ будет предоставлен в ближайшее время.</i></blockquote>"
        )
    elif inquiry.status == InquiryStatus.cancelled:
        ans_section = (
            "<b>💬 Murojaat holati:</b><br/>"
            "<blockquote>🔴 <i>Ushbu murojaat bekor qilingan.</i></blockquote>"
        ) if lang == "uz" else (
            "<b>💬 Статус обращения:</b><br/>"
            "<blockquote>🔴 <i>Обращение было отменено.</i></blockquote>"
        )
    else:
        ans_section = (
            "<b>💬 Mutaxassis javobi:</b><br/>"
            f"<blockquote>{inquiry.answer or 'Yakunlangan'}</blockquote>"
        )

    # Rating info
    if inquiry.rating:
        stars = "⭐" * inquiry.rating
        rating_line = f"<b>⭐️ Bahongiz:</b> {stars} ({inquiry.rating}/5)" if lang == "uz" else f"<b>⭐️ Ваша оценка:</b> {stars} ({inquiry.rating}/5)"
    elif inquiry.status == InquiryStatus.replied:
        rating_line = "<b>⭐️ Bahongiz:</b> <i>Baholanmagan</i>" if lang == "uz" else "<b>⭐️ Ваша оценка:</b> <i>Не оценено</i>"
    else:
        rating_line = ""

    header_title = f"📌 <b>MUROJAAT №{inquiry.id}</b>" if lang == "uz" else f"📌 <b>ОБРАЩЕНИЕ №{inquiry.id}</b>"
    section_label = "📁 <b>Bo'lim:</b>" if lang == "uz" else "📁 <b>Раздел:</b>"
    date_label = "📅 <b>Yuborilgan sana:</b>" if lang == "uz" else "📅 <b>Дата отправки:</b>"
    status_label = "🔄 <b>Holati:</b>" if lang == "uz" else "🔄 <b>Статус:</b>"
    question_label = "❓ <b>Sizning savolingiz:</b>" if lang == "uz" else "❓ <b>Ваш вопрос:</b>"

    card = (
        f"{header_title}<br/>"
        f"{parent_info}"
        f"{section_label} {inquiry.section_name}<br/>"
        f"{date_label} {date_str}<br/>"
        f"{status_label} {status_text}<br/><br/>"
        f"{question_label}<br/>"
        f"<blockquote>{q_text}</blockquote><br/>"
        f"{ans_section}<br/>"
    )

    if rating_line:
        card += f"{rating_line}<br/>"

    return card


@inquiry_archive_router.message(
    F.text.in_([t("menu_my_inquiries", "uz"), t("menu_my_inquiries", "ru"), "🗂 Murojaatlarim arxivi", "🗂 Мои обращения"]),
    is_private_message,
)
@inquiry_archive_router.message(Command("my_inquiries"), is_private_message)
async def user_inquiries_archive_handler(message: Message, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        return await message.answer(t("user_not_found", lang))

    # Fetch inquiries count
    total_count = db_session.exec(
        select(func.count(Inquiry.id)).where(Inquiry.user_id == user.user_id)
    ).one()

    if total_count == 0:
        return await message.answer(
            t("archive_empty", lang),
            reply_markup=get_main_menu(lang),
            parse_mode=SULGUK_PARSE_MODE
        )

    # Fetch first page
    inquiries = db_session.exec(
        select(Inquiry)
        .where(Inquiry.user_id == user.user_id)
        .order_by(Inquiry.created_at.desc())
        .limit(PAGE_SIZE)
        .offset(0)
    ).all()

    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

    await message.answer(
        t("archive_title", lang),
        reply_markup=get_inquiries_archive_keyboard(inquiries, page=1, total_pages=total_pages, lang=lang),
        parse_mode=SULGUK_PARSE_MODE
    )


@inquiry_archive_router.callback_query(F.data.startswith("user:archive:page:"), is_private_message)
async def user_archive_page_callback(query: CallbackQuery, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    page = int(query.data.split(":")[3])

    total_count = db_session.exec(
        select(func.count(Inquiry.id)).where(Inquiry.user_id == query.from_user.id)
    ).one()

    total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    offset = (page - 1) * PAGE_SIZE
    inquiries = db_session.exec(
        select(Inquiry)
        .where(Inquiry.user_id == query.from_user.id)
        .order_by(Inquiry.created_at.desc())
        .limit(PAGE_SIZE)
        .offset(offset)
    ).all()

    await query.message.edit_text(
        t("archive_title", lang),
        reply_markup=get_inquiries_archive_keyboard(inquiries, page=page, total_pages=total_pages, lang=lang),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@inquiry_archive_router.callback_query(F.data == "user:archive:close", is_private_message)
async def user_archive_close_callback(query: CallbackQuery):
    await query.message.delete()
    await query.answer()


@inquiry_archive_router.callback_query(F.data.startswith("user:inquiry:view:"), is_private_message)
async def user_inquiry_view_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await state.clear()
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    inquiry_id = int(query.data.split(":")[3])
    inquiry = db_session.get(Inquiry, inquiry_id)

    if not inquiry or inquiry.user_id != query.from_user.id:
        return await query.answer("Murojaat topilmadi!", show_alert=True)

    text = format_inquiry_detail_card(inquiry, lang)
    keyboard = get_inquiry_detail_keyboard(inquiry, lang)

    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode=SULGUK_PARSE_MODE,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    await query.answer()


@inquiry_archive_router.callback_query(F.data.startswith("user:inquiry:media:"), is_private_message)
async def user_inquiry_media_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    parts = query.data.split(":")
    inquiry_id = int(parts[3])
    media_target = parts[4]  # 'question' or 'answer'

    inquiry = db_session.get(Inquiry, inquiry_id)
    if not inquiry or inquiry.user_id != query.from_user.id:
        return await query.answer("Murojaat topilmadi!", show_alert=True)

    if media_target == "question":
        mediatype = inquiry.question_mediatype
        media_json = inquiry.question_media
        caption = f"📎 №{inquiry.id}-sonli murojaatingizga ilova qilingan fayl"

        try:
            if mediatype == InquiryMediaType.voice:
                data = json.loads(media_json) if media_json else {}
                file_id = data.get("file_id") or inquiry.question
                await bot.send_voice(chat_id=query.from_user.id, voice=file_id, caption=caption)
            elif mediatype == InquiryMediaType.video_note:
                data = json.loads(media_json) if media_json else {}
                file_id = data.get("file_id") or inquiry.question
                await bot.send_video_note(chat_id=query.from_user.id, video_note=file_id)
            elif mediatype == InquiryMediaType.video:
                data = json.loads(media_json) if media_json else {}
                file_id = data.get("file_id") or inquiry.question
                await bot.send_video(chat_id=query.from_user.id, video=file_id, caption=caption)
            elif mediatype == InquiryMediaType.document:
                data = json.loads(media_json) if media_json else {}
                file_id = data.get("file_id")
                if file_id:
                    await bot.send_document(chat_id=query.from_user.id, document=file_id, caption=caption)
                else:
                    await query.answer("Fayl topilmadi", show_alert=True)
                    return
            elif mediatype == InquiryMediaType.photo:
                data = json.loads(media_json) if media_json else {}
                file_id = data.get("file_id")
                if file_id:
                    await bot.send_photo(chat_id=query.from_user.id, photo=file_id, caption=caption)
                else:
                    await query.answer("Rasm topilmadi", show_alert=True)
                    return
            await query.answer("Fayl yuborildi!", show_alert=False)
        except Exception as e:
            print("Failed to send question media:", e)
            await query.answer("Faylni yuklab bo'lmadi.", show_alert=True)

    elif media_target == "answer":
        mediatype = inquiry.answer_mediatype
        file_id = inquiry.answer
        caption = f"📎 №{inquiry.id}-sonli murojaatingiz bo'yicha mutaxassis javobi"

        try:
            if mediatype == InquiryMediaType.voice:
                await bot.send_voice(chat_id=query.from_user.id, voice=file_id, caption=caption)
            elif mediatype == InquiryMediaType.video_note:
                await bot.send_video_note(chat_id=query.from_user.id, video_note=file_id)
            elif mediatype == InquiryMediaType.video:
                await bot.send_video(chat_id=query.from_user.id, video=file_id, caption=caption)
            await query.answer("Javob fayli yuborildi!", show_alert=False)
        except Exception as e:
            print("Failed to send answer media:", e)
            await query.answer("Javob faylini yuklab bo'lmadi.", show_alert=True)


@inquiry_archive_router.callback_query(F.data.startswith("user:inquiry:followup:"), is_private_message)
async def user_inquiry_followup_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    inquiry_id = int(query.data.split(":")[3])
    inquiry = db_session.get(Inquiry, inquiry_id)

    if not inquiry or inquiry.user_id != query.from_user.id:
        return await query.answer("Murojaat topilmadi!", show_alert=True)

    await state.set_state(InquiryFollowupState.waiting_for_message)
    await state.update_data(parent_id=inquiry.id, section_name=inquiry.section_name)

    prompt = t("follow_up_prompt", lang).format(id=inquiry.id)
    await query.message.edit_text(
        prompt,
        reply_markup=get_inquiry_followup_cancel_keyboard(inquiry.id, lang),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()


@inquiry_archive_router.callback_query(F.data.startswith("user:inquiry:cancel:"), is_private_message)
async def user_inquiry_cancel_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    inquiry_id = int(query.data.split(":")[3])
    inquiry = db_session.get(Inquiry, inquiry_id)

    if not inquiry or inquiry.user_id != query.from_user.id:
        return await query.answer("Murojaat topilmadi!", show_alert=True)

    if inquiry.status == InquiryStatus.active:
        inquiry.status = InquiryStatus.cancelled
        inquiry.updated_at = datetime.now()
        db_session.add(inquiry)
        db_session.commit()

        # Delete from group if possible
        try:
            await bot.delete_message(chat_id=inquiry.group_id, message_id=inquiry.group_question_id)
        except Exception:
            pass

        await query.answer("Murojaatingiz bekor qilindi." if lang == "uz" else "Ваше обращение отменено.", show_alert=True)
    else:
        await query.answer("Bu murojaatni bekor qilib bo'lmaydi.", show_alert=True)

    # Re-render card
    text = format_inquiry_detail_card(inquiry, lang)
    keyboard = get_inquiry_detail_keyboard(inquiry, lang)
    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode=SULGUK_PARSE_MODE,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


@inquiry_archive_router.message(InquiryFollowupState.waiting_for_message, is_private_message)
async def handle_followup_message(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    # Cancel if main menu buttons pressed
    if message.text in [
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
        t("btn_back_main", "uz"), t("btn_back_main", "ru"),
        t("menu_profile", "uz"), t("menu_profile", "ru"),
        t("menu_inquiry", "uz"), t("menu_inquiry", "ru"),
        t("menu_appointment", "uz"), t("menu_appointment", "ru"),
        t("menu_my_inquiries", "uz"), t("menu_my_inquiries", "ru"),
        "❌ Bekor qilish", "❌ Отмена", "⬅️ Asosiy menyu", "⬅️ Главное меню"
    ]:
        await state.clear()
        return await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))

    if user.is_blocked:
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    data = await state.get_data()
    parent_id = data.get("parent_id")
    section_name = data.get("section_name", "Boshqa")

    parent_inquiry = db_session.get(Inquiry, parent_id) if parent_id else None

    # Determine group
    inquiry_groups = settings.get_inquiry_groups()
    group_id = inquiry_groups.get(section_name) or inquiry_groups.get("Boshqa") or settings.LAWYER_APPOINTMENT_GROUP_ID

    user_context = create_user_info(user, with_link=True, lang=lang)

    prev_msg_link = None
    reply_to_id = None
    if parent_inquiry and parent_inquiry.group_question_id:
        parent_gid_str = str(parent_inquiry.group_id)
        if str(group_id) == parent_gid_str:
            reply_to_id = parent_inquiry.group_question_id

        if parent_gid_str.startswith("-100"):
            clean_gid = parent_gid_str[4:]
            prev_msg_link = f"https://t.me/c/{clean_gid}/{parent_inquiry.group_question_id}"
        elif parent_gid_str.startswith("@"):
            clean_gid = parent_gid_str[1:]
            prev_msg_link = f"https://t.me/{clean_gid}/{parent_inquiry.group_question_id}"
        else:
            # Telegram basic (oddiy) guruhlarda t.me/c/ havolalari ishlamaydi (faqat superguruhlarda ishlaydi).
            # Shuning uchun havola emas, Telegramning o'zining reply (javob) mexanizmi orqali ulanadi.
            prev_msg_link = None

    if prev_msg_link:
        link_html = f'🔗 <b>Oldingi murojaat:</b> <a href="{prev_msg_link}">№{parent_id}-sonli murojaatga o\'tish ↗️</a><br/>'
    else:
        link_html = f"👆 <b>№{parent_id}-sonli murojaatga javoban (reply qilib) yuborildi.</b><br/>"

    group_header = (
        f"🔄 <b>QO'SHIMCHA SAVOL (№{parent_id}-sonli murojaat bo'yicha)</b><br/>"
        f"📁 <b>Bo'lim:</b> {section_name}<br/>"
        f"{link_html}<br/>"
        f"❓ <b>Yangi qo'shimcha savol:</b><br/>"
    )

    group_markup = None
    if prev_msg_link:
        group_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"🔗 Oldingi murojaatni ko'rish (№{parent_id})", url=prev_msg_link)]
            ]
        )

    async def safe_send_group(send_func, **kwargs):
        try:
            return await send_func(**kwargs)
        except Exception:
            if kwargs.get("reply_to_message_id"):
                kwargs.pop("reply_to_message_id", None)
                return await send_func(**kwargs)
            raise

    if message.text:
        media_data = None
        media_type = InquiryMediaType.text
        message_content = message.text
        sending_text = f"{group_header}<blockquote>{message.text}</blockquote><br/>{user_context}"
        group_message = await safe_send_group(
            bot.send_message,
            chat_id=group_id,
            text=sending_text,
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    elif message.voice:
        media_data = message.voice.model_dump_json()
        media_type = InquiryMediaType.voice
        message_content = message.voice.file_id
        group_message = await safe_send_group(
            bot.send_voice,
            chat_id=group_id,
            voice=message.voice.file_id,
            caption=f"{group_header}{user_context}",
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    elif message.video_note:
        media_data = message.video_note.model_dump_json()
        media_type = InquiryMediaType.video_note
        message_content = message.video_note.file_id
        await bot.send_video_note(chat_id=group_id, video_note=message_content)
        group_message = await safe_send_group(
            bot.send_message,
            chat_id=group_id,
            text=f"{group_header}<b>Yuqoridagi video xabarga javob berish uchun ushbu xabarni tanlang.</b><br/>{user_context}",
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    elif message.video:
        media_data = message.video.model_dump_json()
        media_type = InquiryMediaType.video
        message_content = message.video.file_id
        group_message = await safe_send_group(
            bot.send_video,
            chat_id=group_id,
            video=message_content,
            caption=f"{group_header}{user_context}",
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    elif message.document:
        media_data = message.document.model_dump_json()
        media_type = InquiryMediaType.document
        doc_caption = f"📄 <b>Ilova qilingan hujjat:</b> {message.document.file_name or 'Hujjat'}"
        if message.caption:
            doc_caption += f"<br/><blockquote>{message.caption}</blockquote>"
        message_content = doc_caption
        group_message = await safe_send_group(
            bot.send_document,
            chat_id=group_id,
            document=message.document.file_id,
            caption=f"{group_header}{doc_caption}<br/>{user_context}",
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    elif message.photo:
        photo = message.photo[-1]
        media_data = photo.model_dump_json()
        media_type = InquiryMediaType.photo
        photo_caption = "📷 <b>Ilova qilingan fotosurat</b>"
        if message.caption:
            photo_caption += f"<br/><blockquote>{message.caption}</blockquote>"
        message_content = photo_caption
        group_message = await safe_send_group(
            bot.send_photo,
            chat_id=group_id,
            photo=photo.file_id,
            caption=f"{group_header}{photo_caption}<br/>{user_context}",
            reply_to_message_id=reply_to_id,
            reply_markup=group_markup,
            parse_mode=SULGUK_PARSE_MODE
        )
    else:
        return await message.answer(t("inquiry_type_prompt", lang))

    # Save new follow-up inquiry linked to parent_id
    new_inquiry = Inquiry(
        section_name=section_name,
        question=message_content,
        question_mediatype=media_type,
        question_media=media_data,
        private_question_id=message.message_id,
        group_question_id=group_message.message_id,
        group_id=group_id,
        bot_id=bot.id,
        user_id=message.from_user.id,
        parent_id=parent_id,
        status=InquiryStatus.active
    )

    db_session.add(new_inquiry)
    db_session.commit()
    db_session.refresh(new_inquiry)

    await state.clear()

    await message.answer(
        t("follow_up_received", lang),
        reply_markup=get_main_menu(lang),
        parse_mode=SULGUK_PARSE_MODE
    )
