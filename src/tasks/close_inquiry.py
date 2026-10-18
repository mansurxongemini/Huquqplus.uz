import asyncio
import logging
from datetime import datetime, timedelta

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.storage.base import StorageKey
from sqlmodel import Session, select

from src.app.keyboards import get_role_menu
from src.app.translations import t
from src.config.bot import bot
from src.config.celery_app import celery_app
from src.config.redis_queue import telegram_storage
from src.database.mysql import engine
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.user import User
from src.tasks.utils import async_celery_task

logger = logging.getLogger(__name__)

CLOSE_AFTER = timedelta(hours=4)
# Faqat shu murojaat oqimiga tegishli holatlar tozalanadi: fuqaro boshqa ish (qabulga yozilish,
# yangi savol) bilan band bo'lsa, uning jarayoni buzilmaydi.
INQUIRY_FLOW_STATES = {
    "InquiryState:awaiting_response",
    "InquiryState:received_answer",
    "InquiryState:confirm_cancellation",
}


@async_celery_task(celery_app, name="close_inquiry")
async def close_idle_inquiries():
    with Session(engine) as session:
        deadline = datetime.now() - CLOSE_AFTER
        inquiries = session.exec(
            select(Inquiry).where(Inquiry.status == InquiryStatus.replied, Inquiry.replied_at < deadline)
        ).all()
        for inquiry in inquiries:
            inquiry.close(cancelled=False, session=session, commit=False)
            session.commit()

            key = StorageKey(user_id=inquiry.user_id, chat_id=inquiry.user_id, bot_id=bot.id)
            if await telegram_storage.get_state(key) in INQUIRY_FLOW_STATES:
                await telegram_storage.set_state(key, None)
                await telegram_storage.set_data(key, {})

            user = User.get_by_user_id(inquiry.user_id, session)
            lang = (user.language if user else None) or "uz"
            await notify_closed(inquiry.user_id, t("inquiry_closed_citizen", lang),
                                get_role_menu(inquiry.user_id, lang, session))


async def notify_closed(chat_id: int, text: str, reply_markup) -> None:
    for _ in range(3):
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            return
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            return
        except Exception as e:
            logger.warning("Murojaat yopilgani haqida xabar yuborilmadi (user %s): %s", chat_id, e)
            return
