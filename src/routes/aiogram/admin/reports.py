"""Tahliliy hisobotlar (Excel)."""
import os
import html
import shutil
import logging
from datetime import datetime, timedelta
from aiogram import F, Bot

logger = logging.getLogger(__name__)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.app.generate_staff_report import (
    generate_comprehensive_report,
    format_telegram_analytics_summary,
    send_report_document,
    parse_date_range_string,
)

from src.routes.aiogram.admin.common import AdminReportCustomState, admin_router


async def send_analytics_report_to_admin(
    bot: Bot,
    admin_user_id: int,
    start_dt: datetime | None,
    end_dt: datetime | None,
    period_name: str,
    file_suffix: str,
    status_msg: Message | None = None
):
    """6 ta varaqli tahliliy hisobotni generatsiya qiladi va adminga yuboradi"""
    file_path = None
    try:
        date_range = (start_dt, end_dt) if start_dt and end_dt else None
        file_path, summary_dict = generate_comprehensive_report(date_range=date_range)
        filename = f"HuquqPlus_Hisobot_{file_suffix}.xlsx"

        # Loyiha reports/ papkasida ham nusxasini saqlab qo'yish
        try:
            base_dir = "/app" if os.path.exists("/app") else os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            reports_dir = os.path.join(base_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            shutil.copy2(file_path, os.path.join(reports_dir, filename))
        except Exception:
            pass

        caption_text = format_telegram_analytics_summary(summary_dict, period_name)
        await send_report_document(bot, admin_user_id, file_path, filename, caption_text, period_name)

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Comprehensive report export error: {e}", exc_info=True)
        await bot.send_message(
            chat_id=admin_user_id,
            text=f"⚠️ <b>Hisobot yaratishda xatolik yuz berdi:</b> {html.escape(str(e))}",
            parse_mode=SULGUK_PARSE_MODE
        )
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

@admin_router.callback_query(F.data.in_(["admin:report_menu", "admin:export_staff_excel"]), is_private_message)
async def admin_report_menu_callback(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    now = datetime.now()
    cur_m_name = now.strftime("%m.%Y")
    prev_m_dt = datetime(now.year, now.month, 1) - timedelta(days=1)
    prev_m_name = prev_m_dt.strftime("%m.%Y")

    menu_text = (
        "📊 <b>Keng Qamrovli Tahliliy Hisobot (Master Analytics)</b><br/><br/>"
        "Quyidagi davrlardan birini tanlang yoki o'zingiz istalgan sana oralig'ini kiriting.<br/>"
        "Bot sizga <b>6 ta tahliliy varaqdan</b> iborat to'liq Excel (.xlsx) faylini "
        "va asosiy ko'rsatkichlar xulosasini tayyorlab beradi:<br/><br/>"
        "<i>1-varaq: Umumiy loyiha statistikasi (KPI Dashboard)</i><br/>"
        "<i>2-varaq: 14 ta hudud va Demografiya</i><br/>"
        "<i>3-varaq: Huquqiy sohalar tahlili</i><br/>"
        "<i>4-varaq: Mutaxassislar va volontyorlar KPI reytingi</i><br/>"
        "<i>5-varaq: Barcha murojaatlar registri</i><br/>"
        "<i>6-varaq: Yurist qabullari registri</i><br/><br/>"
        "💡 <i>Tezkor buyruq: istalgan vaqtda chatda <code>/report 01.08.2026#01.10.2026</code> deb yuborishingiz mumkin.</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=f"📅 Joriy oy ({cur_m_name})", callback_data="admin:export_rep:cur_month")
    builder.button(text=f"⏮ O'tgan oy ({prev_m_name})", callback_data="admin:export_rep:prev_month")
    builder.button(text="🗓 Oxirgi 3 oy (Kvartal)", callback_data="admin:export_rep:quarter")
    builder.button(text="🌟 Barcha davr (Jami)", callback_data="admin:export_rep:all")
    builder.button(text="✍️ Sana oralig'ini kiritish (#)", callback_data="admin:export_rep:custom")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    await query.message.edit_text(menu_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data == "admin:export_rep:custom", is_private_message)
async def admin_report_custom_prompt_callback(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminReportCustomState.waiting_for_date_range)
    prompt_text = (
        "✍️ <b>Hisobot davrini kiriting:</b><br/><br/>"
        "Iltimos, sana oralig'ini quyidagi formatda yuboring:<br/>"
        "<code>01.08.2026#01.10.2026</code><br/><br/>"
        "<i>(Shuningdek <code>01.08.2026 - 01.10.2026</code> yoki <code>2026-08-01#2026-10-01</code> formatlari ham qabul qilinadi)</i><br/><br/>"
        "💡 <i>Yoki to'g'ridan-to'g'ri <code>/report 01.08.2026#01.10.2026</code> buyrug'ini yuborishingiz mumkin.</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:report_menu")

    await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.message(AdminReportCustomState.waiting_for_date_range, is_private_message)
async def admin_report_custom_range_received(message: Message, state: FSMContext, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if text.startswith("/cancel") or text.lower() in ["bekor qilish", "cancel"]:
        await state.clear()
        return await message.answer("❌ Bekor qilindi.")

    try:
        start_dt, end_dt, period_name, file_suffix = parse_date_range_string(text)
    except Exception as e:
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Bekor qilish", callback_data="admin:report_menu")
        return await message.answer(
            f"⚠️ <b>Noto'g'ri sana formati:</b> {e}<br/><br/>"
            "Iltimos, quyidagi ko'rinishda kiriting:<br/>"
            "<code>01.08.2026#01.10.2026</code>",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )

    await state.clear()
    status_msg = await message.answer(
        f"⏳ <b>{period_name}</b> oralig'i bo'yicha 6 ta varaqli tahliliy hisobot tayyorlanmoqda, iltimos kuting...",
        parse_mode=SULGUK_PARSE_MODE
    )

    await send_analytics_report_to_admin(
        bot=bot,
        admin_user_id=message.from_user.id,
        start_dt=start_dt,
        end_dt=end_dt,
        period_name=period_name,
        file_suffix=file_suffix,
        status_msg=status_msg
    )

@admin_router.message(Command("report"), is_private_message)
async def admin_report_command(message: Message, state: FSMContext, bot: Bot):
    if not settings.is_admin(message.from_user.id):
        return await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")

    await state.clear()
    raw_text = message.text.strip()
    args_text = raw_text[len("/report"):].strip()

    if args_text:
        try:
            start_dt, end_dt, period_name, file_suffix = parse_date_range_string(args_text)
        except Exception as e:
            return await message.answer(
                f"⚠️ <b>Noto'g'ri parametr:</b> {e}<br/><br/>"
                "To'g'ri format misoli:<br/>"
                "<code>/report 01.08.2026#01.10.2026</code><br/>"
                "<code>/report 01.08.2026 - 01.10.2026</code><br/>"
                "<code>/report month</code> (joriy oy)<br/>"
                "<code>/report all</code> (barcha davr)",
                parse_mode=SULGUK_PARSE_MODE
            )

        status_msg = await message.answer(
            f"⏳ <b>{period_name}</b> oralig'i bo'yicha 6 ta varaqli tahliliy hisobot tayyorlanmoqda, iltimos kuting...",
            parse_mode=SULGUK_PARSE_MODE
        )
        await send_analytics_report_to_admin(
            bot=bot,
            admin_user_id=message.from_user.id,
            start_dt=start_dt,
            end_dt=end_dt,
            period_name=period_name,
            file_suffix=file_suffix,
            status_msg=status_msg
        )
    else:
        # Args berilmaganda interaktiv menyu ochiladi
        now = datetime.now()
        cur_m_name = now.strftime("%m.%Y")
        prev_m_dt = datetime(now.year, now.month, 1) - timedelta(days=1)
        prev_m_name = prev_m_dt.strftime("%m.%Y")

        menu_text = (
            "📊 <b>Keng Qamrovli Tahliliy Hisobot (Master Analytics)</b><br/><br/>"
            "Quyidagi davrlardan birini tanlang yoki sana oralig'ini kiriting.<br/>"
            "Bot sizga <b>6 ta tahliliy varaqdan</b> iborat to'liq Excel (.xlsx) faylini "
            "va asosiy ko'rsatkichlar xulosasini tayyorlab beradi:<br/><br/>"
            "<i>1-varaq: Umumiy loyiha statistikasi (KPI Dashboard)</i><br/>"
            "<i>2-varaq: 14 ta hudud va Demografiya</i><br/>"
            "<i>3-varaq: Huquqiy sohalar tahlili</i><br/>"
            "<i>4-varaq: Mutaxassislar va volontyorlar KPI reytingi</i><br/>"
            "<i>5-varaq: Barcha murojaatlar registri</i><br/>"
            "<i>6-varaq: Yurist qabullari registri</i><br/><br/>"
            "💡 <i>Tezkor buyruq: istalgan vaqtda <code>/report 01.08.2026#01.10.2026</code> deb yuborishingiz mumkin.</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text=f"📅 Joriy oy ({cur_m_name})", callback_data="admin:export_rep:cur_month")
        builder.button(text=f"⏮ O'tgan oy ({prev_m_name})", callback_data="admin:export_rep:prev_month")
        builder.button(text="🗓 Oxirgi 3 oy (Kvartal)", callback_data="admin:export_rep:quarter")
        builder.button(text="🌟 Barcha davr (Jami)", callback_data="admin:export_rep:all")
        builder.button(text="✍️ Sana oralig'ini kiritish (#)", callback_data="admin:export_rep:custom")
        builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
        builder.adjust(1)

        await message.answer(menu_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)

@admin_router.callback_query(F.data.startswith("admin:export_rep:"), is_private_message)
async def admin_export_comprehensive_report_callback(query: CallbackQuery, bot: Bot):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    mode = query.data.split(":")[2]
    now = datetime.now()

    if mode == "cur_month":
        start_date = datetime(now.year, now.month, 1, 0, 0, 0)
        end_date = now
        period_name = f"Joriy oy ({now.strftime('%m.%Y')})"
        file_suffix = f"{now.strftime('%Y_%m')}_joriy_oy"
    elif mode == "prev_month":
        first_this_month = datetime(now.year, now.month, 1, 0, 0, 0)
        end_date = first_this_month - timedelta(seconds=1)
        start_date = datetime(end_date.year, end_date.month, 1, 0, 0, 0)
        period_name = f"O'tgan oy ({start_date.strftime('%m.%Y')})"
        file_suffix = f"{start_date.strftime('%Y_%m')}_otgan_oy"
    elif mode == "quarter":
        start_date = now - timedelta(days=90)
        end_date = now
        period_name = f"Oxirgi 3 oy ({start_date.strftime('%d.%m.%Y')} — {now.strftime('%d.%m.%Y')})"
        file_suffix = "oxirgi_3_oy"
    else:  # 'all'
        start_date = None
        end_date = None
        period_name = "Barcha davr uchun"
        file_suffix = "barcha_davr"

    await query.answer("⏳ 6 ta varaqli tahliliy hisobot tayyorlanmoqda, iltimos kuting...", show_alert=False)

    status_msg = await query.message.answer(
        f"⏳ <b>{period_name}</b> bo'yicha hisobot tayyorlanmoqda...",
        parse_mode=SULGUK_PARSE_MODE
    )

    await send_analytics_report_to_admin(
        bot=bot,
        admin_user_id=query.from_user.id,
        start_dt=start_date,
        end_dt=end_date,
        period_name=period_name,
        file_suffix=file_suffix,
        status_msg=status_msg
    )



# --- yuristlar Boshqaruvi ---
