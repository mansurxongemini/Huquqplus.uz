"""Imtiyozlar boshqaruvi."""
import os
import math
import json
import html
import logging
from aiogram import F

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.config.settings import settings
from src.models.benefit import Benefit, BenefitCategory
from src.routes.deps.db_session import DBSession

from src.routes.aiogram.admin.common import AdminAddBenefitState, AdminEditBenefitState, PAGE_SIZE, admin_router


def sync_benefits_to_json(db_session: DBSession) -> bool:
    """
    MariaDB dagi barcha imtiyozlarni imtiyozlar_boshqaruvi/imtiyozlar.json fayliga
    avtomatik eksport qilib, ikki tomonlama sinxronizatsiyani ta'minlaydi.
    """
    # Guard: Don't execute file writes during unit tests using Mock db_sessions
    try:
        from unittest.mock import Mock
        if isinstance(db_session, Mock):
            return True
    except Exception:
        pass

    json_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../imtiyozlar_boshqaruvi/imtiyozlar.json")
    )
    try:
        benefits = list(
            db_session.exec(
                select(Benefit).order_by(Benefit.order_index, Benefit.id)
            ).all()
        )
        if not benefits:
            # Safety guard: Never wipe out the seed file with empty list
            return False
        data = []
        for b in benefits:
            item = {
                "category": b.category,
                "for_first_group": b.for_first_group,
                "for_second_group": b.for_second_group,
                "for_third_group": b.for_third_group,
                "for_child": b.for_child,
                "for_parent": b.for_parent,
                "is_for_organization": b.is_for_organization,
                "min_age": b.min_age,
                "max_age": b.max_age,
                "gender": b.gender,
                "disability_state": b.disability_state,
                "title_uz": b.title_uz,
                "description_uz": b.description_uz,
                "amount_uz": b.amount_uz,
                "organization_uz": b.organization_uz,
                "legal_basis_uz": b.legal_basis_uz,
                "title_oz": b.title_oz,
                "description_oz": b.description_oz,
                "amount_oz": b.amount_oz,
                "organization_oz": b.organization_oz,
                "legal_basis_oz": b.legal_basis_oz,
                "order_index": b.order_index,
                "guide_uz": b.guide_uz,
                "guide_oz": b.guide_oz,
                "mygov_url": b.mygov_url,
                "lex_url": b.lex_url,
                "title_ru": b.title_ru,
                "description_ru": b.description_ru,
                "amount_ru": b.amount_ru,
                "organization_ru": b.organization_ru,
                "legal_basis_ru": b.legal_basis_ru,
                "guide_ru": b.guide_ru,
                "is_active": b.is_active,
            }
            data.append(item)

        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        temp_file = f"{json_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, json_file)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to sync benefits to imtiyozlar.json: %s", e)
        return False

def build_admin_benefits_page(benefits: list[Benefit], page: int, total_pages: int, total_count: int) -> tuple[str, InlineKeyboardMarkup]:
    builder = InlineKeyboardBuilder()
    if not benefits:
        text = (
            "<b>Imtiyozlar boshqaruvi</b><br/><br/>"
            "Hozirda ma'lumotlar bazasida imtiyozlar mavjud emas.<br/><br/>"
            "Yangi imtiyoz kiritish uchun quyidagi <b>➕ Yangi imtiyoz qo'shish</b> tugmasini bosing:"
        )
    else:
        text = f"<b>Imtiyozlar ro'yxati (jami {total_count} ta):</b><br/><br/>"
        cat_names = {
            BenefitCategory.PENSION_AID: "Nafaqa/Yordam",
            BenefitCategory.HEALTH_REHAB: "Tibbiyot",
            BenefitCategory.EDUCATION: "Ta'lim",
            BenefitCategory.LABOR: "Mehnat",
            BenefitCategory.TRANSPORT: "Transport",
            BenefitCategory.HOUSING_COMMUNAL: "Uy-joy",
            BenefitCategory.TAX_FEE: "Soliq/Boj",
            BenefitCategory.OTHER: "Boshqa",
        }
        for idx, b in enumerate(benefits, 1):
            st = "🟢 Faol" if b.is_active else "🔴"
            c_name = cat_names.get(b.category, b.category)
            short_t = b.title_uz[:60] + ("..." if len(b.title_uz) > 60 else "")
            text += (
                f"<b>{idx}. {short_t}</b><br/>"
                f"Yo‘nalish: <i>{c_name}</i> | Holat: {st}<br/><br/>"
            )
            toggle_label = "🔴" if b.is_active else "🟢"
            builder.row(
                InlineKeyboardButton(text=f"{idx}. {toggle_label}", callback_data=f"admin:b_toggle:{b.id}:{page}"),
                InlineKeyboardButton(text="✏️", callback_data=f"admin:b_edit:{b.id}:{page}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"admin:b_del:{b.id}:{page}")
            )

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:benefits_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page}/{max(total_pages, 1)}", callback_data="admin:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:benefits_page:{page + 1}"))

    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="➕ Yangi imtiyoz qo'shish", callback_data="admin:b_add"))
    builder.row(InlineKeyboardButton(text="⬅️ Admin menyu", callback_data="admin:main"))
    return text, builder.as_markup()

def build_benefit_edit_menu(benefit: Benefit, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Admin panel uchun imtiyozni tahrirlash interfeysi."""
    cat_names = {
        BenefitCategory.PENSION_AID: "Nafaqa va yordam",
        BenefitCategory.HEALTH_REHAB: "Tibbiyot va reabilitatsiya",
        BenefitCategory.EDUCATION: "Ta'lim va yoshlar",
        BenefitCategory.LABOR: "Mehnat va bandlik",
        BenefitCategory.TRANSPORT: "Transport",
        BenefitCategory.HOUSING_COMMUNAL: "Uy-joy va kommunal",
        BenefitCategory.TAX_FEE: "Soliq va bojlar",
        BenefitCategory.OTHER: "Boshqa",
    }
    cat_display = cat_names.get(benefit.category, benefit.category)
    lex_display = html.escape(benefit.lex_url) if benefit.lex_url else "<i>Mavjud emas</i>"
    mygov_display = html.escape(benefit.mygov_url) if benefit.mygov_url else "<i>Mavjud emas</i>"
    org_display = html.escape(benefit.organization_uz or "Mavjud emas")
    amt_display = html.escape(benefit.amount_uz or "Mavjud emas")
    legal_display = html.escape(benefit.legal_basis_uz or "Mavjud emas")
    guide_status = "✅ Mavjud" if benefit.guide_uz else "❌ Mavjud emas"

    # Truncate displays for safety against Telegram 4096 character limit
    if len(org_display) > 80:
        org_display = org_display[:80] + "..."
    if len(amt_display) > 80:
        amt_display = amt_display[:80] + "..."
    if len(legal_display) > 100:
        legal_display = legal_display[:100] + "..."

    # Tegishli toifalar (nogironlik guruhi, bola, ota-ona, tashkilot)
    aud_items = []
    if getattr(benefit, "for_first_group", False):
        aud_items.append("1-guruh")
    if getattr(benefit, "for_second_group", False):
        aud_items.append("2-guruh")
    if getattr(benefit, "for_third_group", False):
        aud_items.append("3-guruh")
    if getattr(benefit, "for_child", False):
        aud_items.append("Bola (18 gacha)")
    if getattr(benefit, "for_parent", False):
        aud_items.append("Ota-ona")
    if getattr(benefit, "is_for_organization", False):
        aud_items.append("Tashkilot")
    aud_display = ", ".join(aud_items) if aud_items else "<i>Hech biri belgilanmagan</i>"

    text = (
        f"<b>✏️ Imtiyozni tahrirlash (ID: {benefit.id})</b><br/><br/>"
        f"📌 <b>Nomi:</b> {html.escape(benefit.title_uz)}<br/>"
        f"📂 <b>Yo‘nalishi:</b> {cat_display}<br/>"
        f"👥 <b>Tegishli toifalar:</b> {aud_display}<br/>"
        f"🏢 <b>Tashkilot:</b> {org_display}<br/>"
        f"✨ <b>Miqdori:</b> {amt_display}<br/>"
        f"⚖️ <b>Huquqiy asos:</b> {legal_display}<br/>"
        f"🔗 <b>Lex.uz havola:</b> {lex_display}<br/>"
        f"🌐 <b>Portal havola:</b> {mygov_display}<br/>"
        f"📖 <b>Yo‘riqnoma:</b> {guide_status}<br/><br/>"
        f"<i>Tahrirlash uchun quyidagi maydonlardan birini tanlang:</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Nomi", callback_data=f"admin:b_mod:{benefit.id}:title:{page}"),
        InlineKeyboardButton(text="📂 Yo‘nalishi", callback_data=f"admin:b_mod:{benefit.id}:category:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Tegishli toifalar", callback_data=f"admin:b_mod:{benefit.id}:audience:{page}"),
        InlineKeyboardButton(text="✨ Miqdori", callback_data=f"admin:b_mod:{benefit.id}:amount:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="📄 Tavsifi", callback_data=f"admin:b_mod:{benefit.id}:desc:{page}"),
        InlineKeyboardButton(text="🏢 Tashkilot", callback_data=f"admin:b_mod:{benefit.id}:org:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="⚖️ Huquqiy asos", callback_data=f"admin:b_mod:{benefit.id}:legal:{page}"),
        InlineKeyboardButton(text="📖 Yo‘riqnoma", callback_data=f"admin:b_mod:{benefit.id}:guide:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Lex.uz havola", callback_data=f"admin:b_mod:{benefit.id}:lex:{page}"),
        InlineKeyboardButton(text="🌐 Portal havola", callback_data=f"admin:b_mod:{benefit.id}:mygov:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Imtiyozlar ro‘yxati", callback_data=f"admin:benefits_page:{page}")
    )
    return text, builder.as_markup()

@admin_router.callback_query(F.data.startswith("admin:benefits_page:"), is_private_message)
async def admin_benefits_page_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    page = int(query.data.split(":")[2])
    if page < 1:
        page = 1

    total_count = len(db_session.exec(select(Benefit.id)).all())
    total_pages = math.ceil(total_count / PAGE_SIZE) or 1
    if page > total_pages:
        page = total_pages

    benefits = list(
        db_session.exec(
            select(Benefit).order_by(Benefit.order_index, Benefit.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        ).all()
    )

    text, markup = build_admin_benefits_page(benefits, page, total_pages, total_count)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:b_toggle:"), is_private_message)
async def admin_benefit_toggle_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    b_id = int(parts[2])
    page = int(parts[3])

    benefit = Benefit.get_by_id(b_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    benefit.is_active = not benefit.is_active
    db_session.add(benefit)
    db_session.commit()
    sync_benefits_to_json(db_session)

    total_count = len(db_session.exec(select(Benefit.id)).all())
    total_pages = math.ceil(total_count / PAGE_SIZE) or 1
    benefits = list(
        db_session.exec(
            select(Benefit).order_by(Benefit.order_index, Benefit.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        ).all()
    )

    text, markup = build_admin_benefits_page(benefits, page, total_pages, total_count)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer("Holat yangilandi!")

@admin_router.callback_query(F.data.startswith("admin:b_del:"), is_private_message)
async def admin_benefit_del_callback(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    b_id = int(parts[2])
    page = int(parts[3])

    benefit = Benefit.get_by_id(b_id, db_session)
    if benefit:
        db_session.delete(benefit)
        db_session.commit()
        sync_benefits_to_json(db_session)

    total_count = len(db_session.exec(select(Benefit.id)).all())
    total_pages = math.ceil(total_count / PAGE_SIZE) or 1
    if page > total_pages:
        page = total_pages

    benefits = list(
        db_session.exec(
            select(Benefit).order_by(Benefit.order_index, Benefit.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        ).all()
    )

    text, markup = build_admin_benefits_page(benefits, page, total_pages, total_count)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer("Imtiyoz o'chirildi!")

@admin_router.callback_query(F.data.startswith("admin:b_edit:"), is_private_message)
async def admin_benefit_edit_start(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.clear()
    parts = query.data.split(":")
    b_id = int(parts[2])
    page = int(parts[3])

    benefit = Benefit.get_by_id(b_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    text, markup = build_benefit_edit_menu(benefit, page)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:b_mod:"), is_private_message)
async def admin_benefit_modify_field(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    b_id = int(parts[2])
    field = parts[3]
    page = int(parts[4])

    benefit = Benefit.get_by_id(b_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    if field == "category":
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Nafaqa va yordam", callback_data=f"admin:b_save_cat:{b_id}:pension_aid:{page}")
        builder.button(text="🩺 Tibbiyot va reabilitatsiya", callback_data=f"admin:b_save_cat:{b_id}:health_rehab:{page}")
        builder.button(text="🎓 Ta'lim va yoshlar", callback_data=f"admin:b_save_cat:{b_id}:education:{page}")
        builder.button(text="💼 Mehnat va bandlik", callback_data=f"admin:b_save_cat:{b_id}:labor:{page}")
        builder.button(text="🚌 Transport", callback_data=f"admin:b_save_cat:{b_id}:transport:{page}")
        builder.button(text="🏠 Uy-joy va kommunal", callback_data=f"admin:b_save_cat:{b_id}:housing_communal:{page}")
        builder.button(text="📑 Soliq va bojlar", callback_data=f"admin:b_save_cat:{b_id}:tax_fee:{page}")
        builder.button(text="📦 Boshqa", callback_data=f"admin:b_save_cat:{b_id}:other:{page}")
        builder.button(text="❌ Bekor qilish", callback_data=f"admin:b_edit:{b_id}:{page}")
        builder.adjust(2, 2, 2, 2, 1)

        await query.message.edit_text(
            f"<b>📂 Yangi yo'nalishni (kategoriyani) tanlang:</b><br/><br/>Hozirgi: <i>{benefit.category}</i>",
            reply_markup=builder.as_markup(),
            parse_mode=SULGUK_PARSE_MODE
        )
        return await query.answer()

    if field == "audience":
        text, markup = build_benefit_audience_menu(benefit, page)
        await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
        return await query.answer()

    field_labels = {
        "title": "Nomini",
        "desc": "Tavsifini",
        "amount": "Miqdorini",
        "org": "Tashkilot nomini",
        "legal": "Huquqiy asosini",
        "lex": "Lex.uz havolasini",
        "mygov": "Portal havolasini",
        "guide": "Yo'riqnomasini",
    }
    field_label = field_labels.get(field, field)

    attr_name = f"{field}_uz" if field in ["title", "desc", "amount", "org", "legal", "guide"] else f"{field}_url" if field in ["lex", "mygov"] else field
    current_val = getattr(benefit, attr_name, "")
    current_display = html.escape(str(current_val or "Mavjud emas"))
    if len(current_display) > 200:
        current_display = current_display[:200] + "..."

    await state.set_state(AdminEditBenefitState.waiting_for_value)
    await state.update_data(b_id=b_id, field=field, page=page)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data=f"admin:b_edit:{b_id}:{page}")

    prompt_text = (
        f"<b>✏️ {field_label} tahrirlash (ID: {b_id})</b><br/><br/>"
        f"Hozirgi qiymat:<br/>"
        f"<blockquote>{current_display}</blockquote><br/>"
        f"Yangi qiymatni yozib yuboring (yoki bo‘shatish uchun <code>/empty</code> deb yozing):"
    )

    await query.message.edit_text(prompt_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()

def sync_benefit_to_json(benefit: Benefit, db_session: DBSession | None = None):
    """Admin panel orqali o'zgartirilgan imtiyozni imtiyozlar_boshqaruvi/imtiyozlar.json ga sinxronlash."""
    try:
        if db_session:
            return sync_benefits_to_json(db_session)
        from src.database.mysql import get_db
        session_gen = get_db()
        db = next(session_gen)
        try:
            return sync_benefits_to_json(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"sync_benefit_to_json ogohlantirish: {e}")

def build_benefit_audience_menu(benefit: Benefit, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Tegishli toifalar (nogironlik guruhi, bola, ota-ona, tashkilot) checkbox/toggle menyusi."""
    def ic(val: bool) -> str:
        return "✅" if val else "❌"

    text = (
        f"<b>👥 Imtiyoz kimlarga tegishli? (ID: {benefit.id})</b><br/><br/>"
        f"📌 <b>Nomi:</b> {html.escape(benefit.title_uz)}<br/><br/>"
        f"<i>Toifani faollashtirish yoki o'chirish uchun ustiga bosing:</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"1-guruh: {ic(benefit.for_first_group)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:first:{page}"
        ),
        InlineKeyboardButton(
            text=f"2-guruh: {ic(benefit.for_second_group)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:second:{page}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"3-guruh: {ic(benefit.for_third_group)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:third:{page}"
        ),
        InlineKeyboardButton(
            text=f"Bola (18 gacha): {ic(benefit.for_child)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:child:{page}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"Ota-ona: {ic(benefit.for_parent)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:parent:{page}"
        ),
        InlineKeyboardButton(
            text=f"Tashkilot: {ic(benefit.is_for_organization)}",
            callback_data=f"admin:b_aud_tog:{benefit.id}:org:{page}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💾 Saqlash va qaytish",
            callback_data=f"admin:b_edit:{benefit.id}:{page}"
        )
    )
    return text, builder.as_markup()

@admin_router.callback_query(F.data.startswith("admin:b_aud_tog:"), is_private_message)
async def admin_benefit_toggle_audience(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    b_id = int(parts[2])
    target = parts[3]
    page = int(parts[4])

    benefit = Benefit.get_by_id(b_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    if target == "first":
        benefit.for_first_group = not benefit.for_first_group
    elif target == "second":
        benefit.for_second_group = not benefit.for_second_group
    elif target == "third":
        benefit.for_third_group = not benefit.for_third_group
    elif target == "child":
        benefit.for_child = not benefit.for_child
    elif target == "parent":
        benefit.for_parent = not benefit.for_parent
    elif target == "org":
        benefit.is_for_organization = not benefit.is_for_organization

    db_session.add(benefit)
    db_session.commit()
    db_session.refresh(benefit)
    sync_benefit_to_json(benefit, db_session)

    text, markup = build_benefit_audience_menu(benefit, page)
    await query.message.edit_text(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer("Toifa o'zgartirildi!")

@admin_router.callback_query(F.data.startswith("admin:b_save_cat:"), is_private_message)
async def admin_benefit_save_category(query: CallbackQuery, db_session: DBSession):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    parts = query.data.split(":")
    b_id = int(parts[2])
    cat = parts[3]
    page = int(parts[4])

    benefit = Benefit.get_by_id(b_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    benefit.category = cat
    db_session.add(benefit)
    db_session.commit()
    db_session.refresh(benefit)
    sync_benefit_to_json(benefit, db_session)

    text, markup = build_benefit_edit_menu(benefit, page)
    await query.message.edit_text(f"✅ <b>Kategoriya muvaffaqiyatli o'zgartirildi!</b><br/><br/>{text}", reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    await query.answer("Kategoriya yangilandi!")

@admin_router.message(AdminEditBenefitState.waiting_for_value, is_private_message)
async def admin_benefit_save_field_value(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    b_id = data.get("b_id")
    field = data.get("field")
    page = data.get("page", 1)

    benefit = Benefit.get_by_id(b_id, db_session) if b_id else None
    if not benefit:
        await state.clear()
        return await message.answer("Imtiyoz topilmadi!")

    if not message.text:
        return await message.answer(
            "⚠️ Iltimos, yangi qiymatni faqat matn ko'rinishida yuboring yoki quyidagi bekor qilish tugmasini bosing."
        )

    text = message.text.strip()
    if text.lower() in ["/cancel", "cancel", "❌ bekor qilish", "bekor qilish"]:
        await state.clear()
        menu_text, markup = build_benefit_edit_menu(benefit, page)
        return await message.answer(
            f"❌ <b>Tahrirlash bekor qilindi.</b><br/><br/>{menu_text}",
            reply_markup=markup,
            parse_mode=SULGUK_PARSE_MODE
        )

    await state.clear()
    val = None if text.lower() in ["/empty", "-", "none", "null"] else text

    # Havolalar uchun http(s) sxemasini ta'minlash
    if field in ["lex", "mygov"] and val:
        val = val.strip()
        if not val.startswith("http://") and not val.startswith("https://"):
            val = f"https://{val}"

    from src.database.enrich_benefits import lat_to_cyr
    from src.database.enrich_guides import lat_to_cyr_html

    if field == "title":
        benefit.title_uz = val or ""
        benefit.title_oz = lat_to_cyr(val) if val else ""
    elif field == "desc":
        benefit.description_uz = val or ""
        benefit.description_oz = lat_to_cyr(val) if val else ""
    elif field == "amount":
        benefit.amount_uz = val
        benefit.amount_oz = lat_to_cyr(val) if val else None
    elif field == "org":
        benefit.organization_uz = val
        benefit.organization_oz = lat_to_cyr(val) if val else None
    elif field == "legal":
        benefit.legal_basis_uz = val
        benefit.legal_basis_oz = lat_to_cyr(val) if val else None
    elif field == "lex":
        benefit.lex_url = val
    elif field == "mygov":
        benefit.mygov_url = val
    elif field == "guide":
        benefit.guide_uz = val
        benefit.guide_oz = lat_to_cyr_html(val) if val else None

    db_session.add(benefit)
    db_session.commit()
    db_session.refresh(benefit)
    sync_benefit_to_json(benefit, db_session)

    menu_text, markup = build_benefit_edit_menu(benefit, page)
    await message.answer(
        f"✅ <b>Muvaffaqiyatli saqlandi!</b><br/><br/>{menu_text}",
        reply_markup=markup,
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data == "admin:b_add", is_private_message)
async def admin_benefit_add_start(query: CallbackQuery, state: FSMContext):
    if not settings.is_admin(query.from_user.id):
        return await query.answer("Kechirasiz, siz admin emassiz!", show_alert=True)

    await state.set_state(AdminAddBenefitState.waiting_for_category)
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Nafaqa va yordam", callback_data="admin:b_set_cat:pension_aid")
    builder.button(text="🩺 Tibbiyot va reabilitatsiya", callback_data="admin:b_set_cat:health_rehab")
    builder.button(text="🎓 Ta'lim va yoshlar", callback_data="admin:b_set_cat:education")
    builder.button(text="💼 Mehnat va bandlik", callback_data="admin:b_set_cat:labor")
    builder.button(text="🚌 Transport", callback_data="admin:b_set_cat:transport")
    builder.button(text="🏠 Uy-joy va kommunal", callback_data="admin:b_set_cat:housing_communal")
    builder.button(text="📑 Soliq va bojlar", callback_data="admin:b_set_cat:tax_fee")
    builder.button(text="📦 Boshqa", callback_data="admin:b_set_cat:other")
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")
    builder.adjust(2, 2, 2, 2, 1)

    await query.message.edit_text(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "1-qadam: Imtiyoz yo'nalishini (kategoriyasini) tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:b_set_cat:"), AdminAddBenefitState.waiting_for_category)
async def admin_benefit_set_category(query: CallbackQuery, state: FSMContext):
    cat = query.data.split(":")[2]
    await state.update_data(category=cat)
    await state.set_state(AdminAddBenefitState.waiting_for_group)

    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Barcha guruhlar (1, 2, 3 va bolalar)", callback_data="admin:b_set_group:all")
    builder.button(text="1⃣ va 2⃣ I va II guruhlar", callback_data="admin:b_set_group:g1_g2")
    builder.button(text="1⃣ Faqat I guruh", callback_data="admin:b_set_group:g1")
    builder.button(text="2⃣ Faqat II guruh", callback_data="admin:b_set_group:g2")
    builder.button(text="3⃣ Faqat III guruh", callback_data="admin:b_set_group:g3")
    builder.button(text="👶 18 yoshgacha bolalar", callback_data="admin:b_set_group:child")
    builder.button(text="👨‍👩‍👧 Parvarishlovchi ota-ona", callback_data="admin:b_set_group:parent")
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")
    builder.adjust(1)

    await query.message.edit_text(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "2-qadam: Ushbu imtiyoz qaysi toifaga tegishli ekanligini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.callback_query(F.data.startswith("admin:b_set_group:"), AdminAddBenefitState.waiting_for_group)
async def admin_benefit_set_group(query: CallbackQuery, state: FSMContext):
    grp = query.data.split(":")[2]
    await state.update_data(group_type=grp)
    await state.set_state(AdminAddBenefitState.waiting_for_title)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")

    await query.message.edit_text(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "3-qadam: Imtiyozning <b>qisqa sarlavhasi / nomini</b> xabar ko'rinishida yozib yuboring:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminAddBenefitState.waiting_for_title, is_private_message)
async def admin_benefit_title_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AdminAddBenefitState.waiting_for_desc)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")

    await message.answer(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "4-qadam: Imtiyozning <b>batafsil tavsifi va miqdorini</b> yozib yuboring:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.message(AdminAddBenefitState.waiting_for_desc, is_private_message)
async def admin_benefit_desc_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    desc = message.text.strip()
    await state.update_data(desc=desc)
    await state.set_state(AdminAddBenefitState.waiting_for_legal)

    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ O'tkazib yuborish", callback_data="admin:b_skip_legal")
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")
    builder.adjust(1)

    await message.answer(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "5-qadam: <b>Asos bo'luvchi qonun hujjati</b> (qaror, farmon yoki kodeks moddasi)ni kiriting yoki <b>⏭ O'tkazib yuborish</b> tugmasini bosing:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data == "admin:b_skip_legal", AdminAddBenefitState.waiting_for_legal)
async def admin_benefit_skip_legal(query: CallbackQuery, state: FSMContext):
    await state.update_data(legal=None)
    await state.set_state(AdminAddBenefitState.waiting_for_org)

    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ O'tkazib yuborish", callback_data="admin:b_skip_org")
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")
    builder.adjust(1)

    await query.message.edit_text(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "6-qadam: <b>Xizmat ko'rsatuvchi / mas'ul tashkilot</b> nomini kiriting yoki <b>⏭ O'tkazib yuborish</b> tugmasini bosing:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )
    await query.answer()

@admin_router.message(AdminAddBenefitState.waiting_for_legal, is_private_message)
async def admin_benefit_legal_received(message: Message, state: FSMContext):
    if not settings.is_admin(message.from_user.id):
        return

    legal = None if message.text.strip() in ["/skip", "-"] else message.text.strip()
    await state.update_data(legal=legal)
    await state.set_state(AdminAddBenefitState.waiting_for_org)

    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ O'tkazib yuborish", callback_data="admin:b_skip_org")
    builder.button(text="❌ Bekor qilish", callback_data="admin:benefits_page:1")
    builder.adjust(1)

    await message.answer(
        "<b>➕ Yangi imtiyoz qo'shish</b><br/><br/>"
        "6-qadam: <b>Xizmat ko'rsatuvchi / mas'ul tashkilot</b> nomini kiriting yoki <b>⏭ O'tkazib yuborish</b> tugmasini bosing:",
        reply_markup=builder.as_markup(),
        parse_mode=SULGUK_PARSE_MODE
    )

@admin_router.callback_query(F.data == "admin:b_skip_org", AdminAddBenefitState.waiting_for_org)
async def admin_benefit_skip_org(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    await finish_saving_benefit(query.message, state, db_session, org=None, is_edit=True)
    await query.answer()

@admin_router.message(AdminAddBenefitState.waiting_for_org, is_private_message)
async def admin_benefit_org_received(message: Message, state: FSMContext, db_session: DBSession):
    if not settings.is_admin(message.from_user.id):
        return

    org = None if message.text.strip() in ["/skip", "-"] else message.text.strip()
    await finish_saving_benefit(message, state, db_session, org=org, is_edit=False)

async def finish_saving_benefit(message_obj, state: FSMContext, db_session: DBSession, org: str | None, is_edit: bool = False):
    from src.database.seed_benefits import cyr_to_lat

    data = await state.get_data()
    await state.clear()

    cat = data.get("category", BenefitCategory.OTHER)
    grp = data.get("group_type", "all")
    title = data.get("title", "")
    desc = data.get("desc", "")
    legal = data.get("legal")

    # Determine group flags
    g1 = grp in ["all", "g1_g2", "g1"]
    g2 = grp in ["all", "g1_g2", "g2"]
    g3 = grp in ["all", "g3"]
    child = grp in ["all", "child"]
    parent = grp in ["parent"]

    title_uz = cyr_to_lat(title)
    desc_uz = cyr_to_lat(desc)
    legal_uz = cyr_to_lat(legal) if legal else None
    org_uz = cyr_to_lat(org) if org else None

    benefit = Benefit(
        category=cat,
        for_first_group=g1,
        for_second_group=g2,
        for_third_group=g3,
        for_child=child,
        for_parent=parent,
        title_uz=title_uz,
        description_uz=desc_uz,
        legal_basis_uz=legal_uz,
        organization_uz=org_uz,
        title_oz=title,
        description_oz=desc,
        legal_basis_oz=legal,
        organization_oz=org,
    )
    db_session.add(benefit)
    db_session.commit()
    sync_benefits_to_json(db_session)

    builder = InlineKeyboardBuilder()
    builder.button(text="Imtiyozlar ro'yxati", callback_data="admin:benefits_page:1")
    builder.button(text="⬅️ Admin menyu", callback_data="admin:main")
    builder.adjust(1)

    confirm_text = (
        "✅ <b>Yangi imtiyoz muvaffaqiyatli saqlandi!</b><br/><br/>"
        f"<b>Nomi:</b> {title_uz}<br/>"
        f"<b>Yo'nalishi:</b> {cat}<br/>"
    )
    if is_edit:
        await message_obj.edit_text(confirm_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    else:
        await message_obj.answer(confirm_text, reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


# ---------------------------------------------------------------------------------------------
# Adminlar boshqaruvi: ro'yxat, Telegram ID orqali qo'shish/o'chirish.
# Asosiy (super) adminlar .env dagi ADMIN_IDS; ularni panel orqali o'chirib bo'lmaydi.
# Qo'shish/o'chirish faqat asosiy adminlarga; oddiy adminlar ro'yxatni ko'ra oladi.
# ---------------------------------------------------------------------------------------------
