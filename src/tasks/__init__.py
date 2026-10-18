# Celery vazifalari ro'yxati: src/worker.py shu paketdan `import *` qiladi. Importlarni o'chirmang.
from .close_inquiry import close_idle_inquiries
from .daily_reminder import daily_reminder
from .generate_reports import generate_monthly_report, generate_weekly_report
from .appointment_reminders import ask_appointment_attendance, check_appointment_reminders, send_pending_appointment_reminders
from .broadcast import execute_broadcast
from .volunteer_leaderboard import post_weekly_volunteer_leaderboard, send_weekly_volunteer_personal_digest
from .monthly_report import send_monthly_analytics_report
from .assignment_reminders import check_assignment_reminders
from .ops_monitor import check_ai_balance, send_daily_error_digest, weekly_gate_summary

__all__ = [
    "close_idle_inquiries",
    "daily_reminder",
    "generate_monthly_report",
    "generate_weekly_report",
    "check_appointment_reminders",
    "send_pending_appointment_reminders",
    "ask_appointment_attendance",
    "execute_broadcast",
    "post_weekly_volunteer_leaderboard",
    "send_weekly_volunteer_personal_digest",
    "send_monthly_analytics_report",
    "check_assignment_reminders",
    "check_ai_balance",
    "send_daily_error_digest",
    "weekly_gate_summary",
]
