import logging
from aiogram import Dispatcher, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent
from aiogram.fsm.storage.memory import SimpleEventIsolation
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
import backoff
from sulguk import AiogramSulgukMiddleware
from src.app.middlewares import BlockCheckMiddleware, ThrottlingMiddleware, MandatorySubscriptionMiddleware, MenuButtonResetMiddleware, ChatMigrationRequestMiddleware

bot = Bot(settings.BOT_TOKEN)
bot.session.middleware(AiogramSulgukMiddleware())
bot.session.middleware(ChatMigrationRequestMiddleware())
dp = Dispatcher(
    storage=telegram_storage,
    events_isolation=SimpleEventIsolation())
dp.message.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))
dp.callback_query.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))
dp.message.outer_middleware(BlockCheckMiddleware())
dp.callback_query.outer_middleware(BlockCheckMiddleware())
dp.message.outer_middleware(MandatorySubscriptionMiddleware())
dp.callback_query.outer_middleware(MandatorySubscriptionMiddleware())
dp.message.outer_middleware(MenuButtonResetMiddleware())

from src.routes.aiogram.admin import admin_router
from src.routes.aiogram.private_router import router as private_router
from src.routes.aiogram.group_router import router as group_router
from src.routes.aiogram.inquiry_assign import assign_router
from src.routes.aiogram.appointment import appointment_router
from src.routes.aiogram.help import help_router
from src.routes.aiogram.ai_assistant import ai_assistant_router
from src.routes.aiogram.auto_inquiry import auto_inquiry_router

logger = logging.getLogger(__name__)

dp.include_router(admin_router)
dp.include_router(private_router)
dp.include_router(group_router)
dp.include_router(assign_router)
dp.include_router(appointment_router)
dp.include_router(help_router)
dp.include_router(ai_assistant_router)
dp.include_router(auto_inquiry_router)


@dp.errors()
async def ignore_not_modified(event: ErrorEvent):
    """Tugma ikki marta bosilsa Telegram "message is not modified" qaytaradi — bu xato emas."""
    if isinstance(event.exception, TelegramBadRequest) and "message is not modified" in str(event.exception):
        if event.update.callback_query:
            try:
                await event.update.callback_query.answer()
            except Exception:
                pass
        return True
    from src.app.ops_checks import record_bot_error
    handler = ""
    if event.update.message and event.update.message.text:
        handler = event.update.message.text[:40]
    elif event.update.callback_query:
        handler = (event.update.callback_query.data or "")[:40]
    record_bot_error(event.exception, handler)
    return False


@backoff.on_exception(backoff.expo, Exception, max_tries=5, max_time=30)
async def set_bot_webhook():
    webhook_path = f"{settings.BOT_WEBHOOK_URL.rstrip('/')}/api/v1/"
    current_url = await bot.get_webhook_info()

    if current_url.url != webhook_path:
        await bot.delete_webhook()
        await bot.set_webhook(url=webhook_path, secret_token=settings.SECRET_KEY)
        logger.info("Telegram webhook set successfully")
    else:
        logger.info("Telegram webhook already set")
