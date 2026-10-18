import re
import json
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE
from src.app.html_utils import nl2br

from src.app.filters import is_private_message
from src.app.keyboards import get_main_menu, get_volunteer_menu
from src.config.settings import settings
from src.database.redisdb import get_redis
from src.models.volunteer import Volunteer
from src.routes.deps.db_session import DBSession

volunteer_reg_router = Router(name="volunteer_reg")


class VolunteerRegState(StatesGroup):
    first_name = State()
    last_name = State()
    study_or_work = State()
    birth_year = State()
    phone_number = State()


CANCEL_WORDS = [
    "❌ Bekor qilish", "/cancel", "Bekor qilish", "bekor qilish",
    "❌ Бекор қилиш", "Бекор қилиш", "бекор қилиш", "❌ Отмена", "Отмена"
]


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
            f"✅ <b>Assalomu alaykum, {existing.first_name}!</b><br/><br/>"
            f"Siz allaqachon HuquqPlus loyihasida rasmiy volontyor sifatida ro'yxatdan o'tgansiz.<br/>"
            f"Guruhdagi fuqarolar murojaatlariga bemalol javob berishingiz mumkin! 🤝",
            reply_markup=get_volunteer_menu("uz"),
            parse_mode=SULGUK_PARSE_MODE
        )

    await state.set_state(VolunteerRegState.first_name)
    await message.answer(
        "👋 <b>Assalomu alaykum!</b><br/><br/>"
        "HuquqPlus loyihasining volontyori bo'lish istagini bildirganingiz uchun tashakkur!<br/>"
        "Rasmiy ro'yxatdan o'tish uchun quyidagi ma'lumotlarni qisqa to'ldiring:<br/><br/>"
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
        "🎓 <b>O'qish yoki ish joyingizni kiriting:</b><br/>"
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
        "📅 <b>Tug'ilgan yilingizni kiriting:</b><br/>"
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
        return await message.answer("Iltimos, to'g'ri yilni 4 ta raqamda kiriting (masalan: 2001):")

    await state.update_data(birth_year=int(text))
    await state.set_state(VolunteerRegState.phone_number)
    await message.answer(
        "📱 <b>Telefon raqamingizni yuboring:</b><br/><br/>"
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

    # Save or update Volunteer record (is_active = False until approved by admin)
    existing = db_session.exec(select(Volunteer).where(Volunteer.user_id == message.from_user.id)).first()
    if existing:
        existing.first_name = first_name
        existing.last_name = last_name
        existing.study_or_work = study_or_work
        existing.birth_year = birth_year
        existing.phone_number = phone
        existing.is_active = False
        db_session.add(existing)
        vol_obj = existing
    else:
        new_vol = Volunteer(
            user_id=message.from_user.id,
            first_name=first_name,
            last_name=last_name,
            study_or_work=study_or_work,
            birth_year=birth_year,
            phone_number=phone,
            is_active=False
        )
        db_session.add(new_vol)
        vol_obj = new_vol

    db_session.commit()
    db_session.refresh(vol_obj)
    await state.clear()

    pending_text = f"""
⏳ <b>Arizangiz qabul qilindi, {first_name}!</b><br/><br/>
Ma'lumotlaringiz muvaffaqiyatli saqlandi. Moderatorlarimiz arizangizni ko'rib chiqqandan so'ng, faoliyatingiz tasdiqlanadi va bot sizga xabar beradi.<br/><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
👤 <b>F.I.Sh:</b> {first_name} {last_name}<br/>
🎓 <b>O'qish/ish:</b> {study_or_work}<br/>
📅 <b>Tug'ilgan yili:</b> {birth_year}<br/>
📱 <b>Tel:</b> {phone}<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
<i>Iltimos, tasdiqlash xabarini kuting!</i>
"""
    await message.answer(pending_text, reply_markup=get_main_menu("uz"), parse_mode=SULGUK_PARSE_MODE)

    # Notify admins about new volunteer request with Approve/Reject buttons
    admin_notice = f"""
🆕 <b>Yangi volontyorlik arizasi kelib tushdi!</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
👤 <b>F.I.Sh:</b> {first_name} {last_name}<br/>
🆔 <b>Telegram ID:</b> <code>{message.from_user.id}</code><br/>
🎓 <b>O'qish/ish:</b> {study_or_work}<br/>
📅 <b>Tug'ilgan yili:</b> {birth_year}<br/>
📱 <b>Tel:</b> {phone}<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
<i>Ushbu nomzodni volontyor sifatida tasdiqlaysizmi?</i>
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"admin:vol_appr:{vol_obj.id}")
    builder.button(text="❌ Rad etish", callback_data=f"admin:vol_rejc:{vol_obj.id}")
    builder.adjust(2)

    redis_client = get_redis(is_async=True)
    admin_messages = []
    for admin_id in settings.admin_ids_list:
        try:
            sent_msg = await bot.send_message(
                chat_id=admin_id,
                text=admin_notice,
                reply_markup=builder.as_markup(),
                parse_mode=SULGUK_PARSE_MODE
            )
            admin_messages.append({"chat_id": admin_id, "message_id": sent_msg.message_id})
        except Exception:
            pass

    if admin_messages:
        try:
            await redis_client.set(
                f"vol_admin_msgs:{vol_obj.id}",
                json.dumps({"notice_text": admin_notice, "messages": admin_messages}),
                ex=86400 * 30
            )
        except Exception:
            pass


async def sync_admin_decision_messages(bot: Bot, redis_client, vol_id: int, acting_query: CallbackQuery, action_badge: str):
    """
    Updates the notification message for the acting admin and all other admins in real-time,
    removing action buttons to prevent conflicting or repeated decisions.
    """
    admin_msgs_raw = None
    try:
        admin_msgs_raw = await redis_client.get(f"vol_admin_msgs:{vol_id}")
    except Exception:
        pass

    if not admin_msgs_raw:
        try:
            orig = nl2br(acting_query.message.html_text or acting_query.message.text or "")
            await acting_query.message.edit_text(f"{orig}<br/><br/>{action_badge}", reply_markup=None, parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass
        return

    try:
        data = json.loads(admin_msgs_raw)
        notice_text = data.get("notice_text", "")
        messages = data.get("messages", [])

        for item in messages:
            chat_id = item["chat_id"]
            message_id = item["message_id"]
            try:
                if chat_id == acting_query.from_user.id:
                    orig = nl2br(acting_query.message.html_text or acting_query.message.text or notice_text)
                    await acting_query.message.edit_text(f"{orig}<br/><br/>{action_badge}", reply_markup=None, parse_mode=SULGUK_PARSE_MODE)
                else:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"{notice_text}<br/><br/>{action_badge}",
                        reply_markup=None,
                        parse_mode=SULGUK_PARSE_MODE
                    )
            except Exception:
                pass
    except Exception:
        pass


@volunteer_reg_router.callback_query(F.data.startswith("admin:vol_appr:"))
async def admin_approve_volunteer_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    vol_id = int(query.data.split(":")[2])
    admin_name = f"{query.from_user.first_name} {query.from_user.last_name or ''}".strip()
    redis_client = get_redis(is_async=True)
    status_key = f"vol_decision:{vol_id}"

    # Atomic lock / decision registration
    is_first = False
    try:
        is_first = await redis_client.set(
            status_key,
            json.dumps({"action": "approved", "admin_name": admin_name, "admin_id": query.from_user.id}),
            nx=True,
            ex=86400 * 30
        )
    except Exception:
        # Fallback to DB check if Redis lock fails
        vol_check = db_session.get(Volunteer, vol_id)
        if vol_check and vol_check.is_active:
            is_first = False
        else:
            is_first = True

    if not is_first:
        msg = "⚠️ Ushbu ariza allaqachon ko'rib chiqilgan!"
        try:
            existing_raw = await redis_client.get(status_key)
            if existing_raw:
                dec = json.loads(existing_raw)
                act_str = "tasdiqlagan" if dec.get("action") == "approved" else "rad etgan"
                msg = f"⚠️ Ushbu ariza allaqachon {dec.get('admin_name', 'boshqa admin')} tomonidan {act_str}!"
        except Exception:
            pass

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return await query.answer(msg, show_alert=True)

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Ariza topilmadi!", show_alert=True)

    vol.is_active = True
    db_session.add(vol)
    db_session.commit()

    await query.answer("Volontyor muvaffaqiyatli tasdiqlandi!", show_alert=False)

    action_badge = f"<b>✅ TASDIQLANDI:</b> <a href=\"tg://user?id={query.from_user.id}\">{admin_name}</a> tomonidan."
    await sync_admin_decision_messages(bot, redis_client, vol_id, query, action_badge)

    # Notify volunteer about approval
    user_msg = f"""
🎉 <b>Tabriklaymiz, {vol.first_name}!</b><br/><br/>
Sizning volontyorlik arizangiz administrator tomonidan <b>tasdiqlandi</b>!<br/>
Endi siz HuquqPlus loyihasining rasmiy volontyori sifatida guruhdagi fuqarolar murojaatlariga bemalol javob berishingiz mumkin. 🤝<br/><br/>
Ezgu faoliyatingizda muvaffaqiyat tilaymiz!
"""
    try:
        await bot.send_message(chat_id=vol.user_id, text=user_msg, reply_markup=get_volunteer_menu("uz"), parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass


@volunteer_reg_router.callback_query(F.data.startswith("admin:vol_rejc:"))
async def admin_reject_volunteer_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    vol_id = int(query.data.split(":")[2])
    admin_name = f"{query.from_user.first_name} {query.from_user.last_name or ''}".strip()
    redis_client = get_redis(is_async=True)
    status_key = f"vol_decision:{vol_id}"

    # Atomic lock / decision registration
    is_first = False
    try:
        is_first = await redis_client.set(
            status_key,
            json.dumps({"action": "rejected", "admin_name": admin_name, "admin_id": query.from_user.id}),
            nx=True,
            ex=86400 * 30
        )
    except Exception:
        vol_check = db_session.get(Volunteer, vol_id)
        if vol_check and not vol_check.is_active:
            is_first = False
        else:
            is_first = True

    if not is_first:
        msg = "⚠️ Ushbu ariza allaqachon ko'rib chiqilgan!"
        try:
            existing_raw = await redis_client.get(status_key)
            if existing_raw:
                dec = json.loads(existing_raw)
                act_str = "tasdiqlagan" if dec.get("action") == "approved" else "rad etgan"
                msg = f"⚠️ Ushbu ariza allaqachon {dec.get('admin_name', 'boshqa admin')} tomonidan {act_str}!"
        except Exception:
            pass

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return await query.answer(msg, show_alert=True)

    vol = db_session.get(Volunteer, vol_id)
    if not vol:
        return await query.answer("Ariza topilmadi!", show_alert=True)

    vol.is_active = False
    db_session.add(vol)
    db_session.commit()

    await query.answer("Volontyor arizasi rad etildi.", show_alert=False)

    action_badge = f"<b>❌ RAD ETILDI:</b> <a href=\"tg://user?id={query.from_user.id}\">{admin_name}</a> tomonidan."
    await sync_admin_decision_messages(bot, redis_client, vol_id, query, action_badge)

    # Notify volunteer
    user_msg = f"""
Hurmatli <b>{vol.first_name}</b>!<br/><br/>
Afsuski, sizning volontyorlik arizangiz administratorlar tomonidan <b>rad etildi</b>.<br/>
HuquqPlus loyihasiga qiziqish bildirganingiz uchun tashakkur!
"""
    try:
        await bot.send_message(chat_id=vol.user_id, text=user_msg, reply_markup=get_main_menu("uz"), parse_mode=SULGUK_PARSE_MODE)
    except Exception:
        pass
