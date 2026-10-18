import html
import math
import re
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"

from src.app.filters import is_private_message
from src.app.keyboards import (
    get_benefit_categories_keyboard,
    get_benefits_list_keyboard,
    get_benefit_detail_keyboard,
    get_benefit_guide_keyboard,
    get_benefit_search_keyboard,
    get_role_menu,
)
from src.app.translations import t, LANG_UZ
from src.config.settings import settings
from src.models.benefit import Benefit, BenefitCategory
from src.models.user import User
from src.app.inquiry_card import benefit_header_html, payload_from_message
from src.app.question_delivery import post_inquiry_to_group
from src.routes.deps.db_session import DBSession

benefits_router = Router(name="benefits")

PAGE_SIZE = 5


def get_user_matching_benefits(user: User | None, db_session: DBSession, category: str | None = None) -> list[Benefit]:
    """Foydalanuvchi ma'lumotlariga mos keladigan imtiyozlarni topish."""
    age = (datetime.now().year - user.birth_year) if (user and user.birth_year) else None
    gender = user.gender.value if (user and user.gender and hasattr(user.gender, "value")) else (str(user.gender) if (user and user.gender) else None)
    d_type = user.disability_type.value if (user and user.disability_type and hasattr(user.disability_type, "value")) else (str(user.disability_type) if (user and user.disability_type) else None)
    d_state = user.disability_state.value if (user and user.disability_state and hasattr(user.disability_state, "value")) else (str(user.disability_state) if (user and user.disability_state) else None)

    cat_filter = None if category in [None, "all"] else category
    return Benefit.get_user_benefits(
        session=db_session,
        category=cat_filter,
        disability_type=d_type,
        disability_state=d_state,
        age=age,
        gender=gender,
    )


def _format_beneficiaries(text: str) -> str:
    if not text:
        return ""
    # Semicolons followed by number or bullet or list item
    parts = re.split(r";\s*(?=\d+[\.\)]|•|\-|\n)", text)
    if len(parts) > 1:
        res = []
        for p in parts:
            p = p.strip()
            if p:
                if not re.match(r"^(\d+[\.\)]|•|\-)", p):
                    res.append(f"• {p}")
                else:
                    res.append(p)
        return "<br/>".join(res)
    # If already has newlines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) > 1:
        res = []
        for l in lines:
            if not re.match(r"^(\d+[\.\)]|•|\-)", l):
                res.append(f"• {l}")
            else:
                res.append(l)
        return "<br/>".join(res)
    return text


def parse_benefit_content(desc: str, amount: str = "") -> tuple[str, str]:
    who = ""
    amt = amount or ""

    m_who = re.search(
        r"(?:Kimlarga|Кимларга|Кому)\s*:\s*(.*?)(?=(?:Miqdori|Миқдори|Размер)\s*:|$)",
        desc,
        re.DOTALL | re.IGNORECASE,
    )
    if m_who:
        who = m_who.group(1).strip()
    else:
        who = desc.strip()

    if not amt:
        m_amt = re.search(
            r"(?:Miqdori|Миқдори|Размер)\s*:\s*(.*)",
            desc,
            re.DOTALL | re.IGNORECASE,
        )
        if m_amt:
            amt = m_amt.group(1).strip()

    who = re.sub(r"([a-z‘\'])(I{1,3}\s+va\s+)", r"\1, \2", who)
    who = re.sub(r"([a-z‘\'])([A-ZА-ЯЁҚҒҲЎ])", r"\1, \2", who)
    who = re.sub(r";\s*(\d+[\.\)])", r";\n\1", who)
    who = re.sub(r"\s+", " ", who).strip()

    amt = re.sub(r"\s+", " ", amt).strip()
    return who, amt


BENEFIT_CATEGORY_TO_INQUIRY_SECTION = {
    BenefitCategory.PENSION_AID: "🛡  Ijtimoiy himoya",
    BenefitCategory.HEALTH_REHAB: "🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya",
    BenefitCategory.EDUCATION: "👨🏻‍🎓 Ta’lim",
    BenefitCategory.LABOR: "👩🏻‍💼 Mehnat",
    BenefitCategory.HOUSING_COMMUNAL: "🏘  Uy-joy",
    BenefitCategory.TRANSPORT: "🛡  Ijtimoiy himoya",
    BenefitCategory.TAX_FEE: "🛡  Ijtimoiy himoya",
    BenefitCategory.OTHER: "Boshqa",
}


DOC_ID_TO_NUMBER = {
    "7215989": "389",
    "7386982": "64",
    "5049511": "641",
    "5055690": "642",
    "6905497": "253",
    "6411319": "119",
    "3765153": "417",
    "6076304": "341",
    "2529674": "361",
    "5789981": "57",
    "5426278": "5114",
    "5342462": "6195",
    "6391378": "74",
    "152415": "3079",
    "5927153": "3163",
    "4674902": "soliq",
    "6257288": "mehnat",
}

ENACTMENT_PATTERNS = [
    # Soliq kodeksi
    (r"(?:soliq|солиқ|налогов)[a-zа-яёқғҳў\s\-]*kodeks", "https://lex.uz/docs/-4674902"),
    # Mehnat kodeksi
    (r"(?:mehnat|меҳнат|трудов)[a-zа-яёқғҳў\s\-]*kodeks", "https://lex.uz/docs/-6257288"),
    # Qonunlar (O‘RQ / ЎРҚ / ЗРУ)
    (r"(?:o‘rq|o'rq|ўрқ|зру)[\s\-_]*641\b|(?<!\d)641(?!\d)[a-zа-яёқғҳў\s\-]*(?:qonun|қонун|закон)", "https://lex.uz/docs/-5049511"),
    (r"(?:o‘rq|o'rq|ўрқ|зру)[\s\-_]*642\b|(?<!\d)642(?!\d)[a-zа-яёқғҳў\s\-]*(?:qonun|қонун|закон)", "https://lex.uz/docs/-5055690"),
    # Hukumat qarorlari (VMQ / ВМҚ / ПКМ / Vazirlar Mahkamasi)
    (r"(?:vmq|вмқ|пкм)[\s\-_]*253\b|(?:vazirlar|вазирлар|кабинет)[a-zа-яёқғҳў\s\-]+(?<!\d)253(?!\d)", "https://lex.uz/docs/-6905497"),
    (r"(?:vmq|вмқ|пкм)[\s\-_]*119\b|(?:vazirlar|вазирлар|кабинет)[a-zа-яёқғҳў\s\-]+(?<!\d)119(?!\d)", "https://lex.uz/docs/-6411319"),
    (r"(?:vmq|вмқ|пкм)[\s\-_]*417\b|(?:vazirlar|вазирлар|кабинет)[a-zа-яёқғҳў\s\-]+(?<!\d)417(?!\d)", "https://lex.uz/docs/-3765153"),
    (r"(?:vmq|вмқ|пкм)[\s\-_]*341\b|(?:vazirlar|вазирлар|кабинет)[a-zа-яёқғҳў\s\-]+(?<!\d)341(?!\d)", "https://lex.uz/docs/-6076304"),
    (r"(?:vmq|вмқ|пкм)[\s\-_]*361\b|(?:vazirlar|вазирлар|кабинет)[a-zа-яёқғҳў\s\-]+(?<!\d)361(?!\d)", "https://lex.uz/docs/-2529674"),
    # Prezident qarorlari (PQ / ПҚ / ПП / Prezident qarori)
    (r"(?:pq|пқ|пп)[\s\-_]*389\b|(?:prezident|президент)[a-zа-яёқғҳў\s\-]+(?<!\d)389(?!\d)", "https://lex.uz/docs/-7215989#-7216081"),
    (r"(?:pq|пқ|пп)[\s\-_]*64\b|(?:prezident|президент)[a-zа-яёқғҳў\s\-]+(?<!\d)64(?!\d)", "https://lex.uz/docs/-7386982#-7390576"),
    (r"(?:pq|пқ|пп)[\s\-_]*57\b|(?:prezident|президент)[a-zа-яёқғҳў\s\-]+(?<!\d)57(?!\d)", "https://lex.uz/docs/-5789981"),
    (r"(?:pq|пқ|пп)[\s\-_]*5114\b|(?:prezident|президент)[a-zа-яёқғҳў\s\-]+(?<!\d)5114(?!\d)", "https://lex.uz/docs/-5426278"),
    # Prezident farmonlari (PF / ПФ / УП / Prezident farmoni)
    (r"(?:pf|пф|уп)[\s\-_]*6195\b|(?:farmon|фармон|указ)[a-zа-яёқғҳў\s\-]+(?<!\d)6195(?!\d)", "https://lex.uz/docs/-5342462"),
    (r"(?:pf|пф|уп)[\s\-_]*74\b|(?:farmon|фармон|указ)[a-zа-яёқғҳў\s\-]+(?<!\d)74(?!\d)", "https://lex.uz/docs/-6391378"),
    (r"(?:pf|пф|уп)[\s\-_]*3079\b|(?:farmon|фармон|указ)[a-zа-яёқғҳў\s\-]+(?<!\d)3079(?!\d)", "https://lex.uz/docs/-152415"),
    # Idoraviy hujjatlar
    (r"(?:idoraviy|идоравий|ведомственн)[a-zа-яёқғҳў\s\-]+(?<!\d)3163(?!\d)|\b3163\b", "https://lex.uz/docs/-5927153"),
]


def resolve_enactment_url(doc_title: str) -> str | None:
    for pattern, url in ENACTMENT_PATTERNS:
        if re.search(pattern, doc_title, re.IGNORECASE):
            return url
    return None


def doc_matches_url(doc_text: str, url: str) -> bool:
    """Hujjat matni Lex.uz havolasidagi hujjat raqami bilan mosligini tekshirish."""
    if not url:
        return False
    m = re.search(r'/docs/(-?\d+)', url)
    if m:
        doc_id = m.group(1).lstrip('-')
        num = DOC_ID_TO_NUMBER.get(doc_id)
        if num and re.search(r'(?<!\d)' + re.escape(num) + r'(?!\d)', doc_text):
            return True
    return False


def split_legal_basis(text: str | None) -> list[str]:
    """Qonuniy asos matnini alohida me'yoriy hujjatlarga ajratish."""
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    pattern = r',\s*(?=(?:Prezident|Президент|Постановление|Vazirlar|Вазирлар|Qonun|Қонун|Закон|Указ|Idoraviy|Идоравий|Ведомственный|Soliq|Солиқ|Налоговый|Mehnat|Меҳнат|Трудовой|O‘zbekiston|Ўзбекистон|Hukumat|Ҳукумат|Buyruq|Буйруқ|Приказ|Kodeks|Кодекс|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ|O‘RQ|ЎРҚ|ЗРУ)\b)'
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    cleaned = [p.strip().rstrip(",").strip() for p in parts if p.strip().rstrip(",").strip()]
    if len(cleaned) <= 1:
        # Faqat keyingi qism modda/band/qism kabi davom bo'lmaganda ajratish
        parts = re.split(r'(?<=\))\s*,\s*(?![0-9\s\-]*(?:modda|band|qism|модда|банд|қисм|статья|пункт|часть))', text, flags=re.IGNORECASE)
        cleaned = [p.strip().rstrip(",").strip() for p in parts if p.strip().rstrip(",").strip()]
    return cleaned if cleaned else [text.strip()]


def format_legal_basis_section(legal_basis: str | None, lex_url: str | None, lang: str = "uz") -> str:
    """Hujjatlar soniga qarab tartib raqam va HTML havola bilan chiroyli formatlash."""
    if not legal_basis and not lex_url:
        return ""

    if lang == "oz":
        label = "⚖️ <b>Асос бўлувчи ҳужжат:</b>"
    elif lang == "ru":
        label = "⚖️ <b>Основание (законодательство):</b>"
    else:
        label = "⚖️ <b>Asos bo‘luvchi hujjat:</b>"

    docs = split_legal_basis(legal_basis)
    if not docs:
        if lex_url:
            fallback_title = "Lex.uz qonunchilik hujjati" if lang == "uz" else ("Lex.uz қонунчилик ҳужжати" if lang == "oz" else "Законодательный акт на Lex.uz")
            docs = [fallback_title]
        else:
            return ""

    urls = [u.strip() for u in re.split(r'[\s,;\n]+', lex_url or '') if u.strip().startswith('http')]

    # Agar faqat 1 ta hujjat bo'lsa
    if len(docs) == 1:
        doc_url = urls[0] if urls else resolve_enactment_url(docs[0])
        safe_doc = html.escape(docs[0].strip().rstrip(",").strip())
        if doc_url:
            return f"{label}<br/>1. <a href=\"{doc_url}\">{safe_doc}</a>"
        else:
            return f"{label}<br/>1. {safe_doc}"

    doc_urls: list[str | None] = [None] * len(docs)
    used_urls: set[str] = set()

    # 1. Hujjat va berilgan URL raqami bevosita mos kelsa, o'sha hujjatga biriktirish
    for i, doc in enumerate(docs):
        for u in urls:
            if u not in used_urls and doc_matches_url(doc, u):
                doc_urls[i] = u
                used_urls.add(u)
                break

    # 2. Qolgan hujjatlar uchun ma'lum bo'lgan qonunlar xaritasidan URL qidirish
    for i, doc in enumerate(docs):
        if not doc_urls[i]:
            resolved = resolve_enactment_url(doc)
            if resolved:
                doc_urls[i] = resolved

    # 3. Hali ham URL topilmagan hujjatlarga mavjud ishlatilmagan URL larni tartib bilan biriktirish
    unused_urls = [u for u in urls if u not in used_urls and u not in doc_urls]
    unused_idx = 0
    for i, doc in enumerate(docs):
        if not doc_urls[i] and unused_idx < len(unused_urls):
            doc_urls[i] = unused_urls[unused_idx]
            unused_idx += 1

    items_html = []
    for i, doc in enumerate(docs, start=1):
        clean_doc = doc.strip().rstrip(",").strip()
        doc_url = doc_urls[i - 1]
        safe_doc = html.escape(clean_doc)
        if doc_url:
            items_html.append(f'{i}. <a href="{doc_url}">{safe_doc}</a>')
        else:
            items_html.append(f"{i}. {safe_doc}")

    return f"{label}<br/>" + "<br/>".join(items_html)


def format_guide_html(guide_text: str | None, lang: str = "uz") -> str:
    """Yo'riqnomani tartibli, bo'limlar alohida vizual ajratilgan va statik ortiqchaliklardan tozalangan holatda formatlash."""
    if not guide_text:
        return "<i>Йўриқнома тайёрланмоқда...</i>" if lang == "oz" else (
            "<i>Инструкция подготавливается...</i>" if lang == "ru" else "<i>Yo‘riqnoma tayyorlanmoqda...</i>"
        )

    # 1. Mavjud <br> teglarini yangi qatorlarga normallashtirish
    text = re.sub(r'<br\s*/?>', '\n', guide_text.strip(), flags=re.IGNORECASE)

    # 2. Mexanik '1-blok:', '2-блок:' kabi belgilarni olib tashlash
    text = re.sub(r'(?i)\b\d+\s*-\s*(?:blok|блок)\s*:\s*', '', text)

    # 3. Ortiqcha statik byurokratik eslatmalarni tozalash
    text = re.sub(
        r'<i>\s*\((?:Eslatma|Эслатма|Примечание)[^<]*?(?:taqiqlanadi|тақиқланади|запрещено)\s*\)\s*\.?\s*</i>',
        '',
        text,
        flags=re.IGNORECASE
    )

    # 4. Ortiqcha bo'sh qatorlarni tozalash
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    # 5. Bo'limlar orasida <br/><br/> va qatorlar orasida <br/> qo'yish (Sulguk HTML to'g'ri o'qishi uchun)
    paragraphs = text.split("\n\n")
    formatted_paragraphs = []
    for p in paragraphs:
        p_clean = p.strip()
        if p_clean:
            formatted_paragraphs.append(p_clean.replace("\n", "<br/>"))

    return "<br/><br/>".join(formatted_paragraphs)


def format_benefit_card(benefit: Benefit, lang: str = "uz") -> str:
    """Imtiyoz kartochkasini aniq, rasmiy va go'zal formatda chiqarish."""
    if lang == "oz":
        title = benefit.title_oz or benefit.title_uz
        desc = benefit.description_oz or benefit.description_uz
        amount = benefit.amount_oz or benefit.amount_uz
        org = benefit.organization_oz or benefit.organization_uz
        legal = benefit.legal_basis_oz or benefit.legal_basis_uz

        who_label = "🎯 <b>Кимларга берилади:</b>"
        amt_label = "✨ <b>Имтиёз миқдори ва тартиби:</b>"
        org_label = "🏢 <b>Хизмат кўрсатувчи ташкилот:</b>"
    elif lang == "ru":
        title = benefit.title_ru or benefit.title_uz
        desc = benefit.description_ru or benefit.description_uz
        amount = benefit.amount_ru or benefit.amount_uz
        org = benefit.organization_ru or benefit.organization_uz
        legal = benefit.legal_basis_ru or benefit.legal_basis_uz

        who_label = "🎯 <b>Кому предоставляется:</b>"
        amt_label = "✨ <b>Размер и условия льготы:</b>"
        org_label = "🏢 <b>Предоставляющая организация:</b>"
    else:
        title = benefit.title_uz
        desc = benefit.description_uz
        amount = benefit.amount_uz
        org = benefit.organization_uz
        legal = benefit.legal_basis_uz

        who_label = "🎯 <b>Kimlarga beriladi:</b>"
        amt_label = "✨ <b>Imtiyoz miqdori va tartibi:</b>"
        org_label = "🏢 <b>Xizmat ko‘rsatuvchi tashkilot:</b>"

    who, amt = parse_benefit_content(desc or "", amount or "")

    safe_title = html.escape(title or "")
    safe_who = _format_beneficiaries(html.escape(who or ""))
    safe_amt = html.escape(amt or "")
    safe_org = html.escape(org or "")

    lines = [f"📌 <b>{safe_title}</b>", ""]

    if safe_who:
        lines.append(f"{who_label}<br/>{safe_who}")
        lines.append("")

    if safe_amt:
        lines.append(f"{amt_label}<br/><blockquote>{safe_amt}</blockquote>")
        lines.append("")

    if safe_org:
        lines.append(f"{org_label} {safe_org}")

    # Asos bo'luvchi hujjatlarni tartib raqam va HTML havola bilan joylashtirish
    legal_section = format_legal_basis_section(legal, getattr(benefit, "lex_url", None), lang)
    if legal_section:
        lines.append(legal_section)

    has_daftarlar = any(
        kw in (who or "").lower() or kw in (desc or "").lower() or kw in (title or "").lower()
        for kw in ["daftar", "дафтар", "тетрад"]
    )
    if has_daftarlar:
        lines.append("")
        if lang == "oz":
            lines.append("💡 <b>Эслатма:</b> Амалдаги тартибга кўра, дафтарлар орқали моддий ёрдам ва имтиёзлардан фойдаланиш учун оила аввало «Ижтимоий реестр» ахборот тизимида ҳисобда туриши лозим.")
        elif lang == "ru":
            lines.append("💡 <b>Примечание:</b> Согласно действующему порядку, для получения помощи и льгот через списки («тетради») семья должна состоять на учете в информационной системе «Ижтимоий реестр».")
        else:
            lines.append("💡 <b>Eslatma:</b> Amaldagi tartibga ko‘ra, daftarlar orqali moddiy yordam va imtiyozlardan foydalanish uchun oila avvalo «Ijtimoiy reyestr» axborot tizimida hisobda turishi lozim.")

    return "<br/>".join(lines)


@benefits_router.message(
    F.text.in_([
        t("menu_benefits", "uz"), t("menu_benefits", "oz"), t("menu_benefits", "ru"),
        "✨Imtiyozlarim", "✨Имтиёзларим", "✨Мои льготы",
    ]),
    is_private_message,
)
@benefits_router.message(Command("benefits"), is_private_message)
@benefits_router.message(Command("imtiyozlar"), is_private_message)
async def benefits_main_menu_handler(message: Message, db_session: DBSession, state: FSMContext):
    await state.clear()
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    await message.answer(
        t("benefits_title", lang),
        reply_markup=get_benefit_categories_keyboard(lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@benefits_router.callback_query(F.data == "benefit_back_cats", is_private_message)
async def benefits_back_cats_callback(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    await state.clear()
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    try:
        await query.message.edit_text(
            t("benefits_title", lang),
            reply_markup=get_benefit_categories_keyboard(lang),
            parse_mode=SULGUK_PARSE_MODE,
        )
    except Exception:
        await query.message.answer(
            t("benefits_title", lang),
            reply_markup=get_benefit_categories_keyboard(lang),
            parse_mode=SULGUK_PARSE_MODE,
        )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_cat:"), is_private_message)
async def benefit_category_selected(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    await state.clear()
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ
    category = query.data.split(":")[1]

    benefits = get_user_matching_benefits(user, db_session, category)

    if not benefits:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats")
        await query.message.edit_text(
            t("benefits_empty", lang),
            reply_markup=kb.as_markup(),
            parse_mode=SULGUK_PARSE_MODE,
        )
        return await query.answer()

    total_pages = math.ceil(len(benefits) / PAGE_SIZE)
    current_benefits = benefits[:PAGE_SIZE]

    cat_name = t(f"cat_{category}", lang) if category != "all" else t("cat_all", lang)
    if lang == "oz":
        header_text = f"📂 <b>{cat_name}</b> бўйича сизга тегишли имтиёзлар (жами {len(benefits)} та):"
    elif lang == "ru":
        header_text = f"📂 Льготы для вас по направлению <b>{cat_name}</b> (всего {len(benefits)}):"
    else:
        header_text = f"📂 <b>{cat_name}</b> bo‘yicha sizga tegishli imtiyozlar (jami {len(benefits)} ta):"

    await query.message.edit_text(
        header_text,
        reply_markup=get_benefits_list_keyboard(current_benefits, 1, total_pages, category, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_page:"), is_private_message)
async def benefit_page_callback(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    await state.clear()
    parts = query.data.split(":")
    category = parts[1]
    page = int(parts[2])

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    benefits = get_user_matching_benefits(user, db_session, category)
    total_pages = math.ceil(len(benefits) / PAGE_SIZE)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    current_benefits = benefits[start_idx : start_idx + PAGE_SIZE]

    cat_name = t(f"cat_{category}", lang) if category != "all" else t("cat_all", lang)
    if lang == "oz":
        header_text = f"📂 <b>{cat_name}</b> бўйича сизга тегишли имтиёзлар (жами {len(benefits)} та):"
    elif lang == "ru":
        header_text = f"📂 Льготы для вас по направлению <b>{cat_name}</b> (всего {len(benefits)}):"
    else:
        header_text = f"📂 <b>{cat_name}</b> bo‘yicha sizga tegishli imtiyozlar (jami {len(benefits)} ta):"

    await query.message.edit_text(
        header_text,
        reply_markup=get_benefits_list_keyboard(current_benefits, page, total_pages, category, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_view:"), is_private_message)
async def benefit_view_callback(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    await state.clear()
    parts = query.data.split(":")
    benefit_id = int(parts[1])
    category = parts[2]
    page = int(parts[3])

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    benefit = Benefit.get_by_id(benefit_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    card_text = format_benefit_card(benefit, lang)

    await query.message.edit_text(
        card_text,
        reply_markup=get_benefit_detail_keyboard(
            benefit_id, category, page, lang, benefit=benefit, is_search=(category == "search")
        ),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_guide:"), is_private_message)
async def benefit_guide_callback(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    await state.clear()
    parts = query.data.split(":")
    benefit_id = int(parts[1])
    category = parts[2]
    page = int(parts[3])
    s_flag = parts[4] if len(parts) > 4 else "0"
    is_search = (s_flag == "1") or (category == "search")

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    benefit = Benefit.get_by_id(benefit_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    if lang == "oz":
        title = benefit.title_oz or benefit.title_uz
        guide = benefit.guide_oz or benefit.guide_uz
        hdr = f"📝 <b>{html.escape(title)}</b><br/><i>Қандай ариза топширилади:</i><br/><br/>"
    elif lang == "ru":
        title = benefit.title_ru or benefit.title_uz
        guide = benefit.guide_ru or benefit.guide_uz
        hdr = f"📝 <b>{html.escape(title)}</b><br/><i>Как подать заявление:</i><br/><br/>"
    else:
        title = benefit.title_uz
        guide = benefit.guide_uz
        hdr = f"📝 <b>{html.escape(title)}</b><br/><i>Qanday ariza topshiriladi:</i><br/><br/>"

    guide_text = hdr + format_guide_html(guide, lang)


    await query.message.edit_text(
        guide_text,
        reply_markup=get_benefit_guide_keyboard(
            benefit_id, category, page, lang, benefit=benefit, is_search=is_search
        ),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


class BenefitInquiryState(StatesGroup):
    waiting_for_question = State()


@benefits_router.callback_query(F.data.startswith("benefit_ask:"), is_private_message)
async def benefit_ask_lawyer_start(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    parts = query.data.split(":")
    benefit_id = int(parts[1])
    category = parts[2]
    page = int(parts[3])

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    benefit = Benefit.get_by_id(benefit_id, db_session)
    if not benefit:
        return await query.answer(t("benefits_empty", lang), show_alert=True)

    title = benefit.title_oz if lang == "oz" else (benefit.title_ru if lang == "ru" else benefit.title_uz)

    await state.set_state(BenefitInquiryState.waiting_for_question)
    await state.update_data(
        benefit_id=benefit_id,
        benefit_title=title,
        category=category,
        page=page,
    )

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(
        text=t("btn_cancel", lang),
        callback_data=f"benefit_view:{benefit_id}:{category}:{page}"
    )

    prompt = t("benefit_ask_prompt", lang).format(title=html.escape(title))
    await query.message.edit_text(prompt, reply_markup=cancel_kb.as_markup(), parse_mode=SULGUK_PARSE_MODE)
    await query.answer()


@benefits_router.message(BenefitInquiryState.waiting_for_question, is_private_message)
async def benefit_inquiry_message_received(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if not user:
        await state.clear()
        return await message.answer(t("user_not_found", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    if user.is_blocked:
        await state.clear()
        return await message.answer(t("user_blocked", lang), parse_mode=SULGUK_PARSE_MODE)

    # Bekor qilish tekshiruvi
    if message.text in [
        t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"),
        "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"
    ]:
        data = await state.get_data()
        b_id = data.get("benefit_id")
        cat = data.get("category", "all")
        page = data.get("page", 1)
        await state.clear()
        if b_id:
            benefit = Benefit.get_by_id(b_id, db_session)
            if benefit:
                card_text = format_benefit_card(benefit, lang)
                return await message.answer(
                    card_text,
                    reply_markup=get_benefit_detail_keyboard(b_id, cat, page, lang, benefit=benefit),
                    parse_mode=SULGUK_PARSE_MODE,
                )
        return await message.answer(t("btn_back_main", lang), reply_markup=get_role_menu(message.from_user.id, lang, db_session))

    data = await state.get_data()
    benefit_id = data.get("benefit_id")
    benefit = Benefit.get_by_id(benefit_id, db_session) if benefit_id else None
    benefit_title = data.get("benefit_title") or (benefit.title_uz if benefit else "Imtiyoz")

    # Imtiyoz kategoriyasiga qarab tegishli yuristlar guruhini avtomatik aniqlash
    b_cat = (benefit.category if benefit else None) or data.get("category")
    section_name = BENEFIT_CATEGORY_TO_INQUIRY_SECTION.get(b_cat, "Boshqa")

    inquiry_groups = settings.get_inquiry_groups()
    group_id = inquiry_groups.get(section_name) or inquiry_groups.get("Boshqa") or settings.LAWYER_APPOINTMENT_GROUP_ID

    payload = payload_from_message(message)
    if payload is None:
        return await message.answer(t("inquiry_type_prompt", lang))

    header_text = benefit_header_html(benefit_title, section_name, benefit.lex_url if benefit else None)
    inquiry = await post_inquiry_to_group(
        bot, db_session, user, section_name, group_id, payload, message.message_id,
        header=header_text, benefit_id=benefit_id,
    )

    await state.clear()

    # Tasdiq xabari
    if lang == "oz":
        succ = (
            f"✅ <b>Саволингиз муваффақиятли юборилди (Мурожаат №{inquiry.id})!</b><br/><br/>"
            f"«{html.escape(benefit_title)}» имтиёзи бўйича саволингиз тегишли соҳа («{section_name}») юристлари гуруҳига етказилди. "
            "Жавоб тайёр бўлиши билан бот орқали сизга хабар берилади."
        )
    elif lang == "ru":
        succ = (
            f"✅ <b>Ваш вопрос успешно отправлен (Обращение №{inquiry.id})!</b><br/><br/>"
            f"Ваш вопрос по льготе «{html.escape(benefit_title)}» передан в соответствующую группу юристов («{section_name}»). "
            "Ответ будет отправлен вам через бота, как только юрист его подготовит."
        )
    else:
        succ = (
            f"✅ <b>Savolingiz muvaffaqiyatli yuborildi (Murojaat №{inquiry.id})!</b><br/><br/>"
            f"«{html.escape(benefit_title)}» imtiyozi bo‘yicha savolingiz tegishli soha («{section_name}») yuristlari guruhiga yetkazildi. "
            "Javob tayyor bo‘lishi bilanoq bot orqali sizga xabar beriladi."
        )

    ret_kb = InlineKeyboardBuilder()
    cat = data.get("category", "all")
    page = data.get("page", 1)
    ret_kb.button(text="📌 Imtiyozga qaytish", callback_data=f"benefit_view:{benefit_id}:{cat}:{page}")
    ret_kb.button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats")
    ret_kb.adjust(1)

    await message.answer(succ, reply_markup=ret_kb.as_markup(), parse_mode=SULGUK_PARSE_MODE)


class BenefitSearchState(StatesGroup):
    waiting_for_query = State()


@benefits_router.callback_query(F.data == "benefit_search", is_private_message)
@benefits_router.message(Command("search"), is_private_message)
@benefits_router.message(Command("qidiruv"), is_private_message)
async def benefit_search_start(event: Message | CallbackQuery, state: FSMContext, db_session: DBSession):
    user_id = event.from_user.id
    user = User.get_by_user_id(user_id, db_session)
    lang = user.language if user else LANG_UZ

    await state.set_state(BenefitSearchState.waiting_for_query)

    if lang == "oz":
        prompt = (
            "🔍 <b>Имтиёзларни қидириш:</b><br/><br/>"
            "Қидирмоқчи бўлган имтиёз номи, соҳаси ёки калит сўзни киритинг "
            "(масалан: <i>аравача</i>, <i>санаторий</i>, <i>квота</i>, <i>солиқ</i>):"
        )
    elif lang == "ru":
        prompt = (
            "🔍 <b>Поиск льгот:</b><br/><br/>"
            "Введите наименование льготы, сферу или ключевое слово "
            "(например: <i>коляска</i>, <i>санаторий</i>, <i>квота</i>, <i>налог</i>):"
        )
    else:
        prompt = (
            "🔍 <b>Imtiyozlarni qidirish:</b><br/><br/>"
            "Qidirmoqchi bo‘lgan imtiyoz nomi, sohasi yoki kalit so‘zni kiriting "
            "(masalan: <i>aravacha</i>, <i>sanatoriy</i>, <i>kvota</i>, <i>soliq</i>):"
        )

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.button(text=t("btn_cancel", lang), callback_data="benefit_back_cats")

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(prompt, reply_markup=cancel_kb.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        await event.answer()
    else:
        await event.answer(prompt, reply_markup=cancel_kb.as_markup(), parse_mode=SULGUK_PARSE_MODE)


@benefits_router.message(BenefitSearchState.waiting_for_query, is_private_message)
async def benefit_search_query_received(message: Message, state: FSMContext, db_session: DBSession):
    user = User.get_by_user_id(message.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    if message.text in [
        t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"),
        "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"
    ]:
        await state.clear()
        return await message.answer(
            t("benefits_title", lang),
            reply_markup=get_benefit_categories_keyboard(lang),
            parse_mode=SULGUK_PARSE_MODE,
        )

    query_text = (message.text or "").strip()
    if not query_text:
        return await message.answer(
            "Iltimos, matnli qidiruv so'rovini kiriting."
        )

    benefits = Benefit.search_benefits(session=db_session, query=query_text, lang=lang, user=user)

    if not benefits:
        kb = InlineKeyboardBuilder()
        new_search_text = "🔍 Янги қидирув" if lang == "oz" else ("🔍 Новый поиск" if lang == "ru" else "🔍 Yangi qidiruv")
        kb.button(text=new_search_text, callback_data="benefit_search")
        kb.button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats")
        kb.adjust(1)

        if lang == "oz":
            empty_text = f"🔍 «{html.escape(query_text)}» бўйича ҳеч қандай имтиёз топилмади.<br/><br/>Бошқа калит сўз билан қидириб кўринг."
        elif lang == "ru":
            empty_text = f"🔍 По запросу «{html.escape(query_text)}» ничего не найдено.<br/><br/>Попробуйте изменить поисковый запрос."
        else:
            empty_text = f"🔍 «{html.escape(query_text)}» bo‘yicha hech qanday imtiyoz topilmadi.<br/><br/>Boshqa kalit so‘z bilan qidirib ko‘ring."

        await message.answer(empty_text, reply_markup=kb.as_markup(), parse_mode=SULGUK_PARSE_MODE)
        return

    total_pages = math.ceil(len(benefits) / PAGE_SIZE)
    current_benefits = benefits[:PAGE_SIZE]

    await state.update_data(
        search_query=query_text,
        search_ids=[b.id for b in benefits],
    )

    if lang == "oz":
        header_text = f"🔍 «{html.escape(query_text)}» бўйича топилган имтиёзлар (жами {len(benefits)} та):"
    elif lang == "ru":
        header_text = f"🔍 Результаты поиска по запросу «{html.escape(query_text)}» (всего {len(benefits)}):"
    else:
        header_text = f"🔍 «{html.escape(query_text)}» bo‘yicha topilgan imtiyozlar (jami {len(benefits)} ta):"

    await message.answer(
        header_text,
        reply_markup=get_benefit_search_keyboard(current_benefits, 1, total_pages, query_text, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@benefits_router.callback_query(F.data.startswith("benefit_spage:"), is_private_message)
async def benefit_search_page_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    page = int(query.data.split(":")[1])
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    data = await state.get_data()
    search_ids = data.get("search_ids", [])
    query_text = data.get("search_query", "")

    benefits = []
    if search_ids:
        for bid in search_ids:
            b = Benefit.get_by_id(bid, db_session)
            if b:
                benefits.append(b)
    elif query_text:
        benefits = Benefit.search_benefits(session=db_session, query=query_text, lang=lang, user=user)

    if not benefits:
        return await query.answer("Qidiruv natijalari eskirgan, yangi qidiruv bering.", show_alert=True)

    total_pages = math.ceil(len(benefits) / PAGE_SIZE)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    current_benefits = benefits[start_idx : start_idx + PAGE_SIZE]

    if lang == "oz":
        header_text = f"🔍 «{html.escape(query_text)}» бўйича топилган имтиёзлар (жами {len(benefits)} та):"
    elif lang == "ru":
        header_text = f"🔍 Результаты поиска по запросу «{html.escape(query_text)}» (всего {len(benefits)}):"
    else:
        header_text = f"🔍 «{html.escape(query_text)}» bo‘yicha topilgan imtiyozlar (jami {len(benefits)} ta):"

    await query.message.edit_text(
        header_text,
        reply_markup=get_benefit_search_keyboard(current_benefits, page, total_pages, query_text, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_sview:"), is_private_message)
async def benefit_search_view_callback(query: CallbackQuery, db_session: DBSession, state: FSMContext):
    parts = query.data.split(":")
    benefit_id = int(parts[1])
    page = int(parts[2])

    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    benefit = Benefit.get_by_id(benefit_id, db_session)
    if not benefit:
        return await query.answer("Imtiyoz topilmadi!", show_alert=True)

    card_text = format_benefit_card(benefit, lang)

    await query.message.edit_text(
        card_text,
        reply_markup=get_benefit_detail_keyboard(
            benefit_id, "search", page, lang, benefit=benefit, is_search=True
        ),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()


@benefits_router.callback_query(F.data.startswith("benefit_search_back:"), is_private_message)
async def benefit_search_back_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    page = int(query.data.split(":")[1])
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = user.language if user else LANG_UZ

    data = await state.get_data()
    search_ids = data.get("search_ids", [])
    query_text = data.get("search_query", "")

    benefits = []
    if search_ids:
        for bid in search_ids:
            b = Benefit.get_by_id(bid, db_session)
            if b:
                benefits.append(b)
    elif query_text:
        benefits = Benefit.search_benefits(session=db_session, query=query_text, lang=lang, user=user)

    if not benefits:
        await query.message.edit_text(
            t("benefits_title", lang),
            reply_markup=get_benefit_categories_keyboard(lang),
            parse_mode=SULGUK_PARSE_MODE,
        )
        return await query.answer()

    total_pages = math.ceil(len(benefits) / PAGE_SIZE)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    current_benefits = benefits[start_idx : start_idx + PAGE_SIZE]

    if lang == "oz":
        header_text = f"🔍 «{html.escape(query_text)}» бўйича топилган имтиёзлар (жами {len(benefits)} та):"
    elif lang == "ru":
        header_text = f"🔍 Результаты поиска по запросу «{html.escape(query_text)}» (всего {len(benefits)}):"
    else:
        header_text = f"🔍 «{html.escape(query_text)}» bo‘yicha topilgan imtiyozlar (jami {len(benefits)} ta):"

    await query.message.edit_text(
        header_text,
        reply_markup=get_benefit_search_keyboard(current_benefits, page, total_pages, query_text, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )
    await query.answer()
