from typing import Any


LANG_UZ = "uz"
LANG_RU = "ru"

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Til tanlash
    "choose_language": {
        LANG_UZ: "🇺🇿 Iltimos, tilni tanlang:\n🇷🇺 Пожалуйста, выберите язык:",
        LANG_RU: "🇺🇿 Iltimos, tilni tanlang:\n🇷🇺 Пожалуйста, выберите язык:",
    },
    "lang_uz_btn": {
        LANG_UZ: "🇺🇿 O'zbekcha",
        LANG_RU: "🇺🇿 O'zbekcha",
    },
    "lang_ru_btn": {
        LANG_UZ: "🇷🇺 Русский",
        LANG_RU: "🇷🇺 Русский",
    },
    "lang_changed": {
        LANG_UZ: "🇺🇿 Til o‘zbekchaga o‘zgartirildi!",
        LANG_RU: "🇷🇺 Язык успешно изменен на русский!",
    },

    # Bloklanganlik
    "user_blocked": {
        LANG_UZ: "⛔️ <b>Kechirasiz, siz botdan bloklangansiz.</b><br/>Murojaat va arizalar yuborish imkoniyatingiz cheklangan.",
        LANG_RU: "⛔️ <b>Извините, вы заблокированы в боте.</b><br/>Возможность отправки обращений и заявок ограничена.",
    },
    "user_blocked_notification": {
        LANG_UZ: "⛔️ <b>Diqqat:</b> Sizning hisobingiz bot qoidalarini buzganlik sababli bloklandi. Savol va arizalar yuborish imkoniyati cheklandi.",
        LANG_RU: "⛔️ <b>Внимание:</b> Ваш аккаунт был заблокирован за нарушение правил бота. Возможность отправки вопросов и заявок ограничена.",
    },
    "user_unblocked_notification": {
        LANG_UZ: "✅ <b>Xushxabar!</b> Sizning hisobingiz blokdan chiqarildi. Endi bot xizmatlaridan yana to'liq foydalanishingiz mumkin.",
        LANG_RU: "✅ <b>Отличная новость!</b> Ваш аккаунт был разблокирован. Теперь вы снова можете полноценно пользоваться ботом.",
    },

    # Tugmalar
    "btn_understood": {
        LANG_UZ: "✅ Tushunarli",
        LANG_RU: "✅ Понятно",
    },
    "btn_back_main": {
        LANG_UZ: "⬅️ Asosiy menyu",
        LANG_RU: "⬅️ Главное меню",
    },
    "btn_cancel": {
        LANG_UZ: "❌ Bekor qilish",
        LANG_RU: "❌ Отмена",
    },
    "btn_yes": {
        LANG_UZ: "✅ Ha",
        LANG_RU: "✅ Да",
    },
    "btn_no": {
        LANG_UZ: "❌ Yoʻq",
        LANG_RU: "❌ Нет",
    },
    "btn_change_lang": {
        LANG_UZ: "🌐 Tilni o'zgartirish",
        LANG_RU: "🌐 Сменить язык",
    },

    # Asosiy menyu
    "menu_profile": {
        LANG_UZ: "🪪 Profil",
        LANG_RU: "🪪 Профиль",
    },
    "menu_inquiry": {
        LANG_UZ: "📩 Savol yuborish",
        LANG_RU: "📩 Задать вопрос",
    },
    "menu_appointment": {
        LANG_UZ: "✍️ Yurist qabuliga yozilish",
        LANG_RU: "✍️ Запись к юристу",
    },
    "menu_my_inquiries": {
        LANG_UZ: "🗂 Murojaatlarim arxivi",
        LANG_RU: "🗂 Мои обращения",
    },
    "menu_about_us": {
        LANG_UZ: "ℹ️ Biz haqimizda",
        LANG_RU: "ℹ️ О нас",
    },
    "menu_help": {
        LANG_UZ: "⁉️ Texnik yordam",
        LANG_RU: "⁉️ Техническая помощь",
    },

    # Murojaatlar arxivi
    "archive_title": {
        LANG_UZ: "🗂 <b>Sizning murojaatlaringiz arxivi</b><br/><br/>Bu yerda barcha yuborgan savollaringiz, ularning holati va mutaxassislardan kelgan javoblarni ko'rishingiz mumkin:",
        LANG_RU: "🗂 <b>Архив ваших обращений</b><br/><br/>Здесь вы можете просмотреть все отправленные вопросы, их статус и ответы специалистов:",
    },
    "archive_empty": {
        LANG_UZ: "📭 Sizda hali birorta ham murojaat mavjud emas.",
        LANG_RU: "📭 У вас пока нет ни одного обращения.",
    },
    "archive_status_active": {
        LANG_UZ: "🟡 Ko'rib chiqilmoqda",
        LANG_RU: "🟡 На рассмотрении",
    },
    "archive_status_replied": {
        LANG_UZ: "🟢 Javob berilgan",
        LANG_RU: "🟢 Получен ответ",
    },
    "archive_status_closed": {
        LANG_UZ: "⚪️ Yakunlangan",
        LANG_RU: "⚪️ Закрыто",
    },
    "archive_status_cancelled": {
        LANG_UZ: "🔴 Bekor qilingan",
        LANG_RU: "🔴 Отменено",
    },
    "btn_follow_up": {
        LANG_UZ: "🔄 Qayta murojaat (Qo'shimcha savol)",
        LANG_RU: "🔄 Уточняющий вопрос",
    },
    "btn_view_question_media": {
        LANG_UZ: "📎 Savol faylini ko'rish",
        LANG_RU: "📎 Файл вопроса",
    },
    "btn_view_answer_media": {
        LANG_UZ: "📎 Javob audio/videosini ko'rish",
        LANG_RU: "📎 Медиа ответа",
    },
    "follow_up_prompt": {
        LANG_UZ: "✍️ <b>№{id}-sonli murojaatingiz bo'yicha qo'shimcha savolingizni yozing:</b><br/><br/><i>Matn, ovozli xabar, video, rasm yoki hujjat (PDF) yuborishingiz mumkin. Savolingiz avvalgi savol-javob bilan birga mutaxassislar guruhiga yetkaziladi.</i>",
        LANG_RU: "✍️ <b>Напишите уточняющий вопрос по обращению №{id}:</b><br/><br/><i>Вы можете отправить текст, голосовое сообщение, видео, фото или документ (PDF). Ваш вопрос будет передан юристам вместе с контекстом предыдущего обращения.</i>",
    },
    "follow_up_received": {
        LANG_UZ: "✅ <b>Qo'shimcha savolingiz qabul qilindi va mutaxassislarga yetkazildi!</b><br/><br/>Javob berilishi bilan sizga xabar yetib keladi.",
        LANG_RU: "✅ <b>Ваш уточняющий вопрос принят и передан специалистам!</b><br/><br/>Как только поступит ответ, бот сразу вас уведомит.",
    },

    # Ro'yxatdan o'tish
    "reg_enter_first_name": {
        LANG_UZ: "<b>Ismingizni kiriting...</b><br/><p>Masalan: Aziz</p>",
        LANG_RU: "<b>Введите ваше имя...</b><br/><p>Например: Азиз</p>",
    },
    "reg_enter_last_name": {
        LANG_UZ: "<b>Familiyangizni kiriting...</b><br/><p>Masalan: Karimov</p>",
        LANG_RU: "<b>Введите вашу фамилию...</b><br/><p>Например: Каримов</p>",
    },
    "reg_choose_gender": {
        LANG_UZ: "Jinsingizni tanlang:",
        LANG_RU: "Выберите ваш пол:",
    },
    "reg_gender_male": {
        LANG_UZ: "Erkak",
        LANG_RU: "Мужской",
    },
    "reg_gender_female": {
        LANG_UZ: "Ayol",
        LANG_RU: "Женский",
    },
    "reg_enter_birth_year": {
        LANG_UZ: "<b>Tug‘ilgan yilingizni kiriting...</b><br/><p>Masalan: 1995</p>",
        LANG_RU: "<b>Введите год вашего рождения...</b><br/><p>Например: 1995</p>",
    },
    "reg_invalid_year": {
        LANG_UZ: "Iltimos, haqiqiy tug'ilgan yilingizni 4 ta raqamda kiriting (masalan: 1995).",
        LANG_RU: "Пожалуйста, введите корректный год рождения (например: 1995).",
    },
    "reg_enter_phone": {
        LANG_UZ: "Telefon raqamingizni yuboring yoki kiriting:",
        LANG_RU: "Отправьте или введите ваш номер телефона:",
    },
    "reg_send_phone_btn": {
        LANG_UZ: "📱 Raqamni yuborish",
        LANG_RU: "📱 Отправить номер",
    },
    "reg_choose_disability_type": {
        LANG_UZ: "Nogironlik guruhingizni tanlang:",
        LANG_RU: "Выберите группу инвалидности:",
    },
    "reg_choose_disability_state": {
        LANG_UZ: "Nogironlik holatingizni tanlang:",
        LANG_RU: "Выберите форму инвалидности:",
    },
    "reg_choose_region": {
        LANG_UZ: "Yashash hududingizni tanlang:",
        LANG_RU: "Выберите регион проживания:",
    },
    "reg_success": {
        LANG_UZ: "Tabriklaymiz, siz muvaffaqiyatli ro'yxatdan o'tdingiz!",
        LANG_RU: "Поздравляем, вы успешно зарегистрировались!",
    },
    "already_registered": {
        LANG_UZ: "Siz ro'yxatdan o'tgansiz",
        LANG_RU: "Вы уже зарегистрированы",
    },
    "user_not_found": {
        LANG_UZ: "Siz haqingizda ma'lumot topilmadi. Iltimos, botni qayta ishga tushirish uchun /start buyrug'ini bosing.",
        LANG_RU: "Информация о вас не найдена. Пожалуйста, перезапустите бота командой /start.",
    },

    # Profil
    "profile_title": {
        LANG_UZ: "<p>Sizning profilingiz.</p>",
        LANG_RU: "<p>Ваш профиль.</p>",
    },
    "profile_edit_btn": {
        LANG_UZ: "🪪 O‘zgartirish",
        LANG_RU: "🪪 Изменить",
    },

    # Murojaat (Inquiry)
    "inquiry_select_section": {
        LANG_UZ: "Savolingiz qaysi yo'nalishga tegishli ekanligini tanlang:",
        LANG_RU: "Выберите направление вашего вопроса:",
    },
    "inquiry_send_prompt": {
        LANG_UZ: "❓O‘z savolingizni matn, ovozli yoki video xabar ko‘rinishida yuboring.",
        LANG_RU: "❓Отправьте свой вопрос в виде текста, голосового или видеосообщения.",
    },
    "inquiry_sections_btn": {
        LANG_UZ: "📁 Boʻlimlar",
        LANG_RU: "📁 Разделы",
    },
    "inquiry_received": {
        LANG_UZ: (
            "<p>✅ Savolingiz muvaffaqiyatli qabul qilindi. Iltimos yuristlarimiz javobini kuting.</p>"
            "<p>⏳Odatda 1-2 ish kunida javob berishga harakat qilamiz.</p>"
            "<p>Telegram kanalimizga obuna boʻlishni unutmang:</p>"
            "<p>👉 https://t.me/huquqplus</p>"
        ),
        LANG_RU: (
            "<p>✅ Ваш вопрос успешно принят. Пожалуйста, дождитесь ответа наших юристов.</p>"
            "<p>⏳Обычно мы стараемся ответить в течение 1-2 рабочих дней.</p>"
            "<p>Не забудьте подписаться на наш Telegram-канал:</p>"
            "<p>👉 https://t.me/huquqplus</p>"
        ),
    },
    "inquiry_cancel_confirm": {
        LANG_UZ: "Amaldagi murojaatingiz o'chirib yuboriladi va ko'rib chiqilmaydi. Ishonchingiz komilmi?",
        LANG_RU: "Ваше текущее обращение будет удалено и не будет рассмотрено. Вы уверены?",
    },
    "inquiry_cancelled": {
        LANG_UZ: "Murojaatingiz muvoffaqiyatli bekor qilindi!",
        LANG_RU: "Ваше обращение успешно отменено!",
    },
    "inquiry_waiting": {
        LANG_UZ: "Savolingiz javob kutmoqda!",
        LANG_RU: "Ваш вопрос ожидает ответа!",
    },
    "inquiry_rate_prompt": {
        LANG_UZ: "⭐ <b>Yuristimiz bergan javobni 1 dan 5 gacha baholang:</b>",
        LANG_RU: "⭐ <b>Оцените ответ юриста от 1 до 5:</b>",
    },
    "rate_received_thanks": {
        LANG_UZ: "✅ <b>Bahoyingiz qabul qilindi!</b> Fikr-mulohazangiz xizmat sifatini oshirishga yordam beradi.",
        LANG_RU: "✅ <b>Ваша оценка принята!</b> Ваш отзыв поможет нам улучшить качество помощи.",
    },
    "rate_leave_feedback": {
        LANG_UZ: "✍️ <i>Xohlasangiz, javob yuzasidan qisqa izoh yoki fikringizni yozib qoldirishingiz mumkin:</i>",
        LANG_RU: "✍️ <i>При желании вы можете написать краткий отзыв или комментарий:</i>",
    },
    "rate_low_ask_again": {
        LANG_UZ: "Agar savolingizga to'liq javob ololmagan bo'lsangiz, bemalol qayta savol yo'llashingiz mumkin:",
        LANG_RU: "Если вы не получили полный ответ на свой вопрос, вы можете задать уточняющий вопрос:",
    },
    "btn_ask_again": {
        LANG_UZ: "🔄 Qayta savol yo'llash",
        LANG_RU: "🔄 Задать повторный вопрос",
    },
    "appointment_claimed_citizen": {
        LANG_UZ: "✅ <b>Xushxabar!</b> Sizning yurist qabuliga arizangiz yuristimiz <b>{lawyer_name}</b> qabul qildi. Tez orada siz bilan bog'lanadi.",
        LANG_RU: "✅ <b>Хорошая новость!</b> Вашу заявку на прием принял наш юрист <b>{lawyer_name}</b>. С вами свяжутся в ближайшее время.",
    },
    "appointment_completed_rate_prompt": {
        LANG_UZ: "📞 <b>Hurmatli fuqaro!</b> Yuristimiz bilan online suhbatingiz yakunlandi.<br/><br/>Iltimos, o'tkazilgan suhbat va ko'rsatilgan huquqiy yordam sifatini <b>1 dan 5 gacha baholang:</b>",
        LANG_RU: "📞 <b>Уважаемый пользователь!</b> Ваша онлайн-консультация с юристом завершена.<br/><br/>Пожалуйста, оцените качество консультации от <b>1 до 5:</b>",
    },
    "feedback_recorded": {
        LANG_UZ: "✅ Fikr-mulohazangiz saqlandi. Rahmat!",
        LANG_RU: "✅ Ваш отзыв сохранен. Спасибо!",
    },

    # Yurist qabuli (Appointment)
    "appointment_remote_btn": {
        LANG_UZ: "📞 Masofaviy qabul",
        LANG_RU: "📞 Дистанционный прием",
    },
    "appointment_in_person_btn": {
        LANG_UZ: "🏢 Yuzma-yuz qabul",
        LANG_RU: "🏢 Очный прием",
    },
    "appointment_enter_problem": {
        LANG_UZ: "📌 Iltimos, qabulga yozilish uchun muammoingizni imkon qadar batafsil tarzda yozib yuboring — bu sizga tez va aniq amaliy yordam ko‘rsatishimizga yordam beradi:",
        LANG_RU: "📌 Пожалуйста, опишите вашу проблему как можно подробнее для записи на прием — это поможет нам оказать вам быструю и точную помощь:",
    },
    "appointment_success": {
        LANG_UZ: "✅ Murojaatingiz qabul qilindi. Tez orada siz bilan bog'lanamiz.",
        LANG_RU: "✅ Ваша заявка принята. В скором времени мы свяжемся с вами.",
    },

    # Texnik yordam (Help)
    "help_start_text": {
        LANG_UZ: "❗️Agarda sizda botdan foydalanish va savolingizni yuborish bo‘yicha muammo yuzaga kelgan bo‘lsa, telefon raqamingizni qoldiring. Siz bilan bog‘lanib tushuntirish berib o‘tamiz!",
        LANG_RU: "❗️Если у вас возникли трудности с использованием бота или отправкой вопроса, оставьте свой номер телефона. Мы свяжемся с вами и поможем разобраться!",
    },
    "help_problem_prompt": {
        LANG_UZ: "Botdan foydalanishda sizga yordam kerakmi? Muammoingizni yozing.",
        LANG_RU: "Вам нужна помощь по использованию бота? Опишите вашу проблему.",
    },
    "help_success": {
        LANG_UZ: "✅ Sizning murojaatingiz qabul qilindi. Tez orada sizga yordam beramiz.",
        LANG_RU: "✅ Ваше обращение принято. Мы свяжемся с вами в ближайшее время.",
    },
}


def t(key: str, lang: str = LANG_UZ, **kwargs: Any) -> str:
    lang = lang if lang in [LANG_UZ, LANG_RU] else LANG_UZ
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_about_us_text(lang: str = LANG_UZ, bot_name: str = "") -> str:
    b_name = f"@{bot_name}" if bot_name else ("@huquqplus_bot" if lang == LANG_UZ else "@huquqplus_bot")
    if lang == LANG_RU:
        return (
            f"{b_name} — ЧЕМ МЫ МОЖЕМ ПОМОЧЬ:<br/><br/>"
            "➖ Онлайн юридические консультации для лиц с инвалидностью и членов их семей;<br/>"
            "➖ Разъяснение прав и порядка их реализации;<br/>"
            "➖ Получение практической правовой помощи по записи к юристу;<br/>"
            "➖ Разъяснение, в какие ведомства обращаться и какие документы необходимы (при необходимости помощь в подготовке);<br/>"
            "➖ Предоставление образцов заявлений и жалоб;<br/>"
            "➖ Подготовка и отправка обращений и документов в организации от вашего имени;<br/>"
            "➖ Участие в судебных процессах в г. Ташкенте от вашего имени.<br/><br/>"
            "❗️Мы не можем следующее:<br/><br/>"
            "➖ Ведение судебных дел в областях;<br/>"
            "➖ Личное обращение в официальные ведомства;<br/>"
            "➖ Гарантировать результат.<br/><br/>"
            "⏳ На ваш вопрос будет дан ответ в течение 1–2 рабочих дней.<br/><br/>"
            "❓ Пожалуйста, отправьте ваш вопрос в виде полного и четкого текста — это поможет нам быстрее оказать помощь.<br/><br/>"
            "🤖 Поделитесь ботом со знакомыми с инвалидностью, нуждающимися в правовой помощи.<br/><br/>"
            'HuquqPlus.uz — специальный правовой информационный веб-портал для лиц с инвалидностью, созданный общественным объединением инвалидов г. Ташкента "SHAROIT PLUS" (https://sharoitplus.uz/).'
        )
    return (
        f"{b_name} orqali BIZ NIMALARGA YORDAM BЕRA OLAMIZ:<br/><br/>"
        "➖Nogironligi bo‘lgan shaxslar va ularning oila a’zolariga onlayn huquqiy maslahat;<br/>"
        "➖Huquqlar va ularni amalga oshirish tartibi bo‘yicha tushuntirish berish;<br/>"
        "➖Yurist qabuliga yozilish orqali amaliy huquqiy yordam olish;<br/>"
        "➖Qaysi idoraga murojaat qilish va qanday hujjatlar kerakligini tushuntirish (zarurat bo‘lsa, tayyorlashda yordam);<br/>"
        "➖Ariza va shikoyatlar namunalarini taqdim etish;<br/>"
        "➖Sizning nomingizdan tashkilotlarga murojaat va hujjatlarni tayyorlab jo‘natish;<br/>"
        "➖Toshkent shahrida sizning nomingizdan sud jarayonlarida qatnashish.<br/><br/>"
        "❗️Biz quyidagilarni qila olmaymiz:<br/><br/>"
        "➖Viloyatlarda sudda ish yuritish;<br/>"
        "➖Rasmiy idoralarga shaxsan murojaat qilish;<br/>"
        "➖Natijaga kafolat berish.<br/><br/>"
        "⏳ Savolingizga 1–2 ish kuni ichida javob beriladi.<br/><br/>"
        "❓ Iltimos, savolingizni to‘liq va aniq matn shaklida yuboring — bu bizga tezroq yordam ko‘rsatishga imkon beradi.<br/><br/>"
        "🤖 Botni nogironligi bor, huquqiy yordamga muhtoj tanishlaringiz bilan ulashing.<br/><br/>"
        'HuquqPlus.uz — nogironligi bo‘lgan shaxslar uchun maxsus huquqiy axborot veb-portali Toshkent shahar "SHAROIT PLYUS" (https://sharoitplus.uz/) nogironlar jamoat birlashmasi tomonidan yaratilgan.'
    )


def get_appointment_text(lang: str = LANG_UZ) -> str:
    if lang == LANG_RU:
        return (
            "Уважаемый пользователь!<br/><br/>"
            "Прием юриста проводится в дистанционной или очной форме.<br/><br/>"
            "📞 <b>Дистанционный прием</b> — наши юристы свяжутся с вами и окажут практическую помощь в решении вашей правовой проблемы.<br/><br/>"
            "🏢 <b>Очный прием</b> — каждую субботу с 10:00 до 17:00 в главном офисе по адресу: г. Ташкент, Юнусабадский район, улица Хиёбон, дом 22.<br/><br/>"
            "📍Локация: https://yandex.com/maps/-/CHAD5P1f <br/><br/>"
            "Выберите форму приема ниже 👇"
        )
    return (
        "Hurmatli foydalanuvchi!<br/><br/>"
        "Yurist qabuli masofaviy yoki yuzma-yuz shaklda amalga oshiriladi.<br/><br/>"
        "📞 <b>Masofaviy qabul</b> — yuristlarimiz siz bilan bog‘lanib, muammoingizni hal etishda amaliy yordam ko‘rsatadi.<br/><br/>"
        "🏢 <b>Yuzma-yuz qabul</b>— har shanba kuni, soat 10:00 dan 17:00 gacha, Toshkent shahar, Yunusobod tumani, Xiyobon ko‘chasi, 22-uy manzildagi bosh ofisda o‘tkaziladi.<br/><br/>"
        "📍Lokatsiya: https://yandex.com/maps/-/CHAD5P1f <br/><br/>"
        "Quyidagi qabul turidan birini tanlang 👇"
    )
