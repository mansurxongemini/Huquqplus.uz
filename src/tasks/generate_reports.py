from datetime import datetime

from aiogram.types import FSInputFile
from dateutil.relativedelta import relativedelta

from src.app.generate_report import generate_report
from src.config.bot import bot
from src.config.celery_app import celery_app
from src.config.settings import settings
from src.tasks.utils import async_celery_task


@async_celery_task(celery_app, name="generate_monthly_report")
async def generate_monthly_report():
    now = datetime.now()
    today = datetime(now.year, now.month, 1)
    previous_month = today - relativedelta(months=1)
    filename = generate_report((previous_month, today))

    file = FSInputFile(filename)

    await bot.send_document(settings.get_report_recipient(), file, caption="Oylik Hisobot")


@async_celery_task(celery_app, name="generate_weekly_report")
async def generate_weekly_report():
    now = datetime.now()
    monday = now - relativedelta(days=now.weekday())
    previous_week = monday - relativedelta(days=7)
    filename = generate_report((previous_week, monday))

    file = FSInputFile(filename)

    await bot.send_document(settings.get_report_recipient(), file, caption="Haftalik Hisobot")
