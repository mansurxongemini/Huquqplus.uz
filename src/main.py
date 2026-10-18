import logging
from fastapi import FastAPI
from src.config.bot import set_bot_webhook
from src.config.settings import settings
from src.routes.main import api_router
from src.routes.api_website import website_router
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    if os.getenv("USE_TELEGRAM_WEBHOOK", "false").lower() in ("true", "1") and settings.BOT_WEBHOOK_URL:
        try:
            await set_bot_webhook()
        except Exception as e:
            logger.info(f"Webhook sozlashda xatolik (ehtimol polling rejimida): {e}")
        from src.app.ops_checks import run_startup_checks
        from src.config.bot import bot
        await run_startup_checks(bot)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

cors_origins = [str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(api_router, prefix=settings.API_V1_STR)
# Rasmiy veb-sayt (WordPress) uchun REST API manzillari:
# 1) GET /api/volunteers-stats
# 2) GET /api/v1/volunteers-stats
app.include_router(website_router, prefix="/api")
app.include_router(website_router, prefix=settings.API_V1_STR)

