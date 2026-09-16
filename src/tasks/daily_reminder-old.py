from typing import TypeVar
from sqlmodel import Session, select, col, and_
from sulguk import SULGUK_PARSE_MODE
from src.app.split_message import truncate_string
from src.config.celery_app import celery_app
from src.database.mysql import engine
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.tasks.utils import async_celery_task
from src.config.bot import bot


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
            await bot.send_message(
                chat_id=group_id,
                text=create_reminder_text(inquiries),
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options={"is_disabled": True}
            )


def create_reminder_text(inquiries: list[InquiryType]):
    paragraph = f"""
        <p><b>Quyidagi savollar hali ham o'z javobini kutmoqda:</b></p>
    """

    for inquiry in inquiries:
        paragraph += (f"<p><a href=\"https://t.me/{inquiry.group_id[1:]}/{inquiry.group_question_id}\">"
                      f"<blockquote>{get_message_text(inquiry)}</blockquote>"
                      f"</a></p>")

    return paragraph


def get_message_text(inquiry: Inquiry):
    if inquiry.question_mediatype != InquiryMediaType.text:
        return "🔉 Ovozli Xabar"
    else:
        return f"📝 {truncate_string(inquiry.question, 120)}"
