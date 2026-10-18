import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.models.required_channel import RequiredChannel
from src.app.translations import t

logger = logging.getLogger(__name__)


async def is_user_subscribed_to_channel(bot: Bot, channel_id: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        # In Telegram channels, valid subscribed statuses are: member, administrator, creator, restricted
        return member.status in ["member", "administrator", "creator", "restricted"]
    except TelegramBadRequest as e:
        logger.debug("Chat member check bad request user=%s chat=%s: %s", user_id, channel_id, e)
        return False
    except TelegramAPIError as e:
        logger.warning("Telegram API error checking chat member user=%s chat=%s: %s", user_id, channel_id, e)
        return False
    except Exception as e:
        logger.warning("Unexpected error checking chat member user=%s chat=%s: %s", user_id, channel_id, e)
        return False


async def check_user_channels(bot: Bot, user_id: int, channels: list[RequiredChannel]) -> tuple[bool, list[RequiredChannel]]:
    """
    Checks user membership across given channels.
    Returns (is_all_subscribed, unsubscribed_channels_list).
    """
    if not channels:
        return True, []

    unsubscribed: list[RequiredChannel] = []
    for ch in channels:
        is_sub = await is_user_subscribed_to_channel(bot, ch.channel_id, user_id)
        if not is_sub:
            unsubscribed.append(ch)

    return (len(unsubscribed) == 0), unsubscribed


def build_subscription_keyboard(channels: list[RequiredChannel], lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Builds the inline keyboard matching the user's design:
    - ➕ Obuna bo'lish (for each channel URL)
    - ✅ Tasdiqlash (callback_data='check_sub')
    """
    builder = InlineKeyboardBuilder()

    btn_sub_text = t("btn_subscribe", lang)
    btn_verify_text = t("btn_verify_sub", lang)

    for ch in channels:
        builder.button(text=btn_sub_text, url=ch.invite_link)

    builder.button(text=btn_verify_text, callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()


def get_subscription_prompt_text(lang: str = "uz") -> str:
    return t("mandatory_sub_prompt", lang)
