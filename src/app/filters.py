from aiogram.types import Message, CallbackQuery
from src.config.settings import settings


def is_private_message(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery) or (hasattr(event, "message") and not hasattr(event, "chat")):
        msg = getattr(event, "message", None)
        if msg and hasattr(msg, "chat") and msg.chat:
            return msg.chat.type == "private"
        return False
    if hasattr(event, "chat") and event.chat:
        return event.chat.type == "private"
    return False


def is_group_message(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery) or (hasattr(event, "message") and not hasattr(event, "chat")):
        msg = getattr(event, "message", None)
        if msg and hasattr(msg, "chat") and msg.chat:
            return msg.chat.type in ["group", "supergroup"]
        return False
    if hasattr(event, "chat") and event.chat:
        return event.chat.type in ["group", "supergroup"]
    return False


def is_group_callback(query: CallbackQuery):
    return bool(query.message and query.message.chat and query.message.chat.type in ["group", "supergroup"])


def reply_to_my_message(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return False
    from_user = message.reply_to_message.from_user
    bot_name = (settings.BOT_NAME or "").lstrip("@").lower()
    replied_user = (from_user.username or "").lower()
    return (replied_user and replied_user == bot_name) or from_user.is_bot
