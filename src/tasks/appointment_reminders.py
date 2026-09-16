import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select, and_
from sulguk import SULGUK_PARSE_MODE
from src.config.celery_app import celery_app
from src.database.mysql import engine
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.tasks.utils import async_celery_task
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
                lawyer_name = lawyer.full_name if lawyer else "Yurist"

                link_text = (
                    f"<br/>👉 <a href=\"{app.meeting_link}\">{app.meeting_link}</a>"
                    if app.meeting_link
                    else "<br/><i>(Yurist belgilangan vaqtda siz bilan Telegram yoki telefon orqali bog'lanadi)</i>"
                )

                # 1. Send reminder to citizen
                citizen_reminder = f"""
⏰ <b>Eslatma: Yurist qabuliga 1 soatdan kam vaqt qoldi! (Ariza №{app.id})</b><br/><br/>
📅 <b>Suhbat vaqti:</b> {time_str}<br/>
👨‍⚖️ <b>Yurist:</b> {lawyer_name}<br/>
🔗 <b>Ulanish havolasi:</b> {link_text}<br/><br/>
<i>Iltimos, belgilangan vaqtda tayyor bo'ling!</i>
"""
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
👤 <b>Fuqaro:</b> {c_name}<br/>
📞 <b>Telefon:</b> {c_phone}<br/>
📅 <b>Vaqti:</b> {time_str}<br/>
📝 <b>Muammo:</b> {app.problem_description[:150]}...
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
