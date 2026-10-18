import os
import logging
from datetime import datetime, timedelta

from src.config.celery_app import celery_app
from src.config.settings import settings
from src.config.bot import bot
from src.tasks.utils import async_celery_task
from src.app.generate_staff_report import generate_comprehensive_report, format_telegram_analytics_summary, send_report_document

logger = logging.getLogger(__name__)


def get_previous_month_range(ref_dt: datetime | None = None) -> tuple[datetime, datetime, str]:
    """Calculates the date range for the previous calendar month"""
    now = ref_dt or datetime.now()
    # 1st of current month
    first_this_month = datetime(now.year, now.month, 1, 0, 0, 0)
    # End of previous month
    last_prev_month = first_this_month - timedelta(seconds=1)
    # 1st of previous month
    first_prev_month = datetime(last_prev_month.year, last_prev_month.month, 1, 0, 0, 0)
    
    period_name = f"O'tgan oy ({first_prev_month.strftime('%m.%Y')})"
    return first_prev_month, last_prev_month, period_name


@async_celery_task(celery_app, name="send_monthly_analytics_report")
async def send_monthly_analytics_report():
    """
    Automated monthly periodic task:
    Runs on the 1st of every month at 09:00 AM.
    Generates the comprehensive 6-sheet Excel report for the previous month
    and sends it to all administrators in Telegram.
    """
    logger.info("Starting monthly automated analytics report task...")
    start_dt, end_dt, period_name = get_previous_month_range()

    file_path = None
    try:
        file_path, summary_dict = generate_comprehensive_report(date_range=(start_dt, end_dt))
        caption_text = format_telegram_analytics_summary(summary_dict, period_name)

        doc_filename = f"HuquqPlus_Oylik_Hisobot_{start_dt.strftime('%Y_%m')}.xlsx"

        for admin_id in settings.admin_ids_list:
            try:
                await send_report_document(bot, admin_id, file_path, doc_filename, caption_text, period_name)
                logger.info("Sent monthly analytics report to admin %s", admin_id)
            except Exception as e:
                logger.error("Failed to send monthly report to admin %s: %s", admin_id, e)

    except Exception as e:
        logger.exception("Error in send_monthly_analytics_report task: %s", e)
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
