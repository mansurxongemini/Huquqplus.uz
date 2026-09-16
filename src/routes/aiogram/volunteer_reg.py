import re
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.keyboards import get_main_menu
from src.config.settings import settings
from src.models.volunteer import Volunteer
from src.routes.deps.db_session import DBSession

volunteer_reg_router = Router(name="volunteer_reg")


class VolunteerRegState(StatesGroup):
    first_name = State()
    last_name = State()
    study_or_work = State()
    birth_year = State()
    phone_number = State()


CANCEL_WORDS = ["❌ Bekor qilish", "/cancel", "Bekor qilish", "bekor qilish"]


def get_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


async def start_volunteer_registration(message: Message, state: FSMContext, db_session: DBSession):
    """
    Called when a user enters via the invite link: https://t.me/<bot>?start=volunteer
    """
    await state.clear()

    # Check if already registered
    existing = db_session.exec(select(Volunteer).where(Volunteer.user_id == message.from_user.id)).first()
    if existing and existing.is_active:
        return await message.answer(
            f"✅ <b>Assalomu alaykum, {existing.first_name}!</b>\n\n"
            f"Siz allaqachon HuquqPlus loyihasida rasmiy volontyor sifatida ro'yxatdan o'tgansiz.\n"
            f"Guruhdagi fuqarolar murojaatlariga bemalol javob berishingiz mumkin! 🤝",
            reply_markup=get_main_menu("uz"),
            parse_mode=SULGUK_PARSE_MODE
        )

    await state.set_state(VolunteerRegState.first_name)
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "HuquqPlus loyihasining volontyori bo'lish istagini bildirganingiz uchun tashakkur!\n"
        "Rasmiy ro'yxatdan o'tish uchun quyidagi ma'lumotlarni qisqa to'ldiring:\n\n"
        "✍️ <b>Ismingizni kiriting:</b>",
        reply_markup=get_cancel_kb(),
        parse_mode=SULGUK_PARSE_MODE
    )


@volunteer_reg_router.message(VolunteerRegState.first_name, is_private_message)
async def process_vol_first_name(message: Message, state: FSMContext):
    if message.text in CANCEL_WORDS:
        await state.clear()
        return await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=ReplyKeyboardRemove())

    text = message.text.strip() if message.text else ""
    if len(text) < 2:
        return await message.answer("Iltimos, ismingizni to'liq kiriting:")

    await state.update_data(first_name=text)
    await state.set_state(VolunteerRegState.last_name)
    await message.answer("✍️ <b>Familiyangizni kiriting:</b>", reply_markup=get_cancel_kb(), parse_mode=SULGUK_PARSE_MODE)


@volunteer_reg_router.message(VolunteerRegState.last_name, is_private_message)
async def process_vol_last_name(message: Message, state: FSMContext):
    if message.text in CANCEL_WORDS:
        await state.clear()
        return await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=ReplyKeyboardRemove())

    text = message.text.strip() if message.text else ""
    if len(text) < 2:
        return await message.answer("Iltimos, familiyangizni to'liq kiriting:")

    await state.update_data(last_name=text)
    await state.set_state(VolunteerRegState.study_or_work)
    await message.answer(
        "🎓 <b>O'qish yoki ish joyingizni kiriting:</b>\n"
        "<i>(Masalan: TDYU 3-bosqich talabasi, yurist yoki mustaqil huquqshunos)</i>",
        reply_markup=get_cancel_kb(),
        parse_mode=SULGUK_PARSE_MODE
    )


@volunteer_reg_router.message(VolunteerRegState.study_or_work, is_private_message)
async def process_vol_study_work(message: Message, state: FSMContext):
    if message.text in CANCEL_WORDS:
        await state.clear()
        return await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=ReplyKeyboardRemove())

    text = message.text.strip() if message.text else ""
    if len(text) < 2:
        return await message.answer("Iltimos, o'qish yoki ish joyingizni kiriting:")

    await state.update_data(study_or_work=text)
    await state.set_state(VolunteerRegState.birth_year)
    await message.answer(
        "📅 <b>Tug'ilgan yilingizni kiriting:</b>\n"
        "<i>(Masalan: 2002)</i>",
        reply_markup=get_cancel_kb(),
        parse_mode=SULGUK_PARSE_MODE
    )


@volunteer_reg_router.message(VolunteerRegState.birth_year, is_private_message)
async def process_vol_birth_year(message: Message, state: FSMContext):
    if message.text in CANCEL_WORDS:
        await state.clear()
        return await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=ReplyKeyboardRemove())

    text = message.text.strip() if message.text else ""
    current_year = datetime.now().year
    if not text.isdigit() or not (1940 <= int(text) <= current_year - 14):
        return await message.answer(f"Iltimos, to'g'ri yilni 4 ta raqamda kiriting (masalan: 2001):")

    await state.update_data(birth_year=int(text))
    await state.set_state(VolunteerRegState.phone_number)
    await message.answer(
        "📱 <b>Telefon raqamingizni yuboring:</b>\n\n"
        "Quyidagi <b>«📱 Telefon raqamni yuborish»</b> tugmasini bosing yoki raqamingizni +998901234567 shaklida yozing:",
        reply_markup=get_phone_kb(),
        parse_mode=SULGUK_PARSE_MODE
    )


@volunteer_reg_router.message(VolunteerRegState.phone_number, is_private_message)
async def process_vol_phone_number(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    if message.text in CANCEL_WORDS:
        await state.clear()
        return await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=ReplyKeyboardRemove())

    phone = None
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = f"+{phone}"
    elif message.text:
        cleaned = re.sub(r"[^\d+]", "", message.text.strip())
        if len(cleaned) >= 9:
            phone = cleaned if cleaned.startswith("+") else f"+{cleaned}"

    if not phone:
        return await message.answer(
            "Iltimos, telefon raqamingizni to'g'ri shaklda yozing yoki pastdagi tugmani bosing:",
            reply_markup=get_phone_kb()
        )

    data = await state.get_data()
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    study_or_work = data.get("study_or_work", "")
    birth_year = data.get("birth_year", 2000)

    # Save or update Volunteer record
    existing = db_session.exec(select(Volunteer).where(Volunteer.user_id == message.from_user.id)).first()
    if existing:
        existing.first_name = first_name
        existing.last_name = last_name
        existing.study_or_work = study_or_work
        existing.birth_year = birth_year
        existing.phone_number = phone
        existing.is_active = True
        db_session.add(existing)
    else:
        new_vol = Volunteer(
            user_id=message.from_user.id,
            first_name=first_name,
            last_name=last_name,
            study_or_work=study_or_work,
            birth_year=birth_year,
            phone_number=phone,
            is_active=True
        )
        db_session.add(new_vol)

    db_session.commit()
    await state.clear()

    congrats_text = f"""
🎉 <b>Tabriklaymiz, {first_name}!</b>

Siz <b>«HuquqPlus»</b> loyihasida rasmiy <b>Volontyor</b> sifatida muvaffaqiyatli ro'yxatdan o'tdingiz!

━━━━━━━━━━━━━━━━━━━━━
👤 <b>F.I.Sh:</b> {first_name} {last_name}
🎓 <b>O'qish/ish:</b> {study_or_work}
📅 <b>Tug'ilgan yili:</b> {birth_year}
📱 <b>Tel:</b> {phone}
━━━━━━━━━━━━━━━━━━━━━

Endi guruhdagi fuqarolar murojaatlariga bemalol javob berishingiz mumkin.
Har yakshanba soat 16:00 da volontyorlar guruhida eng faol Top-5 talik e'lon qilib boriladi.

Beminnat yordamingiz va ezgu faoliyatingizda omad tilaymiz! 🤝
"""
    await message.answer(congrats_text, reply_markup=get_main_menu("uz"), parse_mode=SULGUK_PARSE_MODE)

    # Notify admins about new registered volunteer
    admin_notice = f"""
🆕 <b>Yangi volontyor ro'yxatdan o'tdi!</b>
━━━━━━━━━━━━━━━━━━━━━
👤 <b>F.I.Sh:</b> {first_name} {last_name}
🆔 <b>Telegram ID:</b> <code>{message.from_user.id}</code>
🎓 <b>O'qish/ish:</b> {study_or_work}
📅 <b>Tug'ilgan yili:</b> {birth_year}
📱 <b>Tel:</b> {phone}
━━━━━━━━━━━━━━━━━━━━━
"""
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_notice, parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass
