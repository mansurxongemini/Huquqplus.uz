"""Ommaviy xabar (broadcast)."""
import logging
from datetime import datetime
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select, Session
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.broadcast import Broadcast, BroadcastStatus
from src.models.user import User
from src.routes.deps.db_session import DBSession
from src.database.redisdb import get_redis
from src.database.mysql import engine

from src.routes.aiogram.admin.common import AdminBroadcastState, PAGE_SIZE, admin_router


@admin_router.callback_query(F.data == "admin:broadcast_menu", is_private_message)
async def admin_broadcast_menu_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    running = Broadcast.get_running_broadcast(db_session)

    builder = InlineKeyboardBuilder()

    if running:
        builder.button(text="⚡️ Hozirgi jonli broadcast holati", callback_data=f"admin:broadcast:live:{running.id}")

    builder.button(text="➕ Yangi broadcast yaratish", callback_data="admin:broadcast:start")
    builder.button(text="📊 Broadcastlar tarixi", callback_data="admin:broadcast:history:1")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    running_text = ""
    if running:
        running_text = f"<br/>🔥 <b>DIQQAT: Ayni paytda Broadcast №{running.id} yuborilmoqda!</b><br/>"

    text = f"""
<b>📢 Broadcast bo'limi</b><br/>{running_text}
"""
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data == "admin:broadcast:start", is_private_message)
async def admin_broadcast_start(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminBroadcastState.waiting_for_message)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    prompt = """
📢 <b>Ommaviy yuboriladigan xabarni yuboring:</b><br/><br/>
"""
    await query.message.edit_text(prompt, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.message(AdminBroadcastState.waiting_for_message, is_private_message)
async def admin_broadcast_message_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    # Store message_id and chat_id
    await state.update_data(
        broadcast_from_chat_id=message.chat.id,
        broadcast_message_id=message.message_id
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Ha, havola tugmasi qo'shish", callback_data="admin:broadcast:add_btn:yes")
    builder.button(text="⏭ Yo'q, tugmasiz davom etish", callback_data="admin:broadcast:add_btn:no")
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    await message.answer(
        "✅ <b>Xabar qabul qilindi!</b><br/><br/>"
        "Ushbu xabar ostiga havola beruvchi <b>Inline tugma</b> (masalan: <i>Batafsil ma'lumot</i>) qo'shishni xohlaysizmi?",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data == "admin:broadcast:add_btn:yes", is_private_message)
async def admin_broadcast_add_btn_start(query: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcastState.waiting_for_button_text)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    await query.message.edit_text(
        "🔘 <b>Tugma ustida ko'rinadigan matnni kiriting:</b><br/>"
        "<i>(Masalan: 👉 Batafsil ma'lumot)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminBroadcastState.waiting_for_button_text, is_private_message)
async def admin_broadcast_btn_text_received(message: Message, state: FSMContext):
    btn_text = message.text.strip()
    await state.update_data(broadcast_btn_text=btn_text)
    await state.set_state(AdminBroadcastState.waiting_for_button_url)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")

    await message.answer(
        f"Tugma matni: <b>{btn_text}</b><br/><br/>"
        "Endi tugma bosilganda ochiladigan <b>URL manzilni</b> kiriting:<br/>"
        "<i>(Masalan: https://t.me/huquqplus yoki https://huquqplus.uz)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.message(AdminBroadcastState.waiting_for_button_url, is_private_message)
async def admin_broadcast_btn_url_received(message: Message, state: FSMContext, db_session: DBSession):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/")):
        return await message.answer("⚠️ Iltimos, haqiqiy URL manzil kiriting (https:// bilan boshlanishi kerak):")

    await state.update_data(broadcast_btn_url=url)
    await show_audience_selection(message, state, db_session)

@admin_router.callback_query(F.data == "admin:broadcast:add_btn:no", is_private_message)
async def admin_broadcast_no_btn(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await state.update_data(broadcast_btn_text=None, broadcast_btn_url=None)
    await query.message.delete()
    await show_audience_selection(query.message, state, db_session)
    await query.answer()

async def show_audience_selection(message: Message, state: FSMContext, db_session: DBSession):
    total_users = len(db_session.exec(select(User).where(User.is_blocked == False)).all())
    uz_users = len(db_session.exec(select(User).where(User.is_blocked == False, User.language == "uz")).all())
    oz_users = len(db_session.exec(select(User).where(User.is_blocked == False, User.language == "oz")).all())
    ru_users = len(db_session.exec(select(User).where(User.is_blocked == False, User.language == "ru")).all())

    builder = InlineKeyboardBuilder()
    builder.button(text=f"👥 Barcha foydalanuvchilar ({total_users} ta)", callback_data="admin:broadcast:target:all")
    builder.button(text=f"🇺🇿 O'zbek tili (Lotin) ({uz_users} ta)", callback_data="admin:broadcast:target:lang_uz")
    builder.button(text=f"🇺🇿 Ўзбек тили (Кирилл) ({oz_users} ta)", callback_data="admin:broadcast:target:lang_oz")
    builder.button(text=f"🇷🇺 Rus tili ({ru_users} ta)", callback_data="admin:broadcast:target:lang_ru")
    builder.button(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    await message.answer(
        "🎯 <b>Xabar qaysi auditoriyaga yuborilsin?</b><br/>"
        "Quyidagi toifalardan birini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data.startswith("admin:broadcast:target:"), is_private_message)
async def admin_broadcast_target_chosen(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    target_filter = query.data.replace("admin:broadcast:target:", "")
    data = await state.get_data()

    from_chat_id = data.get("broadcast_from_chat_id")
    message_id = data.get("broadcast_message_id")
    btn_text = data.get("broadcast_btn_text")
    btn_url = data.get("broadcast_btn_url")

    # Count matching users
    q = select(User).where(User.is_blocked == False)
    filter_label = "Barcha foydalanuvchilar"
    if target_filter == "lang_uz":
        q = q.where(User.language == "uz")
        filter_label = "O'zbek tili (Lotin) foydalanuvchilari"
    elif target_filter == "lang_oz":
        q = q.where(User.language == "oz")
        filter_label = "Ўзбек тили (Кирилл) фойдаланувчилари"
    elif target_filter == "lang_ru":
        q = q.where(User.language == "ru")
        filter_label = "Rus tili foydalanuvchilari"

    matched_users = len(db_session.exec(q).all())

    # Create Broadcast entry
    bc = Broadcast(
        admin_id=query.from_user.id,
        from_chat_id=from_chat_id,
        message_id=message_id,
        target_filter=target_filter,
        button_text=btn_text,
        button_url=btn_url,
        total_target=matched_users,
        status=BroadcastStatus.pending
    )
    db_session.add(bc)
    db_session.commit()
    db_session.refresh(bc)

    await state.clear()
    await query.message.delete()

    # Send exact copy of message to admin as preview
    test_markup = None
    if btn_text and btn_url:
        test_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn_text, url=btn_url)]]
        )

    try:
        await bot.copy_message(
            chat_id=query.from_user.id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            reply_markup=test_markup
        )
    except Exception as e:
        logger.warning("Test copy failed: %s", e)

    # Estimate time (at 28 msg/sec)
    eta_sec = int(matched_users / 28) if matched_users else 0
    eta_min = eta_sec // 60
    eta_rem = eta_sec % 60
    eta_str = f"~{eta_min} daqiqa {eta_rem} soniya" if eta_min > 0 else f"~{eta_sec} soniya"

    btn_display = f"'{btn_text}' ({btn_url})" if btn_text else "Mavjud emas"

    confirm_card = f"""
📢 <b>BROADCASTNI TASDIQLANG:</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
🎯 <b>Auditoriya:</b> {filter_label} (<b>{matched_users}</b> ta foydalanuvchi)<br/>
🔘 <b>Tugma:</b> {btn_display}<br/>
⏱ <b>Taxminiy yuborish vaqti:</b> {eta_str}<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
<i>Yuqoridagi xabar nusxasi to'g'rimi? Barcha foydalanuvchilarga yuborishni tasdiqlaysizmi?</i>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Xabarni barchaga yuborish", callback_data=f"admin:broadcast:launch:{bc.id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"admin:broadcast:cancel_draft:{bc.id}")
    builder.adjust(1)

    await query.message.answer(confirm_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:broadcast:launch:"), is_private_message)
async def admin_broadcast_launch(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    bc = db_session.get(Broadcast, bc_id)
    if not bc:
        return await query.answer("Broadcast topilmadi!", show_alert=True)

    if bc.status == BroadcastStatus.running:
        return await query.answer("Ushbu broadcast allaqachon ishga tushirilgan!", show_alert=True)

    # Dispatch Celery background task
    from src.tasks.broadcast import execute_broadcast
    execute_broadcast.delay(bc.id)

    await query.answer("🚀 Broadcast ishga tushirildi!", show_alert=True)
    await show_live_progress(query, bc.id)

@admin_router.callback_query(F.data.startswith("admin:broadcast:cancel_draft:"), is_private_message)
async def admin_broadcast_cancel_draft(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    bc = db_session.get(Broadcast, bc_id)
    if bc and bc.status == BroadcastStatus.pending:
        bc.status = BroadcastStatus.cancelled
        db_session.add(bc)
        db_session.commit()

    await query.answer("Broadcast bekor qilindi.", show_alert=False)
    await admin_broadcast_menu_callback(query, None, db_session)

@admin_router.callback_query(F.data.startswith("admin:broadcast:live:"), is_private_message)
async def admin_broadcast_live_callback(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    await show_live_progress(query, bc_id, db_session)

async def show_live_progress(query: CallbackQuery, broadcast_id: int, db_session: DBSession | None = None):
    redis_client = get_redis(is_async=True)

    if db_session:
        bc = db_session.get(Broadcast, broadcast_id)
    else:
        with Session(engine) as session:
            bc = session.get(Broadcast, broadcast_id)

    if not bc:
        return await query.answer("Broadcast topilmadi!", show_alert=True)

    live_stats = None
    try:
        live_stats = await redis_client.hgetall(f"broadcast:{broadcast_id}:live")
    except Exception:
        pass

    sent = int(live_stats.get("sent", bc.sent_count)) if live_stats else bc.sent_count
    blocked = int(live_stats.get("blocked", bc.blocked_count)) if live_stats else bc.blocked_count
    failed = int(live_stats.get("failed", bc.failed_count)) if live_stats else bc.failed_count
    total = int(live_stats.get("total", bc.total_target)) if live_stats else bc.total_target

    processed = sent + blocked + failed
    pct = (processed / total * 100) if total > 0 else 0.0

    filled = int(pct // 10)
    bar = "█" * filled + "░" * (10 - filled)

    status_icon = "⚡️ Jarayonda..." if bc.status == BroadcastStatus.running else ("✅ Yakunlandi" if bc.status == BroadcastStatus.completed else f"❌ {bc.status}")

    card = f"""
<b>📊 Broadcast holati (№{bc.id}):</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
Holati: <b>{status_icon}</b><br/>
Progress: <code>[{bar}]</code> <b>{pct:.1f}%</b><br/><br/>
🎯 Jami: <b>{total}</b> ta<br/>
✅ Muvaffaqiyatli: <b>{sent}</b> ta<br/>
🚫 Botni bloklagan: <b>{blocked}</b> ta<br/>
⚠️ Xatolik: <b>{failed}</b> ta<br/>
📤 Qayta ishlangan: <b>{processed} / {total}</b><br/>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Yangilash", callback_data=f"admin:broadcast:live:{bc.id}")

    if bc.status == BroadcastStatus.running:
        builder.button(text="🛑 Yuborishni to'xtatish", callback_data=f"admin:broadcast:stop:{bc.id}")

    builder.button(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu")
    builder.adjust(1)

    try:
        await query.message.edit_text(card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:broadcast:stop:"), is_private_message)
async def admin_broadcast_stop(query: CallbackQuery, db_session: DBSession):
    bc_id = int(query.data.split(":")[3])
    redis_client = get_redis(is_async=True)

    try:
        await redis_client.set(f"broadcast:{bc_id}:cancel", 1)
        live_stats = await redis_client.hgetall(f"broadcast:{bc_id}:live")

        bc = db_session.get(Broadcast, bc_id)
        if bc and bc.status == BroadcastStatus.running:
            if live_stats:
                bc.sent_count = int(live_stats.get("sent", bc.sent_count))
                bc.blocked_count = int(live_stats.get("blocked", bc.blocked_count))
                bc.failed_count = int(live_stats.get("failed", bc.failed_count))
            bc.status = BroadcastStatus.cancelled
            bc.completed_at = datetime.now()
            db_session.add(bc)
            db_session.commit()

        await redis_client.delete(f"broadcast:{bc_id}:live")
        await redis_client.delete(f"broadcast:{bc_id}:cancel")
        await query.answer("🛑 Broadcast jarayoni to'xtatildi!", show_alert=True)
    except Exception as e:
        await query.answer(f"Xatolik: {e}", show_alert=True)

    await show_live_progress(query, bc_id, db_session)

@admin_router.callback_query(F.data.startswith("admin:broadcast:history:"), is_private_message)
async def admin_broadcast_history(query: CallbackQuery, db_session: DBSession):
    page = int(query.data.split(":")[3])
    all_bc = db_session.exec(select(Broadcast).order_by(Broadcast.created_at.desc())).all()

    total = len(all_bc)
    if total == 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu")
        return await query.message.edit_text("<i>Hozircha ommaviy xabarlar tarixi mavjud emas.</i>", reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total)
    page_bcs = all_bc[start_idx:end_idx]

    text_lines = [f"<b>📊 Ommaviy xabarlar tarixi</b> (Sahifa: {page}/{total_pages}):<br/>"]
    builder = InlineKeyboardBuilder()

    status_icons = {
        BroadcastStatus.completed: "✅",
        BroadcastStatus.running: "⚡️",
        BroadcastStatus.cancelled: "❌",
        BroadcastStatus.pending: "⏳"
    }

    redis_client = get_redis(is_async=True)
    for b in page_bcs:
        icon = status_icons.get(b.status, "ℹ️")
        dt_str = b.created_at.strftime("%d.%m.%Y %H:%M")
        sent = b.sent_count
        blocked = b.blocked_count
        if b.status == BroadcastStatus.running:
            try:
                live = await redis_client.hgetall(f"broadcast:{b.id}:live")
                if live:
                    sent = int(live.get("sent", sent))
                    blocked = int(live.get("blocked", blocked))
            except Exception:
                pass

        text_lines.append(
            f"{icon} <b>Broadcast №{b.id}</b> ({dt_str})<br/>"
            f"Holat: {b.status.upper()}<br/>"
            f"Yetkazildi: {sent} / {b.total_target} ta<br/>"
        )
        builder.button(text=f"🔍 №{b.id} tafsilotlari", callback_data=f"admin:broadcast:live:{b.id}")

    builder.adjust(1)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:broadcast:history:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:broadcast:history:{page + 1}"))

    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="⬅️ Broadcast menyusi", callback_data="admin:broadcast_menu"))

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# --------------------- ADMIN BENEFITS MANAGEMENT ---------------------
