from celery.schedules import crontab
from src.config.celery_app import celery_app
from src.tasks import *


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(hour="9", minute="0"), daily_reminder.s())
    sender.add_periodic_task(crontab(minute="1"), close_idle_inquiries.s())
    sender.add_periodic_task(crontab(minute="*/10"), check_appointment_reminders.s())
    sender.add_periodic_task(crontab(minute="20"), ask_appointment_attendance.s())
    sender.add_periodic_task(crontab(hour="9", minute="15"), send_pending_appointment_reminders.s())
    sender.add_periodic_task(crontab(hour="9", minute="0", day_of_month="1"), generate_monthly_report.s())
    sender.add_periodic_task(crontab(hour="9", minute="5", day_of_month="1"), send_monthly_analytics_report.s())
    sender.add_periodic_task(crontab(hour="9", minute="0", day_of_week="1"), generate_weekly_report.s())
    sender.add_periodic_task(crontab(hour="16", minute="0", day_of_week="0"), post_weekly_volunteer_leaderboard.s())
    sender.add_periodic_task(crontab(hour="21", minute="0", day_of_week="0"), send_weekly_volunteer_personal_digest.s())
    sender.add_periodic_task(crontab(minute="*/30"), check_assignment_reminders.s())
    sender.add_periodic_task(crontab(minute="7", hour="*/3"), check_ai_balance.s())
    sender.add_periodic_task(crontab(hour="9", minute="5"), send_daily_error_digest.s())
    sender.add_periodic_task(crontab(hour="9", minute="10", day_of_week="1"), weekly_gate_summary.s())
