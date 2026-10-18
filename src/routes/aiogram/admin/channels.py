"""Majburiy obuna kanallari."""
import logging
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.required_channel import RequiredChannel
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import AdminAddChannelState, admin_router


def build_admin_channels_page(channels: list[RequiredChannel]) -> tuple[str, InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if not channels:
        text = (
            "<b>📢 Kanallar boshqaruvi</b><br/><br/>"
            "Hozirda majburiy obuna kanallari kiritilmagan.<br/>"
            "<i>Foydalanuvchilar botdan to'siqsiz foydalanmoqda.</i><br/><br/>"
            "Yangi kanal qo'shish uchun quyidagi <b>➕ Yangi kanal qo'shish</b> tugmasini bosing:"
        )
    else:
        text = f"<b>📢 Majburiy obuna kanallari ({len(channels)} ta):</b><br/><br/>"
        for idx, ch in enumerate(channels, 1):
            st = "🟢" if ch.is_active else "🔴"
            lang_label = (
                "🇺🇿 O'zbek tili (Lotin & Kirill)" if ch.language == "uz" else
                ("🇷🇺 Rus tili" if ch.language == "ru" else "🌐 Barcha tillar")
            )
            text += (
                f"<b>{idx}. {ch.channel_name}</b><br/>"
                f"<b>ID:</b> <code>{ch.channel_id}</code><br/>"
                f"<b>Tili:</b> {lang_label}<br/>"
                f"<b>Havola:</b> <a href=\"{ch.invite_link}\">{ch.invite_link}</a><br/>"
                f"<b>Holati:</b> {st}<br/><br/>"
            )
            toggle_label = "🔴" if ch.is_active else "🟢"
            builder.button(text=f"{idx}. {toggle_label}", callback_data=f"admin:ch_toggle:{ch.id}")
            builder.button(text=f"🌐 {idx}-tilini o'zgartirish", callback_data=f"admin:ch_lang_menu:{ch.id}")
            builder.button(text=f"🗑 {idx}-o'chirish", callback_data=f"admin:ch_del:{ch.id}")

    builder.button(text="➕ Yangi kanal qo'shish", callback_data="admin:ch_add")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    if channels:
        builder.adjust(*([3] * len(channels)), 1, 1)
    else:
        builder.adjust(1, 1)
    return text, builder.as_markup()

@admin_router.callback_query(F.data == "admin:channels_menu", is_private_message)
async def admin_channels_menu_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    channels = RequiredChannel.get_all(db_session)
    text, markup = build_admin_channels_page(channels)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:ch_toggle:"), is_private_message)
async def admin_channel_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    ch_id = int(query.data.split(":")[2])
    ch = RequiredChannel.get_by_id(ch_id, db_session)
    if not ch:
        return await query.answer("⚠️ Kanal topilmadi!", show_alert=True)

    ch.is_active = not ch.is_active
    db_session.add(ch)
    db_session.commit()

    new_st = "faollashtirildi" if ch.is_active else "nofaol qilindi"
    await query.answer(f"Kanal {new_st}!")

    channels = RequiredChannel.get_all(db_session)
    text, markup = build_admin_channels_page(channels)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))

@admin_router.callback_query(F.data.startswith("admin:ch_del:"), is_private_message)
async def admin_channel_delete_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    ch_id = int(query.data.split(":")[2])
    ch = RequiredChannel.get_by_id(ch_id, db_session)
    if ch:
        db_session.delete(ch)
        db_session.commit()
        await query.answer("🗑 Kanal o'chirildi!", show_alert=True)
    else:
        await query.answer("⚠️ Kanal topilmadi!", show_alert=True)

    channels = RequiredChannel.get_all(db_session)
    text, markup = build_admin_channels_page(channels)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))

@admin_router.callback_query(F.data == "admin:ch_add", is_private_message)
async def admin_channel_add_callback(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminAddChannelState.waiting_for_channel)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:channels_menu")

    prompt = (
        "<b>➕ Majburiy obuna uchun kanal qo'shish</b><br/><br/>"
        "Kanal username'ini (masalan: <code>@huquqplus</code>) yoki kanal ID raqamini (masalan: <code>-1001234567890</code>) yuboring.<br/><br/>"
        "<i>Shuningdek, o'sha kanaldan birorta postni ushbu chatga <b>forward</b> (uzatish) qilishingiz ham mumkin.</i><br/><br/>"
        "⚠️ <b>MUHIM:</b> Bot foydalanuvchilarning a'zoligini tekshirishi uchun <b>bot ushbu kanalda Administrator</b> bo'lishi shart!"
    )
    await query.message.edit_text(prompt, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.message(AdminAddChannelState.waiting_for_channel, is_private_message)
async def admin_channel_input_handler(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ["/cancel", "bekor qilish"]:
        await state.clear()
        channels = RequiredChannel.get_all(db_session)
        text, markup = build_admin_channels_page(channels)
        return await message.answer(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))

    target_chat = None
    if message.forward_from_chat and message.forward_from_chat.type in ["channel", "supergroup"]:
        target_chat = message.forward_from_chat.id
    elif message.text:
        txt = message.text.strip()
        if txt.startswith("https://t.me/"):
            clean = txt.replace("https://t.me/", "").strip("/").split("/")[0]
            if clean.startswith("+") or clean.startswith("joinchat/"):
                target_chat = txt
            else:
                target_chat = f"@{clean}"
        elif txt.startswith("-100") or (txt.startswith("-") and txt[1:].isdigit()):
            target_chat = int(txt)
        elif txt.startswith("@"):
            target_chat = txt
        else:
            target_chat = f"@{txt}"
    else:
        return await message.answer("⚠️ Iltimos, kanal username, ID raqamini yuboring yoki kanaldan post forward qiling!")

    try:
        chat = await bot.get_chat(target_chat)
    except Exception as e:
        return await message.answer(
            f"❌ <b>Kanal topilmadi yoki bot kanalga kira olmadi!</b><br/><br/>"
            f"Xatolik: <code>{e}</code><br/><br/>"
            f"Iltimos, avval botni kanalingizga <b>Administrator</b> qilib qo'shing va qaytadan kanal username yoki ID raqamini yuboring.",
            parse_mode=SULGUK_PARSE_MODE
        )

    if chat.type not in ["channel", "supergroup"]:
        return await message.answer("⚠️ Faqat Telegram kanal yoki superguruhlarni qo'shish mumkin!")

    try:
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            return await message.answer(
                "⚠️ <b>Bot ushbu kanalda Administrator emas!</b><br/><br/>"
                "Majburiy obuna a'zolarini tekshira olish uchun bot kanalda admin bo'lishi shart.<br/>"
                "Iltimos, botni kanalga admin qilib qo'shing va qayta yuboring.",
                parse_mode=SULGUK_PARSE_MODE
            )
    except Exception as e:
        return await message.answer(f"⚠️ Botning kanal adminligini tekshirishda xatolik: {e}")

    existing = RequiredChannel.get_by_channel_id(str(chat.id), db_session)
    if not existing and chat.username:
        existing = RequiredChannel.get_by_channel_id(f"@{chat.username}", db_session)
    if existing:
        await state.clear()
        return await message.answer(
            f"⚠️ Ushbu kanal allaqachon qo'shilgan:<br/>"
            f"<b>{existing.channel_name}</b> (ID: <code>{existing.channel_id}</code>)",
            parse_mode=SULGUK_PARSE_MODE
        )

    invite_link = None
    if chat.username:
        invite_link = f"https://t.me/{chat.username}"
    elif chat.invite_link:
        invite_link = chat.invite_link
    else:
        try:
            created = await bot.create_chat_invite_link(chat.id, name="HuquqPlusBot Sub")
            invite_link = created.invite_link
        except Exception:
            clean_id = str(chat.id).replace("-100", "")
            invite_link = f"https://t.me/c/{clean_id}/"

    channel_name = chat.title or (chat.username or "Telegram Kanal")

    await state.update_data(
        new_ch_id=str(chat.id),
        new_ch_name=channel_name,
        new_ch_link=invite_link
    )
    await state.set_state(AdminAddChannelState.waiting_for_language)

    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbek tili (Lotin & Kirill)", callback_data="admin:ch_set_lang:uz")
    builder.button(text="🇷🇺 Rus tili", callback_data="admin:ch_set_lang:ru")
    builder.button(text="🌐 Barcha tillar uchun umumiy", callback_data="admin:ch_set_lang:all")
    builder.button(text="❌ Bekor qilish", callback_data="admin:channels_menu")
    builder.adjust(1)

    await message.answer(
        f"✅ <b>Kanal topildi!</b><br/>"
        f"📢 <b>Nomi:</b> {channel_name}<br/>"
        f"🔗 <b>Havola:</b> {invite_link}<br/><br/>"
        f"❓ <b>Ushbu kanal qaysi til foydalanuvchilari uchun majburiy bo'lsin?</b>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data.startswith("admin:ch_set_lang:"), is_private_message)
async def admin_channel_set_lang_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    chosen_lang = query.data.split(":")[2]
    data = await state.get_data()
    channel_id = data.get("new_ch_id")
    channel_name = data.get("new_ch_name")
    invite_link = data.get("new_ch_link")

    if not channel_id:
        await state.clear()
        return await query.answer("Kanal ma'lumotlari topilmadi. Qaytadan urinib ko'ring.", show_alert=True)

    new_channel = RequiredChannel(
        channel_id=channel_id,
        channel_name=channel_name,
        invite_link=invite_link,
        language=chosen_lang,
        is_active=True
    )
    db_session.add(new_channel)
    db_session.commit()
    db_session.refresh(new_channel)
    await state.clear()

    channels = RequiredChannel.get_all(db_session)
    text, markup = build_admin_channels_page(channels)
    lang_name = (
        "🇺🇿 O'zbek tili (Lotin & Kirill)" if chosen_lang == "uz" else
        ("🇷🇺 Rus tili" if chosen_lang == "ru" else "🌐 Barcha tillar")
    )
    await query.message.edit_text(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b><br/>"
        f"📢 <b>Nomi:</b> {channel_name}<br/>"
        f"🌐 <b>Tili:</b> {lang_name}<br/>"
        f"🔗 <b>Havola:</b> {invite_link}<br/><br/>"
        f"Endi bot faqat belgilangan til foydalanuvchilaridan ushbu kanalga a'zo bo'lishni talab qiladi.<br/><br/>"
        f"{text}",
        reply_markup=markup,
        parse_mode=SULGUK_PARSE_MODE,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:ch_lang_menu:"), is_private_message)
async def admin_channel_lang_menu_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    ch_id = int(query.data.split(":")[2])
    ch = RequiredChannel.get_by_id(ch_id, db_session)
    if not ch:
        return await query.answer("⚠️ Kanal topilmadi!", show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbek tili (Lotin & Kirill)", callback_data=f"admin:ch_update_lang:{ch.id}:uz")
    builder.button(text="🇷🇺 Rus tili", callback_data=f"admin:ch_update_lang:{ch.id}:ru")
    builder.button(text="🌐 Barcha tillar uchun umumiy", callback_data=f"admin:ch_update_lang:{ch.id}:all")
    builder.button(text="⬅️ Kanallar ro'yxati", callback_data="admin:channels_menu")
    builder.adjust(1)

    cur_lang = (
        "🇺🇿 O'zbek tili" if ch.language == "uz" else
        ("🇷🇺 Rus tili" if ch.language == "ru" else "🌐 Barcha tillar")
    )
    await query.message.edit_text(
        f"📢 <b>Kanal:</b> {ch.channel_name}<br/>"
        f"🌐 <b>Hozirgi tili:</b> {cur_lang}<br/><br/>"
        f"Ushbu kanal qaysi til foydalanuvchilariga ko'rsatilsin?",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:ch_update_lang:"), is_private_message)
async def admin_channel_update_lang_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    ch_id = int(parts[2])
    new_lang = parts[3]

    ch = RequiredChannel.get_by_id(ch_id, db_session)
    if not ch:
        return await query.answer("⚠️ Kanal topilmadi!", show_alert=True)

    ch.language = new_lang
    db_session.add(ch)
    db_session.commit()

    await query.answer("Kanal tili yangilandi!")
    channels = RequiredChannel.get_all(db_session)
    text, markup = build_admin_channels_page(channels)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE, link_preview_options=LinkPreviewOptions(is_disabled=True))
