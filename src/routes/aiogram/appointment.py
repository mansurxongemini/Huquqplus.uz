import json
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LinkPreviewOptions,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE

from src.app.calendar_utils import get_available_dates, get_time_slots_for_date, format_uz_date
from src.app.enums import create_user_info
from src.app.keyboards import get_main_menu
from src.app.translations import t, get_appointment_text, LANG_UZ
from src.config.settings import settings
from sqlmodel import select
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.routes.deps.db_session import DBSession

appointment_router = Router(name="appointment")


class AppointmentState(StatesGroup):
    choosing_appointment_type = State()
    choosing_lawyer = State()
    choosing_date = State()
    choosing_time_slot = State()
    entering_problem_and_media = State()
    confirming_booking = State()


class AppointmentFeedbackState(StatesGroup):
    waiting_for_feedback = State()


# --- Step 1: Start Appointment & Choose Type ---


@appointment_router.message(
    F.text.in_([t("menu_appointment", "uz"), t("menu_appointment", "ru"), "✍️ Yurist qabuliga yozilish", "✍️ Запись к юристу"])
)
async def start_appointment(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        return await message.answer(t("user_not_found", lang), reply_markup=get_main_menu(lang))

    if user.is_blocked:
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    await state.clear()
    await state.set_state(AppointmentState.choosing_appointment_type)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("appointment_remote_btn", lang), callback_data="remote_appointment")],
            [InlineKeyboardButton(text=t("appointment_in_person_btn", lang), callback_data="in_person_appointment")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="app_cancel")]
        ]
    )
    await message.answer(
        get_appointment_text(lang),
        reply_markup=kb,
        disable_web_page_preview=True,
        parse_mode=SULGUK_PARSE_MODE,
    )


# --- Step 2: Choose Lawyer (or directly Date if in-person) ---


@appointment_router.callback_query(
    AppointmentState.choosing_appointment_type,
    F.data.in_(["remote_appointment", "in_person_appointment", "app_cancel"])
)
async def process_appointment_type(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if query.data == "app_cancel":
        await state.clear()
        user = User.get_by_user_id(query.from_user.id, db_session)
        lang = user.language if user else LANG_UZ
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    app_type = query.data

    # Check if user already has an active appointment of this type
    active_app = db_session.exec(
        select(Appointment).where(
            Appointment.user_id == user.user_id,
            Appointment.appointment_type == app_type,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
        )
    ).first()

    if active_app:
        await state.clear()
        app_name = "📞 Masofaviy qabul (Online)" if app_type == "remote_appointment" else "🏢 Yuzma-yuz qabul (Bosh ofis)"
        app_time = format_uz_date(active_app.scheduled_at) if active_app.scheduled_at else "Belgilanmagan"
        status_name = "⏳ Ko'rib chiqilmoqda" if active_app.status == AppointmentStatus.pending else "✅ Qabul qilingan"
        if lang == "ru":
            status_name = "⏳ На рассмотрении" if active_app.status == AppointmentStatus.pending else "✅ Принято"
        lawyer_display = "Istalgan bo'sh yurist"
        if active_app.lawyer_id:
            lawyer_obj = db_session.get(OfficialLawyer, active_app.lawyer_id)
            if not lawyer_obj:
                lawyer_obj = OfficialLawyer.get_by_user_id(active_app.lawyer_id, db_session)
            if lawyer_obj:
                lawyer_display = lawyer_obj.full_name
        if app_type == "in_person_appointment":
            lawyer_display = "Bosh ofis navbatchi yuristlari"

        warning_card = (
            f"⚠️ <b>Sizda ushbu yo'nalish bo'yicha faol ariza mavjud!</b><br/><br/>"
            f"📋 <b>Ariza raqami:</b> №{active_app.id}<br/>"
            f"🏢 <b>Qabul shakli:</b> {app_name}<br/>"
            f"📅 <b>Belgilangan vaqt:</b> <b>{app_time}</b><br/>"
            f"👨‍⚖️ <b>Yurist:</b> {lawyer_display}<br/>"
            f"🔄 <b>Holati:</b> {status_name}<br/><br/>"
            f"ℹ️ <i>Bir vaqtning o'zida har bir yo'nalish bo'yicha faqat 1 dona faol ariza bo'lishi mumkin. "
            f"Yangi ariza topshirish uchun avvalgi qabul yakunlanishi yoki bekor qilinishi lozim.</i>"
            if lang == "uz" else
            f"⚠️ <b>У вас уже есть активная запись по этому направлению!</b><br/><br/>"
            f"📋 <b>Номер заявки:</b> №{active_app.id}<br/>"
            f"🏢 <b>Формат приема:</b> {app_name}<br/>"
            f"📅 <b>Время приема:</b> <b>{app_time}</b><br/>"
            f"👨‍⚖️ <b>Юрист:</b> {lawyer_display}<br/>"
            f"🔄 <b>Статус:</b> {status_name}<br/><br/>"
            f"ℹ️ <i>Одновременно разрешена только одна активная запись по каждому направлению. "
            f"Для новой записи дождитесь завершения или отмените текущую.</i>"
        )

        builder = InlineKeyboardBuilder()
        builder.button(
            text="❌ Qabulni bekor qilish" if lang == "uz" else "❌ Отменить прием",
            callback_data=f"app_user_cancel_prompt:{active_app.id}"
        )
        builder.button(
            text="⬅️ Asosiy menyu" if lang == "uz" else "⬅️ Главное меню",
            callback_data="app_cancel"
        )
        builder.adjust(1)

        await query.message.edit_text(warning_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        return await query.answer()

    await state.update_data(appointment_type=app_type)

    if app_type == "in_person_appointment":
        # In person is on Saturdays at central office with on-duty team
        await state.update_data(lawyer_id=None, lawyer_name="Bosh ofis navbatchi yuristlari")
        await state.set_state(AppointmentState.choosing_date)

        dates = get_available_dates(app_type)
        builder = InlineKeyboardBuilder()
        for d in dates:
            builder.button(text=d["label"], callback_data=f"app_date:{d['date_str']}")
        builder.button(text=t("btn_cancel", lang), callback_data="app_cancel")
        builder.adjust(1)

        prompt_text = (
            "🏢 <b>Yuzma-yuz qabul uchun shanba kunlaridan birini tanlang:</b><br/>"
            "<i>(Qabul har shanba 10:00 dan 16:00 gacha Toshkent sh., Yunusobod tumani, Xiyobon ko'chasi 22-uyda o'tkaziladi)</i>"
            if lang == "uz"
            else "🏢 <b>Выберите субботу для очного приема:</b>"
        )
        await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        return await query.answer()

    # Remote appointment: Offer lawyer choice or any available
    await state.set_state(AppointmentState.choosing_lawyer)
    active_lawyers = OfficialLawyer.get_active_lawyers(db_session)

    builder = InlineKeyboardBuilder()
    builder.button(
        text="⭐️ Istalgan bo'sh yurist (Tezroq qabul)" if lang == "uz" else "⭐️ Любой свободный юрист",
        callback_data="app_lawyer:any"
    )

    for lawyer in active_lawyers:
        spec_text = f" ({lawyer.specialization})" if lawyer.specialization else ""
        builder.button(
            text=f"👨‍⚖️ {lawyer.full_name}{spec_text}",
            callback_data=f"app_lawyer:{lawyer.id}"
        )

    builder.button(text=t("btn_cancel", lang), callback_data="app_cancel")
    builder.adjust(1)

    prompt_text = (
        "👨‍⚖️ <b>O'zingizga ma'qul yuristni tanlang yoki istalgan bo'sh yuristga yoziling:</b>"
        if lang == "uz"
        else "👨‍⚖️ <b>Выберите юриста или запишитесь к любому свободному специалисту:</b>"
    )

    await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# --- Step 3: Choose Date from Smart Calendar ---


@appointment_router.callback_query(AppointmentState.choosing_lawyer, F.data.startswith("app_lawyer:"))
async def process_lawyer_choice(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    lawyer_arg = query.data.split(":")[1]
    if lawyer_arg == "any":
        lawyer_id = None
        lawyer_name = "Istalgan bo'sh yurist" if lang == "uz" else "Любой свободный юрист"
    else:
        lawyer_id = int(lawyer_arg)
        lawyer = db_session.get(OfficialLawyer, lawyer_id)
        lawyer_name = lawyer.full_name if lawyer else "Yurist"

    await state.update_data(lawyer_id=lawyer_id, lawyer_name=lawyer_name)
    await state.set_state(AppointmentState.choosing_date)

    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")

    dates = get_available_dates(app_type)
    builder = InlineKeyboardBuilder()
    for d in dates:
        builder.button(text=d["label"], callback_data=f"app_date:{d['date_str']}")
    builder.button(text=t("btn_cancel", lang), callback_data="app_cancel")
    builder.adjust(1)

    prompt_text = (
        f"👨‍⚖️ Yurist: <b>{lawyer_name}</b><br/><br/>"
        "📅 <b>Online konsultatsiya uchun qulay sanani tanlang:</b>"
        if lang == "uz"
        else f"👨‍⚖️ Юрист: <b>{lawyer_name}</b><br/><br/>📅 <b>Выберите удобную дату:</b>"
    )

    await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# --- Step 4: Choose Time Slot ---


@appointment_router.callback_query(AppointmentState.choosing_date, F.data.startswith("app_date:"))
@appointment_router.callback_query(AppointmentState.choosing_time_slot, F.data == "app_back_to_dates")
async def process_date_choice(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")
    lawyer_id = data.get("lawyer_id")

    if query.data == "app_back_to_dates":
        # Go back to date selection
        await state.set_state(AppointmentState.choosing_date)
        dates = get_available_dates(app_type)
        builder = InlineKeyboardBuilder()
        for d in dates:
            builder.button(text=d["label"], callback_data=f"app_date:{d['date_str']}")
        builder.button(text=t("btn_cancel", lang), callback_data="app_cancel")
        builder.adjust(1)
        await query.message.edit_text("📅 <b>Qayta sanani tanlang:</b>", reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        return await query.answer()

    date_str = query.data.split(":")[1]
    await state.update_data(selected_date=date_str)
    await state.set_state(AppointmentState.choosing_time_slot)

    slots = get_time_slots_for_date(date_str, lawyer_id, app_type, db_session)

    builder = InlineKeyboardBuilder()
    for s in slots:
        if s["is_available"]:
            builder.button(text=f"🟢 {s['label']}", callback_data=f"app_slot:{s['time_str']}")
        else:
            builder.button(text=f"🔴 {s['time_str']} (Band)", callback_data="app_slot_busy")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Boshqa sana tanlash", callback_data="app_back_to_dates"))
    builder.row(InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="app_cancel"))

    target_dt = datetime.strptime(date_str, "%Y-%m-%d")
    date_display = format_uz_date(target_dt).split(",")[0]

    prompt_text = (
        f"📅 Tanlangan sana: <b>{date_display}</b><br/><br/>"
        "⏰ <b>O'zingizga qulay bo'sh vaqt oralig'ini tanlang:</b><br/>"
        "<i>(Yashil rangdagi vaqtlar bo'sh)</i>"
        if lang == "uz"
        else f"📅 Выбранная дата: <b>{date_display}</b><br/><br/>⏰ <b>Выберите свободное время:</b>"
    )

    await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@appointment_router.callback_query(F.data == "app_slot_busy")
async def slot_busy_callback(query: CallbackQuery):
    await query.answer("⚠️ Ushbu vaqt oralig'i band qilingan. Iltimos, yashil rangdagi bo'sh vaqtlardan birini tanlang.", show_alert=True)


# --- Step 5: Enter Problem & Attach Multimodal Media (Audio, Video, PDF, Photo) ---


@appointment_router.callback_query(AppointmentState.choosing_time_slot, F.data.startswith("app_slot:"))
async def process_slot_choice(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    slot_time = query.data.split(":", 1)[1]
    data = await state.get_data()
    date_str = data.get("selected_date")

    scheduled_at_str = f"{date_str} {slot_time}"
    await state.update_data(slot_time=slot_time, scheduled_at_str=scheduled_at_str)
    await state.set_state(AppointmentState.entering_problem_and_media)

    action_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📤 Yuborish" if lang == "uz" else "📤 Отправить"),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )

    prompt = (
        f"✅ Vaqt tanlandi: <b>{scheduled_at_str}</b><br/><br/>"
        "📌 <b>Endi muammoingizni bayon qiling va zarur hujjatlarni ilova qiling:</b><br/><br/>"
        "Siz quyidagi formatlarda ma'lumot yuborishingiz mumkin:<br/>"
        "• ✍️ <b>Matn</b> shaklida muammo tavsifi<br/>"
        "• 🎤 <b>Ovozli xabar (Audio)</b> orqali<br/>"
        "• 📹 <b>Video</b> yoki video-xabar (krujok) orqali<br/>"
        "• 📄 <b>PDF yoki Word hujjat</b> (sud hujjati, ariza, tibbiy ma'lumotnoma)<br/>"
        "• 📷 <b>Hujjatning fotosurati</b><br/><br/>"
        "ℹ️ <i>Bir nechta xabar yoki fayllar yuborishingiz mumkin. Kerakli ma'lumotlarni tashlab bo'lgach, pastdagi <b>📤 Yuborish</b> tugmasini bosing.</i>"
        if lang == "uz"
        else (
            f"✅ Время выбрано: <b>{scheduled_at_str}</b><br/><br/>"
            "📌 <b>Опишите вашу проблему и прикрепите необходимые документы:</b><br/><br/>"
            "Вы можете отправить:<br/>"
            "• ✍️ Текстовое описание<br/>"
            "• 🎤 Голосовое сообщение<br/>"
            "• 📹 Видео или видеосообщение<br/>"
            "• 📄 PDF / Word документ<br/>"
            "• 📷 Фото документа<br/><br/>"
            "ℹ️ <i>Вы можете отправить несколько сообщений или файлов. После отправки нажмите <b>📤 Отправить</b> внизу.</i>"
        )
    )

    await query.message.delete()
    await query.message.answer(prompt, reply_markup=action_kb, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


# --- Step 6: Capture Problem Description / Media and Show Confirmation Card ---


def parse_scheduled_datetime(dt_str: str) -> datetime:
    if not dt_str:
        return datetime.now(tz)
    dt_str = str(dt_str).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    return datetime.now(tz)


import html


async def render_confirmation_card(target_message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")
    app_type_name = "📞 Masofaviy qabul (Online suhbat)" if app_type == "remote_appointment" else "🏢 Yuzma-yuz qabul (Bosh ofisda)"
    lawyer_name = data.get("lawyer_name", "Istalgan bo'sh yurist")
    scheduled_at_str = data.get("scheduled_at_str", "")
    problem_text = data.get("problem_description", "")

    media_items = list(data.get("media_items", []))
    if not media_items and data.get("media_file_id"):
        media_items = [{
            "type": data.get("media_type", "document"),
            "file_id": data.get("media_file_id"),
            "name": data.get("media_name", "Fayl"),
            "caption": ""
        }]

    scheduled_dt = parse_scheduled_datetime(scheduled_at_str)
    formatted_time = format_uz_date(scheduled_dt)

    if not media_items:
        media_display = "Faqat matn"
    elif len(media_items) == 1:
        media_display = f"📄 {media_items[0]['name']}"
    else:
        names_str = ", ".join([item['name'] for item in media_items])
        media_display = f"📎 {len(media_items)} ta fayl ({names_str})"

    desc_display = problem_text.strip() if problem_text and problem_text.strip() else "(Muammo audio/video/fayl orqali bayon etilgan)"
    desc_escaped = html.escape(desc_display[:350])

    preview_card = f"""
📋 <b>QABUL MA'LUMOTLARINI TASDIQLANG:</b><br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
🏢 <b>Qabul shakli:</b> {app_type_name}<br/>
👨‍⚖️ <b>Yurist:</b> {lawyer_name}<br/>
📅 <b>Sana va vaqt:</b> <b>{formatted_time}</b><br/>
📎 <b>Biriktirilgan fayllar:</b> {media_display}<br/><br/>
📝 <b>Muammo mazmuni:</b><br/>
<blockquote>{desc_escaped}</blockquote>
━━━━━━━━━━━━━━━━━━━━━<br/>
<i>Barcha ma'lumotlar to'g'rimi? Qabulni tasdiqlaysizmi?</i>
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabulni tasdiqlash", callback_data="app_confirm:yes")
    builder.button(text="❌ Bekor qilish", callback_data="app_cancel")
    builder.adjust(1)

    confirm_reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Qabulni tasdiqlash" if lang == "uz" else "✅ Подтвердить прием"),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )

    await target_message.answer(preview_card, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await target_message.answer(
        "Qabulni tasdiqlash uchun <b>✅ Qabulni tasdiqlash</b> tugmasini bosing:" if lang == "uz" else "Для подтверждения нажмите <b>✅ Подтвердить прием</b>:",
        reply_markup=confirm_reply_kb,
        parse_mode=SULGUK_PARSE_MODE
    )


@appointment_router.message(
    AppointmentState.entering_problem_and_media,
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Отмена"]),
)
async def cancel_at_media_step(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))


@appointment_router.message(AppointmentState.entering_problem_and_media)
async def handle_appointment_media_input(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        await state.clear()
        return await message.answer(t("user_not_found", lang), reply_markup=get_main_menu(lang))

    if user.is_blocked:
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    # Check if user pressed "📤 Yuborish" / "📩 Yuborish"
    is_submit = (
        message.text in [
            "📤 Yuborish", "📤 Отправить",
            "📩 Yuborish", "📩 Отправить",
            "✅ Yuborish", "✅ Отправить",
            "Yuborish", "Отправить",
            "✅ Qabulni tasdiqlash", "✅ Подтвердить прием"
        ]
        or (message.text and any(w in message.text.strip().lower() for w in ["yuborish", "отправить"]))
    )
    if is_submit:
        data = await state.get_data()
        if not data.get("problem_description") and not data.get("media_items") and not data.get("media_file_id"):
            warning_text = (
                "⚠️ <b>Iltimos, avval muammoingizni yozing yoki kerakli fayl/audio yuboring!</b><br/><br/>"
                "So'ng pastdagi <b>📩 Yuborish</b> tugmasini bosing."
                if lang == "uz" else
                "⚠️ <b>Пожалуйста, сначала опишите проблему или отправьте файл!</b><br/><br/>"
                "Затем нажмите <b>📩 Отправить</b> внизу."
            )
            return await message.answer(warning_text, parse_mode=SULGUK_PARSE_MODE)

        await state.set_state(AppointmentState.confirming_booking)
        return await render_confirmation_card(message, state, lang)

    # User sent text or media - accumulate into state
    data = await state.get_data()
    current_desc = data.get("problem_description", "")
    media_items = list(data.get("media_items", []))

    if message.text:
        current_desc = f"{current_desc}\n{message.text}".strip() if current_desc else message.text
    elif message.voice:
        caption = message.caption or "🎤 Ovozli xabar"
        media_items.append({
            "type": "voice",
            "file_id": message.voice.file_id,
            "name": "Ovozli xabar",
            "caption": caption
        })
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip() if current_desc else message.caption
    elif message.video_note:
        media_items.append({
            "type": "video_note",
            "file_id": message.video_note.file_id,
            "name": "Video xabar (krujok)",
            "caption": "📹 Video xabar (krujok)"
        })
    elif message.video:
        caption = message.caption or "📹 Video murojaat"
        media_items.append({
            "type": "video",
            "file_id": message.video.file_id,
            "name": "Video fayl",
            "caption": caption
        })
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip() if current_desc else message.caption
    elif message.document:
        doc_name = message.document.file_name or "Hujjat.pdf"
        caption = message.caption or f"📄 {doc_name}"
        media_items.append({
            "type": "document",
            "file_id": message.document.file_id,
            "name": doc_name,
            "caption": caption
        })
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip() if current_desc else message.caption
    elif message.photo:
        caption = message.caption or "📷 Fotohujjat"
        media_items.append({
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "name": "Fotohujjat",
            "caption": caption
        })
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip() if current_desc else message.caption
    else:
        return await message.answer("⚠️ Iltimos, matn, ovozli xabar, video, PDF hujjat yoki rasm yuboring.")

    latest_media = media_items[-1] if media_items else None
    await state.update_data(
        media_items=media_items,
        media_type=latest_media["type"] if latest_media else "text",
        media_file_id=latest_media["file_id"] if latest_media else None,
        media_name=latest_media["name"] if latest_media else None,
        problem_description=current_desc
    )

    action_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📩 Yuborish" if lang == "uz" else "📩 Отправить"),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )

    items_count = len(media_items)
    items_info = ""
    if items_count > 0:
        names_list = ", ".join([it["name"] for it in media_items])
        items_info = f"<br/>📎 <b>Qabul qilingan fayllar ({items_count} ta):</b> <i>{names_list}</i>"

    ack_prompt = (
        f"📥 <b>Ma'lumot qabul qilindi!</b>{items_info}<br/><br/>"
        "• Agar yana qo'shimcha ma'lumot yoki fayllar bo'lsa, yuborishingiz mumkin.<br/>"
        "• Barcha ma'lumotlarni tashlab bo'lgach, pastdagi <b>📩 Yuborish</b> tugmasini bosing."
        if lang == "uz" else
        f"📥 <b>Информация принята!</b>{items_info}<br/><br/>"
        "• Вы можете отправить еще текст или файлы.<br/>"
        "• Когда все будет готово, нажмите кнопку <b>📩 Отправить</b> внизу."
    )
    await message.answer(ack_prompt, reply_markup=action_kb, parse_mode=SULGUK_PARSE_MODE)


# --- Step 7: Confirm Booking & Dispatch to Lawyer Group ---


async def execute_appointment_submission(user: User, lang: str, state: FSMContext, db_session: DBSession, bot: Bot, message_target: Message, is_callback: bool = False, query: CallbackQuery | None = None):
    data = await state.get_data()
    app_type = data.get("appointment_type", "remote_appointment")
    lawyer_id = data.get("lawyer_id")
    lawyer_name = data.get("lawyer_name", "Istalgan bo'sh yurist")
    scheduled_at_str = data.get("scheduled_at_str")
    problem_description = data.get("problem_description", "")

    media_items = list(data.get("media_items", []))
    if not media_items and data.get("media_file_id"):
        media_items = [{
            "type": data.get("media_type", "document"),
            "file_id": data.get("media_file_id"),
            "name": data.get("media_name", "Fayl"),
            "caption": ""
        }]

    scheduled_dt = parse_scheduled_datetime(scheduled_at_str)

    # Double-check slot availability to prevent double-booking
    if lawyer_id:
        taken = db_session.exec(
            Appointment.__table__.select().where(
                Appointment.lawyer_id == lawyer_id,
                Appointment.scheduled_at == scheduled_dt,
                Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
            )
        ).first()
        if taken:
            msg = "⚠️ Kechirasiz, ushbu vaqt hozirgina boshqa fuqaro tomonidan band qilindi. Iltimos boshqa vaqt tanlang."
            if is_callback and query:
                await query.answer(msg, show_alert=True)
            else:
                await message_target.answer(msg)
            return

    # Guard against duplicate active appointment of same type
    existing_active = db_session.exec(
        select(Appointment).where(
            Appointment.user_id == user.user_id,
            Appointment.appointment_type == app_type,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
        )
    ).first()
    if existing_active:
        msg = (
            f"⚠️ Sizda ushbu yo'nalish bo'yicha allaqachon faol ariza (№{existing_active.id}) mavjud!"
            if lang == "uz" else
            f"⚠️ У вас уже есть активная запись по этому направлению (№{existing_active.id})!"
        )
        await state.clear()
        if is_callback and query:
            await query.answer(msg, show_alert=True)
        else:
            await message_target.answer(msg, reply_markup=get_main_menu(lang))
        return

    # Create Appointment record
    initial_status = AppointmentStatus.accepted if lawyer_id else AppointmentStatus.pending
    latest_media = media_items[-1] if media_items else None
    primary_type = latest_media["type"] if latest_media else "text"
    primary_fid = latest_media["file_id"] if latest_media else None
    primary_name = latest_media["name"] if latest_media else None
    media_meta_json = json.dumps(media_items, ensure_ascii=False) if media_items else None

    desc_cleaned = problem_description.strip() if problem_description and problem_description.strip() else "(Muammo audio/video/fayl orqali bayon etilgan)"

    app = Appointment(
        user_id=user.user_id,
        appointment_type=app_type,
        problem_description=desc_cleaned,
        lawyer_id=lawyer_id,
        scheduled_at=scheduled_dt,
        media_type=primary_type,
        media_file_id=primary_fid,
        media_name=primary_name,
        media_meta=media_meta_json,
        status=initial_status,
        reminder_sent=False
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    user_context = create_user_info(user, with_link=True, lang=lang)
    formatted_time = format_uz_date(scheduled_dt)
    app_type_text = "Masofaviy qabul (Online)" if app_type == "remote_appointment" else "Yuzma-yuz qabul (Bosh ofis)"

    media_count = len(media_items)
    if media_count == 0:
        media_summary = "<i>Faqat matn</i>"
    elif media_count == 1:
        media_summary = f"<b>{media_items[0]['name']}</b>"
    else:
        names_str = ", ".join([item['name'] for item in media_items])
        media_summary = f"<b>{media_count} ta fayl</b> ({names_str})"

    group_caption = (
        f"📅 <b>YURIST QABULIGA YANGI ARIZA! (№{app.id})</b><br/>"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"👤 <b>FUQARO MA'LUMOTLARI:</b><br/>"
        f"{user_context}<br/>"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"🏢 <b>QABUL MA'LUMOTLARI:</b><br/>"
        f"• <b>Qabul shakli:</b> {app_type_text}<br/>"
        f"• <b>Belgilangan vaqt:</b> <b>{formatted_time}</b><br/>"
        f"• <b>Biriktirilgan yurist:</b> {lawyer_name}<br/>"
        f"• 📎 <b>Biriktirilgan fayllar:</b> {media_summary}<br/>"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"📝 <b>MUAMMO MAZMUNI:</b><br/>"
        f"<blockquote>{html.escape(desc_cleaned)}</blockquote>"
    )

    group_builder = InlineKeyboardBuilder()
    if not lawyer_id:
        group_builder.button(text="📌 Qabulni olish", callback_data=f"appointment:claim:{app.id}")
    else:
        group_builder.button(text="✅ Suhbat yakunlandi", callback_data=f"appointment:complete:{app.id}")
    group_builder.button(text="🚫 Bloklash", callback_data=f"block_user:{user.user_id}")
    group_builder.adjust(1)

    group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
    group_msg = None

    try:
        group_msg = await bot.send_message(
            chat_id=group_id,
            text=group_caption,
            reply_markup=group_builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        print("Failed to dispatch appointment to lawyer group:", e)

    if group_msg:
        app.group_message_id = group_msg.message_id
        db_session.add(app)
        db_session.commit()

        # Send all attached media items (voice, video, note, doc, photo) as threaded replies to group_msg
        for idx, item in enumerate(media_items, 1):
            m_type = item.get("type")
            m_fid = item.get("file_id")
            m_name = item.get("name", "Fayl")
            caption_note = f"📎 Ariza №{app.id} ilovasi ({idx}/{media_count}): {m_name}"
            try:
                if m_type == "voice":
                    await bot.send_voice(
                        chat_id=group_id,
                        voice=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "video_note":
                    await bot.send_video_note(
                        chat_id=group_id,
                        video_note=m_fid,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "video":
                    await bot.send_video(
                        chat_id=group_id,
                        video=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "document":
                    await bot.send_document(
                        chat_id=group_id,
                        document=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
                elif m_type == "photo":
                    await bot.send_photo(
                        chat_id=group_id,
                        photo=m_fid,
                        caption=caption_note,
                        reply_to_message_id=group_msg.message_id
                    )
            except Exception as me:
                print(f"Failed to send attached media {idx} ({m_type}) to lawyer group:", me)

    # Notify specific lawyer in private chat if pre-selected
    if lawyer_id:
        try:
            lawyer_private_text = (
                f"🔔 <b>Hurmatli yurist! Sizga yangi qabul belgilandi (Ariza №{app.id}):</b><br/><br/>"
                f"👤 Fuqaro: <b>{user.first_name} {user.last_name or ''}</b><br/>"
                f"📞 Tel: {user.phone or 'noma lum'}<br/>"
                f"📅 Belgilangan vaqt: <b>{formatted_time}</b><br/>"
                f"📝 Muammo: <i>{problem_description}</i>"
            )
            await bot.send_message(chat_id=lawyer_id, text=lawyer_private_text, parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass

    await state.clear()

    if is_callback and query:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.answer()

    success_msg = (
        f"✅ <b>Qabul muvaffaqiyatli band qilindi! (Ariza №{app.id})</b><br/><br/>"
        f"📅 <b>Sana va vaqt:</b> {formatted_time}<br/>"
        f"👨‍⚖️ <b>Yurist:</b> {lawyer_name}<br/>"
        f"🏢 <b>Qabul shakli:</b> {app_type_text}<br/><br/>"
        "⏰ <i>Suhbat boshlanishiga 1 soat qolganda bot sizga eslatma yuboradi. Iltimos, belgilangan vaqtda aloqada bo'ling!</i>"
        if lang == "uz"
        else (
            f"✅ <b>Запись успешно оформлена! (Заявка №{app.id})</b><br/><br/>"
            f"📅 <b>Дата и время:</b> {formatted_time}<br/>"
            f"👨‍⚖️ <b>Юрист:</b> {lawyer_name}<br/><br/>"
            "⏰ <i>За 1 час до консультации вам придет напоминание.</i>"
        )
    )

    await message_target.answer(success_msg, reply_markup=get_main_menu(lang), parse_mode=SULGUK_PARSE_MODE)


@appointment_router.callback_query(AppointmentState.confirming_booking, F.data == "app_confirm:yes")
async def confirm_booking_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await execute_appointment_submission(user, lang, state, db_session, bot, message_target=query.message, is_callback=True, query=query)


@appointment_router.message(
    AppointmentState.confirming_booking,
    F.text.in_(["✅ Qabulni tasdiqlash", "✅ Подтвердить прием", "✅ Tasdiqlash", "📤 Yuborish", "📤 Отправить", "✅ Ha", "✅ Да"])
)
async def confirm_booking_text_message(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await execute_appointment_submission(user, lang, state, db_session, bot, message_target=message, is_callback=False)


@appointment_router.message(
    AppointmentState.confirming_booking,
    F.text.in_([t("btn_cancel", "uz"), t("btn_cancel", "ru"), "❌ Bekor qilish", "❌ Отмена"])
)
async def cancel_booking_text_message(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    await message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))


@appointment_router.message(AppointmentState.confirming_booking)
async def extra_media_in_confirming(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    data = await state.get_data()
    current_desc = data.get("problem_description", "")

    if message.text:
        current_desc = f"{current_desc}\n{message.text}".strip()
    elif message.voice:
        await state.update_data(media_type="voice", media_file_id=message.voice.file_id, media_name="Ovozli xabar")
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip()
    elif message.document:
        await state.update_data(media_type="document", media_file_id=message.document.file_id, media_name=message.document.file_name or "Hujjat.pdf")
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip()
    elif message.photo:
        await state.update_data(media_type="photo", media_file_id=message.photo[-1].file_id, media_name="Fotohujjat")
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip()
    elif message.video:
        await state.update_data(media_type="video", media_file_id=message.video.file_id, media_name="Video fayl")
        if message.caption:
            current_desc = f"{current_desc}\n{message.caption}".strip()

    await state.update_data(problem_description=current_desc)
    await render_confirmation_card(message, state, lang)


@appointment_router.callback_query(F.data == "app_cancel", StateFilter("*"))
async def cancel_appointment_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    await state.clear()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))
    try:
        await query.answer()
    except Exception:
        pass


# --- Appointment Rating Handlers ---


@appointment_router.callback_query(F.data.startswith("rate:appointment:"))
async def handle_appointment_rating(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    parts = query.data.split(":")
    app_id = int(parts[2])
    stars = int(parts[3])

    app = Appointment.get_by_id(app_id, db_session)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if app:
        app.rating = stars
        app.rated_at = datetime.now()
        db_session.add(app)
        db_session.commit()

    await query.answer(f"Bahoyingiz: {stars} ⭐", show_alert=False)

    text = f"{t('rate_received_thanks', lang)}<br/><br/>{t('rate_leave_feedback', lang)}"
    await query.message.edit_text(text, parse_mode=SULGUK_PARSE_MODE)

    await state.set_state(AppointmentFeedbackState.waiting_for_feedback)
    await state.update_data(rating_appointment_id=app_id)


@appointment_router.message(AppointmentFeedbackState.waiting_for_feedback)
async def handle_appointment_feedback_message(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text in [
        t("menu_profile", "uz"), t("menu_profile", "ru"),
        t("menu_inquiry", "uz"), t("menu_inquiry", "ru"),
        t("menu_appointment", "uz"), t("menu_appointment", "ru"),
        t("menu_about_us", "uz"), t("menu_about_us", "ru"),
        t("menu_help", "uz"), t("menu_help", "ru"),
        t("btn_change_lang", "uz"), t("btn_change_lang", "ru"),
        t("btn_cancel", "uz"), t("btn_cancel", "ru"),
    ]:
        await state.clear()
        return

    data = await state.get_data()
    app_id = data.get("rating_appointment_id")
    if app_id:
        app = Appointment.get_by_id(app_id, db_session)
        if app and message.text:
            app.feedback = message.text.strip()
            db_session.add(app)
            db_session.commit()

    await state.clear()
    await message.answer(t("feedback_recorded", lang), reply_markup=get_main_menu(lang))


# --- User-initiated Appointment Cancellation ---


@appointment_router.callback_query(F.data.startswith("app_user_cancel_prompt:"), StateFilter("*"))
async def app_user_cancel_prompt_handler(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await state.clear()
    app_id = int(query.data.split(":")[1])
    app = db_session.get(Appointment, app_id)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not app or app.user_id != query.from_user.id:
        return await query.answer("Ariza topilmadi!", show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Ha, bekor qilinsin" if lang == "uz" else "✅ Да, отменить",
        callback_data=f"app_user_cancel_confirm:{app_id}"
    )
    builder.button(
        text="⬅️ Yo'q, qolsin" if lang == "uz" else "⬅️ Нет, оставить",
        callback_data="app_cancel"
    )
    builder.adjust(1)

    confirm_text = (
        f"❓ <b>Haqiqatan ham №{app_id}-sonli qabul arizangizni bekor qilmoqchimisiz?</b>"
        if lang == "uz" else
        f"❓ <b>Вы действительно хотите отменить запись №{app_id}?</b>"
    )
    await query.message.edit_text(confirm_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@appointment_router.callback_query(F.data.startswith("app_user_cancel_confirm:"), StateFilter("*"))
async def app_user_cancel_confirm_handler(query: CallbackQuery, db_session: DBSession, bot: Bot, state: FSMContext):
    await state.clear()
    app_id = int(query.data.split(":")[1])
    app = db_session.get(Appointment, app_id)
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not app or app.user_id != query.from_user.id:
        return await query.answer("Ariza topilmadi!", show_alert=True)

    if app.status in [AppointmentStatus.completed, AppointmentStatus.cancelled]:
        await query.answer("Ushbu ariza allaqachon yakunlangan yoki bekor qilingan!", show_alert=True)
        return await query.message.answer(t("btn_back_main", lang), reply_markup=get_main_menu(lang))

    app.status = AppointmentStatus.cancelled
    app.cancellation_reason = "Foydalanuvchi tomonidan bekor qilindi"
    app.updated_at = datetime.now()
    db_session.add(app)
    db_session.commit()

    # If message was posted in lawyer group, notify group and disable claim button
    if app.group_message_id:
        group_id = settings.LAWYER_APPOINTMENT_GROUP_ID
        try:
            await bot.edit_message_reply_markup(
                chat_id=group_id,
                message_id=app.group_message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Fuqaro tomonidan bekor qilingan", callback_data="none")
                ]])
            )
        except Exception as e:
            print("Failed to update group card markup on cancel:", e)

        try:
            await bot.send_message(
                chat_id=group_id,
                text=f"⚠️ <b>Ariza №{app.id}</b> fuqaro tomonidan bekor qilindi.",
                reply_to_message_id=app.group_message_id,
                parse_mode=SULGUK_PARSE_MODE
            )
        except Exception as e:
            print("Failed to notify group of user cancellation:", e)

    await query.answer("Qabul bekor qilindi!")
    success_text = (
        f"✅ <b>№{app.id}-sonli qabul arizangiz muvaffaqiyatli bekor qilindi.</b><br/><br/>"
        "Endi yangi qabul arizasini topshirishingiz mumkin."
        if lang == "uz" else
        f"✅ <b>Запись №{app.id} успешно отменена.</b><br/><br/>"
        "Теперь вы можете оформить новую запись."
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(success_text, reply_markup=get_main_menu(lang), parse_mode=SULGUK_PARSE_MODE)
