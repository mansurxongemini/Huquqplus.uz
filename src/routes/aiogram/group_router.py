import re
import asyncio
from datetime import datetime
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
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE
from src.app.enums import create_user_info
from src.app.filters import is_group_message, reply_to_my_message, is_group_callback
from src.app.keyboards import inquiry_sections, get_rating_keyboard, get_main_menu
from src.app.timeutils import tz
from src.app.translations import t
from src.config.redis_queue import telegram_storage
from src.config.settings import settings
from sqlmodel import select
from src.models.inquiry import Inquiry, InquiryStatus, InquiryMediaType
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.volunteer import Volunteer
from src.models.user import User
from src.routes.aiogram.admin import execute_block_user, execute_unblock_user
from src.routes.aiogram.inquiry import InquiryState
from src.routes.deps.db_session import DBSession
from aiogram.exceptions import TelegramBadRequest

router = Router(name="group")


def get_group_id(chat: Chat) -> str:
    if chat.username:
        return f"@{chat.username}"
    return str(chat.id)


def get_message_link(chat: Chat, message_id: int) -> str | None:
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    if chat.id < 0:
        internal_id = str(chat.id).replace("-100", "", 1)
        return f"https://t.me/c/{internal_id}/{message_id}"
    return None


async def try_with_reply(handler, reply_to_message_id: int, **kwargs):
    try:
        return await handler(reply_to_message_id=reply_to_message_id, **kwargs)
    except TelegramBadRequest as e:
        if "message to be replied not found" in e.message:
            return await handler(**kwargs)
        else:
            raise e


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
        print("Failed to clear FSM state on block:", e)

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
        print("Failed to cancel active inquiries on block:", e)

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
        print("Failed to cancel active appointments on block:", e)

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
        print("Failed to edit reply markup: ", e)

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
        print("Failed to edit reply markup: ", e)

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
                if btn.callback_data.startswith("appointment:"):
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
        return await message.reply("⛔️ Kechirasiz, sizda bu amalni bajarish huquqi yo'q!")

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
        return await message.reply("⚠️ Ushbu xabarga tegishli foydalanuvchi ID si aniqlanmadi.")

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
        return await message.reply("⛔️ Kechirasiz, sizda bu amalni bajarish huquqi yo'q!")

    target_user_id = extract_user_id_from_reply(message.reply_to_message, db_session, bot)

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip().isdigit():
        target_user_id = int(args[1].strip())

    if not target_user_id:
        return await message.reply("⚠️ Ushbu xabarga tegishli foydalanuvchi ID si aniqlanmadi.")

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


@router.message(is_group_message, reply_to_my_message)
async def handle_response(message: Message, db_session: DBSession, bot: Bot):
    # Ignore commands so they are never sent as answers
    if message.text and message.text.strip().startswith("/"):
        return

    group_id = get_group_id(message.chat)
    inquiry = Inquiry.get_by_message_id(
        group_id=group_id,
        group_question_id=message.reply_to_message.message_id,
        bot_id=bot.id,
        session=db_session
    )

    if not inquiry or inquiry.status in [InquiryStatus.closed, InquiryStatus.cancelled]:
        return

    # Check if respondent is authorized (Admin, Official Lawyer, or Registered Volunteer)
    is_admin_user = settings.is_admin(message.from_user.id)
    is_lawyer = db_session.exec(select(OfficialLawyer).where(OfficialLawyer.user_id == message.from_user.id, OfficialLawyer.is_active == True)).first() is not None
    is_volunteer = db_session.exec(select(Volunteer).where(Volunteer.user_id == message.from_user.id, Volunteer.is_active == True)).first() is not None

    if not (is_admin_user or is_lawyer or is_volunteer):
        try:
            bot_info = await bot.get_me()
            bot_user = bot_info.username or settings.BOT_NAME.replace("@", "")
            reg_link = f"https://t.me/{bot_user}?start=volunteer"
            await message.reply(
                f"⚠️ <b>Kechirasiz!</b><br/>"
                f"Fuqarolar murojaatlariga faqat ro'yxatdan o'tgan volontyorlar va yuristlar javob bera oladi.<br/><br/>"
                f"Iltimos, avval bot orqali ro'yxatdan o'ting: <a href=\"{reg_link}\">Ro'yxatdan o'tish ↗️</a>",
                parse_mode=SULGUK_PARSE_MODE
            )
        except Exception:
            pass
        return

    if message.text:
        inquiry.answer_mediatype = InquiryMediaType.text
        inquiry.answer = message.text
        handler = bot.send_message
        args = dict(
            chat_id=inquiry.user_id,
            text=inquiry.answer,
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
            reply_to_message_id=inquiry.private_question_id,
        )
    else:
        return await message.answer("Bunday turdagi xabarlar qabul qilinmaydi.")

    try:
        await edit_message(inquiry, message, bot)

        # Rating is handled via inline buttons; no need to block user state

        inquiry.group_answer_id = message.message_id
        inquiry.responder_id = message.from_user.id
        inquiry.replied_at = inquiry.updated_at = datetime.now()
        inquiry.status = InquiryStatus.replied
        db_session.add(inquiry)
        db_session.commit()

        await try_with_reply(handler, **args)

        user_lang = inquiry.user.language if inquiry.user else "uz"
        rating_prompt = t("Sizga ko'rsatilgan xizmat sifatini hamda Huquqshunos javobini baholang:", user_lang)
        await bot.send_message(
            chat_id=inquiry.user_id,
            text=rating_prompt,
            reply_markup=get_rating_keyboard("inquiry", inquiry.id),
            parse_mode=SULGUK_PARSE_MODE
        )
    except TelegramBadRequest as e:
        if "restricted" in e.message:
            await message.reply(
                "Foydalanuvchi bu formatdagi xabarlarni ta'qiqlagan. Iltimos javobingizni boshqa formatda yuboring."
            )
            return await bot.send_message(
                chat_id=inquiry.user_id,
                text="Sizning xafsizlik sozlamalaringiz ovozli/video xabarlar ta'qiqlanganligi sababli huquqshunos "
                     "javobini yubora olmadik. Iltimos huquqshunosimiz boshqa formatda xabar yuborishini kuting yoki "
                     "sozlamalaringizni o'zgartiring."
            )
        else:
            raise e


async def edit_message(inquiry: Inquiry, message: Message, bot: Bot):
    group_id = get_group_id(message.chat)
    user_lang = inquiry.user.language if inquiry.user else "uz"
    user_context = create_user_info(inquiry.user, lang=user_lang)
    message_link = get_message_link(message.chat, message.message_id)

    if message.reply_to_message.text:
        sending_message = f"<p><blockquote>{inquiry.question}</blockquote></p>{user_context}"
        await bot.edit_message_text(
            chat_id=group_id,
            text=sending_message + replied_context(message),
            message_id=message.reply_to_message.message_id,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(url=message_link) if message_link else LinkPreviewOptions(is_disabled=True)
        )
    elif (
        message.reply_to_message.voice
        or message.reply_to_message.video
        or message.reply_to_message.document
        or message.reply_to_message.photo
    ):
        await bot.edit_message_caption(
            chat_id=group_id,
            caption=user_context + replied_context(message),
            message_id=message.reply_to_message.message_id,
            parse_mode=SULGUK_PARSE_MODE
        )


def replied_context(message: Message):
    message_link = get_message_link(message.chat, message.message_id)
    link_html = (
        f"<a href=\"{message_link}\">Javobga havola</a>"
        if message_link
        else "Javobga havola mavjud emas"
    )
    return f"""
        <hr/>
        <b>✅ Murojaatga javob berildi:</b><br/>
        <b>Javob Vaqti: </b>{message.date.astimezone(tz)}<br/>
        <b>Xabar: </b>{link_html}<br/>
        <b>Muallif: </b><a href="tg://user?id={message.from_user.id}">{message.from_user.first_name} {message.from_user.last_name or ''}</a>
    """


@router.callback_query(F.data.startswith("appointment:claim:"), is_group_callback)
async def claim_appointment_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    # Check if user is an official lawyer or an admin
    lawyer = OfficialLawyer.get_by_user_id(query.from_user.id, db_session)
    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin:
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
    appointment.status = AppointmentStatus.accepted
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()

    # Update group message button to "Complete", "Add Link", "Cancel"
    new_builder = InlineKeyboardBuilder()
    new_builder.button(text="🔗 Havola kiritish", callback_data=f"appointment:add_link:{appointment.id}")
    new_builder.button(text="✅ Suhbat yakunlandi", callback_data=f"appointment:complete:{appointment.id}")
    new_builder.button(text="❌ Qabulni bekor qilish", callback_data=f"appointment:cancel:{appointment.id}")
    new_builder.adjust(2, 1)

    original_text = query.message.html_text or query.message.text or ""
    updated_text = (
        f"{original_text}<br/><br/>"
        f"<b>📌 Qabul qilgan yurist:</b> <a href=\"tg://user?id={query.from_user.id}\">{lawyer_name}</a><br/>"
        f"<b>Holati:</b> Qabul qilindi (Jarayonda)"
    )
    try:
        await query.message.edit_text(
            text=updated_text,
            reply_markup=new_builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception as e:
        print("Failed to update appointment message:", e)

    # Notify citizen in DM
    citizen = User.get_by_user_id(appointment.user_id, db_session)
    citizen_lang = citizen.language if citizen else "uz"
    try:
        await bot.send_message(
            chat_id=appointment.user_id,
            text=t("appointment_claimed_citizen", citizen_lang, lawyer_name=lawyer_name),
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception as e:
        print("Failed to notify citizen:", e)

    await query.answer(f"✅ Ariza sizga biriktirildi ({lawyer_name})!", show_alert=True)


@router.callback_query(F.data.startswith("appointment:add_link:"), is_group_callback)
async def add_link_prompt_callback(query: CallbackQuery):
    await query.answer(
        "💡 Suhbat havolasini kiritish uchun ushbu xabarga Reply qilib: /link <havola> yuboring.\nMasalan: /link https://meet.google.com/abc-defg",
        show_alert=True
    )


@router.message(is_group_message, Command("link"), reply_to_my_message)
async def handle_appointment_link_command(message: Message, db_session: DBSession, bot: Bot):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("⚠️ Format: <code>/link &lt;uchrashuv_havolasi&gt;</code>\nMisol: <code>/link https://meet.google.com/abc-defg</code>", parse_mode=SULGUK_PARSE_MODE)

    link = args[1].strip()
    if not (link.startswith("http://") or link.startswith("https://") or link.startswith("t.me/")):
        return await message.reply("⚠️ Iltimos, haqiqiy URL manzil kiriting (https:// bilan boshlanishi kerak).")

    # Find appointment
    appointment = Appointment.get_by_group_message_id(message.reply_to_message.message_id, db_session)
    if not appointment:
        # Try finding by regex in replied text
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        match = re.search(r"Ariza №(\d+)", text)
        if match:
            appointment = Appointment.get_by_id(int(match.group(1)), db_session)

    if not appointment:
        return await message.reply("⚠️ Tegishli qabul arizasi topilmadi.")

    appointment.meeting_link = link
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()

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
        print("Failed to send meeting link to citizen:", e)

    await message.reply(f"✅ Havola saqlandi va fuqaroga yuborildi!\n🔗 {link}")


@router.callback_query(F.data.startswith("appointment:cancel:"), is_group_callback)
async def cancel_appointment_by_lawyer(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin:
        try:
            member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception:
            pass

    if appointment.lawyer_id != query.from_user.id and not is_admin:
        return await query.answer("⛔️ Faqat arizani qabul qilgan yurist yoki admin bekor qilishi mumkin!", show_alert=True)

    appointment.status = AppointmentStatus.cancelled
    appointment.cancellation_reason = f"Yurist ({query.from_user.first_name}) tomonidan bekor qilindi"
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()

    original_text = query.message.html_text or query.message.text or ""
    cancelled_text = (
        f"{original_text}<br/><br/>"
        f"<b>❌ Qabul bekor qilindi:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"<b>Bekor qiluvchi:</b> {query.from_user.first_name} {query.from_user.last_name or ''}"
    )
    try:
        await query.message.edit_text(text=cancelled_text, reply_markup=None, parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass

    # Notify citizen
    try:
        await bot.send_message(
            chat_id=appointment.user_id,
            text=f"⚠️ <b>Hurmatli fuqaro!</b> Sizning yurist qabuliga arizangiz (№{appointment.id}) bekor qilindi.<br/>Qayta yozilish uchun /start bosing.",
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception:
        pass

    await query.answer("Qabul bekor qilindi!", show_alert=True)


@router.callback_query(F.data.startswith("appointment:complete:"), is_group_callback)
async def complete_appointment_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    app_id = int(query.data.split(":")[2])
    appointment = Appointment.get_by_id(app_id, db_session)
    if not appointment:
        return await query.answer("⚠️ Ariza topilmadi!", show_alert=True)

    is_admin = settings.is_admin(query.from_user.id)
    if not is_admin:
        try:
            member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
        except Exception:
            pass

    if appointment.lawyer_id != query.from_user.id and not is_admin:
        return await query.answer("⛔️ Faqat arizani qabul qilgan yurist yoki admin suhbatni yakunlashi mumkin!", show_alert=True)

    if appointment.status == AppointmentStatus.completed:
        return await query.answer("⚠️ Ushbu ariza allaqachon yakunlangan!", show_alert=True)

    appointment.status = AppointmentStatus.completed
    appointment.completed_at = datetime.now()
    appointment.updated_at = datetime.now()
    db_session.add(appointment)
    db_session.commit()

    # Update group message
    original_text = query.message.html_text or query.message.text or ""
    completed_text = (
        f"{original_text}<br/><br/>"
        f"<b>🏁 Online suhbat yakunlandi:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"<b>Yakunlovchi:</b> {query.from_user.first_name} {query.from_user.last_name or ''}"
    )
    try:
        await query.message.edit_text(
            text=completed_text,
            reply_markup=None,
            parse_mode=SULGUK_PARSE_MODE
        )
    except Exception as e:
        print("Failed to edit appointment complete message:", e)

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
        print("Failed to send rating prompt to citizen:", e)

    await query.answer("✅ Suhbat yakunlandi va fuqaroga 1 dan 5 gacha baholash so'rovi yuborildi!", show_alert=True)


