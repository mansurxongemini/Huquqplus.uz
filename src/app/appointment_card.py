import html
import json
import logging
import re
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sulguk import SULGUK_PARSE_MODE

from src.app.calendar_utils import format_uz_date, get_available_dates, get_time_slots_for_date
from src.app.enums import create_user_info
from src.app.html_utils import escape_multiline
from src.app.translations import t, LANG_UZ
from src.models.appointment import Appointment, AppointmentStatus
from src.models.inquiry import Inquiry
from src.models.lawyer import OfficialLawyer
from src.models.user import User
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

CARD_DESC_LIMIT = 1200


def get_appointment_type_display(app_type: str, lang: str = "uz") -> str:
    """Returns human-readable appointment type without hardcoding."""
    if app_type == "remote_appointment":
        if lang == "oz":
            return "📞 Масофавий қабул (Онлайн)"
        elif lang == "ru":
            return "📞 Дистанционный прием (Онлайн)"
        return "📞 Masofaviy qabul (Online)"
    elif app_type == "in_person_appointment":
        if lang == "oz":
            return "🏢 Юзма-юз қабул (Бош офис)"
        elif lang == "ru":
            return "🏢 Очный прием (Главный офис)"
        return "🏢 Yuzma-yuz qabul (Bosh ofis)"
    return app_type.replace("_", " ").capitalize()


def render_appointment_card(appointment: Appointment, db_session: DBSession, inquiry: Inquiry | None = None) -> str:
    """
    Renders unified HTML card text for any appointment (citizen submission, /yurist escalation, Admin CRM).
    Includes:
      - Fuqaro ma'lumotlari
      - Qabul shakli (from appointment_type)
      - Murojaat yo'nalishi (inquiry.section_name or '—')
      - Fayllar soni / biriktirilgan fayllar
      - Belgilangan vaqt
      - Biriktirilgan yurist
      - Holati
      - Uchrashuv havolasi (if available)
      - Muammo mazmuni
    """
    user = User.get_by_user_id(appointment.user_id, db_session)
    user_lang = user.language if user else "uz"
    user_context = create_user_info(user, with_link=True, lang=user_lang)

    # 1. Qabul shakli
    app_type_display = get_appointment_type_display(appointment.appointment_type or "remote_appointment", lang=user_lang)

    # 2. Murojaat yo'nalishi
    if inquiry is None and appointment.inquiry_id:
        inquiry = db_session.get(Inquiry, appointment.inquiry_id)
    section_name = inquiry.section_name if (inquiry and inquiry.section_name) else "—"

    # 3. Fayllar soni / tavsifi
    media_display = "—"
    if appointment.media_meta:
        try:
            items = json.loads(appointment.media_meta)
            if isinstance(items, list) and items:
                count = len(items)
                if count == 1:
                    media_display = f"1 ta fayl ({items[0].get('name', 'Fayl')})"
                else:
                    names_str = ", ".join(item.get("name", "Fayl") for item in items[:3])
                    extra_str = f" va yana {count - 3} ta" if count > 3 else ""
                    media_display = f"{count} ta fayl ({names_str}{extra_str})"
            elif isinstance(items, dict):
                media_display = items.get("file_name") or items.get("name") or "1 ta fayl"
        except Exception:
            media_display = f"1 ta fayl ({appointment.media_name or appointment.media_type or 'Fayl'})"
    elif appointment.media_type and appointment.media_type != "text":
        media_display = f"1 ta fayl ({appointment.media_name or appointment.media_type.capitalize()})"

    # 4. Belgilangan vaqt
    if appointment.scheduled_at:
        time_display = f"<b>{format_uz_date(appointment.scheduled_at)}</b>"
    else:
        time_display = "<i>Belgilanmagan</i>"

    # 5. Biriktirilgan yurist
    if appointment.lawyer_id:
        lawyer = OfficialLawyer.get_by_user_id(appointment.lawyer_id, db_session)
        if lawyer:
            lawyer_display = f"<a href=\"tg://user?id={appointment.lawyer_id}\">{lawyer.full_name}</a>"
        else:
            lawyer_display = f"<a href=\"tg://user?id={appointment.lawyer_id}\">Yurist (ID: {appointment.lawyer_id})</a>"
    else:
        lawyer_display = "<i>Biriktirilmagan</i>"

    # 6. Holati
    if appointment.status == AppointmentStatus.completed:
        status_display = "🏁 Suhbat yakunlangan"
    elif appointment.status == AppointmentStatus.cancelled:
        reason_suffix = f" ({appointment.cancellation_reason})" if appointment.cancellation_reason else ""
        status_display = f"❌ Bekor qilingan{reason_suffix}"
    elif appointment.lawyer_id and appointment.scheduled_at:
        status_display = "✅ Qabul tasdiqlangan (Suhbat kutilmoqda)"
    elif appointment.lawyer_id:
        status_display = "⏳ Qabul vaqti belgilanmagan"
    elif appointment.scheduled_at:
        status_display = "⏳ Yurist biriktirilmagan"
    else:
        status_display = "⏳ Yangi (Yurist va vaqt belgilanmagan)"

    attend_row = ""
    if appointment.citizen_confirmation == "yes":
        attend_row = "• <b>Fuqaro:</b> ✅ belgilangan vaqtga tayyorligini tasdiqladi<br/>"
    elif appointment.citizen_confirmation == "no":
        attend_row = "• <b>Fuqaro:</b> ❌ bu vaqtda qatnasha olmaydi — yangi vaqt kerak<br/>"

    # 7. Uchrashuv havolasi
    link_row = ""
    if appointment.meeting_link and appointment.status != AppointmentStatus.cancelled:
        escaped_link = html.escape(appointment.meeting_link)
        link_row = f"• 🔗 <b>Uchrashuv havolasi:</b> <a href=\"{escaped_link}\">{escaped_link}</a><br/>"

    # 8. Muammo matni
    raw_desc = appointment.problem_description or ""
    if appointment.media_type and appointment.media_type != "text":
        raw_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip()  # murojaatdan kelgan media tavsifi HTML bo'ladi
    desc = escape_multiline(raw_desc[:CARD_DESC_LIMIT]) + ("…" if len(raw_desc) > CARD_DESC_LIMIT else "") if raw_desc else "—"

    card = (
        f"📅 <b>YURIST QABULIGA ARIZA (№{appointment.id})</b><br/>"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"👤 <b>FUQARO MA'LUMOTLARI:</b><br/>"
        f"{user_context}<br/>"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"🏢 <b>QABUL MA'LUMOTLARI:</b><br/>"
        f"• <b>Qabul shakli:</b> {app_type_display}<br/>"
        f"• <b>Murojaat yo'nalishi:</b> {section_name}<br/>"
        f"• 📎 <b>Biriktirilgan fayllar:</b> {media_display}<br/>"
        f"• <b>Belgilangan vaqt:</b> {time_display}<br/>"
        f"• <b>Biriktirilgan yurist:</b> {lawyer_display}<br/>"
        f"• <b>Holati:</b> {status_display}<br/>"
        f"{attend_row}"
        f"{link_row}"
        f"━━━━━━━━━━━━━━━━━━━━━<br/>"
        f"📝 <b>MUAMMO MAZMUNI:</b><br/>"
        f"<blockquote>{desc}</blockquote>"
    )
    return card


# Backwards compatibility alias for existing code/imports
render_escalated_appointment_card = render_appointment_card


def get_appointment_markup(
    appointment: Appointment,
    extra_rows: list[list[InlineKeyboardButton]] | None = None
) -> InlineKeyboardMarkup:
    """
    Renders unified inline keyboard for any appointment.
    States:
      - cancelled: '♻️ Qayta tiklash' (for admins)
      - completed: no action buttons
      - pending / accepted (ready):
          if both lawyer_id and scheduled_at:
              [🔗 Havola kiritish, ✅ Suhbat yakunlandi]
              [❌ Qabulni bekor qilish, 🔄 O'zgartirish (Yurist/Vaqt)]
          else:
              [📌 Qabulni olish (if not lawyer), 👨‍⚖️ Yurist biriktirish/o'zgartirish]
              [📅 Vaqtni belgilash/o'zgartirish, ❌ Bekor qilish]
    """
    builder = InlineKeyboardBuilder()

    if appointment.status == AppointmentStatus.cancelled:
        builder.button(text="♻️ Qayta tiklash", callback_data=f"app_escalate:restore:{appointment.id}")
        builder.adjust(1)
    elif appointment.status == AppointmentStatus.completed:
        # Completed appointments have no action buttons
        pass
    elif appointment.lawyer_id and appointment.scheduled_at:
        builder.button(text="🔗 Havola kiritish", callback_data=f"appointment:add_link:{appointment.id}")
        builder.button(text="✅ Suhbat yakunlandi", callback_data=f"appointment:complete:{appointment.id}")
        builder.button(text="❌ Qabulni bekor qilish", callback_data=f"appointment:cancel:{appointment.id}")
        builder.button(text="🔄 O'zgartirish (Yurist/Vaqt)", callback_data=f"app_escalate:manage:{appointment.id}")
        builder.adjust(2, 2)
    else:
        # Not yet fully scheduled (missing lawyer or time)
        if not appointment.lawyer_id:
            builder.button(text="📌 Qabulni olish", callback_data=f"appointment:claim:{appointment.id}")
            builder.button(text="👨‍⚖️ Yurist biriktirish", callback_data=f"app_escalate:assign:{appointment.id}")
        else:
            builder.button(text="👨‍⚖️ Yuristni o'zgartirish", callback_data=f"app_escalate:assign:{appointment.id}")

        if not appointment.scheduled_at:
            builder.button(text="📅 Vaqtni belgilash", callback_data=f"app_escalate:date:{appointment.id}")
        else:
            builder.button(text="📅 Vaqtni o'zgartirish", callback_data=f"app_escalate:date:{appointment.id}")

        builder.button(text="❌ Bekor qilish", callback_data=f"appointment:cancel:{appointment.id}")

        if not appointment.lawyer_id:
            builder.adjust(2, 2, 1)
        else:
            builder.adjust(2, 1)

    if extra_rows:
        for row in extra_rows:
            builder.row(*row)

    return builder.as_markup()


# Backwards compatibility alias for existing code/imports
get_escalated_appointment_markup = get_appointment_markup


def get_lawyers_keyboard(app_id: int, current_user_id: int, db_session: DBSession) -> InlineKeyboardMarkup:
    """Keyboard for selecting a lawyer for an appointment."""
    builder = InlineKeyboardBuilder()
    active_lawyers = OfficialLawyer.get_active_lawyers(db_session)

    is_self_lawyer = any(l.user_id == current_user_id for l in active_lawyers)
    if is_self_lawyer:
        builder.button(text="📌 O'zimga biriktirish", callback_data=f"app_escalate:set_lawyer:{app_id}:{current_user_id}")

    for lawyer in active_lawyers:
        if is_self_lawyer and lawyer.user_id == current_user_id:
            continue
        builder.button(text=f"👨‍⚖️ {lawyer.full_name}", callback_data=f"app_escalate:set_lawyer:{app_id}:{lawyer.user_id}")

    builder.button(text="⬅️ Ortga", callback_data=f"app_escalate:back:{app_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_escalation_dates_keyboard(app_id: int) -> InlineKeyboardMarkup:
    """Keyboard for selecting a date for an appointment."""
    builder = InlineKeyboardBuilder()
    dates = get_available_dates(appointment_type="remote_appointment", count=8)
    for d in dates:
        builder.button(text=d["label"], callback_data=f"app_escalate:time:{app_id}:{d['date_str']}")
    builder.button(text="⬅️ Ortga", callback_data=f"app_escalate:back:{app_id}")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def get_escalation_slots_keyboard(app_id: int, date_str: str, lawyer_id: int | None, db_session: DBSession) -> InlineKeyboardMarkup:
    """Keyboard for selecting a time slot on a chosen date."""
    builder = InlineKeyboardBuilder()
    slots = get_time_slots_for_date(
        date_str=date_str,
        lawyer_id=lawyer_id,
        appointment_type="remote_appointment",
        db_session=db_session
    )
    for slot in slots:
        if slot["is_available"]:
            builder.button(
                text=f"🟢 {slot['label']}",
                callback_data=f"app_escalate:slot:{app_id}:{date_str}:{slot['time_str']}"
            )
        else:
            builder.button(
                text=f"🔒 {slot['time_str']} (Band)",
                callback_data="app_escalate:slot_taken"
            )
    builder.button(text="📅 Boshqa kunni tanlash", callback_data=f"app_escalate:date:{app_id}")
    builder.button(text="⬅️ Bekor qilish", callback_data=f"app_escalate:back:{app_id}")
    builder.adjust(2)
    return builder.as_markup()


async def notify_citizen_appointment_update(
    bot: Bot,
    appointment: Appointment,
    db_session: DBSession,
    kind: str,
) -> None:
    """
    Sends updated status notification to the citizen in private chat,
    and automatically deletes the previous status notification message if stored.
    Updates appointment.citizen_notice_message_id with the new message ID.

    `kind` options:
      - 'claimed' / 'lawyer_assigned': lawyer assigned for the first time
      - 'lawyer_changed' / 'reassigned': lawyer changed to another lawyer
      - 'confirmed' / 'time_set': both lawyer and time are set
      - 'time_changed' / 'rescheduled': time changed
      - 'cancelled': appointment cancelled
      - 'restored': appointment restored
    """
    citizen = User.get_by_user_id(appointment.user_id, db_session)
    if not citizen:
        logger.warning("Cannot notify citizen: User %s not found in DB", appointment.user_id)
        return

    lang = citizen.language or LANG_UZ

    # Resolve lawyer name if assigned
    lawyer_name = "Huquqshunos"
    if appointment.lawyer_id:
        lawyer_obj = OfficialLawyer.get_by_user_id(appointment.lawyer_id, db_session)
        if lawyer_obj:
            lawyer_name = lawyer_obj.full_name

    scheduled_time = format_uz_date(appointment.scheduled_at) if appointment.scheduled_at else ""
    app_type_display = get_appointment_type_display(appointment.appointment_type or "remote_appointment", lang=lang)

    # 1. Select appropriate translation based on `kind`
    if kind in ["claimed", "lawyer_assigned"]:
        if appointment.scheduled_at:
            text = t("appointment_confirmed_citizen", lang, scheduled_time=scheduled_time, lawyer_name=lawyer_name, app_type=app_type_display)
        else:
            text = t("appointment_claimed_citizen", lang, lawyer_name=lawyer_name)
    elif kind in ["lawyer_changed", "reassigned"]:
        text = t("appointment_lawyer_changed_citizen", lang, lawyer_name=lawyer_name)
    elif kind in ["confirmed", "time_set"]:
        text = t("appointment_confirmed_citizen", lang, scheduled_time=scheduled_time, lawyer_name=lawyer_name, app_type=app_type_display)
    elif kind in ["time_changed", "rescheduled"]:
        text = t("appointment_time_changed_citizen", lang, scheduled_time=scheduled_time, lawyer_name=lawyer_name)
    elif kind == "cancelled":
        reason_text = f"<br/><b>Sabab:</b> <i>{appointment.cancellation_reason}</i>" if appointment.cancellation_reason else ""
        text = t("appointment_cancelled_citizen", lang, app_id=appointment.id, reason_text=reason_text)
    elif kind == "restored":
        text = t("appointment_restored_citizen", lang, app_id=appointment.id)
    else:
        logger.warning("Unknown appointment notification kind '%s', fallback to confirmed/claimed", kind)
        text = t("appointment_claimed_citizen", lang, lawyer_name=lawyer_name)

    # 2. Delete previous citizen notification message if present
    if appointment.citizen_notice_message_id:
        try:
            await bot.delete_message(
                chat_id=appointment.user_id,
                message_id=appointment.citizen_notice_message_id
            )
            logger.info(
                "Deleted previous citizen notice message %s for appointment %s",
                appointment.citizen_notice_message_id,
                appointment.id
            )
        except Exception as e:
            logger.debug(
                "Failed to delete previous citizen notice %s (user %s): %s",
                appointment.citizen_notice_message_id,
                appointment.user_id,
                e
            )
        appointment.citizen_notice_message_id = None

    # 3. Send new notification and record message ID
    try:
        sent_msg = await bot.send_message(
            chat_id=appointment.user_id,
            text=text,
            parse_mode=SULGUK_PARSE_MODE
        )
        appointment.citizen_notice_message_id = sent_msg.message_id
        db_session.add(appointment)
        db_session.commit()
        logger.info(
            "Sent citizen appointment notification (kind=%s, msg_id=%s) for appointment %s",
            kind,
            sent_msg.message_id,
            appointment.id
        )
    except Exception as e:
        logger.warning(
            "Failed to send appointment notification to citizen %s for appointment %s: %s",
            appointment.user_id,
            appointment.id,
            e
        )
