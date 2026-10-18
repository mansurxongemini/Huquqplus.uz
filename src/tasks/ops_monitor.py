import logging
from datetime import datetime, timedelta

from src.app.ops_checks import check_llm_balance, send_error_digest, send_weekly_gate_summary
from src.config.bot import bot
from src.config.celery_app import celery_app
from src.tasks.utils import async_celery_task

logger = logging.getLogger(__name__)


@async_celery_task(celery_app, name="check_ai_balance")
async def check_ai_balance():
    await check_llm_balance(bot)


@async_celery_task(celery_app, name="send_daily_error_digest")
async def send_daily_error_digest():
    """Kechagi kutilmagan xatolar xulosasi asosiy adminlarga (xato bo'lmasa xabar yuborilmaydi)."""
    await send_error_digest(bot, datetime.now() - timedelta(days=1))


@async_celery_task(celery_app, name="send_weekly_gate_summary")
async def weekly_gate_summary():
    """O'tgan haftadagi qoidaga zid guruh javoblari (kim, necha marta) asosiy adminlarga."""
    await send_weekly_gate_summary(bot, datetime.now() - timedelta(days=7))
