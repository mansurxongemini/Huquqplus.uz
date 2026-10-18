"""Botga soxta Telegram update yuborib, qaysi handler ishlashini va bot nima javob berishini ko'rsatadi.

Telegram'ga hech narsa yuborilmaydi: bot so'rovlari ushlab qolinadi va konsolga chiqariladi.
Ishlatish (konteyner ichida):  python scripts/simulate_update.py <user_id> "<matn>"
Inline tugma uchun matn o'rniga:  "cb:<callback_data>"
"""
import asyncio
import sys
from datetime import datetime

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import CallbackQuery, Chat, Message, Update, User as TgUser


class RecordingSession(BaseSession):
    """Bot so'rovlarini Telegram'ga yubormasdan yig'adi."""

    def __init__(self, verbose: bool = True):
        super().__init__()
        self.calls: list = []
        self.verbose = verbose
        self._next_id = 100000

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if self.verbose:
            text = getattr(method, "text", None) or getattr(method, "caption", None) or ""
            print(f"  -> {type(method).__name__}: {text}"[:400])
        returning = method.__returning__
        if returning is bool:
            return True
        if returning is Message or getattr(returning, "__name__", "") == "Message":
            self._next_id += 1
            return Message(message_id=self._next_id, date=datetime.now(),
                           chat=Chat(id=getattr(method, "chat_id", 0) or 0, type="private"))
        return None

    async def stream_content(self, *a, **k):
        yield b""

    async def close(self):
        pass


_dispatcher = None


def get_dispatcher():
    global _dispatcher
    if _dispatcher is None:
        from src.config.bot import dp
        from src.run_polling import DbMiddleware
        if not any(isinstance(m, DbMiddleware) for m in dp.update.middleware):
            dp.update.middleware(DbMiddleware())
        _dispatcher = dp
    return _dispatcher


def make_bot(verbose: bool = True) -> Bot:
    from src.config.settings import settings
    return Bot(settings.BOT_TOKEN, session=RecordingSession(verbose))


async def feed(bot: Bot, user_id: int, text: str):
    """Bitta xabar yoki tugma bosilishini yuboradi; bot qilgan so'rovlar ro'yxatini qaytaradi."""
    session: RecordingSession = bot.session  # type: ignore[assignment]
    start = len(session.calls)
    tg_user = TgUser(id=user_id, is_bot=False, first_name="Test")
    if text.startswith("cb:"):
        bot_msg = Message(message_id=999998, date=datetime.now(), chat=Chat(id=user_id, type="private"),
                          from_user=TgUser(id=bot.id, is_bot=True, first_name="Bot"), text="...")
        update = Update(update_id=1, callback_query=CallbackQuery(
            id="1", from_user=tg_user, chat_instance="1", message=bot_msg, data=text[3:]))
    else:
        update = Update(update_id=1, message=Message(
            message_id=999999, date=datetime.now(), chat=Chat(id=user_id, type="private"),
            from_user=tg_user, text=text))
    await get_dispatcher().feed_update(bot, update)
    return session.calls[start:]


async def main(user_id: int, text: str):
    calls = await feed(make_bot(), user_id, text)
    print("so'rovlar:", len(calls))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
