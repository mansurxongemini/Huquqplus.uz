import asyncio
import html
import logging
import re

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LinkPreviewOptions,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.keyboards import get_role_menu, get_ai_chat_menu, inquiry_main_menu
from src.app.rag_client import rag_client, RagError
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.database.redisdb import get_redis
from src.models.inquiry import InquiryMediaType
from src.models.user import User
from src.routes.aiogram.auto_inquiry import (
    AutoInquiryState,
    MENU_BUTTONS_LIST,
    extract_message_payload,
)
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

ai_assistant_router = Router(name="ai_assistant")


class AiChatState(StatesGroup):
    chatting = State()


def strip_html_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text)
    return html.unescape(cleaned)


def get_ai_response_inline_keyboard(answer_id: str | None, lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # callback_data is limited to 64 bytes ("ai_fb:u:" + id); a truncated id would point to nothing
    if answer_id and len(str(answer_id).encode()) <= 56:
        builder.row(
            InlineKeyboardButton(text="👍", callback_data=f"ai_fb:u:{answer_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"ai_fb:d:{answer_id}"),
        )
    builder.row(
        InlineKeyboardButton(text=t("btn_send_to_lawyer", lang), callback_data="ai_to_lawyer")
    )
    return builder.as_markup()


async def send_ai_part(
    bot: Bot,
    chat_id: int | str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    reply_to_message_id: int | None = None,
    disable_notification: bool = False,
) -> Message:
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            disable_notification=disable_notification,
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            plain_text = strip_html_tags(text)
            return await bot.send_message(
                chat_id=chat_id,
                text=plain_text,
                parse_mode=None,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
                disable_notification=disable_notification,
            )
        raise


async def handle_rag_error(err: RagError, message: Message, lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_send_to_lawyer", lang), callback_data="ai_to_lawyer")
    if err.status == 429 or err.code in ("rate_limited", "user_rate_limited", "quota_exceeded"):
        seconds = err.retry_after or 10
        err_text = t("ai_rate_limited", lang).format(seconds=seconds)
        return await message.answer(err_text, reply_markup=builder.as_markup())
    else:
        err_text = t("ai_temporary_unavailable", lang)
        return await message.answer(err_text, reply_markup=builder.as_markup())


async def process_ai_query(
    message: Message,
    text: str,
    user: User | None,
    state: FSMContext,
    bot: Bot,
    user_id: int,
    question_msg_id: int | None = None,
):
    """user_id is the asking citizen's Telegram id (for a callback, message.from_user is the bot)."""
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        return await message.answer(t("ai_unavailable", lang))
    rag_lang = "ru" if lang == "ru" else "uz"
    user_id = str(user_id)

    if len(text) > 4000:
        return await message.answer(t("ai_question_too_long", lang))

    await state.update_data(last_question=text, last_question_msg_id=question_msg_id, pending_media_payload=None)

    data = await state.get_data()
    conv_id = data.get("conversation_id")

    stop_typing = asyncio.Event()

    async def typing_worker():
        while not stop_typing.is_set():
            try:
                await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_typing.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(typing_worker())

    try:
        resp = await rag_client.ask(
            question=text,
            user_id=user_id,
            conversation_id=conv_id,
            language=rag_lang,
        )
    except RagError as e:
        stop_typing.set()
        await typing_task
        return await handle_rag_error(e, message, lang)
    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.warning("Unexpected error during RAG ask: %s", type(e).__name__)
        return await handle_rag_error(RagError(code="server_error", status=500), message, lang)
    finally:
        stop_typing.set()
        if not typing_task.done():
            typing_task.cancel()

    new_conv_id = resp.get("conversation_id")
    answer_id = resp.get("answer_id")
    await state.update_data(
        conversation_id=new_conv_id,
        last_answer_id=answer_id,
        last_question=text,
    )

    parts = resp.get("parts")
    if not parts or not isinstance(parts, list):
        answer = resp.get("answer", "")
        parts = [answer] if answer else ["..."]

    # The generated answer already ends with the disclaimer in its own language, and telegram_html parts end with
    # the numbered source list; adding resp["disclaimer"] here would repeat it (in Uzbek, even under a Russian answer).
    for part in parts[:-1]:
        await send_ai_part(bot=bot, chat_id=message.chat.id, text=part)
    await send_ai_part(
        bot=bot,
        chat_id=message.chat.id,
        text=parts[-1],
        reply_markup=get_ai_response_inline_keyboard(answer_id, lang),
    )


_background_tasks: set[asyncio.Task] = set()


def spawn_lawyer_ai_draft(**kwargs) -> asyncio.Task:
    """Runs send_lawyer_ai_draft in the background without delaying the citizen's flow."""
    task = asyncio.create_task(send_lawyer_ai_draft(**kwargs))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def send_lawyer_ai_draft(
    bot: Bot,
    inquiry_id: int,
    user_id: int,
    group_id: str | int,
    reply_to_message_id: int,
    question_text: str,
    user_lang: str = "uz",
):
    if not settings.AI_LAWYER_DRAFTS or not rag_client.is_configured():
        return

    try:
        rag_lang = "ru" if user_lang == "ru" else "uz"
        resp = await rag_client.ask(
            question=question_text,
            user_id=str(user_id),
            conversation_id=None,
            language=rag_lang,
            internal=True,
        )

        if resp.get("is_refusal") is True:
            return

        parts = resp.get("parts")
        if not parts or not isinstance(parts, list):
            answer = resp.get("answer", "")
            parts = [answer] if answer else []

        if not parts:
            return

        header = "🤖 <b>AI qoralamasi</b> <i>(fuqaroga yuborilmagan, tekshirib foydalaning)</i>\n\n"

        formatted_parts: list[str] = []
        if len(header) + len(parts[0]) <= 4096:
            formatted_parts.append(header + parts[0])
            formatted_parts.extend(parts[1:])
        else:
            formatted_parts.append(header.strip())
            formatted_parts.extend(parts)

        redis_client = get_redis(is_async=True)

        for part in formatted_parts:
            sent_msg = await send_ai_part(
                bot=bot,
                chat_id=group_id,
                text=part,
                reply_to_message_id=reply_to_message_id,
                disable_notification=True,
            )
            if sent_msg:
                try:
                    await redis_client.set(
                        f"inquiry_cont:{group_id}:{sent_msg.message_id}",
                        str(inquiry_id),
                        ex=86400 * 30,
                    )
                    if str(sent_msg.chat.id) != str(group_id):
                        await redis_client.set(
                            f"inquiry_cont:{sent_msg.chat.id}:{sent_msg.message_id}",
                            str(inquiry_id),
                            ex=86400 * 30,
                        )
                except Exception as err:
                    logger.warning("Failed to save lawyer draft cont mapping in Redis: %s", err)

    except Exception as e:
        logger.warning(
            "Error generating lawyer AI draft for inquiry %s: %s",
            inquiry_id,
            type(e).__name__,
        )


@ai_assistant_router.message(Command("ai"), is_private_message)
@ai_assistant_router.message(
    F.text.in_([
        t("menu_ai", "uz"), t("menu_ai", "oz"), t("menu_ai", "ru"),
        "🤖 AI yordamchi", "🤖 AI ёрдамчи", "🤖 ИИ-помощник"
    ]),
    is_private_message
)
async def enter_ai_assistant_mode(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        return await message.answer(t("ai_unavailable", lang))
    if not rag_client.is_enabled():
        return

    if user and user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(AiChatState.chatting)
    await state.update_data(conversation_id=None, last_question=None, last_answer_id=None)
    await message.answer(
        t("ai_intro", lang),
        reply_markup=get_ai_chat_menu(lang),
        parse_mode=ParseMode.HTML,
    )


@ai_assistant_router.message(
    AiChatState.chatting,
    F.text.in_([
        t("btn_back_main", "uz"), t("btn_back_main", "oz"), t("btn_back_main", "ru"),
        "⬅️ Asosiy menyu", "⬅️ Асосий меню", "⬅️ Главное меню",
        t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"),
        "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"
    ]),
    is_private_message
)
async def ai_chat_back_to_main(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@ai_assistant_router.message(
    AiChatState.chatting,
    F.text.in_([
        t("btn_new_ai_chat", "uz"), t("btn_new_ai_chat", "oz"), t("btn_new_ai_chat", "ru"),
        "🔄 Yangi suhbat", "🔄 Янги суҳбат", "🔄 Новый диалог"
    ]),
    is_private_message
)
async def ai_chat_new_dialog(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        await state.clear()
        return await message.answer(t("ai_unavailable", lang))
    data = await state.get_data()
    conv_id = data.get("conversation_id")
    if conv_id:
        try:
            await rag_client.delete_conversation(conv_id, str(message.from_user.id))
        except Exception:
            pass

    await state.update_data(conversation_id=None, last_question=None, last_answer_id=None)
    await message.answer(t("ai_new_chat_started", lang), reply_markup=get_ai_chat_menu(lang))


@ai_assistant_router.message(
    AiChatState.chatting,
    F.text.in_(MENU_BUTTONS_LIST),
    is_private_message
)
async def ai_chat_other_menu_button(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()

    if message.text in [
        t("menu_inquiry", "uz"), t("menu_inquiry", "oz"), t("menu_inquiry", "ru"),
        "📩 Savol yuborish", "📩 Савол юбориш", "📩 Задать вопрос"
    ]:
        from src.routes.aiogram.inquiry import start_inquiry
        return await start_inquiry(message, state, db_session)

    if message.text in [
        t("menu_benefits", "uz"), t("menu_benefits", "oz"), t("menu_benefits", "ru"),
        "Imtiyozlarim", "Имтиёзларим", "Мои льготы", "✨Imtiyozlarim", "✨Имтиёзларим", "✨Мои льготы"
    ]:
        from src.routes.aiogram.benefits import benefits_main_menu
        return await benefits_main_menu(message, db_session)

    return await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))


@ai_assistant_router.callback_query(F.data.startswith("ai_fb:"), is_private_message)
async def handle_ai_feedback(query: CallbackQuery, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        return await query.answer(t("ai_unavailable", lang), show_alert=True)

    parts = query.data.split(":")
    if len(parts) >= 3:
        rating_code = parts[1]
        answer_id = ":".join(parts[2:])
        rating = "up" if rating_code == "u" else "down"
        try:
            await rag_client.feedback(answer_id=answer_id, rating=rating)
        except Exception:
            pass

    await query.answer(t("ai_feedback_received", lang), show_alert=False)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_send_to_lawyer", lang), callback_data="ai_to_lawyer")
    try:
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception:
        pass


@ai_assistant_router.callback_query(F.data == "ai_to_lawyer", is_private_message)
async def handle_ai_to_lawyer_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        return await query.answer(t("ai_unavailable", lang), show_alert=True)
    data = await state.get_data()

    payload = data.get("pending_media_payload")
    if not payload:
        last_q = data.get("last_question")
        if last_q:
            payload = {
                "private_msg_id": data.get("last_question_msg_id") or query.message.message_id,
                "media_type": InquiryMediaType.text.value,
                "text": last_q,
            }

    if not payload:
        await query.answer("Savol topilmadi.", show_alert=True)
        return

    await state.set_state(AutoInquiryState.selecting_section)
    await state.set_data(payload)

    prompt_text = (
        "📁 <b>Илтимос, мурожаатингиз қайси соҳага тегишли эканлигини танланг:</b>"
        if lang == "oz" else
        (
            "📁 <b>Пожалуйста, выберите сферу вашего обращения:</b>"
            if lang == "ru" else
            "📁 <b>Iltimos, murojaatingiz qaysi sohaga tegishli ekanligini tanlang:</b>"
        )
    )
    await query.message.answer(
        prompt_text,
        reply_markup=inquiry_main_menu(lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@ai_assistant_router.message(AiChatState.chatting, F.text, is_private_message)
async def ai_chat_text_handler(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    await process_ai_query(
        message=message,
        text=message.text,
        user=user,
        state=state,
        bot=bot,
        user_id=message.from_user.id,
        question_msg_id=message.message_id,
    )


@ai_assistant_router.message(AiChatState.chatting, is_private_message)
async def ai_chat_non_text_handler(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    if not settings.AI_CITIZEN_ENABLED:
        await state.clear()
        return await message.answer(t("ai_unavailable", lang))

    payload = extract_message_payload(message)
    if payload:
        await state.update_data(pending_media_payload=payload)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_send_to_lawyer", lang), callback_data="ai_to_lawyer")
    await message.reply(
        t("ai_only_text", lang),
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML,
    )
