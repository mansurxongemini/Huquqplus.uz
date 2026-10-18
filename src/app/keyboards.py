from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.app.translations import t


inquiry_sections_uz = {
    '🛡  Ijtimoiy himoya': 1470,
    '👨🏻‍🎓 Ta’lim': 1441,
    '👩🏻‍💼 Mehnat': 1466,
    '🏘  Uy-joy': 1340,
    '🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya': 1349,
    '⚖️ Sud-huquq': 1477,
    '🚍 Transport': 1346,
    "🧒🏻 Bolalar": 1458,
    "🧑🏻 Yoshlar": 1451,
    "👩🏻 Ayollar": 1447,
    "🗒 Temir, yoshlar va ayollar daftari": 1355,
    "🏢 Tadbirkorlik": 1439
}

inquiry_sections_oz = {
    '🛡  Ижтимоий ҳимоя': 1470,
    '👨🏻‍🎓 Таълим': 1441,
    '👩🏻‍💼 Меҳнат': 1466,
    '🏘  Уй-жой': 1340,
    '🧑🏻‍⚕ Тиббий хизмат ва реабилитация': 1349,
    '⚖️ Суд-ҳуқуқ': 1477,
    '🚍 Транспорт': 1346,
    "🧒🏻 Болалар": 1458,
    "🧑🏻 Ёшлар": 1451,
    "👩🏻 Аёллар": 1447,
    "🗒 Темир, ёшлар ва аёллар дафтари": 1355,
    "🏢 Тадбиркорлик": 1439
}

inquiry_sections_ru = {
    '🛡  Социальная защита': 1470,
    '👨🏻‍🎓 Образование': 1441,
    '👩🏻‍💼 Труд': 1466,
    '🏘  Жилье': 1340,
    '🧑🏻‍⚕ Медицинские услуги и реабилитация': 1349,
    '⚖️ Судебно-правовая сфера': 1477,
    '🚍 Транспорт': 1346,
    "🧒🏻 Дети": 1458,
    "🧑🏻 Молодежь": 1451,
    "👩🏻 Женщины": 1447,
    "🗒 Железная, молодежная и женская тетради": 1355,
    "🏢 Предпринимательство": 1439
}

# Compatibility mapping combining all
inquiry_sections = {**inquiry_sections_uz, **inquiry_sections_ru, **inquiry_sections_oz}

# Soha nomlarining kanonik (uz) tartibi — admin toggle va biriktirish uchun
section_names_uz = list(inquiry_sections_uz.keys())


def normalize_section_name(name: str | None) -> str | None:
    """Soha nomini kanonik uz shakliga keltirish (yagona manba: yuqoridagi lug'atlar).

    Istalgan tildagi (uz/oz/ru) soha nomi shu sohaning uz nomiga almashadi;
    ro'yxatda yo'q nom o'zgarishsiz qaytadi.
    """
    if not name:
        return name
    key = name.strip()
    if key in inquiry_sections_uz:
        return key
    section_id = inquiry_sections.get(key)
    if section_id is None:
        return name
    for uz_name, uz_id in inquiry_sections_uz.items():
        if uz_id == section_id:
            return uz_name
    return name


def get_inquiry_sections(lang: str = "uz") -> dict[str, int]:
    if lang == "ru":
        return inquiry_sections_ru
    elif lang == "oz":
        return inquiry_sections_oz
    return inquiry_sections_uz


main_menu_items = {
    'profile': "🪪 Profil",
    'inquiry': "📩 Savol yuborish",
    'lawyer_appointment': "✍️ Yurist qabuliga yozilish",
    'about_us': "ℹ️ Biz haqimizda",
    'help': "⁉️ Texnik yordam",
    'change_lang': "🌐 Tilni o'zgartirish",
}


def get_language_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz")
    builder.button(text="🇺🇿 Ўзбекча", callback_data="set_lang:oz")
    builder.button(text="🇷🇺 Русский", callback_data="set_lang:ru")
    return builder.adjust(2, 1).as_markup()


def get_main_menu(lang: str = "uz", user_id: int | None = None, db_session=None, show_volunteer_panel: bool = False):
    """Fuqaro menyusi. user_id berilsa rolga qarab (volontyorga — volontyor paneli) qaytaradi."""
    if user_id and db_session is not None and is_volunteer_menu_user(user_id, db_session) and not show_volunteer_panel:
        return get_volunteer_menu(lang)
    main_menu = ReplyKeyboardBuilder()
    main_menu.button(text=t("menu_profile", lang))
    main_menu.button(text=t("menu_benefits", lang))
    main_menu.button(text=t("menu_inquiry", lang))
    main_menu.button(text=t("menu_appointment", lang))
    main_menu.button(text=t("menu_my_inquiries", lang))
    main_menu.button(text=t("menu_about_us", lang))
    main_menu.button(text=t("menu_help", lang))
    main_menu.button(text=t("btn_change_lang", lang))
    if show_volunteer_panel:
        main_menu.button(text=t("menu_vol_panel", lang))
    return main_menu.adjust(2).as_markup(resize_keyboard=True)


def is_volunteer_menu_user(user_id: int, db_session) -> bool:
    """Faol volontyor (admin yoki yurist bo'lsa ham) volontyor panelini oladi."""
    from src.models.volunteer import Volunteer
    try:
        vol = Volunteer.get_by_user_id(user_id, db_session)
        return bool(vol and vol.is_active)
    except Exception:
        return False


def get_role_menu(user_id: int, lang: str = "uz", db_session=None):
    """Bitta joydagi rol-wrapper: barcha "asosiy menyuga qaytish" joylari shuni chaqiradi."""
    return get_main_menu(lang, user_id=user_id, db_session=db_session)


def get_volunteer_menu(lang: str = "uz"):
    vol_menu = ReplyKeyboardBuilder()
    vol_menu.button(text=t("menu_vol_assigns", lang))
    vol_menu.button(text=t("menu_vol_review", lang))
    vol_menu.button(text=t("menu_vol_result", lang))
    vol_menu.button(text=t("menu_vol_sections", lang))
    vol_menu.button(text=t("menu_vol_citizen", lang))
    return vol_menu.adjust(1, 1, 2, 1).as_markup(resize_keyboard=True)


MENU_BUTTON_KEYS = (
    "menu_profile", "menu_benefits", "menu_inquiry", "menu_appointment", "menu_my_inquiries",
    "menu_about_us", "menu_help", "btn_change_lang", "menu_ai", "btn_back_main",
    "menu_vol_result", "menu_vol_assigns", "menu_vol_review", "menu_vol_citizen", "menu_vol_panel",
    "menu_vol_sections",
)


def menu_button_texts() -> frozenset[str]:
    """Pastki menyu tugmalari matnlari (3 tilda). Ular hech qachon foydalanuvchi kiritmasi emas."""
    return frozenset(t(key, lang) for key in MENU_BUTTON_KEYS for lang in ("uz", "oz", "ru"))


def get_ai_chat_menu(lang: str = "uz"):
    builder = ReplyKeyboardBuilder()
    builder.button(text=t("btn_new_ai_chat", lang))
    builder.button(text=t("btn_back_main", lang))
    return builder.adjust(2).as_markup(resize_keyboard=True)


def get_agreement_keyboard(callback_data: str = "understood_about_us", lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_understood", lang), callback_data=callback_data)
    return builder.as_markup()


def inquiry_main_menu(lang: str = "uz"):
    main_menu = ReplyKeyboardBuilder()
    sections = get_inquiry_sections(lang)
    for key in sections.keys():
        main_menu.button(text=key)
    main_menu.button(text=t("btn_back_main", lang))
    return main_menu.adjust(2).as_markup(resize_keyboard=True)


def get_rating_keyboard(item_type: str, item_id: int):
    builder = InlineKeyboardBuilder()
    for star in range(1, 6):
        builder.button(text=f"⭐ {star}", callback_data=f"rate:{item_type}:{item_id}:{star}")
    return builder.adjust(5).as_markup()


def get_low_rating_action_keyboard(inquiry_id: int | None = None, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    cb_data = f"user:inquiry:followup:{inquiry_id}" if inquiry_id else "inquiry:ask_again"
    builder.button(text=t("btn_ask_again", lang), callback_data=cb_data)
    return builder.as_markup()


def get_inquiries_archive_keyboard(inquiries, page: int, total_pages: int, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for inq in inquiries:
        status_icon = "🟢" if inq.status == "replied" else ("🟡" if inq.status == "active" else ("🔴" if inq.status == "cancelled" else "⚪️"))
        section_short = inq.section_name[:20] if inq.section_name else "Murojaat"
        builder.button(
            text=f"{status_icon} №{inq.id} • {section_short}",
            callback_data=f"user:inquiry:view:{inq.id}"
        )
    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardBuilder().button(text="⬅️", callback_data=f"user:archive:page:{page - 1}").as_markup().inline_keyboard[0][0])
    nav_buttons.append(InlineKeyboardBuilder().button(text=f"📄 {page}/{max(total_pages, 1)}", callback_data="noop").as_markup().inline_keyboard[0][0])
    if page < total_pages:
        nav_buttons.append(InlineKeyboardBuilder().button(text="➡️", callback_data=f"user:archive:page:{page + 1}").as_markup().inline_keyboard[0][0])

    if nav_buttons:
        builder.row(*nav_buttons)

    close_text = "❌ Ёпиш" if lang == "oz" else ("❌ Yopish" if lang == "uz" else "❌ Закрыть")
    builder.row(
        InlineKeyboardBuilder().button(text=close_text, callback_data="user:archive:close").as_markup().inline_keyboard[0][0]
    )
    return builder.as_markup()


def get_inquiry_detail_keyboard(inquiry, lang: str = "uz"):
    builder = InlineKeyboardBuilder()

    # If question has media
    if inquiry.question_mediatype and inquiry.question_mediatype != "text" and inquiry.question_media:
        builder.button(
            text=t("btn_view_question_media", lang),
            callback_data=f"user:inquiry:media:{inquiry.id}:question"
        )

    # If answer has media
    if inquiry.answer_mediatype and inquiry.answer_mediatype != "text" and inquiry.answer:
        builder.button(
            text=t("btn_view_answer_media", lang),
            callback_data=f"user:inquiry:media:{inquiry.id}:answer"
        )

    # If inquiry is answered or closed, allow follow-up re-inquiry
    if inquiry.status in ["replied", "closed"]:
        builder.button(
            text=t("btn_follow_up", lang),
            callback_data=f"user:inquiry:followup:{inquiry.id}"
        )

    # If inquiry is active, allow user to cancel it from archive
    if inquiry.status == "active":
        cancel_text = "❌ Мурожаатни бекор қилиш" if lang == "oz" else ("❌ Murojaatni bekor qilish" if lang == "uz" else "❌ Отменить обращение")
        builder.button(
            text=cancel_text,
            callback_data=f"user:inquiry:cancel:{inquiry.id}"
        )

    # Back to list
    back_text = "⬅️ Рўйхатга қайтиш" if lang == "oz" else ("⬅️ Ro'yxatga qaytish" if lang == "uz" else "⬅️ К списку")
    builder.button(
        text=back_text,
        callback_data="user:archive:page:1"
    )

    return builder.adjust(1).as_markup()


def get_inquiry_followup_cancel_keyboard(inquiry_id: int, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn_cancel", lang),
        callback_data=f"user:inquiry:view:{inquiry_id}"
    )
    return builder.as_markup()


def get_benefit_categories_keyboard(lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("cat_pension_aid", lang), callback_data="benefit_cat:pension_aid")
    builder.button(text=t("cat_health_rehab", lang), callback_data="benefit_cat:health_rehab")
    builder.button(text=t("cat_education", lang), callback_data="benefit_cat:education")
    builder.button(text=t("cat_labor", lang), callback_data="benefit_cat:labor")
    builder.button(text=t("cat_transport", lang), callback_data="benefit_cat:transport")
    builder.button(text=t("cat_housing_communal", lang), callback_data="benefit_cat:housing_communal")
    builder.button(text=t("cat_tax_fee", lang), callback_data="benefit_cat:tax_fee")
    builder.button(text=t("cat_all", lang), callback_data="benefit_cat:all")

    search_text = "🔍 Қидирув" if lang == "oz" else ("🔍 Поиск" if lang == "ru" else "🔍 Qidiruv")
    builder.button(text=search_text, callback_data="benefit_search")
    return builder.adjust(2, 2, 2, 1, 2).as_markup()


def get_benefits_list_keyboard(benefits: list, page: int, total_pages: int, category: str, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for b in benefits:
        # Title according to language
        if lang == "oz":
            title = b.title_oz or b.title_uz
        elif lang == "ru":
            title = b.title_ru or b.title_uz
        else:
            title = b.title_uz

        short_title = title[:45] + ("..." if len(title) > 45 else "")
        builder.button(
            text=f"{short_title}",
            callback_data=f"benefit_view:{b.id}:{category}:{page}"
        )
    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardBuilder().button(text="⬅️", callback_data=f"benefit_page:{category}:{page - 1}").as_markup().inline_keyboard[0][0])
    nav_buttons.append(InlineKeyboardBuilder().button(text=f"📄 {page}/{max(total_pages, 1)}", callback_data="noop").as_markup().inline_keyboard[0][0])
    if page < total_pages:
        nav_buttons.append(InlineKeyboardBuilder().button(text="➡️", callback_data=f"benefit_page:{category}:{page + 1}").as_markup().inline_keyboard[0][0])

    if nav_buttons:
        builder.row(*nav_buttons)

    # Back to categories
    builder.row(
        InlineKeyboardBuilder().button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats").as_markup().inline_keyboard[0][0]
    )
    return builder.as_markup()


def get_portal_button_label(url: str | None, lang: str = "uz") -> str:
    """Havola domeniga qarab ariza tugmasi matnini dinamik moslashtirish."""
    if not url:
        return "🌐 Ариза топшириш" if lang == "oz" else ("🌐 Подать заявление" if lang == "ru" else "🌐 Ariza topshirish")

    url_clean = url.strip()
    url_lower = url_clean.lower()
    if "yoshlardaftari.uz" in url_lower:
        if lang == "oz":
            return "🌐 Ёшлар дафтари орқали ариза"
        elif lang == "ru":
            return "🌐 Заявка через Yoshlar daftari"
        else:
            return "🌐 Yoshlar daftari orqali ariza"
    elif "my.gov.uz" in url_lower:
        if lang == "oz":
            return "🌐 My.gov.uz орқали ариза"
        elif lang == "ru":
            return "🌐 Заявка на My.gov.uz"
        else:
            return "🌐 My.gov.uz orqali ariza"
    elif "uzairways.com" in url_lower:
        if lang == "oz":
            return "🌐 UzAirways орқали чипта"
        elif lang == "ru":
            return "🌐 Билеты на UzAirways"
        else:
            return "🌐 UzAirways orqali chipta"
    elif "railway.uz" in url_lower or "eticket" in url_lower:
        if lang == "oz":
            return "🌐 Темир йўл чиптаси (eticket)"
        elif lang == "ru":
            return "🌐 Ж/д билет (eticket)"
        else:
            return "🌐 Temir yo‘l chiptasi (eticket)"
    elif "my.sud.uz" in url_lower:
        if lang == "oz":
            return "🌐 my.sud.uz орқали мурожаат"
        elif lang == "ru":
            return "🌐 Обращение через my.sud.uz"
        else:
            return "🌐 my.sud.uz orqali murojaat"
    elif "license.gov.uz" in url_lower:
        if lang == "oz":
            return "🌐 license.gov.uz орқали ариза"
        elif lang == "ru":
            return "🌐 Заявка на license.gov.uz"
        else:
            return "🌐 license.gov.uz orqali ariza"
    elif "soliq.uz" in url_lower:
        if lang == "oz":
            return "🌐 Soliq.uz орқали ариза"
        elif lang == "ru":
            return "🌐 Заявка на Soliq.uz"
        else:
            return "🌐 Soliq.uz orqali ariza"
    elif "ihma.uz" in url_lower or "inson.gov.uz" in url_lower:
        if lang == "oz":
            return "🌐 «Инсон» маркази орқали ариза"
        elif lang == "ru":
            return "🌐 Заявка через центр «Инсон»"
        else:
            return "🌐 «Inson» markazi orqali ariza"
    else:
        domain = ""
        try:
            from urllib.parse import urlparse
            parsed_target = url_clean if (url_clean.startswith("http://") or url_clean.startswith("https://")) else f"https://{url_clean}"
            netloc = urlparse(parsed_target).netloc
            domain = netloc.replace("www.", "")
        except Exception:
            pass
        portal_name = domain or ("Портал" if lang in ["oz", "ru"] else "Portal")
        if lang == "oz":
            return f"🌐 {portal_name} орқали ариза"
        elif lang == "ru":
            return f"🌐 Заявка через {portal_name}"
        else:
            return f"🌐 {portal_name} orqali ariza"


def get_benefit_detail_keyboard(
    benefit_id: int,
    category: str,
    page: int,
    lang: str = "uz",
    benefit = None,
    is_search: bool = False,
):
    builder = InlineKeyboardBuilder()

    # 1. Qanday ariza topshiriladi tugmasi (Qadam-baqadam yo'riqnoma so'zi almashtirildi)
    guide_btn_text = t("btn_how_to_apply", lang)
    s_flag = "1" if is_search else "0"
    builder.button(
        text=guide_btn_text,
        callback_data=f"benefit_guide:{benefit_id}:{category}:{page}:{s_flag}"
    )

    # 2. Portallar orqali ariza (Lex.uz tugmasi olib tashlandi, matn shaklida beriladi)
    portal_buttons = []
    if benefit and getattr(benefit, "mygov_url", None):
        raw_url = benefit.mygov_url.strip()
        btn_url = raw_url if (raw_url.startswith("http://") or raw_url.startswith("https://")) else f"https://{raw_url}"
        portal_text = get_portal_button_label(raw_url, lang)
        portal_buttons.append(InlineKeyboardButton(text=portal_text, url=btn_url))

    # 3. Yuristga savol berish tugmasi
    builder.button(
        text=t("btn_ask_lawyer_benefit", lang),
        callback_data=f"benefit_ask:{benefit_id}:{category}:{page}"
    )

    # 4. Navigatsiya tugmalari
    if is_search:
        back_list_text = "⬅️ Қидирувга қайтиш" if lang == "oz" else ("⬅️ К поиску" if lang == "ru" else "⬅️ Qidiruvga qaytish")
        back_cb = f"benefit_search_back:{page}"
    else:
        back_list_text = t("benefits_back_list", lang)
        back_cb = f"benefit_page:{category}:{page}"

    builder.button(text=back_list_text, callback_data=back_cb)
    builder.button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats")

    if portal_buttons:
        builder.adjust(1, 1, 2)
        markup = builder.as_markup()
        markup.inline_keyboard.insert(1, portal_buttons)
        return markup
    else:
        return builder.adjust(1, 1, 2).as_markup()


def get_benefit_guide_keyboard(
    benefit_id: int,
    category: str,
    page: int,
    lang: str = "uz",
    benefit = None,
    is_search: bool = False,
):
    builder = InlineKeyboardBuilder()

    # Portallar havolasi (Lex.uz tugmasi butunlay olib tashlandi)
    portal_buttons = []
    if benefit and getattr(benefit, "mygov_url", None):
        raw_url = benefit.mygov_url.strip()
        btn_url = raw_url if (raw_url.startswith("http://") or raw_url.startswith("https://")) else f"https://{raw_url}"
        portal_text = get_portal_button_label(raw_url, lang)
        portal_buttons.append(InlineKeyboardButton(text=portal_text, url=btn_url))

    builder.button(
        text=t("btn_ask_lawyer_benefit", lang),
        callback_data=f"benefit_ask:{benefit_id}:{category}:{page}"
    )

    back_card_text = t("btn_back_to_card", lang)
    builder.button(text=back_card_text, callback_data=f"benefit_view:{benefit_id}:{category}:{page}")
    builder.button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats")

    if portal_buttons:
        builder.adjust(1, 2)
        markup = builder.as_markup()
        markup.inline_keyboard.insert(0, portal_buttons)
        return markup
    else:
        return builder.adjust(1, 2).as_markup()



def get_benefit_search_keyboard(benefits: list, page: int, total_pages: int, query: str, lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for b in benefits:
        if lang == "oz":
            title = b.title_oz or b.title_uz
        elif lang == "ru":
            title = b.title_ru or b.title_uz
        else:
            title = b.title_uz

        short_title = title[:45] + ("..." if len(title) > 45 else "")
        builder.button(
            text=f"{short_title}",
            callback_data=f"benefit_sview:{b.id}:{page}"
        )
    builder.adjust(1)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardBuilder().button(text="⬅️", callback_data=f"benefit_spage:{page - 1}").as_markup().inline_keyboard[0][0])
    nav_buttons.append(InlineKeyboardBuilder().button(text=f"📄 {page}/{max(total_pages, 1)}", callback_data="noop").as_markup().inline_keyboard[0][0])
    if page < total_pages:
        nav_buttons.append(InlineKeyboardBuilder().button(text="➡️", callback_data=f"benefit_spage:{page + 1}").as_markup().inline_keyboard[0][0])

    if nav_buttons:
        builder.row(*nav_buttons)

    new_search_text = "🔍 Янги қидирув" if lang == "oz" else ("🔍 Новый поиск" if lang == "ru" else "🔍 Yangi qidiruv")
    builder.row(
        InlineKeyboardBuilder().button(text=new_search_text, callback_data="benefit_search").as_markup().inline_keyboard[0][0],
        InlineKeyboardBuilder().button(text=t("benefits_back_cats", lang), callback_data="benefit_back_cats").as_markup().inline_keyboard[0][0],
    )
    return builder.as_markup()

