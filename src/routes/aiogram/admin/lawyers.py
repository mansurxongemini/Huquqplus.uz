"""Rasmiy yuristlar boshqaruvi."""
import logging
from aiogram import F

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.lawyer import OfficialLawyer
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import AdminAddLawyerState, admin_router


@admin_router.callback_query(F.data == "admin:lawyers_list", is_private_message)
async def admin_lawyers_list_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    lawyers = db_session.exec(select(OfficialLawyer)).all()
    builder = InlineKeyboardBuilder()

    text_lines = ["<b>👨‍⚖️ Yuristlar ro'yxati:</b><br/>"]
    if not lawyers:
        text_lines.append("<i>Hozirda ro'yxatdan o'tgan yuristlar mavjud emas.</i>")
    else:
        for idx, l in enumerate(lawyers, start=1):
            status = "🟢" if l.is_active else "🔴"
            phone_str = f" | Tel: {l.phone}" if l.phone else ""
            spec_str = f" ({l.specialization})" if l.specialization else ""
            text_lines.append(f"{idx}. <b>{l.full_name}</b>{spec_str} — {status}<br/>   ID: <code>{l.user_id}</code>{phone_str}")

            icon = "🟢" if l.is_active else "🔴"
            builder.button(
                text=f"{icon} {l.full_name[:20]}",
                callback_data=f"admin:lawyer_view:{l.id}"
            )

    builder.button(text="➕ Yangi yurist qo'shish", callback_data="admin:lawyer_add")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:lawyer_view:"), is_private_message)
async def admin_lawyer_view_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    status_str = "🟢 Faol" if lawyer.is_active else "🔴"
    toggle_btn_text = "🔴" if lawyer.is_active else "🟢"

    text = f"""
<b>👨‍⚖️ Yurist ma'lumotlari:</b><br/><br/>
Ism-familiya: <b>{lawyer.full_name}</b><br/>
Telegram ID: <code>{lawyer.user_id}</code><br/>
Telefon: <b>{lawyer.phone or "kiritilmagan"}</b><br/>
Soha/Mutaxassislik: <b>{lawyer.specialization or "kiritilmagan"}</b><br/>
Holati: <b>{status_str}</b><br/>
Qo'shilgan sana: <b>{lawyer.created_at.strftime('%Y-%m-%d %H:%M')}</b>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=toggle_btn_text, callback_data=f"admin:lawyer_toggle:{lawyer.id}")
    builder.button(text="🗑 O'chirish", callback_data=f"admin:lawyer_delete:{lawyer.id}")
    builder.button(text="⬅️ Yuristlar ro'yxatiga", callback_data="admin:lawyers_list")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:lawyer_toggle:"), is_private_message)
async def admin_lawyer_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    lawyer.is_active = not lawyer.is_active
    db_session.add(lawyer)
    db_session.commit()

    action_text = "faollashtirildi" if lawyer.is_active else "faolsizlantirildi"
    await query.answer(f"Yurist muvaffaqiyatli {action_text}!", show_alert=True)

    status_str = "🟢 Faol" if lawyer.is_active else "🔴"
    toggle_btn_text = "🔴" if lawyer.is_active else "🟢"

    text = f"""
<b>👨‍⚖️ Yurist ma'lumotlari:</b><br/><br/>
Ism-familiya: <b>{lawyer.full_name}</b><br/>
Telegram ID: <code>{lawyer.user_id}</code><br/>
Telefon: <b>{lawyer.phone or "kiritilmagan"}</b><br/>
Soha/Mutaxassislik: <b>{lawyer.specialization or "kiritilmagan"}</b><br/>
Holati: <b>{status_str}</b><br/>
Qo'shilgan sana: <b>{lawyer.created_at.strftime('%Y-%m-%d %H:%M')}</b>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=toggle_btn_text, callback_data=f"admin:lawyer_toggle:{lawyer.id}")
    builder.button(text="🗑 O'chirish", callback_data=f"admin:lawyer_delete:{lawyer.id}")
    builder.button(text="⬅️ Yuristlar ro'yxatiga", callback_data="admin:lawyers_list")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)

@admin_router.callback_query(F.data.startswith("admin:lawyer_delete:"), is_private_message)
async def admin_lawyer_delete_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    lawyer_id = int(query.data.split(":")[2])
    lawyer = db_session.get(OfficialLawyer, lawyer_id)
    if not lawyer:
        return await query.answer("Yurist topilmadi!", show_alert=True)

    db_session.delete(lawyer)
    db_session.commit()

    await query.answer("Yurist muvaffaqiyatli o'chirildi!", show_alert=True)

    lawyers = db_session.exec(select(OfficialLawyer)).all()
    builder = InlineKeyboardBuilder()

    text_lines = ["<b>👨‍⚖️ yuristlar ro'yxati:</b><br/>"]
    if not lawyers:
        text_lines.append("<i>Hozirda ro'yxatdan o'tgan yuristlar mavjud emas.</i>")
    else:
        for idx, l in enumerate(lawyers, start=1):
            status = "🟢" if l.is_active else "🔴"
            phone_str = f" | Tel: {l.phone}" if l.phone else ""
            spec_str = f" ({l.specialization})" if l.specialization else ""
            text_lines.append(f"{idx}. <b>{l.full_name}</b>{spec_str} — {status}<br/>   ID: <code>{l.user_id}</code>{phone_str}")
            icon = "🟢" if l.is_active else "🔴"
            builder.button(
                text=f"{icon} {l.full_name[:20]}",
                callback_data=f"admin:lawyer_view:{l.id}"
            )

    builder.button(text="➕ Yangi yurist qo'shish", callback_data="admin:lawyer_add")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text("<br/>".join(text_lines), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


# --- Add Lawyer FSM Handlers ---

@admin_router.callback_query(F.data == "admin:lawyer_add", is_private_message)
async def admin_lawyer_add_start(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminAddLawyerState.waiting_for_user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await query.message.edit_text(
        "<b>➕ Yangi yurist qo'shish</b><br/><br/>"
        "Yuristning <b>Telegram ID</b> raqamini kiriting:<br/>"
        "<i>(Masalan: 123456789)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminAddLawyerState.waiting_for_user_id, is_private_message)
async def admin_lawyer_id_received(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        return await message.answer("⚠️ Iltimos, faqat raqamlardan iborat to'g'ri Telegram ID kiriting:")

    lawyer_uid = int(text)
    existing = OfficialLawyer.get_by_user_id(lawyer_uid, db_session)
    if existing:
        return await message.answer(f"⚠️ Bu foydalanuvchi ({existing.full_name}) allaqachon yuristlar ro'yxatida mavjud!")

    await state.update_data(lawyer_user_id=lawyer_uid)
    await state.set_state(AdminAddLawyerState.waiting_for_name)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await message.answer(
        f"Telegram ID: <code>{lawyer_uid}</code> qabul qilindi.<br/><br/>"
        "Endi yuristning <b>to'liq ism-familiyasini</b> kiriting:<br/>"
        "<i>(Masalan: Alisher Qodirov)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.message(AdminAddLawyerState.waiting_for_name, is_private_message)
async def admin_lawyer_name_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    name = message.text.strip()
    if len(name) < 3:
        return await message.answer("⚠️ Iltimos, ism-familiyani to'liqroq kiriting:")

    await state.update_data(lawyer_name=name)
    await state.set_state(AdminAddLawyerState.waiting_for_details)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:lawyers_list")

    await message.answer(
        f"Ism: <b>{name}</b> qabul qilindi.<br/><br/>"
        "Endi yuristning <b>sohasi/mutaxassisligi</b> yoki telefon raqamini kiriting:<br/>"
        "<i>(Agar kiritishni istamasangiz, shunchaki <b>-</b> belgisini yuboring)</i>",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.message(AdminAddLawyerState.waiting_for_details, is_private_message)
async def admin_lawyer_details_received(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    lawyer_uid = data.get("lawyer_user_id")
    lawyer_name = data.get("lawyer_name")

    details = message.text.strip()
    spec = None if details == "-" else details

    new_lawyer = OfficialLawyer(
        user_id=lawyer_uid,
        full_name=lawyer_name,
        specialization=spec,
        is_active=True
    )
    db_session.add(new_lawyer)
    db_session.commit()
    db_session.refresh(new_lawyer)

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍⚖️ Yuristlar ro'yxatiga qaytish", callback_data="admin:lawyers_list")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await message.answer(
        f"✅ <b>Yangi yurist muvaffaqiyatli qo'shildi!</b><br/><br/>"
        f"Ism: <b>{new_lawyer.full_name}</b><br/>"
        f"ID: <code>{new_lawyer.user_id}</code><br/>"
        f"Soha: <b>{new_lawyer.specialization or 'kiritilmagan'}</b><br/>"
        f"Holat: 🟢 Faol",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )


# =====================================================================
# --- Yurist Qabullari CRM va Taqvimi ---
# =====================================================================
