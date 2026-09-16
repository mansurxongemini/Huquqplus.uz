from celery.schedules import crontab
from src.config.celery_app import celery_app
from src.tasks import *


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(hour="9", minute="0"), daily_reminder.s())
    sender.add_periodic_task(crontab(minute="1"), close_idle_inquiries.s())
    sender.add_periodic_task(crontab(minute="*/10"), check_appointment_reminders.s())
    sender.add_periodic_task(crontab(hour="9", minute="0", day_of_month="1"), generate_monthly_report.s())
    sender.add_periodic_task(crontab(hour="9", minute="0", day_of_week="1"), generate_weekly_report.s())
    sender.add_periodic_task(crontab(hour="16", minute="0", day_of_week="0"), post_weekly_volunteer_leaderboard.s())
