import asyncio
import logging
from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlmodel import Session

from src.config.bot import bot, dp
from src.database.mysql import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DbMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        with Session(engine) as session:
            data["db_session"] = session
            return await handler(event, data)


def ensure_db_schema():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE tg_bot_appointments ADD COLUMN inquiry_id INT NULL;"))
            conn.commit()
            logger.info("Added inquiry_id column to tg_bot_appointments")
        except Exception:
            pass
        try:
            conn.execute(text("CREATE INDEX ix_tg_bot_appointments_inquiry_id ON tg_bot_appointments (inquiry_id);"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tg_bot_required_channels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_id VARCHAR(100) NOT NULL UNIQUE,
                    channel_name VARCHAR(255) NOT NULL,
                    invite_link VARCHAR(500) NOT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX ix_tg_bot_required_channels_channel_id (channel_id),
                    INDEX ix_tg_bot_required_channels_is_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            conn.commit()
            logger.info("Ensured tg_bot_required_channels table exists")
        except Exception as e:
            logger.warning("ensure_db_schema required_channels warning: %s", e)
        try:
            conn.execute(text("""
                UPDATE tg_bot_users 
                SET is_blocked = 0, block_reason = NULL, blocked_at = NULL, blocked_by = NULL 
                WHERE block_reason LIKE '%Broadcast%';
            """))
            conn.commit()
            logger.info("Unblocked users previously auto-blocked by broadcast")
        except Exception:
            pass



async def start_api_server():
    """
    Veb-sayt (WordPress) REST API so'rovlarini qabul qilish uchun
    FastAPI serverini orqa fonda (background) parallel ishga tushirish
    """
    try:
        import os
        os.environ["USE_TELEGRAM_WEBHOOK"] = "false"
        import uvicorn
        from src.config.settings import settings
        from src.main import app

        port = int(os.getenv("PORT", getattr(settings, "API_PORT", 80)))
        host = os.getenv("HOST", "0.0.0.0")
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        logger.info(f"REST API server {host}:{port} manzilida ishga tushmoqda...")
        await server.serve()
    except Exception as e:
        logger.error(f"REST API serverini ishga tushirishda xatolik yuz berdi: {e}")


async def main():
    ensure_db_schema()
    try:
        from src.database.seed_benefits import seed_benefits
        seed_benefits()
    except Exception as e:
        logger.warning("seed_benefits warning: %s", e)

    await bot.delete_webhook(drop_pending_updates=True)
    dp.update.middleware(DbMiddleware())

    from src.app.ops_checks import run_startup_checks
    asyncio.create_task(run_startup_checks(bot))

    # REST API serverini background task sifatida parallel ishga tushiramiz
    api_task = asyncio.create_task(start_api_server())

    logger.info("Bot Long-Polling rejimida doimiy ishga tushmoqda...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        api_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())

