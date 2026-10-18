import re
import html
import json
import asyncio
import aiohttp
from datetime import datetime, time, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    Message,
    LinkPreviewOptions,
    Chat,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE
from src.app.assign_helpers import decide_answer_gate, review_hashes_match
from src.app.calendar_utils import format_uz_date
from src.app.filters import is_group_message, reply_to_my_message, is_group_callback
from src.app.keyboards import get_rating_keyboard
from src.app.html_utils import escape_multiline
from src.app.inquiry_card import refresh_inquiry_card
from src.app.link_utils import build_group_message_link
from src.app.timeutils import tz
from src.app.translations import t
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
from src.database.redisdb import get_redis
from sqlmodel import select
from src.models.assignment import AssignmentStatus, InquiryAssignment
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.volunteer import Volunteer
from src.models.user import User
from src.routes.aiogram.admin import execute_block_user, execute_unblock_user
from src.routes.deps.db_session import DBSession
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
import logging
from src.app.appointment_card import (
    render_appointment_card,
    get_appointment_markup,
    get_lawyers_keyboard,
    get_escalation_dates_keyboard,
    get_escalation_slots_keyboard,
    notify_citizen_appointment_update,
    render_escalated_appointment_card,
    get_escalated_appointment_markup,
)

logger = logging.getLogger(__name__)

router = Router(name="group")


def get_group_id(chat: Chat) -> str:
    if chat.username:
        return f"@{chat.username}"
    return str(chat.id)


def get_message_link(chat: Chat, message_id: int) -> str | None:
    return build_group_message_link(get_group_id(chat), message_id)


async def try_with_reply(handler, reply_to_message_id: int | None = None, **kwargs):
    if reply_to_message_id:
        try:
            return await handler(reply_to_message_id=reply_to_message_id, **kwargs)
        except TelegramBadRequest as e:
            if "message to be replied not found" in str(e.message).lower():
                return await handler(**kwargs)
            raise e
    else:
        return await handler(**kwargs)


async def send_answer_to_citizen(
    handler,
    args: dict,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> tuple[bool, str, any]:
    """
    Sends the answer to the citizen with automatic retry for transient network/server errors.
    Returns:
        (success: bool, status_reason: str, result_or_exception)
        status_reason in ["success", "blocked", "restricted", "network_error", "bad_request", "unknown_error"]
    """
    last_exception = None
    current_args = dict(args)

    for attempt in range(1, max_retries + 1):
        try:
            sent_msg = await try_with_reply(handler, **current_args)
            return True, "success", sent_msg
        except TelegramForbiddenError as e:
            # Citizen blocked the bot or account deleted
            return False, "blocked", e
        except TelegramBadRequest as e:
            err_text = str(e.message).lower()
            if "restricted" in err_text:
                return False, "restricted", e
            if "bot was blocked by the user" in err_text or "user is deactivated" in err_text or "chat not found" in err_text:
                return False, "blocked", e
            if "message to be replied not found" in err_text:
                current_args.pop("reply_to_message_id", None)
                try:
                    sent_msg = await handler(**current_args)
                    return True, "success", sent_msg
                except Exception as inner_e:
                    last_exception = inner_e
            else:
                last_exception = e
                if attempt >= 2:
                    return False, f"bad_request: {e}", e
        except TelegramRetryAfter as e:
            last_exception = e
            wait_time = max(float(getattr(e, "retry_after", 1.0)), 1.0)
            await asyncio.sleep(wait_time)
            continue
        except (TelegramNetworkError, aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(initial_delay * attempt)
                continue
            return False, f"network_error: {e}", e
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(initial_delay * attempt)
                continue
            return False, f"unknown_error: {e}", e

    return False, f"failed_after_retries: {last_exception}", last_exception


def is_inquiry_already_edited(message: Message, inquiry: Inquiry) -> bool:
    """Checks whether the inquiry group card has already been edited with 'Murojaatga javob berildi'."""
    # 1. If lawyer replied directly to the group inquiry card:
    replied_msg = getattr(message, "reply_to_message", None)
    if replied_msg and getattr(replied_msg, "message_id", None) == inquiry.group_question_id:
        content = getattr(replied_msg, "text", None) or getattr(replied_msg, "caption", None) or ""
        return "Murojaatga javob berildi" in content

    # 2. If lawyer replied to another message (continuation or thread reply), check Redis:
    try:
        r = get_redis(is_async=False)
        if r.get(f"inquiry_group_edited:{inquiry.id}"):
            return True
    except Exception:
        pass

    return False


@router.callback_query(F.data.startswith("block_user:"), is_group_callback)
async def block_user_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    is_admin = False
    try:
        member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
        if member.status in ["creator", "administrator"]:
            is_admin = True
    except Exception:
        pass

    if not is_admin and settings.is_admin(query.from_user.id):
        is_admin = True

    if not is_admin:
        return await query.answer("Kechirasiz, sizda bu amalni bajarish huquqi yo'q!", show_alert=True)

    target_user_id = int(query.data.split(":")[1])
    target_user = User.get_by_user_id(target_user_id, db_session)
    if not target_user:
        return await query.answer("Foydalanuvchi topilmadi!", show_alert=True)

    target_user.block(blocked_by=query.from_user.id, reason="Guruh ma'muriyati tomonidan", session=db_session)

    # 1. Clear FSM state
    try:
        storage_key = StorageKey(user_id=target_user_id, chat_id=target_user_id, bot_id=bot.id)
        user_state = FSMContext(telegram_storage, storage_key)
        await user_state.clear()
    except Exception as e:
        logger.warning("Failed to clear FSM state on block: %s", e)

    # 2. Cancel all active/replied inquiries
    try:
        from sqlmodel import select
        active_inquiries = db_session.exec(
            select(Inquiry).where(
                Inquiry.user_id == target_user_id,
                Inquiry.status.in_([InquiryStatus.active, InquiryStatus.replied])
            )
        ).all()
        for inq in active_inquiries:
            inq.status = InquiryStatus.cancelled
            inq.updated_at = datetime.now()
            db_session.add(inq)
        db_session.commit()
    except Exception as e:
        logger.warning("Failed to cancel active inquiries on block: %s", e)

    # 2.1 Cancel all active appointments
    try:
        active_apps = db_session.exec(
            select(Appointment).where(
                Appointment.user_id == target_user_id,
                Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
            )
        ).all()
        for app in active_apps:
            app.status = AppointmentStatus.cancelled
            app.cancellation_reason = "Foydalanuvchi bloklandi (Guruh ma'muriyati tomonidan)"
            app.updated_at = datetime.now()
            db_session.add(app)
        db_session.commit()
    except Exception as e:
        logger.warning("Failed to cancel active appointments on block: %s", e)

    # 3. Notify user
    user_lang = target_user.language or "uz"
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=t("user_blocked_notification", user_lang),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception:
        pass

    new_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Blokdan chiqarish", callback_data=f"unblock_user:{target_user_id}")]
        ]
    )
    try:
        await query.message.edit_reply_markup(reply_markup=new_markup)
    except Exception as e:
        logger.warning("Failed to edit reply markup: %s", e)

    name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or str(target_user_id)
    await query.answer(f"🚫 {name} (ID: {target_user.user_id}) muvaffaqiyatli bloklandi!", show_alert=True)


@router.callback_query(F.data.startswith("unblock_user:"), is_group_callback)
async def unblock_user_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    is_admin = False
    try:
        member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
        if member.status in ["creator", "administrator"]:
            is_admin = True
    except Exception:
        pass

    if not is_admin and settings.is_admin(query.from_user.id):
        is_admin = True

    if not is_admin:
        return await query.answer("Kechirasiz, sizda bu amalni bajarish huquqi yo'q!", show_alert=True)

    target_user_id = int(query.data.split(":")[1])
    target_user = User.get_by_user_id(target_user_id, db_session)
    if not target_user:
        return await query.answer("Foydalanuvchi topilmadi!", show_alert=True)

    target_user.unblock(db_session)

    # Notify user
    user_lang = target_user.language or "uz"
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=t("user_unblocked_notification", user_lang),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception:
        pass

    new_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block_user:{target_user_id}")]
        ]
    )
    try:
        await query.message.edit_reply_markup(reply_markup=new_markup)
    except Exception as e:
        logger.warning("Failed to edit reply markup: %s", e)

    name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or str(target_user_id)
    await query.answer(f"✅ {name} (ID: {target_user.user_id}) blokdan chiqarildi!", show_alert=True)


def extract_user_id_from_reply(reply_message: Message | None, db_session: DBSession, bot: Bot) -> int | None:
    """Extract user_id from replied bot message (Inquiry, Appointment, or text with ID)"""
    if not reply_message:
        return None

    group_id = get_group_id(reply_message.chat)
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=reply_message.message_id,
        bot_id=bot.id,
        session=db_session
    )
    if not inquiry:
        inquiry = Inquiry.get_by_message_id(
            group_id=str(reply_message.chat.id),
            group_question_id=reply_message.message_id,
            bot_id=bot.id,
            session=db_session
        )
    if not inquiry:
        try:
            r = get_redis(is_async=False)
            cont_id = r.get(f"inquiry_cont:{group_id}:{reply_message.message_id}")
            if not cont_id:
                cont_id = r.get(f"inquiry_cont:{reply_message.chat.id}:{reply_message.message_id}")
            if cont_id:
                inq_id_int = int(cont_id.decode() if isinstance(cont_id, bytes) else cont_id)
                inquiry = db_session.get(Inquiry, inq_id_int)
        except Exception:
            pass
    if inquiry and inquiry.user_id:
        return inquiry.user_id

    # 1. Check Appointment by message_id
    appointment = Appointment.get_by_group_message_id(reply_message.message_id, db_session)
    if not appointment and reply_message.reply_to_message:
        appointment = Appointment.get_by_group_message_id(reply_message.reply_to_message.message_id, db_session)
    if appointment and appointment.user_id:
        return appointment.user_id

    # 2. Check inline keyboard buttons
    if reply_message.reply_markup and reply_message.reply_markup.inline_keyboard:
        for row in reply_message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data:
                    continue
                if btn.callback_data.startswith(("block_user:", "unblock_user:")):
                    try:
                        return int(btn.callback_data.split(":")[1])
                    except (ValueError, IndexError):
                        pass
                if btn.callback_data.startswith(("appointment:", "app_escalate:")):
                    parts = btn.callback_data.split(":")
                    if len(parts) >= 3:
                        try:
                            app_id = int(parts[2])
                            app = Appointment.get_by_id(app_id, db_session)
                            if app and app.user_id:
                                return app.user_id
                        except (ValueError, IndexError):
                            pass

    # 3. Check entities and caption_entities for user links
    entities = (reply_message.entities or []) + (reply_message.caption_entities or [])
    for entity in entities:
        if entity.type == "text_link" and entity.url:
            match = re.search(r"tg://user\?id=(\d+)", entity.url)
            if match:
                return int(match.group(1))
            match_un = re.search(r"t\.me/([a-zA-Z0-9_]+)", entity.url)
            if match_un:
                uname = match_un.group(1)
                if uname.lower() not in ["c", "share", "joinchat"]:
                    u = db_session.exec(select(User).where(User.username == uname)).first()
                    if u and u.user_id:
                        return u.user_id

    # 4. Check text/caption for Appointment ID (№14, #14)
    text = reply_message.text or reply_message.caption or ""
    match_app = re.search(r"ARIZA!\s*\(№(\d+)\)", text, re.IGNORECASE)
    if not match_app:
        match_app = re.search(r"YURIST QABULIGA.*?№(\d+)", text, re.IGNORECASE)
    if not match_app:
        match_app = re.search(r"[№#](\d+)", text)
    if match_app:
        try:
            app_id = int(match_app.group(1))
            app = Appointment.get_by_id(app_id, db_session)
            if app and app.user_id:
                return app.user_id
        except Exception:
            pass

    # 5. Regex matching in text or caption
    match = re.search(r"ID:\s*<code>(\d+)</code>", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"ID:\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"tg://user\?id=(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


@router.message(is_group_message, Command("block"), reply_to_my_message)
async def handle_group_block_command(message: Message, db_session: DBSession, bot: Bot):
    is_admin = False
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ["creator", "administrator"]:
            is_admin = True
    except Exception:
        pass

    if not is_admin and settings.is_admin(message.from_user.id):
        is_admin = True

    if not is_admin:
        return await _temporary_group_reply(message, bot, "⛔️ Kechirasiz, sizda bu amalni bajarish huquqi yo'q!")

    target_user_id = extract_user_id_from_reply(message.reply_to_message, db_session, bot)

    args = message.text.split(maxsplit=1)
    reason = "Guruh ma'muriyati tomonidan"

    if len(args) > 1:
        rest = args[1].strip()
        parts = rest.split(maxsplit=1)
        if parts[0].isdigit():
            target_user_id = int(parts[0])
            reason = parts[1].strip() if len(parts) > 1 else reason
        else:
            reason = rest

    if not target_user_id:
        return await _temporary_group_reply(message, bot, "⚠️ Ushbu xabarga tegishli foydalanuvchi ID si aniqlanmadi.")

    success, name = await execute_block_user(target_user_id, message.from_user.id, reason, db_session, bot)

    # Update replied message markup to "Unblock" if possible
    if message.reply_to_message:
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔓 Blokdan chiqarish", callback_data=f"unblock_user:{target_user_id}")
                ]])
            )
        except Exception:
            pass

    await message.reply(
        f"🚫 <b>Foydalanuvchi bloklandi!</b><br/>"
        f"👤 {name} (ID: <code>{target_user_id}</code>)<br/>"
        f"📝 Sabab: <i>{reason}</i>",
        parse_mode=SULGUK_PARSE_MODE
    )

    try:
        await asyncio.sleep(4)
        await message.delete()
    except Exception:
        pass


@router.message(is_group_message, Command("unblock"), reply_to_my_message)
async def handle_group_unblock_command(message: Message, db_session: DBSession, bot: Bot):
    is_admin = False
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ["creator", "administrator"]:
            is_admin = True
    except Exception:
        pass

    if not is_admin and settings.is_admin(message.from_user.id):
        is_admin = True

    if not is_admin:
        return await _temporary_group_reply(message, bot, "⛔️ Kechirasiz, sizda bu amalni bajarish huquqi yo'q!")

    target_user_id = extract_user_id_from_reply(message.reply_to_message, db_session, bot)

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip().isdigit():
        target_user_id = int(args[1].strip())

    if not target_user_id:
        return await _temporary_group_reply(message, bot, "⚠️ Ushbu xabarga tegishli foydalanuvchi ID si aniqlanmadi.")

    success, name = await execute_unblock_user(target_user_id, db_session, bot)

    # Update replied message markup to "Block" if possible
    if message.reply_to_message:
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block_user:{target_user_id}")
                ]])
            )
        except Exception:
            pass

    await message.reply(
        f"🔓 <b>Foydalanuvchi blokdan chiqarildi!</b><br/>"
        f"👤 {name} (ID: <code>{target_user_id}</code>)",
        parse_mode=SULGUK_PARSE_MODE
    )

    try:
        await asyncio.sleep(4)
        await message.delete()
    except Exception:
        pass


@router.message(is_group_message, Command("del"))
async def handle_group_delete_command(message: Message, db_session: DBSession, bot: Bot):
    if not message.reply_to_message:
        try:
            await message.delete()
        except Exception:
            pass
        return

    # 1. Verify admin permissions (group admin, anonymous group admin, official lawyer, or bot superadmin)
    is_admin = False
    if message.from_user and settings.is_admin(message.from_user.id):
        is_admin = True
    elif message.sender_chat and message.sender_chat.id == message.chat.id:
        is_admin = True
    elif message.from_user and OfficialLawyer.get_by_user_id(message.from_user.id, db_session):
        is_admin = True
    elif message.from_user:
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception as e:
            logger.warning("Failed to get chat member in /del: %s", e)

    if not is_admin:
        try:
            await message.delete()
        except Exception:
            pass
        return

    # 2. Check if replied message is an Inquiry
    group_id = get_group_id(message.chat)
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=message.reply_to_message.message_id,
        bot_id=bot.id,
        session=db_session
    )
    if not inquiry:
        try:
            r = get_redis(is_async=False)
            cont_id = r.get(f"inquiry_cont:{group_id}:{message.reply_to_message.message_id}")
            if not cont_id:
                cont_id = r.get(f"inquiry_cont:{message.chat.id}:{message.reply_to_message.message_id}")
            if cont_id:
                inq_id_int = int(cont_id.decode() if isinstance(cont_id, bytes) else cont_id)
                inquiry = db_session.get(Inquiry, inq_id_int)
        except Exception:
            pass

    if inquiry:
        # Check if there is a linked continuation message in group
        try:
            r = get_redis(is_async=False)
            cont_msg_id = r.get(f"inquiry_cont_msg:{inquiry.id}")
            if cont_msg_id:
                cont_msg_id_int = int(cont_msg_id.decode() if isinstance(cont_msg_id, bytes) else cont_msg_id)
                await bot.delete_message(chat_id=message.chat.id, message_id=cont_msg_id_int)
        except Exception:
            pass

        # Also delete any linked Appointment if it was escalated
        try:
            linked_app = db_session.exec(select(Appointment).where(Appointment.inquiry_id == inquiry.id)).first()
            if linked_app:
                db_session.delete(linked_app)
        except Exception:
            pass

        db_session.delete(inquiry)
        db_session.commit()

        # Audit log
        logger.info(
            "deleted_inquiry_via_del_command",
            extra={
                "admin_id": message.from_user.id,
                "inquiry_id": inquiry.id,
                "chat_id": message.chat.id,
            }
        )

    # 3. Check if replied message is an Appointment
    appointment = Appointment.get_by_group_message_id(message.reply_to_message.message_id, db_session)
    if not appointment:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        match = re.search(r"№(\d+)", text)
        if match:
            appointment = Appointment.get_by_id(int(match.group(1)), db_session)

    if appointment:
        app_id_val = appointment.id
        db_session.delete(appointment)
        db_session.commit()
        logger.info(
            "deleted_appointment_via_del_command",
            extra={
                "admin_id": message.from_user.id,
                "appointment_id": app_id_val,
                "chat_id": message.chat.id,
            }
        )

    # 4. Delete the replied message and the /del command message
    try:
        await message.reply_to_message.delete()
    except Exception as e:
        logger.warning("Failed to delete replied message: %s", e)

    try:
        await message.delete()
    except Exception:
        pass


async def is_coordinator_or_lawyer_or_admin(message_or_query, db_session: DBSession, bot: Bot) -> bool:
    user_id = message_or_query.from_user.id if message_or_query.from_user else 0
    if isinstance(message_or_query, CallbackQuery):
        chat_id = message_or_query.message.chat.id if message_or_query.message else 0
    else:
        chat_id = message_or_query.chat.id if hasattr(message_or_query, "chat") else 0
        if hasattr(message_or_query, "sender_chat") and message_or_query.sender_chat:
            return True

    if user_id and settings.is_admin(user_id):
        return True
    if user_id and OfficialLawyer.get_by_user_id(user_id, db_session):
        return True
    if user_id and db_session.exec(select(Volunteer).where(Volunteer.user_id == user_id, Volunteer.is_active == True)).first():
        return True
    if user_id and chat_id:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ["creator", "administrator"]:
                return True
        except Exception:
            pass
    return False






@router.message(is_group_message, Command("bot", "murojaat", "savol"))
async def handle_redirect_to_bot_command(message: Message, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(message, db_session, bot):
        return

    # Delete the admin's command message so discussion comments stay clean
    try:
        await message.delete()
    except Exception:
        pass

    bot_info = await bot.get_me()
    bot_username = bot_info.username or settings.BOT_NAME.replace("@", "")

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 Savol yuborish",
                    url=f"https://t.me/{bot_username}?start=inquiry"
                )
            ]
        ]
    )

    if message.reply_to_message:
        target_id = message.reply_to_message.message_id
        text = (
            "<i>Assalomu alaykum, hurmatli fuqaro!</i><br/><br/>"
            "Savolingiz yuristlarimiz tomonidan bepul va to‘liq ko‘rib chiqilishi"
            "uchun, iltimos, murojaatingizni <b>Huquq+</b> botimiz orqali yuboring.<br/><br/>"
            f"👉 @{bot_username}<br/><br/>"
            "<i>Izohlar ko'pligi sababli bu yerda savollarga javob berilmasligi mumkin. "
            "Bot orqali esa har bir murojaat ro'yxatga olinadi va mutaxassislarimiz nazoratida bo'ladi.</i><br/><br/>"
        )

        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_to_message_id=target_id,
                reply_markup=markup,
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.warning("send_message with reply_to_message_id failed: %s", e)
            try:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=text,
                    reply_markup=markup,
                    parse_mode=SULGUK_PARSE_MODE,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception as e2:
                logger.warning("Fallback send_message failed: %s", e2)
    else:
        text = (
            f"Assalomu alaykum, hurmatli kanalimiz a'zolari!<br/><br/>"
            f"Savollaringiz huquqshunoslarimiz va mutaxassislarimiz tomonidan <b>bepul</b> va to'liq ko'rib chiqilishi uchun, "
            f"iltimos, murojaatingizni rasmiy <b>Huquq+</b> botimiz orqali yo'llang.<br/><br/>"
            f"👉 @{bot_username}"
        )
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=markup,
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.warning("Failed to send general redirect message in group: %s", e)


@router.message(is_group_message, Command("yurist"))
async def handle_group_yurist_command(message: Message, db_session: DBSession, bot: Bot):
    # 1. Yuristlar qabuli guruhida /yurist buyrug'i ishlamasin (chunki bu guruh qabul joyining o'zi)
    if str(message.chat.id) == str(settings.LAWYER_APPOINTMENT_GROUP_ID):
        return

    # 2. Xabarga reply qilingan bo'lishi shart
    if not message.reply_to_message:
        try:
            await message.delete()
        except Exception:
            pass
        return

    if not await is_coordinator_or_lawyer_or_admin(message, db_session, bot):
        return await _temporary_group_reply(message, bot, "⛔️ Kechirasiz, faqat guruh adminlari, koordinatorlar va rasmiy yuristlar murojaatni yurist qabuliga yo'naltira oladi.")
        
    group_id = get_group_id(message.chat)
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=message.reply_to_message.message_id,
        bot_id=bot.id,
        session=db_session
    )
    if not inquiry:
        inquiry = Inquiry.get_by_message_id(
            group_id=str(message.chat.id),
            group_question_id=message.reply_to_message.message_id,
            bot_id=bot.id,
            session=db_session
        )
    if not inquiry and message.chat.username:
        inquiry = Inquiry.get_by_message_id(
            group_id=f"@{message.chat.username}",
            group_question_id=message.reply_to_message.message_id,
            bot_id=bot.id,
            session=db_session
        )
    if not inquiry:
        try:
            r = get_redis(is_async=False)
            cont_id = r.get(f"inquiry_cont:{group_id}:{message.reply_to_message.message_id}")
            if not cont_id:
                cont_id = r.get(f"inquiry_cont:{message.chat.id}:{message.reply_to_message.message_id}")
            if cont_id:
                inq_id_int = int(cont_id.decode() if isinstance(cont_id, bytes) else cont_id)
                inquiry = db_session.get(Inquiry, inq_id_int)
        except Exception:
            pass
            
    if not inquiry:
        return await _temporary_group_reply(message, bot, "⚠️ Ushbu xabarga tegishli murojaat topilmadi.")
        
    # Check if already escalated
    existing_app = db_session.exec(select(Appointment).where(Appointment.inquiry_id == inquiry.id)).first()
    if existing_app:
        return await _temporary_group_reply(message, bot, f"⚠️ Ushbu murojaat allaqachon yurist qabuliga yo'naltirilgan (Ariza №{existing_app.id})!")

    if inquiry.status == InquiryStatus.cancelled:
        return await _temporary_group_reply(message, bot, "⚠️ Ushbu murojaat bekor qilingan.")
        
    # Mark original inquiry as closed
    inquiry.status = InquiryStatus.closed
    inquiry.updated_at = datetime.now()
    db_session.add(inquiry)
    db_session.commit()
    
    # Delete original inquiry message from volunteer group
    try:
        await message.reply_to_message.delete()
    except Exception as e:
        logger.warning("Failed to delete inquiry message from volunteer group: %s", e)

    # If there was a continuation message, delete it too
    try:
        r = get_redis(is_async=False)
        cont_msg_id = r.get(f"inquiry_cont_msg:{inquiry.id}")
        if cont_msg_id:
            cont_msg_id_int = int(cont_msg_id.decode() if isinstance(cont_msg_id, bytes) else cont_msg_id)
            await bot.delete_message(chat_id=message.chat.id, message_id=cont_msg_id_int)
    except Exception:
        pass

    # Delete coordinator's /yurist command message
    try:
        await message.delete()
    except Exception:
        pass
        
    # Notify citizen in DM (stage 1)
    user_lang = inquiry.user.language if inquiry.user else "uz"
    try:
        await bot.send_message(
            chat_id=inquiry.user_id,
            text=t("inquiry_escalated_to_lawyer_citizen", user_lang, id=inquiry.id),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception as e:
        logger.warning("Failed to notify citizen of escalation: %s", e)
        
    # Create Appointment in DB
    primary_fid = None
    if inquiry.question_media:
        try:
            media_json = json.loads(inquiry.question_media)
            primary_fid = media_json.get("file_id")
        except Exception:
            pass
            
    app = Appointment(
        user_id=inquiry.user_id,
        inquiry_id=inquiry.id,
        appointment_type="remote_appointment",
        problem_description=inquiry.question or f"Murojaat bo'yicha yurist qabuli ({inquiry.section_name})",
        media_type=inquiry.question_mediatype.value if hasattr(inquiry.question_mediatype, "value") else str(inquiry.question_mediatype),
        media_file_id=primary_fid,
        media_meta=inquiry.question_media,
        status=AppointmentStatus.pending,
        lawyer_id=None,
        scheduled_at=None,
        reminder_sent=False,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    logger.info(
        "appointment_created_via_yurist_command",
        extra={
            "appointment_id": app.id,
            "inquiry_id": inquiry.id,
            "coordinator_id": message.from_user.id,
        }
    )
    
    # Dispatch card to Lawyer Appointment Group
    lawyer_group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
    card_text = render_escalated_appointment_card(app, db_session, inquiry)
    card_markup = get_escalated_appointment_markup(app)
    
    group_msg = None
    try:
        group_msg = await bot.send_message(
            chat_id=lawyer_group_id,
            text=card_text,
            reply_markup=card_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to dispatch escalated appointment to lawyer group: %s", e)
        
    if group_msg:
        app.group_message_id = group_msg.message_id
        db_session.add(app)
        db_session.commit()
        
        # Forward media if present
        if primary_fid:
            try:
                m_type = app.media_type
                if m_type == InquiryMediaType.voice.value:
                    await bot.send_voice(chat_id=lawyer_group_id, voice=primary_fid, reply_to_message_id=group_msg.message_id)
                elif m_type == InquiryMediaType.photo.value:
                    await bot.send_photo(chat_id=lawyer_group_id, photo=primary_fid, reply_to_message_id=group_msg.message_id)
                elif m_type == InquiryMediaType.video.value:
                    await bot.send_video(chat_id=lawyer_group_id, video=primary_fid, reply_to_message_id=group_msg.message_id)
                elif m_type == InquiryMediaType.video_note.value:
                    await bot.send_video_note(chat_id=lawyer_group_id, video_note=primary_fid)
                elif m_type == InquiryMediaType.document.value:
                    await bot.send_document(chat_id=lawyer_group_id, document=primary_fid, reply_to_message_id=group_msg.message_id)
            except Exception as e:
                logger.warning("Failed to attach media to escalated appointment: %s", e)


GROUP_NOTICE_TTL = 60  # guruhdagi vaqtinchalik ogohlantirishlar shu soniyadan keyin o'chadi


async def _delete_later(bot: Bot, chat_id: int, message_id: int, delay: int = GROUP_NOTICE_TTL) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _temporary_group_reply(message: Message, bot: Bot, text: str) -> None:
    """Guruhda qisqa muddatli javob: shovqin qolmasligi uchun o'zi o'chadi."""
    try:
        notice = await message.reply(text, parse_mode=SULGUK_PARSE_MODE)
        asyncio.create_task(_delete_later(bot, notice.chat.id, notice.message_id))
    except Exception as e:
        logger.debug("Group notice failed: %s", e)


async def _gate_notice(message: Message, bot: Bot, text: str, reason: str = "") -> None:
    """Darvoza rad etgan javob: sabab volontyorga shaxsiyda (matni bilan) yuboriladi va guruhdagi
    yuborilmagan javob o'chiriladi — guruhda fuqaroga ketmagan "javob" va ogohlantirish qolmaydi.
    Shaxsiyga yozib bo'lmasa, guruhda vaqtinchalik ogohlantirish."""
    from src.app.ops_checks import record_gate_denial
    author = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    record_gate_denial(message.from_user.id, author, reason)
    draft = message.text or message.caption or ""
    dm_text = text
    if draft:
        dm_text += f"<br/><br/><b>Yuborgan matningiz:</b><br/><blockquote>{escape_multiline(draft[:3000])}</blockquote>"
    try:
        await bot.send_message(chat_id=message.from_user.id, text=dm_text, parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        return await _temporary_group_reply(message, bot, text)
    try:
        await message.delete()
    except Exception:
        await _temporary_group_reply(message, bot, text)


@router.message(is_group_message, reply_to_my_message, ~F.text.startswith("/"))
async def handle_response(message: Message, db_session: DBSession, bot: Bot):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return
    if message.reply_to_message.from_user.id != bot.id:
        return

    group_id = get_group_id(message.chat)
    replied_msg_id = message.reply_to_message.message_id

    # 1. Look up by group_question_id (strictly bot-posted inquiry message)
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=replied_msg_id,
        bot_id=bot.id,
        session=db_session
    )
    if not inquiry:
        inquiry = Inquiry.get_by_message_id(
            group_id=str(message.chat.id),
            group_question_id=replied_msg_id,
            bot_id=bot.id,
            session=db_session
        )
    if not inquiry and message.chat.username:
        inquiry = Inquiry.get_by_message_id(
            group_id=f"@{message.chat.username}",
            group_question_id=replied_msg_id,
            bot_id=bot.id,
            session=db_session
        )

    # 2. Look up by Redis (strictly bot-posted continuation message)
    if not inquiry:
        try:
            r = get_redis(is_async=False)
            cont_id = (
                r.get(f"inquiry_cont:{group_id}:{replied_msg_id}")
                or r.get(f"inquiry_cont:{message.chat.id}:{replied_msg_id}")
            )
            if cont_id:
                inq_id_int = int(cont_id.decode() if isinstance(cont_id, bytes) else cont_id)
                inquiry = db_session.get(Inquiry, inq_id_int)
        except Exception:
            pass

    if not inquiry or inquiry.status == InquiryStatus.cancelled:
        return

    # Check if respondent is authorized (Admin, Official Lawyer, or Registered Volunteer)
    is_admin_user = settings.is_admin(message.from_user.id)
    is_lawyer = db_session.exec(select(OfficialLawyer).where(OfficialLawyer.user_id == message.from_user.id, OfficialLawyer.is_active == True)).first() is not None
    is_volunteer = db_session.exec(select(Volunteer).where(Volunteer.user_id == message.from_user.id, Volunteer.is_active == True)).first() is not None

    if not (is_admin_user or is_lawyer or is_volunteer):
        try:
            r = get_redis(is_async=False)
            if not r.set(f"unregistered_reply_notice:{message.from_user.id}", "1", ex=86400, nx=True):
                return
        except Exception:
            pass
        bot_user = settings.BOT_NAME.replace("@", "")
        reg_link = f"https://t.me/{bot_user}?start={settings.VOLUNTEER_REG_KEY}"
        await _temporary_group_reply(
            message, bot,
            "⚠️ Murojaatlarga faqat ro'yxatdan o'tgan volontyor va yuristlar javob bera oladi. "
            f'<a href="{reg_link}">Ro\'yxatdan o\'tish ↗️</a>',
        )
        return

    # D bosqich javob darvozasi (faqat ASSIGN_ENFORCE_FROM dan keyingi ochiq murojaatlarda)
    resp_user = User.get_by_user_id(message.from_user.id, db_session)
    gate_lang = resp_user.language if resp_user and resp_user.language else "uz"
    gate_row = None
    if (
        settings.ASSIGN_ENFORCE_FROM is not None
        and inquiry.created_at is not None
        and inquiry.created_at >= settings.ASSIGN_ENFORCE_FROM
        and inquiry.status == InquiryStatus.active
    ):
        try:
            mine = db_session.exec(
                select(InquiryAssignment).where(
                    InquiryAssignment.inquiry_id == inquiry.id,
                    InquiryAssignment.volunteer_user_id == message.from_user.id,
                    InquiryAssignment.status.in_(AssignmentStatus.OPEN),
                ).order_by(InquiryAssignment.id.desc())
            ).all()
            gate_row = mine[0] if mine else None
        except Exception:
            gate_row = None
        sent_text = message.text or message.caption
        decision = decide_answer_gate(
            enforce_from=settings.ASSIGN_ENFORCE_FROM,
            inquiry_created_at=inquiry.created_at,
            inquiry_status=getattr(inquiry.status, "value", inquiry.status),
            assigned_volunteer_id=inquiry.assigned_volunteer_id,
            replier_id=message.from_user.id,
            is_admin=is_admin_user,
            is_lawyer=is_lawyer,
            review_row_exists=gate_row is not None,
            review_passed=bool(gate_row and gate_row.review_status == "passed"),
            hashes_match=review_hashes_match(sent_text, gate_row.review_draft_hash if gate_row else None),
            has_text=bool(sent_text and sent_text.strip()),
        )
        if decision == "wait_unassigned":
            return await _gate_notice(message, bot, t("gate_unassigned", gate_lang), "unassigned")
        if decision == "deny_foreign":
            assigned_vol = Volunteer.get_by_user_id(inquiry.assigned_volunteer_id, db_session)
            aname = assigned_vol.full_name if assigned_vol else str(inquiry.assigned_volunteer_id)
            return await _gate_notice(message, bot, t("gate_foreign", gate_lang, name=html.escape(aname)), "foreign")
        if decision == "deny_no_review":
            return await _gate_notice(message, bot, t("gate_need_review", gate_lang), "no_review")
        if decision == "deny_changed":
            return await _gate_notice(message, bot, t("gate_changed", gate_lang), "changed")

    if message.text:
        inquiry.answer_mediatype = InquiryMediaType.text
        inquiry.answer = message.text
        handler = bot.send_message
        args = dict(
            chat_id=inquiry.user_id,
            text=inquiry.answer,
            entities=message.entities,  # volontyor yozgan formatlash va havolalar saqlanadi
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.voice:
        inquiry.answer_media = message.voice.model_dump_json()
        inquiry.answer_mediatype = InquiryMediaType.voice
        inquiry.answer = message.voice.file_id
        handler = bot.send_voice
        args = dict(
            chat_id=inquiry.user_id,
            voice=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.video_note:
        inquiry.answer_media = message.video_note.model_dump_json()
        inquiry.answer_mediatype = InquiryMediaType.video_note
        inquiry.answer = message.video_note.file_id
        handler = bot.send_video_note
        args = dict(
            chat_id=inquiry.user_id,
            video_note=inquiry.answer,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.video:
        inquiry.answer_media = message.video.model_dump_json()
        inquiry.answer_mediatype = InquiryMediaType.video
        inquiry.answer = message.video.file_id
        handler = bot.send_video
        args = dict(
            chat_id=inquiry.user_id,
            video=inquiry.answer,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.photo:
        photo = message.photo[-1]
        inquiry.answer_media = photo.model_dump_json()
        inquiry.answer_mediatype = InquiryMediaType.photo
        inquiry.answer = photo.file_id
        handler = bot.send_photo
        args = dict(
            chat_id=inquiry.user_id,
            photo=photo.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            reply_to_message_id=inquiry.private_question_id,
        )
    elif message.document:
        inquiry.answer_media = message.document.model_dump_json()
        inquiry.answer_mediatype = InquiryMediaType.document
        inquiry.answer = message.document.file_id
        handler = bot.send_document
        args = dict(
            chat_id=inquiry.user_id,
            document=message.document.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            reply_to_message_id=inquiry.private_question_id,
        )
    else:
        return  # stiker va h.k. javob hisoblanmaydi

    # 1. Send answer to citizen with automatic retry
    success, reason, _ = await send_answer_to_citizen(handler, args)

    if not success:
        if reason == "blocked":
            await message.reply(
                "⚠️ <b>Xabar yetkazilmadi:</b> Fuqaro botni bloklagan yoki hisobini o'chirgan.",
                parse_mode=SULGUK_PARSE_MODE
            )
        elif reason == "restricted":
            await message.reply(
                "⚠️ <b>Xabar yetkazilmadi:</b> Fuqaro maxfiylik sozlamalarida ovozli/video xabarlarni qabul qilishni taqiqlagan. "
                "Iltimos, javobni matn ko'rinishida yuboring.",
                parse_mode=SULGUK_PARSE_MODE
            )
            try:
                await bot.send_message(
                    chat_id=inquiry.user_id,
                    text="Sizning xavfsizlik sozlamalaringizda ovozli/video xabarlar taqiqlanganligi sababli huquqshunos "
                         "javobini yubora olmadik. Iltimos, huquqshunosimiz matn ko'rinishida xabar yuborishini kuting "
                         "yoki sozlamalaringizni o'zgartiring."
                )
            except Exception:
                pass
        else:
            await message.reply(
                "❌ <b>Xatolik:</b> Aloqa yoki tizim nosozligi sababli javob fuqaroga yetkazilmadi.<br/>"
                "Iltimos, bir ozdan so'ng qayta javob yuboring!",
                parse_mode=SULGUK_PARSE_MODE
            )
        return

    # 2. Check if the inquiry post in the group is already edited as answered. If not, edit it now!
    already_edited = is_inquiry_already_edited(message, inquiry)
    if not already_edited:
        edit_ok = await edit_message(inquiry, message, bot, db_session=db_session)
        if edit_ok:
            try:
                r = get_redis(is_async=False)
                r.set(f"inquiry_group_edited:{inquiry.id}", "1", ex=86400 * 30)
            except Exception:
                pass

    await finalize_inquiry_answer(bot, db_session, inquiry, message.from_user.id, message.message_id)

    # 5. Visual confirmation to lawyer: add reaction 👍
    try:
        from aiogram.types import ReactionTypeEmoji
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")]
        )
    except Exception:
        pass


async def finalize_inquiry_answer(bot: Bot, db_session: DBSession, inquiry: Inquiry, responder_id: int,
                                  group_answer_id: int | None) -> None:
    """Javob fuqaroga yetgach: murojaat holati, biriktirishlarni yopish, baholash so'rovi (bir marta)."""
    inquiry.group_answer_id = group_answer_id
    inquiry.responder_id = responder_id
    if not inquiry.replied_at:
        inquiry.replied_at = datetime.now()
    inquiry.updated_at = datetime.now()
    inquiry.status = InquiryStatus.replied
    db_session.add(inquiry)
    db_session.commit()

    try:
        for row in db_session.exec(
            select(InquiryAssignment).where(
                InquiryAssignment.inquiry_id == inquiry.id,
                InquiryAssignment.status.in_(AssignmentStatus.OPEN),
            )
        ).all():
            row.status = AssignmentStatus.replied
            db_session.add(row)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.warning("Failed to mark assignments replied: %s", e)

    try:
        r = get_redis(is_async=False)
        if inquiry.rating is not None or not r.set(f"inquiry_rating_sent:{inquiry.id}", "1", ex=86400 * 30, nx=True):
            return
    except Exception:
        if inquiry.rating is not None:
            return
    try:
        user_lang = inquiry.user.language if inquiry.user else "uz"
        await bot.send_message(
            chat_id=inquiry.user_id,
            text=t("inquiry_rate_prompt", user_lang),
            reply_markup=get_rating_keyboard("inquiry", inquiry.id),
            parse_mode=SULGUK_PARSE_MODE,
        )
    except Exception as e:
        logger.warning("Failed to send rating prompt to citizen: %s", e)


def answered_block(author_id: int, author_name: str, when: datetime, message_link: str | None = None) -> str:
    link_line = f'<b>Xabar: </b><a href="{message_link}">Javobga havola</a><br/>' if message_link else ""
    return (
        "<hr/>"
        "<b>✅ Murojaatga javob berildi</b><br/>"
        f"<b>Javob vaqti: </b>{when.astimezone(tz).strftime('%d.%m.%Y %H:%M')}<br/>"
        f"{link_line}"
        f'<b>Muallif: </b><a href="tg://user?id={author_id}">{html.escape(author_name) or "Huquqshunos"}</a>'
    )


def replied_context(message: Message) -> str:
    author_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    return answered_block(message.from_user.id, author_name, message.date,
                          get_message_link(message.chat, message.message_id))


async def edit_message(inquiry: Inquiry, message: Message, bot: Bot, db_session: DBSession | None = None) -> bool:
    """Javobdan keyin guruhdagi kartani yagona formatda qayta chizadi (Biriktirish tugmasisiz)."""
    if not inquiry.group_question_id:
        replied_msg = getattr(message, "reply_to_message", None)
        inquiry.group_question_id = getattr(replied_msg, "message_id", None)
    if not inquiry.group_id:
        inquiry.group_id = get_group_id(message.chat)
    return await refresh_inquiry_card(
        bot, inquiry, db_session, extra_html=replied_context(message), keep_assign_button=False,
    )


@router.callback_query(F.data.startswith("appointment:claim:"))
async def claim_appointment_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    # Check if user is an official lawyer or an admin
    lawyer = OfficialLawyer.get_by_user_id(query.from_user.id, db_session)
    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin and query.message and query.message.chat:
        try:
            member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception:
            pass

    if not lawyer and not is_admin:
        return await query.answer(
            "⛔️ Faqat ro'yxatdan o'tgan yuristlar yoki adminlar arizani qabul qilishi mumkin!",
            show_alert=True
        )

    if appointment.lawyer_id and appointment.status != AppointmentStatus.pending:
        return await query.answer("⚠️ Ushbu ariza allaqachon boshqa yurist tomonidan qabul qilingan!", show_alert=True)

    lawyer_name = lawyer.full_name if lawyer else f"{query.from_user.first_name} {query.from_user.last_name or ''}".strip()

    appointment.lawyer_id = query.from_user.id
    if appointment.scheduled_at:
        appointment.status = AppointmentStatus.accepted
    else:
        appointment.status = AppointmentStatus.pending
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s claimed by user %s (%s)", appointment.id, query.from_user.id, lawyer_name)

    # Redraw card with unified render_appointment_card and get_appointment_markup
    card_text = render_appointment_card(appointment, db_session)
    card_markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=card_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to update appointment message on claim: %s", e)

    # Notify citizen in DM
    await notify_citizen_appointment_update(bot, appointment, db_session, kind="claimed")

    await query.answer(f"✅ Ariza sizga biriktirildi ({lawyer_name})!", show_alert=True)


@router.callback_query(F.data.startswith("appointment:add_link:"))
async def add_link_prompt_callback(query: CallbackQuery):
    await query.answer(
        "💡 Suhbat havolasini kiritish uchun ushbu xabarga Reply qilib: /link <havola> yuboring.\nMasalan: /link https://meet.google.com/abc-defg",
        show_alert=True
    )


@router.message(Command("link"), reply_to_my_message)
async def handle_appointment_link_command(message: Message, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(message, db_session, bot):
        return await _temporary_group_reply(message, bot, "⛔️ Kechirasiz, faqat rasmiy yuristlar yoki adminlar havola kirita oladi.")

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("⚠️ Format: <code>/link &lt;uchrashuv_havolasi&gt;</code>\nMisol: <code>/link https://meet.google.com/abc-defg</code>", parse_mode=SULGUK_PARSE_MODE)

    link = args[1].strip()
    if not (link.startswith("http://") or link.startswith("https://") or link.startswith("t.me/")):
        return await _temporary_group_reply(message, bot, "⚠️ Iltimos, haqiqiy URL manzil kiriting (https:// bilan boshlanishi kerak).")

    # Find appointment
    appointment = Appointment.get_by_group_message_id(message.reply_to_message.message_id, db_session)
    if not appointment:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        match = re.search(r"Ariza №(\d+)", text)
        if not match:
            match = re.search(r"[№#](\d+)", text)
        if match:
            appointment = Appointment.get_by_id(int(match.group(1)), db_session)

    if not appointment:
        return await _temporary_group_reply(message, bot, "⚠️ Tegishli qabul arizasi topilmadi.")

    appointment.meeting_link = link
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s meeting link set to %s by user %s", appointment.id, link, message.from_user.id)

    # Redraw group card if present
    if appointment.group_message_id:
        try:
            card_text = render_appointment_card(appointment, db_session)
            card_markup = get_appointment_markup(appointment)
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=appointment.group_message_id,
                text=card_text,
                reply_markup=card_markup,
                parse_mode=SULGUK_PARSE_MODE,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception as e:
            logger.warning("Failed to update group card with meeting link: %s", e)

    # Notify citizen in DM
    try:
        citizen_msg = (
            f"🔗 <b>Online suhbat havolasi taqdim etildi! (Ariza №{appointment.id})</b><br/><br/>"
            f"Hurmatli fuqaro, yuristimiz suhbat havolasini yubordi:<br/>"
            f"👉 <a href=\"{link}\">{link}</a><br/><br/>"
            "Iltimos, belgilangan qabul vaqtida ushbu havola orqali ulaning."
        )
        await bot.send_message(chat_id=appointment.user_id, text=citizen_msg, parse_mode=SULGUK_PARSE_MODE)
    except Exception as e:
        logger.warning("Failed to send meeting link to citizen: %s", e)

    await _temporary_group_reply(message, bot, f"✅ Havola saqlandi va fuqaroga yuborildi: {html.escape(link)}")


@router.callback_query(F.data.startswith("appointment:cancel:"))
async def cancel_appointment_by_lawyer(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    is_lawyer = OfficialLawyer.get_by_user_id(query.from_user.id, db_session) is not None
    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin and query.message and query.message.chat:
        try:
            member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception:
            pass

    if not is_lawyer and not is_admin:
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar qabulni bekor qilishi mumkin!", show_alert=True)

    appointment.status = AppointmentStatus.cancelled
    appointment.cancellation_reason = f"Yurist ({query.from_user.first_name}) tomonidan bekor qilindi"
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s cancelled by user %s", appointment.id, query.from_user.id)

    card_text = render_appointment_card(appointment, db_session)
    card_markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=card_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to edit card on cancel: %s", e)

    # Notify citizen
    await notify_citizen_appointment_update(bot, appointment, db_session, kind="cancelled")

    await query.answer("Qabul bekor qilindi!", show_alert=True)


@router.callback_query(F.data.startswith("appointment:complete:"))
async def complete_appointment_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    is_lawyer = OfficialLawyer.get_by_user_id(query.from_user.id, db_session) is not None
    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin and query.message and query.message.chat:
        try:
            member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception:
            pass

    if not is_lawyer and not is_admin:
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar suhbatni yakunlashi mumkin!", show_alert=True)

    if appointment.status == AppointmentStatus.completed:
        return await query.answer("⚠️ Ushbu ariza allaqachon yakunlangan!", show_alert=True)

    appointment.status = AppointmentStatus.completed
    appointment.completed_at = datetime.now()
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s completed by user %s", appointment.id, query.from_user.id)

    # Update group message
    card_text = render_appointment_card(appointment, db_session)
    card_markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=card_markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to edit appointment complete message: %s", e)

    # Send 1-5 rating prompt to the citizen in private chat
    citizen = User.get_by_user_id(appointment.user_id, db_session)
    citizen_lang = citizen.language if citizen else "uz"
    try:
        rate_prompt = t("appointment_completed_rate_prompt", citizen_lang)
        await bot.send_message(
            chat_id=appointment.user_id,
            text=rate_prompt,
            reply_markup=get_rating_keyboard("appointment", appointment.id),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception as e:
        logger.warning("Failed to send rating prompt to citizen: %s", e)

    await query.answer("✅ Suhbat yakunlandi va fuqaroga 1 dan 5 gacha baholash so'rovi yuborildi!", show_alert=True)


# --- Escalated Appointment Callbacks (Biriktirish, Vaqt belgilash, boshqaruv, qayta tiklash) ---


@router.callback_query(F.data.startswith("app_escalate:assign:"))
async def escalate_assign_menu_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar yurist biriktira oladi!", show_alert=True)

    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    kb = get_lawyers_keyboard(app_id, query.from_user.id, db_session)
    try:
        await query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data.startswith("app_escalate:set_lawyer:"))
async def escalate_set_lawyer_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar yurist biriktira oladi!", show_alert=True)

    parts = query.data.split(":")
    app_id = int(parts[2])
    lawyer_user_id = int(parts[3])

    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    lawyer = OfficialLawyer.get_by_user_id(lawyer_user_id, db_session)
    if not lawyer:
        return await query.answer("⚠️ Tanlangan yurist topilmadi!", show_alert=True)

    # Vaqt to'qnashuvi tekshiruvi: if scheduled_at is set, check if lawyer is busy at that hour
    if appointment.scheduled_at:
        start_of_day = datetime.combine(appointment.scheduled_at.date(), time.min)
        end_of_day = datetime.combine(appointment.scheduled_at.date(), time.max)
        h_int = appointment.scheduled_at.hour

        booked_apps = db_session.exec(
            select(Appointment).where(
                Appointment.id != appointment.id,
                Appointment.lawyer_id == lawyer_user_id,
                Appointment.scheduled_at >= start_of_day,
                Appointment.scheduled_at <= end_of_day,
                Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
            )
        ).all()
        if any(b.scheduled_at and b.scheduled_at.hour == h_int for b in booked_apps):
            return await query.answer(
                "⚠️ Kechirasiz, tanlangan yuristda bu vaqtda boshqa qabul mavjud! Boshqa yurist yoki yangi vaqt tanlang.",
                show_alert=True
            )

    is_reassign = (appointment.lawyer_id is not None and appointment.lawyer_id != lawyer_user_id)
    old_lawyer_id = appointment.lawyer_id
    appointment.lawyer_id = lawyer_user_id
    appointment.updated_at = datetime.now()

    if appointment.scheduled_at:
        appointment.status = AppointmentStatus.accepted
    else:
        appointment.status = AppointmentStatus.pending

    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s lawyer set: %s -> %s by user %s", appointment.id, old_lawyer_id, lawyer_user_id, query.from_user.id)

    # Notify citizen
    if is_reassign:
        kind = "reassigned"
    elif appointment.scheduled_at:
        kind = "confirmed"
    else:
        kind = "lawyer_assigned"
    await notify_citizen_appointment_update(bot, appointment, db_session, kind=kind)

    # Update card
    card_text = render_appointment_card(appointment, db_session)
    markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to edit escalated appointment card: %s", e)

    await query.answer(f"✅ Ariza {lawyer.full_name}ga biriktirildi!", show_alert=True)


@router.callback_query(F.data.startswith("app_escalate:date:"))
async def escalate_date_menu_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar vaqt belgilay oladi!", show_alert=True)

    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    kb = get_escalation_dates_keyboard(app_id)
    try:
        await query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data.startswith("app_escalate:time:"))
async def escalate_time_menu_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar vaqt belgilay oladi!", show_alert=True)

    parts = query.data.split(":")
    app_id = int(parts[2])
    date_str = parts[3]

    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    kb = get_escalation_slots_keyboard(app_id, date_str, appointment.lawyer_id, db_session)
    try:
        await query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data == "app_escalate:slot_taken")
async def escalate_slot_taken_callback(query: CallbackQuery):
    await query.answer("🔒 Ushbu vaqt band qilingan! Iltimos, boshqa vaqtni tanlang.", show_alert=True)


@router.callback_query(F.data.startswith("app_escalate:slot:"))
async def escalate_book_slot_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar vaqt belgilay oladi!", show_alert=True)

    parts = query.data.split(":")
    app_id = int(parts[2])
    date_str = parts[3]
    time_str = ":".join(parts[4:]).strip()
    if ":" not in time_str:
        time_str = f"{time_str}:00"

    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    slot_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    target_date = slot_dt.date()
    h_int = slot_dt.hour

    # Check if slot is already in the past for today
    now = datetime.now(tz)
    slot_dt_aware = slot_dt.replace(tzinfo=tz)
    if target_date == now.date() and slot_dt_aware <= now + timedelta(minutes=30):
        return await query.answer("⚠️ Kechirasiz, ushbu vaqt o'tib ketgan. Iltimos boshqa vaqtni tanlang.", show_alert=True)

    # Synchronized slot availability verification
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    booked_appointments = db_session.exec(
        select(Appointment).where(
            Appointment.id != appointment.id,
            Appointment.scheduled_at >= start_of_day,
            Appointment.scheduled_at <= end_of_day,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
        )
    ).all()

    active_lawyers = OfficialLawyer.get_active_lawyers(db_session)
    total_lawyers = max(len(active_lawyers), 1)

    is_available = True
    if appointment.lawyer_id:
        for app_item in booked_appointments:
            if app_item.lawyer_id == appointment.lawyer_id and app_item.scheduled_at and app_item.scheduled_at.hour == h_int:
                is_available = False
                break
    else:
        booked_count = sum(1 for app_item in booked_appointments if app_item.scheduled_at and app_item.scheduled_at.hour == h_int)
        if booked_count >= total_lawyers:
            is_available = False

    if not is_available:
        return await query.answer("⚠️ Kechirasiz, ushbu vaqt band bo'ldi. Iltimos, boshqa vaqtni tanlang.", show_alert=True)

    is_reschedule = (appointment.scheduled_at is not None)
    old_time = appointment.scheduled_at
    appointment.scheduled_at = slot_dt
    appointment.confirm_asked_at = None  # yangi vaqt uchun fuqarodan qayta so'raladi
    appointment.citizen_confirmation = None
    appointment.reminder_sent = False  # Always reset reminder flag on reschedule
    appointment.updated_at = datetime.now()

    if appointment.lawyer_id:
        appointment.status = AppointmentStatus.accepted

    db_session.add(appointment)
    db_session.commit()
    logger.info("Appointment %s scheduled_at set: %s -> %s by user %s", appointment.id, old_time, slot_dt, query.from_user.id)

    # Notify citizen
    if is_reschedule:
        kind = "time_changed"
    elif appointment.lawyer_id:
        kind = "confirmed"
    else:
        kind = "time_set"
    await notify_citizen_appointment_update(bot, appointment, db_session, kind=kind)

    # Update lawyer group message
    card_text = render_appointment_card(appointment, db_session)
    markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to edit escalated appointment card: %s", e)

    await query.answer(f"✅ Qabul vaqti belgilandi: {format_uz_date(slot_dt)}", show_alert=True)


@router.callback_query(F.data.startswith("app_escalate:manage:"))
async def escalate_manage_menu_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not await is_coordinator_or_lawyer_or_admin(query, db_session, bot):
        return await query.answer("⛔️ Faqat rasmiy yuristlar yoki adminlar arizani o'zgartira oladi!", show_alert=True)

    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍⚖️ Yuristni o'zgartirish", callback_data=f"app_escalate:assign:{app_id}")
    builder.button(text="📅 Vaqtni o'zgartirish", callback_data=f"app_escalate:date:{app_id}")
    builder.button(text="⬅️ Ortga", callback_data=f"app_escalate:back:{app_id}")
    builder.adjust(2, 1)

    try:
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data.startswith("app_escalate:back:"))
async def escalate_back_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data.startswith("app_escalate:restore:"))
async def escalate_restore_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    """
    Restores a cancelled appointment.
    Only bot admins (settings.is_admin) have permission to restore.
    If scheduled_at has already expired, resets scheduled_at to None and asks for new time.
    Resets cancellation_reason and reminder_sent.
    """
    if not settings.is_admin(query.from_user.id):
        return await query.answer("⛔️ Qabulni qayta tiklash faqat adminlar uchun!", show_alert=True)

    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    if appointment.status != AppointmentStatus.cancelled:
        return await query.answer("⚠️ Ushbu ariza bekor qilinmagan!", show_alert=True)

    appointment.cancellation_reason = None
    time_expired = False
    now = datetime.now()
    if appointment.scheduled_at:
        if appointment.scheduled_at <= now:
            appointment.scheduled_at = None
            time_expired = True
        elif appointment.lawyer_id:
            # Bekor qilingan paytda shu yurist shu soatga boshqa qabul olgan bo'lishi mumkin
            slot_start = appointment.scheduled_at.replace(minute=0, second=0, microsecond=0)
            clash = db_session.exec(
                select(Appointment).where(
                    Appointment.id != appointment.id,
                    Appointment.lawyer_id == appointment.lawyer_id,
                    Appointment.scheduled_at >= slot_start,
                    Appointment.scheduled_at < slot_start + timedelta(hours=1),
                    Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted]),
                )
            ).first()
            if clash:
                appointment.scheduled_at = None
                time_expired = True

    appointment.reminder_sent = False

    if appointment.lawyer_id and appointment.scheduled_at:
        appointment.status = AppointmentStatus.accepted
    else:
        appointment.status = AppointmentStatus.pending

    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()

    logger.info(
        "Appointment %s restored by admin %s (status=%s, scheduled_at=%s, time_expired=%s)",
        appointment.id,
        query.from_user.id,
        appointment.status,
        appointment.scheduled_at,
        time_expired
    )

    # Notify citizen
    await notify_citizen_appointment_update(bot, appointment, db_session, kind="restored")

    # Redraw card with unified render_appointment_card and get_appointment_markup
    card_text = render_appointment_card(appointment, db_session)
    markup = get_appointment_markup(appointment)
    try:
        await query.message.edit_text(
            text=card_text,
            reply_markup=markup,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.warning("Failed to edit appointment card on restore: %s", e)

    if time_expired:
        await query.answer("♻️ Qabul qayta tiklandi! Eski vaqt o'tib ketganligi sababli, yangi vaqt belgilang.", show_alert=True)
    else:
        await query.answer("♻️ Qabul muvaffaqiyatli qayta tiklandi!", show_alert=True)



