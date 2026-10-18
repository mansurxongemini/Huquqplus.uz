import html
import logging
from typing import TypeVar
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from sqlmodel import Session, select, col, and_
from sulguk import SULGUK_PARSE_MODE
from src.app.link_utils import build_group_message_link
from src.app.split_message import truncate_string
from src.config.celery_app import celery_app
from src.database.mysql import engine
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.tasks.utils import async_celery_task
from src.config.bot import bot

logger = logging.getLogger(__name__)


InquiryType = TypeVar("InquiryType", bound="Inquiry")


@async_celery_task(celery_app, name="daily_reminder")
async def daily_reminder():
    with Session(engine) as session:
        and_close = and_(Inquiry.status == InquiryStatus.active, col(Inquiry.group_answer_id).is_(None),
                         col(Inquiry.assigned_volunteer_id).is_(None))
        inquiries: list[InquiryType] = session.exec(select(Inquiry).where(and_close)).all()

        grouped_inquiries = {}

        for i in inquiries:
            if i.group_id in grouped_inquiries:
                grouped_inquiries[i.group_id].append(i)
            else:
                grouped_inquiries[i.group_id] = [i]

        for group_id, group_inquiries in grouped_inquiries.items():
            for text in create_reminder_text(group_inquiries):
                try:
                    await bot.send_message(
                        chat_id=group_id,
                        text=text,
                        parse_mode=SULGUK_PARSE_MODE,
                        link_preview_options={"is_disabled": True}
                    )
                except TelegramBadRequest as e:
                    logger.error(
                        "daily_reminder bad request for group_id=%s msg_len=%s error=%s",
                        group_id,
                        len(text),
                        e
                    )
                except TelegramForbiddenError as e:
                    logger.error("daily_reminder forbidden for group_id=%s error=%s", group_id, e)
                    break
                except TelegramAPIError as e:
                    logger.error("daily_reminder api error for group_id=%s error=%s", group_id, e)


REMINDER_CHUNK_LIMIT = 3500  # Telegram 4096 belgi chegarasi (HTML teglari bilan zaxira)
MEDIA_LABELS = {
    InquiryMediaType.voice: "🎙 Ovozli murojaat",
    InquiryMediaType.video_note: "📹 Video xabar",
    InquiryMediaType.video: "🎬 Video murojaat",
    InquiryMediaType.photo: "📷 Rasmli murojaat",
    InquiryMediaType.document: "📄 Hujjatli murojaat",
}


def create_reminder_text(inquiries: list[InquiryType]) -> list[str]:
    """Javobsiz murojaatlar ro'yxati; uzun bo'lsa bir nechta xabarga bo'linadi."""
    header = "<p><b>Quyidagi savollar hali ham o'z javobini kutmoqda:</b></p>"
    chunks, current = [], header
    for inquiry in inquiries:
        link = build_group_message_link(str(inquiry.group_id), inquiry.group_question_id)
        quote = f"<blockquote>{get_message_text(inquiry)}</blockquote>"
        item = f'<p><a href="{link}">{quote}</a></p>' if link else f"<p>{quote}</p>"
        if len(current) + len(item) > REMINDER_CHUNK_LIMIT and current != header:
            chunks.append(current)
            current = header
        current += item
    chunks.append(current)
    return chunks


def get_message_text(inquiry: Inquiry) -> str:
    if inquiry.question_mediatype == InquiryMediaType.text:
        return f"📝 {html.escape(truncate_string(inquiry.question or '', 120))}"
    return f"№{inquiry.id} — {MEDIA_LABELS.get(inquiry.question_mediatype, 'Media murojaat')}"
