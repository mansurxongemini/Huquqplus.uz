import logging
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

        # 1. Never throttle media groups (albums sent by Telegram)
        if isinstance(event, Message) and getattr(event, "media_group_id", None):
            self.last_update[user_id] = now
            return await handler(event, data)

        # 2. Never drop legitimate media files (photos, documents, audio, videos) in private chats
        if isinstance(event, Message) and event.chat and event.chat.type == "private" and (
            getattr(event, "photo", None)
            or getattr(event, "document", None)
            or getattr(event, "video", None)
            or getattr(event, "voice", None)
            or getattr(event, "video_note", None)
        ):
            self.last_update[user_id] = now
            return await handler(event, data)

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
                    reason_title = t("block_reason_label", lang)
                    text += f"<br/><br/>{reason_title} <i>{user.block_reason}</i>"

                if isinstance(event, Message):
                    await event.answer(text, parse_mode=SULGUK_PARSE_MODE)
                elif isinstance(event, CallbackQuery):
                    await event.answer(t("user_blocked", lang), show_alert=True)
                return

        return await handler(event, data)


class MandatorySubscriptionMiddleware(BaseMiddleware):
    """
    Middleware that enforces mandatory channel subscription in private chats.
    If the user has not subscribed or leaves the channel, blocks access and
    prompts the user with subscription buttons and a verification button.
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

        if not is_private or not user_id:
            return await handler(event, data)

        # 1. Skip check for bot administrators
        from src.config.settings import settings
        if settings.is_admin(user_id):
            return await handler(event, data)

        # 2. Allow /start, language selection, and subscription verification callbacks to pass through
        if isinstance(event, CallbackQuery) and event.data and (event.data == "check_sub" or event.data.startswith("set_lang:")):
            return await handler(event, data)
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        # 3. Retrieve user and their language
        from src.models.required_channel import RequiredChannel
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

        # If user is not yet registered and hasn't selected language yet, let them start
        state = data.get("state")
        state_data = await state.get_data() if state else {}
        user_lang = user.language if (user and user.language) else state_data.get("language")

        if not user and not user_lang:
            # New user who hasn't selected a language yet; let them interact with /start or language selection
            return await handler(event, data)

        user_lang = user_lang or "uz"

        # 4. Retrieve active channels matching user's language
        if db_session:
            channels = RequiredChannel.get_active_channels_for_lang(user_lang, db_session)
        else:
            session_gen = get_db()
            db = next(session_gen)
            try:
                channels = RequiredChannel.get_active_channels_for_lang(user_lang, db)
            finally:
                db.close()

        if not channels:
            return await handler(event, data)

        # 5. Check Redis cache (60s validity) to ensure high performance without API spam
        from src.database.redisdb import get_redis
        redis = get_redis(is_async=True)
        cache_key = f"user_sub_ok:{user_id}:{user_lang}"
        try:
            is_cached = await redis.get(cache_key)
            if is_cached:
                return await handler(event, data)
        except Exception:
            pass

        # 6. Live check via Bot API
        bot = data.get("bot")
        from src.app.subscription_utils import check_user_channels, build_subscription_keyboard, get_subscription_prompt_text
        is_all_sub, unsubscribed = await check_user_channels(bot, user_id, channels)

        if is_all_sub:
            try:
                await redis.set(cache_key, "1", ex=60)
            except Exception:
                pass
            return await handler(event, data)

        # 7. Not subscribed: prompt user with only their language's channel(s) and drop update
        prompt_text = get_subscription_prompt_text(user_lang)
        markup = build_subscription_keyboard(unsubscribed, user_lang)

        if isinstance(event, Message):
            await event.answer(prompt_text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
        elif isinstance(event, CallbackQuery):
            await event.answer(t("sub_not_verified", user_lang), show_alert=True)
            try:
                await event.message.answer(prompt_text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
            except Exception:
                pass

        return


class MenuButtonResetMiddleware(BaseMiddleware):
    """Biror bosqich (FSM holati) matn kutayotganda pastki menyu tugmasi bosilsa, tugma nomi
    foydalanuvchi kiritmasi (fikr, savol, javob) bo'lib ketmasligi uchun holat tozalanadi va
    xabar oddiy menyu buyrug'i sifatida qayta ishlanadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if (
            isinstance(event, Message)
            and event.chat.type == "private"
            and event.text
            and data.get("raw_state")
        ):
            from src.app.keyboards import menu_button_texts
            if event.text.strip() in menu_button_texts():
                state = data.get("state")
                if state is not None:
                    await state.clear()
                data["raw_state"] = None
        return await handler(event, data)


class ChatMigrationRequestMiddleware:
    """Guruh superguruhga aylantirilsa Telegram eski ID ni rad etadi (migrate_to_chat_id).
    So'rov yangi ID bilan bir marta qayta yuboriladi va moslik eslab qolinadi — bot yiqilmaydi.
    .env dagi ID ni baribir yangilash kerak: log shuni eslatadi."""

    migrations: dict[int, int] = {}

    async def __call__(self, make_request, bot, method):
        from aiogram.exceptions import TelegramMigrateToChat
        chat_id = getattr(method, "chat_id", None)
        new_id = self.migrations.get(self._as_int(chat_id))
        if new_id is not None:
            method.chat_id = new_id
        try:
            return await make_request(bot, method)
        except TelegramMigrateToChat as e:
            old = self._as_int(getattr(method, "chat_id", None))
            if old is None or not hasattr(method, "chat_id"):
                raise
            self.migrations[old] = e.migrate_to_chat_id
            logging.getLogger(__name__).error(
                "Guruh %s superguruhga ko'chgan, yangi ID %s. .env dagi guruh ID sini yangilang!",
                old, e.migrate_to_chat_id,
            )
            method.chat_id = e.migrate_to_chat_id
            return await make_request(bot, method)

    @staticmethod
    def _as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
