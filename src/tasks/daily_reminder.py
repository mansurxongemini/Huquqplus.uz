import logging
from typing import TypeVar
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from sqlmodel import Session, select, col, and_
from sulguk import SULGUK_PARSE_MODE
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
        and_close = and_(Inquiry.status == InquiryStatus.active, col(Inquiry.group_answer_id).is_(None))
        inquiries: list[InquiryType] = session.exec(select(Inquiry).where(and_close)).all()

        grouped_inquiries = {}

        for i in inquiries:
            if i.group_id in grouped_inquiries:
                grouped_inquiries[i.group_id].append(i)
            else:
                grouped_inquiries[i.group_id] = [i]

        for group_id, inquiries in grouped_inquiries.items():
            text = create_reminder_text(inquiries)
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
            except TelegramAPIError as e:
                logger.error("daily_reminder api error for group_id=%s error=%s", group_id, e)


def create_reminder_text(inquiries: list[InquiryType]):
    paragraph = f"""
        <p><b>Quyidagi savollar hali ham o'z javobini kutmoqda:</b></p>
    """

    for inquiry in inquiries:
        group_id = str(inquiry.group_id)
        link = build_group_message_link(group_id, inquiry.group_question_id)
        if link:
            paragraph += (f"<p><a href=\"{link}\">"
                          f"<blockquote>{get_message_text(inquiry)}</blockquote>"
                          f"</a></p>")
        else:
            paragraph += f"<p><blockquote>{get_message_text(inquiry)}</blockquote></p>"

    return paragraph


def build_group_message_link(group_id: str, message_id: int) -> str | None:
    if group_id.startswith("@"):
        return f"https://t.me/{group_id[1:]}/{message_id}"
    # Private supergroup/channel ids look like -1001234567890
    if group_id.startswith("-100") and group_id[4:].isdigit():
        return f"https://t.me/c/{group_id[4:]}/{message_id}"
    return None


def get_message_text(inquiry: Inquiry):
    if inquiry.question_mediatype != InquiryMediaType.text:
        return "🔉 Ovozli Xabar"
    else:
        return f"📝 {truncate_string(inquiry.question, 120)}"
