import html
import logging
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
)
from sqlmodel import select, func
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.html_utils import escape_multiline
from src.app.inquiry_card import followup_header_html, payload_from_message
from src.app.link_utils import build_group_message_link
from src.app.question_delivery import post_inquiry_to_group
from src.app.keyboards import (
    get_role_menu,
    get_inquiries_archive_keyboard,
    get_inquiry_detail_keyboard,
    get_inquiry_followup_cancel_keyboard,
)
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.user import User
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

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


QUESTION_MEDIA_KEYS = {
    InquiryMediaType.voice: "media_voice",
    InquiryMediaType.video: "media_video",
    InquiryMediaType.video_note: "media_video_note",
    InquiryMediaType.document: "media_document",
    InquiryMediaType.photo: "media_photo",
}


def _question_html(inquiry: Inquiry, lang: str) -> str:
    if inquiry.question_mediatype == InquiryMediaType.text:
        return escape_multiline(inquiry.question)
    question = inquiry.question or ""
    if not question or (" " not in question and "<" not in question):  # eski yozuvlarda — file_id
        return f"📎 {t(QUESTION_MEDIA_KEYS.get(inquiry.question_mediatype, 'media_document'), lang)}"
    return question  # bot tomonidan tayyorlangan tavsif (HTML)


def _answer_block(inquiry: Inquiry, lang: str) -> str:
    if inquiry.answer_mediatype in (InquiryMediaType.voice,):
        return t("arch_answer_voice", lang)
    if inquiry.answer_mediatype in (InquiryMediaType.video, InquiryMediaType.video_note):
        return t("arch_answer_video", lang)
    if inquiry.answer_mediatype in (InquiryMediaType.photo, InquiryMediaType.document):
        return t("arch_answer_file", lang)
    return escape_multiline(inquiry.answer)


def format_inquiry_detail_card(inquiry: Inquiry, lang: str = "uz") -> str:
    status_text = get_status_label(inquiry.status.value if hasattr(inquiry.status, "value") else str(inquiry.status), lang)
    date_str = inquiry.created_at.strftime("%d.%m.%Y %H:%M") if inquiry.created_at else "-"
    parts = [t("arch_title", lang, id=inquiry.id) + "<br/>"]
    if inquiry.parent_id:
        parts.append(t("arch_followup_of", lang, id=inquiry.parent_id))
    parts.append(t("arch_meta", lang, section=html.escape((inquiry.section_name or "—").strip()), date=date_str, status=status_text))
    if inquiry.status == InquiryStatus.active:
        if inquiry.assigned_at:
            parts.append("<br/>" + t("arch_assigned", lang, date=inquiry.assigned_at.strftime("%d.%m.%Y %H:%M")))
        else:
            parts.append("<br/>" + t("arch_waiting_assign", lang))
    parts.append("<br/><br/>" + t("arch_your_question", lang) + f"<br/><blockquote>{_question_html(inquiry, lang)}</blockquote><br/>")

    if inquiry.status == InquiryStatus.replied and inquiry.answer:
        a_date = f" <i>({inquiry.replied_at:%d.%m.%Y %H:%M})</i>" if isinstance(inquiry.replied_at, datetime) else ""
        parts.append(t("arch_answer_title", lang, date=a_date) + f"<br/><blockquote>{_answer_block(inquiry, lang)}</blockquote><br/>")
    elif inquiry.status == InquiryStatus.active:
        parts.append(t("arch_answer_title", lang, date="") + f"<br/><blockquote>{t('arch_pending_answer', lang)}</blockquote><br/>")
    elif inquiry.status == InquiryStatus.cancelled:
        parts.append(t("arch_status_title", lang) + f"<br/><blockquote>{t('arch_cancelled', lang)}</blockquote><br/>")
    else:
        body = _answer_block(inquiry, lang) if inquiry.answer else t("arch_closed", lang)
        parts.append(t("arch_answer_title", lang, date="") + f"<br/><blockquote>{body}</blockquote><br/>")

    if inquiry.rating:
        parts.append(t("arch_rating", lang, stars=f"{'⭐' * inquiry.rating} ({inquiry.rating}/5)") + "<br/>")
    elif inquiry.status == InquiryStatus.replied:
        parts.append(t("arch_rating", lang, stars=t("arch_not_rated", lang)) + "<br/>")
    return "".join(parts)


@inquiry_archive_router.message(
    F.text.in_([t("menu_my_inquiries", "uz"), t("menu_my_inquiries", "oz"), t("menu_my_inquiries", "ru"), "🗂 Murojaatlarim arxivi", "🗂 Мурожаатларим архиви", "🗂 Мои обращения"]),
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
            reply_markup=get_role_menu(message.from_user.id, lang, db_session),
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
            logger.warning("Failed to send question media: %s", e)
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
            logger.warning("Failed to send answer media: %s", e)
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

        cancel_alert = t("arch_cancel_done", lang)
        await query.answer(cancel_alert, show_alert=True)
    else:
        err_alert = t("arch_cancel_impossible", lang)
        await query.answer(err_alert, show_alert=True)

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
        t("menu_benefits", "uz"), t("menu_benefits", "oz"), t("menu_benefits", "ru"),
        t("menu_inquiry", "uz"), t("menu_inquiry", "ru"),
        t("menu_appointment", "uz"), t("menu_appointment", "ru"),
        t("menu_my_inquiries", "uz"), t("menu_my_inquiries", "ru"),
        "❌ Bekor qilish", "❌ Отмена", "⬅️ Asosiy menyu", "⬅️ Главное меню"
    ]:
        await state.clear()
        return await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

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

    payload = payload_from_message(message)
    if payload is None:
        return await message.answer(t("inquiry_type_prompt", lang))

    parent_link, reply_to_id = None, None
    if parent_inquiry and parent_inquiry.group_question_id:
        parent_link = build_group_message_link(parent_inquiry.group_id, parent_inquiry.group_question_id)
        if str(group_id) == str(parent_inquiry.group_id):
            reply_to_id = parent_inquiry.group_question_id  # oddiy guruhda havola bo'lmasa ham reply bog'laydi
    await post_inquiry_to_group(
        bot, db_session, user, section_name, group_id, payload, message.message_id,
        header=followup_header_html(parent_id, parent_link) if parent_id else "",
        parent_id=parent_id, reply_to_message_id=reply_to_id,
    )

    await state.clear()

    await message.answer(
        t("follow_up_received", lang),
        reply_markup=get_role_menu(message.from_user.id, lang, db_session),
        parse_mode=SULGUK_PARSE_MODE
    )
