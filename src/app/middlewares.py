import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sulguk import SULGUK_PARSE_MODE
from src.models.user import User
from src.routes.deps.db_session import get_db
from src.app.translations import t


class ThrottlingMiddleware(BaseMiddleware):
    """
    In-memory anti-flood / rate limiting middleware.
    Prevents Telegram FloodWait errors and DOS attacks from spammers.
    """
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.last_update: dict[int, float] = {}
        self.warned: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        from src.config.settings import settings
        if settings.is_admin(user_id):
            return await handler(event, data)

        now = time.monotonic()
        last_time = self.last_update.get(user_id, 0.0)

        # Periodic dictionary cleanup if it grows large
        if len(self.last_update) > 10000:
            threshold = now - 60.0
            self.last_update = {k: v for k, v in self.last_update.items() if v > threshold}
            self.warned = {k: v for k, v in self.warned.items() if v > threshold}

        if (now - last_time) < self.rate_limit:
            # Throttled!
            last_warn = self.warned.get(user_id, 0.0)
            if (now - last_warn) > 2.0:
                self.warned[user_id] = now
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⚠️ Iltimos, biroz kuting...", show_alert=False)
                    except Exception:
                        pass
                elif isinstance(event, Message) and event.chat and event.chat.type == "private":
                    try:
                        await event.answer("⚠️ Iltimos, biroz kuting (juda tez xabar yuborildi)!")
                    except Exception:
                        pass
            return

        self.last_update[user_id] = now
        return await handler(event, data)


class BlockCheckMiddleware(BaseMiddleware):
    """
    Global middleware to block access for blocked users in private chats.
    If a user has is_blocked == True, drops execution and informs the user.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        is_private = False

        if isinstance(event, Message):
            if event.chat and event.chat.type == "private" and event.from_user:
                user_id = event.from_user.id
                is_private = True
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat and event.message.chat.type == "private" and event.from_user:
                user_id = event.from_user.id
                is_private = True
            elif not event.message and event.from_user:
                user_id = event.from_user.id
                is_private = True

        if is_private and user_id:
            from src.config.settings import settings
            if settings.is_admin(user_id):
                return await handler(event, data)

            db_session = data.get("db_session")
            if db_session:
                user = User.get_by_user_id(user_id, db_session)
            else:
                session_gen = get_db()
                db = next(session_gen)
                try:
                    user = User.get_by_user_id(user_id, db)
                finally:
                    db.close()

            if user and user.is_blocked:
                lang = user.language or "uz"
                text = t("user_blocked", lang)
                if user.block_reason:
                    reason_title = "<b>Sabab:</b>" if lang == "uz" else "<b>Причина:</b>"
                    text += f"<br/><br/>{reason_title} <i>{user.block_reason}</i>"

                if isinstance(event, Message):
                    await event.answer(text, parse_mode=SULGUK_PARSE_MODE)
                elif isinstance(event, CallbackQuery):
                    await event.answer(t("user_blocked", lang), show_alert=True)
                return

        return await handler(event, data)
