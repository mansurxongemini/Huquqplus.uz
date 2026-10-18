import logging
from aiogram.types import Update
from fastapi import APIRouter, Request, HTTPException, status
from src.config.bot import dp, bot
from src.config.settings import settings
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

api_router = APIRouter()


@api_router.post("/")
async def root(update: Update, db_session: DBSession, request: Request):
    if request.headers.get("x-telegram-bot-api-secret-token", "") != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid secret token"
        )

    try:
        await dp.feed_update(bot, update, db_session=db_session)
    except Exception as e:
        logger.exception("Update handling traceback")
        logger.warning("Failed to handle update: %s", e)
    return {"ok": True}


@api_router.get("/")
async def home_function():
    return {"ok": "Works as expected"}
