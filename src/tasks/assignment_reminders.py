import html
import logging
from datetime import datetime

from sqlmodel import Session, select
from sulguk import SULGUK_PARSE_MODE

from src.app.assign_helpers import is_quiet_day, is_quiet_hour, reminder_applies, reminder_due
from src.app.link_utils import build_group_message_link
from src.app.timeutils import tz
from src.app.translations import t
from src.config.bot import bot
from src.config.celery_app import celery_app
from src.config.settings import settings
from src.database.mysql import engine
from src.database.redisdb import get_redis
from src.models.assignment import AssignmentStatus, InquiryAssignment
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.user import User
from src.models.volunteer import Volunteer
from src.routes.aiogram.group_router import send_answer_to_citizen
from src.tasks.utils import async_celery_task

logger = logging.getLogger(__name__)

BLOCK_NOTICE_TTL = 86400 * 30


def _inquiry_link_html(inquiry: Inquiry) -> str:
    link = build_group_message_link(inquiry.group_id, inquiry.group_question_id)
    if link:
        return f'<a href="{link}">Murojaat №{inquiry.id}</a>'
    return f"Murojaat №{inquiry.id}"


def _blocked_notice_sent(assignment_id: int) -> bool:
    try:
        r = get_redis(is_async=False)
        return r.get(f"assign_remind_blockna:{assignment_id}") is not None
    except Exception:
        return False


def _mark_blocked_notice_sent(assignment_id: int):
    try:
        r = get_redis(is_async=False)
        r.set(f"assign_remind_blockna:{assignment_id}", "1", ex=BLOCK_NOTICE_TTL)
    except Exception:
        pass


async def _notify_admins_blocked(bot_, inquiry: Inquiry, vol_name: str, lang: str = "uz"):
    text = t("assign_remind_blocked_admin", lang, name=html.escape(vol_name), id=inquiry.id)
    try:
        await bot_.send_message(
            chat_id=inquiry.group_id,
            text=text,
            parse_mode=SULGUK_PARSE_MODE,
        )
        return True
    except Exception as e:
        logger.warning("Reminder blocked-notice to group %s failed: %s", inquiry.group_id, e)
    for admin_id in settings.admin_ids_list:
        try:
            await bot_.send_message(chat_id=admin_id, text=text, parse_mode=SULGUK_PARSE_MODE)
            return True
        except Exception:
            pass
    return False


@async_celery_task(celery_app, name="check_assignment_reminders")
async def check_assignment_reminders():
    now_tashkent = datetime.now(tz)
    if is_quiet_day(now_tashkent.weekday(), settings.ASSIGN_REMINDER_SKIP_WEEKDAYS):
        return
    if is_quiet_hour(now_tashkent.hour, settings.ASSIGN_REMINDER_QUIET_START, settings.ASSIGN_REMINDER_QUIET_END):
        return
    now = datetime.now()
    with Session(engine) as session:
        rows = session.exec(
            select(InquiryAssignment).where(
                InquiryAssignment.status.in_(AssignmentStatus.OPEN),
            )
        ).all()
        for a in rows:
            inquiry = session.get(Inquiry, a.inquiry_id)
            if not inquiry or inquiry.status != InquiryStatus.active:
                continue
            if not reminder_applies(inquiry.created_at, settings.ASSIGN_ENFORCE_FROM):
                continue
            due = reminder_due(a.assigned_at, a.first_reminded_at, a.last_reminded_at, now)
            if not due:
                continue
            vol_user = User.get_by_user_id(a.volunteer_user_id, session)
            vol_lang = vol_user.language if vol_user and vol_user.language else "uz"
            key = "assign_remind_first" if due == "first" else "assign_remind_follow"
            text = t(key, vol_lang, link=_inquiry_link_html(inquiry))
            ok, reason, exc = await send_answer_to_citizen(
                bot.send_message,
                dict(chat_id=a.volunteer_user_id, text=text, parse_mode=SULGUK_PARSE_MODE),
            )
            a.remind_count += 1
            if a.first_reminded_at is None:
                a.first_reminded_at = now
            a.last_reminded_at = now
            session.add(a)
            session.commit()
            if ok:
                continue
            err_text = f"{reason} {exc}".lower()
            if reason == "blocked" or "bot was blocked" in err_text or "chat not found" in err_text:
                if _blocked_notice_sent(a.id):
                    continue
                vol = Volunteer.get_by_user_id(a.volunteer_user_id, session)
                vol_name = vol.full_name if vol else str(a.volunteer_user_id)
                if await _notify_admins_blocked(bot, inquiry, vol_name):
                    _mark_blocked_notice_sent(a.id)
            else:
                logger.warning("Assignment reminder failed (inquiry %s): %s", inquiry.id, reason)
