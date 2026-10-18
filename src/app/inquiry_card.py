"""Guruhdagi murojaat kartasi: yagona format, yuborish va qayta chizish.

Murojaat uch joydan keladi (bo'lim tanlab yuborilgan savol, botga tasodifiy yozilgan xabar,
imtiyoz bo'yicha savol) — hammasi shu modul orqali bir xil ko'rinishda guruhga tushadi va
biriktirish/javobdan keyin ham shu funksiya bilan qayta chiziladi (Telegram'dan olingan matnni
qayta ishlatmaslik kerak: u qatorlarni yo'qotadi).
"""
import html
import logging
import re
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Message
from sulguk import SULGUK_PARSE_MODE

from src.app.enums import create_user_info
from src.app.html_utils import escape_multiline
from src.models.inquiry import Inquiry, InquiryMediaType
from src.models.user import User
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
FIRST_PART_LIMIT = 2200
AI_ESCALATION_HEADER = "⚠️ <b>Fuqaro AI javobidan qoniqmadi</b><br/><br/>"
VIDEO_NOTE_HINT = "<b>Yuqoridagi video xabarga javob yuborish uchun ushbu xabarni tanlang.</b><br/>"
MEDIA_CAPTION_TYPES = (
    InquiryMediaType.voice,
    InquiryMediaType.video,
    InquiryMediaType.document,
    InquiryMediaType.photo,
)


@dataclass
class InquiryPayload:
    """Fuqaro yuborgan murojaat mazmuni (xabardan yoki FSM ma'lumotidan)."""
    media_type: InquiryMediaType
    text: str | None = None
    file_id: str | None = None
    caption: str | None = None
    file_name: str | None = None
    media_json: str | None = None


def payload_from_message(message: Message) -> InquiryPayload | None:
    if message.text:
        return InquiryPayload(InquiryMediaType.text, text=message.text)
    if message.voice:
        return InquiryPayload(InquiryMediaType.voice, file_id=message.voice.file_id,
                              caption=message.caption, media_json=message.voice.model_dump_json())
    if message.video_note:
        return InquiryPayload(InquiryMediaType.video_note, file_id=message.video_note.file_id,
                              media_json=message.video_note.model_dump_json())
    if message.video:
        return InquiryPayload(InquiryMediaType.video, file_id=message.video.file_id,
                              caption=message.caption, media_json=message.video.model_dump_json())
    if message.document:
        return InquiryPayload(InquiryMediaType.document, file_id=message.document.file_id,
                              caption=message.caption, file_name=message.document.file_name,
                              media_json=message.document.model_dump_json())
    if message.photo:
        photo = message.photo[-1]
        return InquiryPayload(InquiryMediaType.photo, file_id=photo.file_id,
                              caption=message.caption, media_json=photo.model_dump_json())
    return None


def payload_from_state(data: dict) -> InquiryPayload | None:
    """auto_inquiry FSM ma'lumotidan (media_type, text, file_id, caption, file_name, media_data)."""
    try:
        media_type = InquiryMediaType(data.get("media_type"))
    except ValueError:
        return None
    return InquiryPayload(
        media_type,
        text=data.get("text"),
        file_id=data.get("file_id"),
        caption=data.get("caption"),
        file_name=data.get("file_name"),
        media_json=data.get("media_data"),
    )


def split_inquiry_text(text: str, max_first_part: int = FIRST_PART_LIMIT) -> tuple[str, str]:
    """Uzun matnni so'z/gapni kesmasdan ikkiga bo'ladi (1-qism ~2200 belgi, foydalanuvchi ma'lumotiga joy qoladi)."""
    if len(text) <= max_first_part:
        return text, ""

    search_sub = text[:max_first_part]
    idx = search_sub.rfind("\n\n")
    if idx >= 1000:
        return text[:idx].strip(), text[idx:].strip()

    idx = search_sub.rfind("\n")
    if idx >= 1000:
        return text[:idx].strip(), text[idx:].strip()

    for punct in [". ", "? ", "! "]:
        idx = search_sub.rfind(punct)
        if idx >= 1000:
            split_at = idx + len(punct.strip())
            return text[:split_at].strip(), text[split_at:].strip()

    idx = search_sub.rfind(" ")
    if idx >= 800:
        return text[:idx].strip(), text[idx:].strip()

    return text[:max_first_part].strip(), text[max_first_part:].strip()


def media_question_html(payload: InquiryPayload) -> str:
    """Media murojaatning Inquiry.question da saqlanadigan qisqa tavsifi (fuqaro izohi bilan)."""
    titles = {
        InquiryMediaType.voice: "🎙 <b>Ovozli murojaat</b>",
        InquiryMediaType.video_note: "📹 <b>Video xabar</b>",
        InquiryMediaType.video: "🎬 <b>Ilova qilingan video</b>",
        InquiryMediaType.photo: "📷 <b>Ilova qilingan fotohujjat</b>",
    }
    if payload.media_type == InquiryMediaType.document:
        title = f"📄 <b>Ilova qilingan hujjat:</b> {html.escape(payload.file_name or 'Hujjat')}"
    else:
        title = titles.get(payload.media_type, "")
    if payload.caption:
        title += f"<br/><blockquote>{escape_multiline(payload.caption)}</blockquote>"
    return title


def _looks_like_file_id(value: str) -> bool:
    # eski yozuvlarda ovoz/video uchun question = file_id
    return bool(value) and " " not in value and "<" not in value and len(value) > 20


def benefit_header_html(title: str, section_name: str | None, lex_url: str | None = None) -> str:
    lex = f' | <a href="{html.escape(lex_url, quote=True)}">⚖️ Lex.uz</a>' if lex_url else ""
    return (
        f"📌 <b>Imtiyoz bo‘yicha murojaat:</b> <i>«{html.escape(title)}»</i>{lex}<br/>"
        f"📂 <b>Yo‘nalish:</b> {html.escape(section_name or '—')}<br/><br/>"
    )


def followup_header_html(parent_id: int, parent_link: str | None = None) -> str:
    link = f' — <a href="{parent_link}">oldingi murojaat ↗️</a>' if parent_link else ""
    return f"🔄 <b>Qo'shimcha savol (№{parent_id} murojaat bo'yicha)</b>{link}<br/><br/>"


def _followup_header(inquiry: Inquiry, db_session: DBSession | None) -> str:
    if not getattr(inquiry, "parent_id", None):
        return ""
    from src.app.link_utils import build_group_message_link
    parent = db_session.get(Inquiry, inquiry.parent_id) if db_session is not None else None
    link = build_group_message_link(parent.group_id, parent.group_question_id) if parent else None
    return followup_header_html(inquiry.parent_id, link)


def _benefit_header(inquiry: Inquiry, db_session: DBSession | None) -> str:
    if not inquiry.benefit_id or db_session is None:
        return ""
    from src.models.benefit import Benefit
    benefit = Benefit.get_by_id(inquiry.benefit_id, db_session)
    if not benefit:
        return ""
    return benefit_header_html(benefit.title_uz, inquiry.section_name, benefit.lex_url)


def _responsible_line(inquiry: Inquiry, db_session: DBSession | None) -> str:
    if not inquiry.assigned_volunteer_id or db_session is None:
        return ""
    from src.models.volunteer import Volunteer
    vol = Volunteer.get_by_user_id(inquiry.assigned_volunteer_id, db_session)
    name = vol.full_name if vol else str(inquiry.assigned_volunteer_id)
    return f'<br/>👤 <b>Mas\'ul volontyor:</b> <a href="tg://user?id={inquiry.assigned_volunteer_id}">{html.escape(name)}</a>'


def _rendered_len(html_text: str) -> int:
    try:
        from sulguk import transform_html
        return len(transform_html(html_text).text)
    except Exception:
        return len(re.sub(r"<[^>]+>", "", html_text))


def render_inquiry_card(
    inquiry: Inquiry,
    db_session: DBSession | None,
    user: User | None = None,
    extra_html: str = "",
) -> tuple[str, bool]:
    """Kartaning HTML matni va u caption (media) ekanligi. extra_html — holat bloki (javob, yo'naltirish)."""
    if user is None:
        user = inquiry.user if getattr(inquiry, "user", None) else (
            User.get_by_user_id(inquiry.user_id, db_session) if db_session is not None else None
        )
    user_lang = (user.language if user else None) or "uz"
    user_ctx = create_user_info(user, with_link=True, lang=user_lang)
    header = _followup_header(inquiry, db_session) + _benefit_header(inquiry, db_session)
    if getattr(inquiry, "from_ai_answer_id", None):
        header = AI_ESCALATION_HEADER + header
    tail = f"{_responsible_line(inquiry, db_session)}{extra_html}"
    media_type = inquiry.question_mediatype
    question = inquiry.question or ""

    if media_type == InquiryMediaType.text:
        part1, _ = split_inquiry_text(question)
        card = f"{header}<p><blockquote>{escape_multiline(part1)}</blockquote></p>{user_ctx}{tail}"
        if _rendered_len(card) > TEXT_LIMIT:
            card = f"{header}<p><blockquote>{escape_multiline(part1[:1500])}…</blockquote></p>{user_ctx}{tail}"
        return card, False

    if media_type == InquiryMediaType.video_note:
        return f"{header}{VIDEO_NOTE_HINT}{user_ctx}{tail}", False

    prefix = "" if _looks_like_file_id(question) else question
    body = f"{header}{prefix}<br/>{user_ctx}" if prefix else f"{header}{user_ctx}"
    caption = f"{body}{tail}"
    if _rendered_len(caption) > CAPTION_LIMIT:
        # caption chegarasi: avval fuqaro izohi, keyin imtiyoz sarlavhasi tushirib qoldiriladi
        caption = f"{header}{user_ctx}{tail}"
        if _rendered_len(caption) > CAPTION_LIMIT:
            caption = f"{user_ctx}{tail}"
    return caption, True


def inquiry_card_markup(inquiry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Biriktirish", callback_data=f"inq_assign:{inquiry_id}:1")]]
    )


async def post_inquiry_card(
    bot: Bot,
    group_id: int | str,
    user: User,
    payload: InquiryPayload,
    benefit_header: str = "",
    reply_to_message_id: int | None = None,
) -> tuple[Message, Message | None, str]:
    """Guruhga yangi murojaat kartasini yuboradi. Qaytaradi: (karta, davom xabari, Inquiry.question)."""
    user_ctx = create_user_info(user, with_link=True, lang=user.language or "uz")
    cont_message = None

    if payload.media_type == InquiryMediaType.text:
        text = payload.text or ""
        part1, part2 = split_inquiry_text(text)
        card = await bot.send_message(
            chat_id=group_id,
            text=f"{benefit_header}<p><blockquote>{escape_multiline(part1)}</blockquote></p>{user_ctx}",
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
        )
        if part2:
            cont_message = await bot.send_message(
                chat_id=group_id,
                text=f"📌 <b>Murojaatning davomi:</b><br/><p><blockquote>{escape_multiline(part2)}</blockquote></p>",
                reply_to_message_id=card.message_id,
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        return card, cont_message, text

    question = media_question_html(payload)
    if payload.media_type == InquiryMediaType.video_note:
        await bot.send_video_note(chat_id=group_id, video_note=payload.file_id)
        card = await bot.send_message(
            chat_id=group_id,
            text=f"{benefit_header}{VIDEO_NOTE_HINT}{user_ctx}",
            parse_mode=SULGUK_PARSE_MODE,
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
        )
        return card, None, question

    caption = f"{benefit_header}{question}<br/>{user_ctx}"
    if _rendered_len(caption) > CAPTION_LIMIT:
        # izoh juda uzun: kartada qisqa sarlavha, to'liq izoh alohida xabarda
        short = media_question_html(InquiryPayload(payload.media_type, file_name=payload.file_name))
        caption = f"{benefit_header}{short}<br/>{user_ctx}"
    senders = {
        InquiryMediaType.voice: (bot.send_voice, "voice"),
        InquiryMediaType.video: (bot.send_video, "video"),
        InquiryMediaType.document: (bot.send_document, "document"),
        InquiryMediaType.photo: (bot.send_photo, "photo"),
    }
    sender, field = senders[payload.media_type]
    card = await sender(chat_id=group_id, caption=caption, parse_mode=SULGUK_PARSE_MODE,
                        reply_to_message_id=reply_to_message_id, allow_sending_without_reply=True,
                        **{field: payload.file_id})
    if payload.caption and caption.find(escape_multiline(payload.caption)) == -1:
        cont_message = await bot.send_message(
            chat_id=group_id,
            text=f"📌 <b>Fuqaro izohi:</b><br/><p><blockquote>{escape_multiline(payload.caption)}</blockquote></p>",
            reply_to_message_id=card.message_id,
            parse_mode=SULGUK_PARSE_MODE,
        )
    return card, cont_message, question


async def finalize_new_inquiry(
    bot: Bot,
    inquiry: Inquiry,
    card: Message,
    cont_message: Message | None,
    user_lang: str,
) -> None:
    """Karta yuborilib Inquiry saqlangach: Biriktirish tugmasi, davom xabari bog'lanishi, AI qoralama."""
    try:
        await bot.edit_message_reply_markup(
            chat_id=inquiry.group_id,
            message_id=card.message_id,
            reply_markup=inquiry_card_markup(inquiry.id),
        )
    except Exception as e:
        logger.warning("Inquiry %s: Biriktirish tugmasini qo'shib bo'lmadi: %s", inquiry.id, e)

    if cont_message:
        try:
            from src.database.redisdb import get_redis
            redis_client = get_redis(is_async=True)
            await redis_client.set(f"inquiry_cont:{inquiry.group_id}:{cont_message.message_id}", str(inquiry.id), ex=86400 * 30)
            await redis_client.set(f"inquiry_cont_msg:{inquiry.id}", str(cont_message.message_id), ex=86400 * 30)
        except Exception as e:
            logger.warning("Inquiry %s: davom xabarini Redis'ga yozib bo'lmadi: %s", inquiry.id, e)

    if inquiry.question_mediatype == InquiryMediaType.text and inquiry.question:
        from src.routes.aiogram.ai_assistant import spawn_lawyer_ai_draft
        spawn_lawyer_ai_draft(
            bot=bot,
            inquiry_id=inquiry.id,
            user_id=inquiry.user_id,
            group_id=inquiry.group_id,
            reply_to_message_id=card.message_id,
            question_text=inquiry.question,
            user_lang=user_lang,
        )


async def refresh_inquiry_card(
    bot: Bot,
    inquiry: Inquiry,
    db_session: DBSession | None,
    extra_html: str = "",
    reply_markup: InlineKeyboardMarkup | None = None,
    keep_assign_button: bool = True,
) -> bool:
    """Kartani bazadagi ma'lumotdan qayta chizadi (mas'ul, holat). Muvaffaqiyatli bo'lsa True."""
    if not inquiry.group_question_id or not inquiry.group_id:
        return False
    text, is_caption = render_inquiry_card(inquiry, db_session, extra_html=extra_html)
    markup = reply_markup if reply_markup is not None else (inquiry_card_markup(inquiry.id) if keep_assign_button else None)

    async def _edit(as_caption: bool):
        if as_caption:
            await bot.edit_message_caption(
                chat_id=inquiry.group_id, message_id=inquiry.group_question_id,
                caption=text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE,
            )
        else:
            await bot.edit_message_text(
                chat_id=inquiry.group_id, message_id=inquiry.group_question_id,
                text=text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    try:
        await _edit(is_caption)
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "no text in the message" in err or "has no text" in err or "no caption" in err:
            # eski kartalar: media turi bazadagidan farq qilgan holat
            try:
                await _edit(not is_caption)
                return True
            except Exception as e2:
                e = e2
        logger.warning("Inquiry %s: kartani yangilab bo'lmadi: %s", inquiry.id, e)
        return False
