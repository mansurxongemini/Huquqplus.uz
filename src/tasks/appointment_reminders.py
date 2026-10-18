import html
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select
from sulguk import SULGUK_PARSE_MODE
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from src.app.translations import t
from src.config.celery_app import celery_app
from src.config.settings import settings
from src.database.mysql import engine
from src.database.redisdb import get_redis
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.app.link_utils import build_group_message_link
from src.tasks.utils import async_celery_task
from src.app.split_message import truncate_string
from src.config.bot import bot

logger = logging.getLogger(__name__)


@async_celery_task(celery_app, name="check_appointment_reminders")
async def check_appointment_reminders():
    """
    Periodic task running every 10 minutes:
    Finds accepted appointments coming up in the next 60 minutes
    and sends automatic reminder notifications to citizen and lawyer.
    """
    now = datetime.now()
    window_end = now + timedelta(minutes=65)

    with Session(engine) as session:
        upcoming_appointments = session.exec(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.accepted,
                Appointment.scheduled_at >= now,
                Appointment.scheduled_at <= window_end,
                Appointment.reminder_sent == False
            )
        ).all()

        if not upcoming_appointments:
            return

        for app in upcoming_appointments:
            try:
                citizen = User.get_by_user_id(app.user_id, session)
                lawyer = OfficialLawyer.get_by_user_id(app.lawyer_id, session) if app.lawyer_id else None

                time_str = app.scheduled_at.strftime('%H:%M') if app.scheduled_at else ""
                lawyer_name = lawyer.full_name if lawyer else "—"
                lang = (citizen.language if citizen else None) or "uz"
                link_text = (
                    t("app_reminder_link", lang, url=html.escape(app.meeting_link))
                    if app.meeting_link else t("app_reminder_no_link", lang)
                )
                citizen_reminder = t("app_reminder_citizen", lang, id=app.id, time=time_str,
                                     lawyer=html.escape(lawyer_name), link=link_text)
                await bot.send_message(
                    chat_id=app.user_id,
                    text=citizen_reminder,
                    parse_mode=SULGUK_PARSE_MODE
                )

                # 2. Send reminder to lawyer (if official lawyer assigned)
                if app.lawyer_id:
                    c_name = f"{citizen.first_name} {citizen.last_name or ''}".strip() if citizen else f"ID: {app.user_id}"
                    c_phone = citizen.phone if citizen else "noma'lum"

                    lawyer_reminder = f"""
⏰ <b>Eslatma: Fuqaro bilan qabulga 1 soat qoldi! (Ariza №{app.id})</b><br/><br/>
👤 <b>Fuqaro:</b> {html.escape(c_name)}<br/>
📞 <b>Telefon:</b> {c_phone}<br/>
📅 <b>Vaqti:</b> {time_str}<br/>
📝 <b>Muammo:</b> {html.escape((app.problem_description or "")[:150])}...
"""
                    await bot.send_message(
                        chat_id=app.lawyer_id,
                        text=lawyer_reminder,
                        parse_mode=SULGUK_PARSE_MODE
                    )

                app.reminder_sent = True
                session.add(app)
                session.commit()
                logger.info("Sent appointment reminder for appointment ID %s", app.id)

            except Exception as e:
                logger.error("Failed to send reminder for appointment ID %s: %s", app.id, e)


@async_celery_task(celery_app, name="send_pending_appointment_reminders")
async def send_pending_appointment_reminders():
    """
    Davriy vazifa (har 3 kunda yuristlar guruhiga eslatma):
    Hali birorta yurist tomonidan qabul qilinmagan (pending) yoki
    muddati o'tgan yurist qabuli arizalarini ro'yxat qilib
    LAWYER_APPOINTMENT_GROUP_ID guruhiga eslatma sifatida yuboradi.
    """
    now = datetime.now()
    redis = get_redis(is_async=True)
    redis_key = "last_pending_appointment_reminder_time"

    try:
        last_sent_str = await redis.get(redis_key)
        if last_sent_str:
            try:
                last_sent = datetime.fromisoformat(last_sent_str)
                # 3 kun (71 soat bufer bilan) o'tganligini tekshiramiz
                if (now - last_sent).total_seconds() < (3 * 86400 - 3600):
                    logger.info(
                        "Yurist qabuli eslatmasi o'tkazildi: oxirgi marta %s da yuborilgan (hali 3 kun bo'lmadi).",
                        last_sent
                    )
                    await redis.aclose()
                    return
            except Exception as pe:
                logger.warning("last_sent parsing xatosi: %s", pe)
    except Exception as re:
        logger.warning("Redis tekshirishda xatolik: %s", re)

    group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
    if not group_id:
        logger.warning("LAWYER_APPOINTMENT_GROUP_ID sozlanmagan, eslatma yuborilmadi.")
        try:
            await redis.aclose()
        except Exception:
            pass
        return

    with Session(engine) as session:
        # 1. Pending (hali birorta yurist qabul qilmagan) arizalar
        pending_appointments = session.exec(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.pending
            ).order_by(Appointment.created_at.asc())
        ).all()

        # 2. Accepted bo'lib, lekin belgilangan vaqti o'tib ketgan (overdue) arizalar
        overdue_appointments = session.exec(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.accepted,
                Appointment.scheduled_at < now
            ).order_by(Appointment.scheduled_at.asc())
        ).all()

        if not pending_appointments and not overdue_appointments:
            logger.info("Ko'rib chiqilishi kutilayotgan yurist qabuli arizalari yo'q.")
            try:
                await redis.aclose()
            except Exception:
                pass
            return

        # Eslatma xabari bloklarini shakllantiramiz
        messages_to_send = []
        current_block = [
            "<p><b>⚖️ Yurist qabuli: Ko'rib chiqilishi kutilayotgan arizalar eslatmasi</b></p>"
        ]

        if pending_appointments:
            current_block.append(
                f"<p><b>⏳ Qabul qilinmagan yangi arizalar ({len(pending_appointments)} ta):</b></p>"
            )
            for app in pending_appointments:
                citizen = User.get_by_user_id(app.user_id, session)
                c_name = f"{citizen.first_name or ''} {citizen.last_name or ''}".strip() if citizen else f"ID: {app.user_id}"
                c_phone = citizen.phone if citizen and citizen.phone else "Ko'rsatilmadi"
                time_str = app.scheduled_at.strftime('%d.%m.%Y %H:%M') if app.scheduled_at else "Belgilanmagan"
                snippet = truncate_string(app.problem_description or "Tavsif yo'q", 100)

                link = build_group_message_link(group_id, app.group_message_id)
                card = (
                    f"<b>Ariza №{app.id}</b> — 👤 {c_name} (📞 {c_phone})<br/>"
                    f"📅 <b>Vaqti:</b> {time_str}<br/>"
                    f"📝 <i>{snippet}</i>"
                )
                if link:
                    item_html = f'<p><a href="{link}"><blockquote>{card}</blockquote></a></p>'
                else:
                    item_html = f'<p><blockquote>{card}</blockquote></p>'

                # Xabar hajmini nazorat qilamiz (Telegram 4096 limit)
                if sum(len(x) for x in current_block) + len(item_html) > 3500:
                    messages_to_send.append("\n".join(current_block))
                    current_block = [item_html]
                else:
                    current_block.append(item_html)

        if overdue_appointments:
            overdue_header = (
                f"<p><b>⚠️ Belgilangan vaqti o'tgan yoki yakunlanmagan arizalar ({len(overdue_appointments)} ta):</b></p>"
            )
            if sum(len(x) for x in current_block) + len(overdue_header) > 3500:
                messages_to_send.append("\n".join(current_block))
                current_block = [overdue_header]
            else:
                current_block.append(overdue_header)

            for app in overdue_appointments:
                citizen = User.get_by_user_id(app.user_id, session)
                c_name = f"{citizen.first_name or ''} {citizen.last_name or ''}".strip() if citizen else f"ID: {app.user_id}"
                lawyer = OfficialLawyer.get_by_user_id(app.lawyer_id, session) if app.lawyer_id else None
                lawyer_name = lawyer.full_name if lawyer else (f"ID: {app.lawyer_id}" if app.lawyer_id else "Noma'lum")
                time_str = app.scheduled_at.strftime('%d.%m.%Y %H:%M') if app.scheduled_at else "Belgilanmagan"

                link = build_group_message_link(group_id, app.group_message_id)
                card = (
                    f"<b>Ariza №{app.id}</b> — 👤 {c_name}<br/>"
                    f"👨‍⚖️ <b>Yurist:</b> {lawyer_name} | 📅 <b>Belgilangan vaqt:</b> {time_str}"
                )
                if link:
                    item_html = f'<p><a href="{link}"><blockquote>{card}</blockquote></a></p>'
                else:
                    item_html = f'<p><blockquote>{card}</blockquote></p>'

                if sum(len(x) for x in current_block) + len(item_html) > 3500:
                    messages_to_send.append("\n".join(current_block))
                    current_block = [item_html]
                else:
                    current_block.append(item_html)

        footer = "<p><i>👉 Hurmatli yuristlar, iltimos, yuqoridagi arizalarni ochib, qabulni o'z zimmangizga oling yoki suhbatni yakunlang!</i></p>"
        current_block.append(footer)
        messages_to_send.append("\n".join(current_block))

        sent_successfully = False
        for msg_text in messages_to_send:
            try:
                await bot.send_message(
                    chat_id=group_id,
                    text=msg_text,
                    parse_mode=SULGUK_PARSE_MODE,
                    link_preview_options={"is_disabled": True}
                )
                sent_successfully = True
            except TelegramBadRequest as e:
                logger.error("Yurist qabuli eslatmasi TelegramBadRequest: %s", e)
            except TelegramForbiddenError as e:
                logger.error("Yurist qabuli eslatmasi TelegramForbiddenError: %s", e)
            except TelegramAPIError as e:
                logger.error("Yurist qabuli eslatmasi TelegramAPIError: %s", e)
            except Exception as e:
                logger.error("Yurist qabuli eslatmasini yuborishda kutilmagan xatolik: %s", e)

        if sent_successfully:
            try:
                await redis.set(redis_key, now.isoformat())
                logger.info("Yurist qabuli eslatmasi muvaffaqiyatli yuborildi va Redis yangilandi.")
            except Exception as re:
                logger.warning("Redis vaqtini yangilashda xatolik: %s", re)

    try:
        await redis.aclose()
    except Exception:
        pass


ATTEND_ASK_FROM_HOUR, ATTEND_ASK_TO_HOUR = 9, 21  # fuqaroga kunduzi so'raladi


@async_celery_task(celery_app, name="ask_appointment_attendance")
async def ask_appointment_attendance():
    """Qabuldan 3-30 soat oldin fuqarodan bir marta "tayyor bo'lasizmi?" deb so'raladi."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from src.app.calendar_utils import format_uz_date
    from src.app.timeutils import tz

    if not ATTEND_ASK_FROM_HOUR <= datetime.now(tz).hour < ATTEND_ASK_TO_HOUR:
        return
    now = datetime.now()
    with Session(engine) as session:
        apps = session.exec(
            select(Appointment).where(
                Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted]),
                Appointment.scheduled_at >= now + timedelta(hours=3),
                Appointment.scheduled_at <= now + timedelta(hours=30),
                Appointment.confirm_asked_at == None,  # noqa: E711
            )
        ).all()
        for app in apps:
            citizen = User.get_by_user_id(app.user_id, session)
            lang = (citizen.language if citizen else None) or "uz"
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_attend_yes", lang), callback_data=f"app_att:{app.id}:yes")],
                [InlineKeyboardButton(text=t("btn_attend_no", lang), callback_data=f"app_att:{app.id}:no")],
            ])
            try:
                await bot.send_message(
                    chat_id=app.user_id,
                    text=t("app_attend_ask", lang, when=format_uz_date(app.scheduled_at), id=app.id),
                    reply_markup=markup,
                    parse_mode=SULGUK_PARSE_MODE,
                )
            except Exception as e:
                logger.info("Qabul tasdig'i so'rovi yuborilmadi (ariza %s): %s", app.id, type(e).__name__)
            app.confirm_asked_at = now
            session.add(app)
            session.commit()
