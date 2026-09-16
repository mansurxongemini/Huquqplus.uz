from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import SimpleEventIsolation
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
from src.routes.aiogram.admin import admin_router
from src.routes.aiogram.private_router import router as private_router
from src.routes.aiogram.group_router import router as group_router
from src.routes.aiogram.appointment import appointment_router
from src.routes.aiogram.help import help_router
import backoff
from sulguk import AiogramSulgukMiddleware
from src.app.middlewares import BlockCheckMiddleware, ThrottlingMiddleware


bot = Bot(settings.BOT_TOKEN)
bot.session.middleware(AiogramSulgukMiddleware())
dp = Dispatcher(
    storage=telegram_storage,
    events_isolation=SimpleEventIsolation())
dp.message.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))
dp.callback_query.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))
dp.message.outer_middleware(BlockCheckMiddleware())
dp.callback_query.outer_middleware(BlockCheckMiddleware())
dp.include_router(admin_router)
dp.include_router(private_router)
dp.include_router(group_router)
dp.include_router(appointment_router)
dp.include_router(help_router)


@backoff.on_exception(backoff.expo, Exception, max_tries=5, max_time=30)
async def set_bot_webhook():
    webhook_path = f"{settings.BOT_WEBHOOK_URL.rstrip('/')}/api/v1/"
    current_url = await bot.get_webhook_info()

    if current_url.url != webhook_path:
        await bot.delete_webhook()
        await bot.set_webhook(url=webhook_path, secret_token=settings.SECRET_KEY)
        print("Telegram webhook set successfully")
    else:
        print("Telegram webhook already set")
