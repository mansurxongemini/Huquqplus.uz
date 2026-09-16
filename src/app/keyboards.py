from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.app.translations import t, LANG_UZ, LANG_RU


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

# Compatibility mapping combining both
inquiry_sections = {**inquiry_sections_uz, **inquiry_sections_ru}


def get_inquiry_sections(lang: str = "uz") -> dict[str, int]:
    return inquiry_sections_ru if lang == "ru" else inquiry_sections_uz


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
    builder.button(text="🇷🇺 Русский", callback_data="set_lang:ru")
    return builder.adjust(2).as_markup()


def get_main_menu(lang: str = "uz"):
    main_menu = ReplyKeyboardBuilder()
    main_menu.button(text=t("menu_profile", lang))
    main_menu.button(text=t("menu_inquiry", lang))
    main_menu.button(text=t("menu_appointment", lang))
    main_menu.button(text=t("menu_my_inquiries", lang))
    main_menu.button(text=t("menu_about_us", lang))
    main_menu.button(text=t("menu_help", lang))
    main_menu.button(text=t("btn_change_lang", lang))
    return main_menu.adjust(2).as_markup(resize_keyboard=True)


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
        date_str = inq.created_at.strftime("%d.%m") if inq.created_at else ""
        section_short = inq.section_name[:15] if inq.section_name else "Murojaat"
        builder.button(
            text=f"{status_icon} №{inq.id} • {date_str} • {section_short}",
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

    builder.row(
        InlineKeyboardBuilder().button(text="❌ Yopish" if lang == "uz" else "❌ Закрыть", callback_data="user:archive:close").as_markup().inline_keyboard[0][0]
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
        builder.button(
            text="❌ Murojaatni bekor qilish" if lang == "uz" else "❌ Отменить обращение",
            callback_data=f"user:inquiry:cancel:{inquiry.id}"
        )

    # Back to list
    builder.button(
        text="⬅️ Ro'yxatga qaytish" if lang == "uz" else "⬅️ К списку",
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

