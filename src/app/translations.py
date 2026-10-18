from typing import Any


LANG_UZ = "uz"
LANG_RU = "ru"
LANG_OZ = "oz"

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Til tanlash
    "choose_language": {
        LANG_UZ: "🇺🇿 Iltimos, tilni tanlang:\n🇺🇿 Илтимос, тилни танланг:\n🇷🇺 Пожалуйста, выберите язык:",
        LANG_OZ: "🇺🇿 Iltimos, tilni tanlang:\n🇺🇿 Илтимос, тилни танланг:\n🇷🇺 Пожалуйста, выберите язык:",
        LANG_RU: "🇺🇿 Iltimos, tilni tanlang:\n🇺🇿 Илтимос, тилни танланг:\n🇷🇺 Пожалуйста, выберите язык:",
    },
    "lang_changed": {
        LANG_UZ: "🇺🇿 Til o‘zbekchaga o‘zgartirildi!",
        LANG_OZ: "🇺🇿 Тил ўзбекча (кирилл)га ўзгартирилди!",
        LANG_RU: "🇷🇺 Язык успешно изменен на русский!",
    },

    # Bloklanganlik
    "user_blocked": {
        LANG_UZ: "⛔️ <b>Kechirasiz, siz botdan bloklangansiz.</b><br/>Murojaat va arizalar yuborish imkoniyatingiz cheklangan.",
        LANG_OZ: "⛔️ <b>Кечирасиз, сиз ботдан блоклангансиз.</b><br/>Мурожаат ва аризалар юбориш имкониятингиз чекланган.",
        LANG_RU: "⛔️ <b>Извините, вы заблокированы в боте.</b><br/>Возможность отправки обращений и заявок ограничена.",
    },
    "user_blocked_notification": {
        LANG_UZ: "⛔️ <b>Diqqat:</b> Sizning hisobingiz bot qoidalarini buzganlik sababli bloklandi. Savol va arizalar yuborish imkoniyati cheklandi.",
        LANG_OZ: "⛔️ <b>Диққат:</b> Сизнинг ҳисобингиз бот қоидаларини бузганлик сабабли блокланди. Савол ва аризалар юбориш имконияти чекланди.",
        LANG_RU: "⛔️ <b>Внимание:</b> Ваш аккаунт был заблокирован за нарушение правил бота. Возможность отправки вопросов и заявок ограничена.",
    },
    "user_unblocked_notification": {
        LANG_UZ: "✅ <b>Xushxabar!</b> Sizning hisobingiz blokdan chiqarildi. Endi bot xizmatlaridan yana to'liq foydalanishingiz mumkin.",
        LANG_OZ: "✅ <b>Хушхабар!</b> Сизнинг ҳисобингиз блокдан чиқарилди. Энди бот хизматларидан яна тўлиқ фойдаланишингиз мумкин.",
        LANG_RU: "✅ <b>Отличная новость!</b> Ваш аккаунт был разблокирован. Теперь вы снова можете полноценно пользоваться ботом.",
    },

    # Majburiy obuna
    "mandatory_sub_prompt": {
        LANG_UZ: "Iltimos, quyidagi kanallarimizga obuna bo'ling, keyin botni ishlatishingiz mumkin.",
        LANG_OZ: "Илтимос, қуйидаги каналларимизга обуна бўлинг, кейин ботни ишлатишингиз мумкин.",
        LANG_RU: "Пожалуйста, подпишитесь на наши каналы ниже, после чего вы сможете пользоваться ботом.",
    },
    "btn_subscribe": {
        LANG_UZ: "➕ Obuna bo'lish",
        LANG_OZ: "➕ Обуна бўлиш",
        LANG_RU: "➕ Подписаться",
    },
    "btn_verify_sub": {
        LANG_UZ: "✅ Tasdiqlash",
        LANG_OZ: "✅ Тасдиқлаш",
        LANG_RU: "✅ Подтвердить",
    },
    "sub_verified_success": {
        LANG_UZ: "✅ Rahmat, barcha kanallarga obuna tasdiqlandi!",
        LANG_OZ: "✅ Раҳмат, барча каналларга обуна тасдиқланди!",
        LANG_RU: "✅ Спасибо, подписка на все каналы подтверждена!",
    },
    "sub_not_verified": {
        LANG_UZ: "⚠️ Siz hali barcha kanallarga a'zo bo'lmadingiz! Iltimos, kanallarga a'zo bo'lib, qayta 'Tasdiqlash' tugmasini bosing.",
        LANG_OZ: "⚠️ Сиз ҳали барча каналларга аъзо бўлмадингиз! Илтимос, каналларга аъзо бўлиб, қайта 'Тасдиқлаш' тугмасини босинг.",
        LANG_RU: "⚠️ Вы еще не подписались на все каналы! Пожалуйста, подпишитесь и снова нажмите кнопку 'Подтвердить'.",
    },

    # Tugmalar
    "btn_understood": {
        LANG_UZ: "✅ Tushunarli",
        LANG_OZ: "✅ Тушунарли",
        LANG_RU: "✅ Понятно",
    },
    "btn_back_main": {
        LANG_UZ: "⬅️ Asosiy menyu",
        LANG_OZ: "⬅️ Асосий меню",
        LANG_RU: "⬅️ Главное меню",
    },
    "btn_cancel": {
        LANG_UZ: "❌ Bekor qilish",
        LANG_OZ: "❌ Бекор қилиш",
        LANG_RU: "❌ Отмена",
    },
    "btn_yes": {
        LANG_UZ: "✅ Ha",
        LANG_OZ: "✅ Ҳа",
        LANG_RU: "✅ Да",
    },
    "btn_no": {
        LANG_UZ: "❌ Yoʻq",
        LANG_OZ: "❌ Йўқ",
        LANG_RU: "❌ Нет",
    },
    "btn_change_lang": {
        LANG_UZ: "🌐 Tilni o'zgartirish",
        LANG_OZ: "🌐 Тилни ўзгартириш",
        LANG_RU: "🌐 Сменить язык",
    },

    # Asosiy menyu
    "menu_profile": {
        LANG_UZ: "🪪 Profil",
        LANG_OZ: "🪪 Профил",
        LANG_RU: "🪪 Профиль",
    },
    "menu_benefits": {
        LANG_UZ: "✨Imtiyozlarim",
        LANG_OZ: "✨Имтиёзларим",
        LANG_RU: "✨Мои льготы",
    },
    "menu_inquiry": {
        LANG_UZ: "📩 Savol yuborish",
        LANG_OZ: "📩 Савол юбориш",
        LANG_RU: "📩 Задать вопрос",
    },
    "menu_appointment": {
        LANG_UZ: "✍️ Yurist qabuliga yozilish",
        LANG_OZ: "✍️ Юрист қабулига ёзилиш",
        LANG_RU: "✍️ Запись к юристу",
    },
    "menu_my_inquiries": {
        LANG_UZ: "🗂 Murojaatlarim arxivi",
        LANG_OZ: "🗂 Мурожаатларим архиви",
        LANG_RU: "🗂 Мои обращения",
    },
    "menu_about_us": {
        LANG_UZ: "ℹ️ Biz haqimizda",
        LANG_OZ: "ℹ️ Биз ҳақимизда",
        LANG_RU: "ℹ️ О нас",
    },
    "menu_help": {
        LANG_UZ: "⁉️ Texnik yordam",
        LANG_OZ: "⁉️ Техник ёрдам",
        LANG_RU: "⁉️ Техническая помощь",
    },
    "menu_ai": {
        LANG_UZ: "🤖 AI yordamchi",
        LANG_OZ: "🤖 AI ёрдамчи",
        LANG_RU: "🤖 ИИ-помощник",
    },
    "btn_auto_inquiry_ai": {
        LANG_UZ: "🤖 AI javobi",
        LANG_OZ: "🤖 AI жавоби",
        LANG_RU: "🤖 Ответ ИИ",
    },
    "btn_new_ai_chat": {
        LANG_UZ: "🔄 Yangi suhbat",
        LANG_OZ: "🔄 Янги суҳбат",
        LANG_RU: "🔄 Новый диалог",
    },
    "btn_send_to_lawyer": {
        LANG_UZ: "👨‍⚖️ Yuristga yuborish",
        LANG_OZ: "👨‍⚖️ Юристга юбориш",
        LANG_RU: "👨‍⚖️ Отправить юристу",
    },
    "ai_intro": {
        LANG_UZ: "🤖 <b>AI yordamchi rejimiga xush kelibsiz!</b>\n\nAI O‘zbekiston qonunchiligi bo‘yicha manbali tushuntirish beradi. Bu rasmiy yuridik xulosa emas, aniq holatingiz bo‘yicha yuristga murojaat qilishingiz mumkin.\n\nSavolingizni yozing:",
        LANG_OZ: "🤖 <b>AI ёрдамчи режимига хуш келибсиз!</b>\n\nAI Ўзбекистон қонунчилиги бўйича манбали тушунтириш беради. Бу расмий юридик хулоса эмас, аниқ ҳолатингиз бўйича юристга мурожаат қилишингиз мумкин.\n\nСаволингизни ёзинг:",
        LANG_RU: "🤖 <b>Добро пожаловать в режим ИИ-помощника!</b>\n\nИИ предоставляет разъяснения по законодательству Узбекистана со ссылками на нормы права. Это не является официальным юридическим заключением, по конкретной ситуации вы можете обратиться к юристу.\n\nНапишите ваш вопрос:",
    },
    "ai_new_chat_started": {
        LANG_UZ: "🔄 Yangi suhbat boshlandi. Savolingizni yozishingiz mumkin:",
        LANG_OZ: "🔄 Янги суҳбат бошланди. Саволингизни ёзишингиз мумкин:",
        LANG_RU: "🔄 Начат новый диалог. Вы можете написать свой вопрос:",
    },
    "ai_question_too_long": {
        LANG_UZ: "⚠️ Savol matni juda uzun (4000 belgidan oshmasligi kerak). Iltimos, savolingizni qisqartirib yuboring.",
        LANG_OZ: "⚠️ Савол матни жуда узун (4000 белгидан ошмаслиги керак). Илтимос, саволингизни қисқартириб юборинг.",
        LANG_RU: "⚠️ Текст вопроса слишком длинный (не более 4000 символов). Пожалуйста, сократите ваш вопрос.",
    },
    "ai_only_text": {
        LANG_UZ: "AI hozircha faqat matnli savolni qabul qiladi. Fayl bilan yuristga murojaat qilishingiz mumkin.",
        LANG_OZ: "AI ҳозирча фақат матнли саволни қабул қилади. Файл билан юристга мурожаат қилишингиз мумкин.",
        LANG_RU: "ИИ пока принимает только текстовые вопросы. Вы можете обратиться к юристу с прикрепленным файлом.",
    },
    "ai_rate_limited": {
        LANG_UZ: "⏳ Juda ko'p so'rov yuborildi. Iltimos, {seconds} soniyadan keyin urinib ko'ring.",
        LANG_OZ: "⏳ Жуда кўп сўров юборилди. Илтимос, {seconds} сониядан кейин уриниб кўринг.",
        LANG_RU: "⏳ Слишком много запросов. Пожалуйста, повторите попытку через {seconds} сек.",
    },
    "ai_temporary_unavailable": {
        LANG_UZ: "⚠️ AI yordamchi vaqtincha ishlamayapti. Savolingizni yuristga yuborishingiz mumkin.",
        LANG_OZ: "⚠️ AI ёрдамчи вақтинча ишламаяпти. Саволингизни юристга юборишингиз мумкин.",
        LANG_RU: "⚠️ ИИ-помощник временно недоступен. Вы можете отправить вопрос юристу.",
    },
    "ai_unavailable": {
        LANG_UZ: "Bu xizmat hozir mavjud emas, 📩 Savol yuborish orqali murojaat qiling.",
        LANG_OZ: "Бу хизмат ҳозир мавжуд эмас, 📩 Савол юбориш орқали мурожаат қилинг.",
        LANG_RU: "Эта услуга сейчас недоступна, обратитесь через 📩 «Задать вопрос».",
    },
    "ai_feedback_received": {
        LANG_UZ: "Fikringiz uchun rahmat!",
        LANG_OZ: "Фикрингиз учун раҳмат!",
        LANG_RU: "Спасибо за ваш отзыв!",
    },

    # Imtiyozlar bo'limi
    "benefits_title": {
        LANG_UZ: "<b>Siz uchun belgilangan imtiyozlar</b><br/><br/>Quyidagi yo‘nalishlardan birini tanlang. Tizim sizning toifangiz va yoshingizga mos imtiyozlarni ko‘rsatadi:",
        LANG_OZ: "<b>Сиз учун белгиланган имтиёзлар</b><br/><br/>Қуйидаги йўналишлардан бирини танланг. Тизим сизнинг тоифангиз ва ёшингизга мос имтиёзларни кўрсатади:",
        LANG_RU: "<b>Льготы, установленные для вас</b><br/><br/>Выберите одно из направлений. Система покажет льготы, соответствующие вашей категории и возрасту:",
    },
    "cat_pension_aid": {
        LANG_UZ: "💰 Nafaqa va moddiy yordam",
        LANG_OZ: "💰 Нафақа ва моддий ёрдам",
        LANG_RU: "💰 Пособия и матпомощь",
    },
    "cat_health_rehab": {
        LANG_UZ: "🩺 Tibbiyot va reabilitatsiya",
        LANG_OZ: "🩺 Тиббиёт ва реабилитация",
        LANG_RU: "🩺 Медицина и реабилитация",
    },
    "cat_education": {
        LANG_UZ: "🎓 Ta’lim va yoshlar",
        LANG_OZ: "🎓 Таълим ва ёшлар",
        LANG_RU: "🎓 Образование и молодежь",
    },
    "cat_labor": {
        LANG_UZ: "💼 Mehnat va bandlik",
        LANG_OZ: "💼 Меҳнат ва бандлик",
        LANG_RU: "💼 Труд и занятость",
    },
    "cat_transport": {
        LANG_UZ: "🚌 Transport va yo‘l haqi",
        LANG_OZ: "🚌 Транспорт ва йўл ҳақи",
        LANG_RU: "🚌 Транспорт и проезд",
    },
    "cat_housing_communal": {
        LANG_UZ: "🏠 Uy-joy va kommunal",
        LANG_OZ: "🏠 Уй-жой ва коммунал",
        LANG_RU: "🏠 Жилье и коммунальные льготы",
    },
    "cat_tax_fee": {
        LANG_UZ: "📑 Soliq va davlat bojlari",
        LANG_OZ: "📑 Солиқ ва давлат божлари",
        LANG_RU: "📑 Налоги и госпошлины",
    },
    "cat_all": {
        LANG_UZ: "📋 Barcha imtiyozlarim",
        LANG_OZ: "📋 Барча имтиёзларим",
        LANG_RU: "📋 Все мои льготы",
    },
    "benefits_empty": {
        LANG_UZ: "ℹ️ Ushbu yo‘nalish bo‘yicha sizning toifangizga mos imtiyozlar topilmadi.",
        LANG_OZ: "ℹ️ Ушбу йўналиш бўйича сизнинг тоифангизга мос имтиёзлар топилмади.",
        LANG_RU: "ℹ️ По данному направлению для вашей категории льгот не найдено.",
    },
    "benefits_back_cats": {
        LANG_UZ: "📂 Yo‘nalishlar menyusi",
        LANG_OZ: "📂 Йўналишлар менюси",
        LANG_RU: "📂 Меню направлений",
    },
    "benefits_back_list": {
        LANG_UZ: "⬅️ Ro‘yxatga qaytish",
        LANG_OZ: "⬅️ Рўйхатга қайтиш",
        LANG_RU: "⬅️ Вернуться к списку",
    },
    "btn_how_to_apply": {
        LANG_UZ: "📝 Qanday ariza topshiriladi",
        LANG_OZ: "📝 Қандай ариза топширилади",
        LANG_RU: "📝 Как подать заявление",
    },
    "btn_back_to_card": {
        LANG_UZ: "📌 Qisqa tavsifga qaytish",
        LANG_OZ: "📌 Қисқа тавсифга қайтиш",
        LANG_RU: "📌 К краткому описанию",
    },
    "btn_ask_lawyer_benefit": {
        LANG_UZ: "✍️ Shu bo‘yicha yuristga savol berish",
        LANG_OZ: "✍️ Шу бўйича юристга савол бериш",
        LANG_RU: "✍️ Задать вопрос юристу по этой льготе",
    },
    "benefit_ask_prompt": {
        LANG_UZ: "✍️ <b>«{title}»</b> imtiyozi bo‘yicha savol yuborish<br/><br/>Ushbu imtiyozni olishda qanday savol yoki muammoga duch keldingiz? Marhamat, batafsil yozib yuboring (yoki ovozli xabar yo‘llang). Yuristlarimiz ko‘rib chiqib tez orada javob berishadi:",
        LANG_OZ: "✍️ <b>«{title}»</b> имтиёзи бўйича савол юбориш<br/><br/>Ушбу имтиёзни олишда қандай савол ёки муаммога дуч келдингиз? Марҳамат, батафсил ёзиб юборинг (ёки овозли хабар йўлланг). Юристларимиз кўриб чиқиб тез орада жавоб беришади:",
        LANG_RU: "✍️ <b>Вопрос по льготе «{title}»</b><br/><br/>С каким вопросом или трудностью вы столкнулись при получении этой льготы? Напишите подробно (или отправьте голосовое сообщение). Наши юристы изучат обращение и ответят вам:",
    },

    # Murojaatlar arxivi
    "archive_title": {
        LANG_UZ: "🗂 <b>Sizning murojaatlaringiz arxivi</b><br/><br/>Bu yerda barcha yuborgan savollaringiz, ularning holati va mutaxassislardan kelgan javoblarni ko'rishingiz mumkin:",
        LANG_OZ: "🗂 <b>Сизнинг мурожаатларингиз архиви</b><br/><br/>Бу ерда барча юборган саволларингиз, уларнинг ҳолати ва мутахассислардан келган жавобларни кўришингиз мумкин:",
        LANG_RU: "🗂 <b>Архив ваших обращений</b><br/><br/>Здесь вы можете просмотреть все отправленные вопросы, их статус и ответы специалистов:",
    },
    "archive_empty": {
        LANG_UZ: "📭 Sizda hali birorta ham murojaat mavjud emas.",
        LANG_OZ: "📭 Сизда ҳали бирорта ҳам мурожаат мавжуд эмас.",
        LANG_RU: "📭 У вас пока нет ни одного обращения.",
    },
    "archive_status_active": {
        LANG_UZ: "🟡 Ko'rib chiqilmoqda",
        LANG_OZ: "🟡 Кўриб чиқилмоқда",
        LANG_RU: "🟡 На рассмотрении",
    },
    "archive_status_replied": {
        LANG_UZ: "🟢 Javob berilgan",
        LANG_OZ: "🟢 Жавоб берилган",
        LANG_RU: "🟢 Получен ответ",
    },
    "archive_status_closed": {
        LANG_UZ: "⚪️ Yakunlangan",
        LANG_OZ: "⚪️ Якунланган",
        LANG_RU: "⚪️ Закрыто",
    },
    "archive_status_cancelled": {
        LANG_UZ: "🔴 Bekor qilingan",
        LANG_OZ: "🔴 Бекор қилинган",
        LANG_RU: "🔴 Отменено",
    },
    "btn_follow_up": {
        LANG_UZ: "🔄 Qayta murojaat (Qo'shimcha savol)",
        LANG_OZ: "🔄 Қайта мурожаат (Қўшимча савол)",
        LANG_RU: "🔄 Уточняющий вопрос",
    },
    "btn_view_question_media": {
        LANG_UZ: "📎 Savol faylini ko'rish",
        LANG_OZ: "📎 Савол файлини кўриш",
        LANG_RU: "📎 Файл вопроса",
    },
    "btn_view_answer_media": {
        LANG_UZ: "📎 Javob audio/videosini ko'rish",
        LANG_OZ: "📎 Жавоб аудио/видеосини кўриш",
        LANG_RU: "📎 Медиа ответа",
    },
    "follow_up_prompt": {
        LANG_UZ: "✍️ <b>№{id}-sonli murojaatingiz bo'yicha qo'shimcha savolingizni yozing:</b><br/><br/><i>Matn, ovozli xabar, video, rasm yoki hujjat (PDF) yuborishingiz mumkin. Savolingiz avvalgi savol-javob bilan birga mutaxassislar guruhiga yetkaziladi.</i>",
        LANG_OZ: "✍️ <b>№{id}-сонли мурожаатингиз бўйича қўшимча саволингизни ёзинг:</b><br/><br/><i>Матн, овозли хабар, видео, расм ёки ҳужжат (PDF) юборишингиз мумкин. Саволингиз аввалги савол-жавоб билан бирга мутахассислар гуруҳига етказилади.</i>",
        LANG_RU: "✍️ <b>Напишите уточняющий вопрос по обращению №{id}:</b><br/><br/><i>Вы можете отправить текст, голосовое сообщение, видео, фото или документ (PDF). Ваш вопрос будет передан юристам вместе с контекстом предыдущего обращения.</i>",
    },
    "follow_up_received": {
        LANG_UZ: "✅ <b>Qo'shimcha savolingiz qabul qilindi va mutaxassislarga yetkazildi!</b><br/><br/>Javob berilishi bilan sizga xabar yetib keladi.",
        LANG_OZ: "✅ <b>Қўшимча саволингиз қабул қилинди ва мутахассисларга етказилди!</b><br/><br/>Жавоб берилиши билан сизга хабар етиб келади.",
        LANG_RU: "✅ <b>Ваш уточняющий вопрос принят и передан специалистам!</b><br/><br/>Как только поступит ответ, бот сразу вас уведомит.",
    },

    # Ro'yxatdan o'tish
    "reg_enter_first_name": {
        LANG_UZ: "<b>Ismingizni kiriting...</b><br/><p>Masalan: Aziz</p>",
        LANG_OZ: "<b>Исмингизни киритинг...</b><br/><p>Масалан: Азиз</p>",
        LANG_RU: "<b>Введите ваше имя...</b><br/><p>Например: Азиз</p>",
    },
    "reg_enter_last_name": {
        LANG_UZ: "<b>Familiyangizni kiriting...</b><br/><p>Masalan: Karimov</p>",
        LANG_OZ: "<b>Фамилиянгизни киритинг...</b><br/><p>Масалан: Каримов</p>",
        LANG_RU: "<b>Введите вашу фамилию...</b><br/><p>Например: Каримов</p>",
    },
    "reg_choose_gender": {
        LANG_UZ: "Jinsingizni tanlang:",
        LANG_OZ: "Жинсингизни танланг:",
        LANG_RU: "Выберите ваш пол:",
    },
    "reg_gender_male": {
        LANG_UZ: "Erkak",
        LANG_OZ: "Эркак",
        LANG_RU: "Мужской",
    },
    "reg_gender_female": {
        LANG_UZ: "Ayol",
        LANG_OZ: "Аёл",
        LANG_RU: "Женский",
    },
    "reg_enter_birth_year": {
        LANG_UZ: "<b>Tug‘ilgan yilingizni kiriting...</b><br/><p>Masalan: 1995</p>",
        LANG_OZ: "<b>Туғилган йилингизни киритинг...</b><br/><p>Масалан: 1995</p>",
        LANG_RU: "<b>Введите год вашего рождения...</b><br/><p>Например: 1995</p>",
    },
    "reg_invalid_year": {
        LANG_UZ: "Iltimos, haqiqiy tug'ilgan yilingizni 4 ta raqamda kiriting (masalan: 1995).",
        LANG_OZ: "Илтимос, ҳақиқий туғилган йилингизни 4 та рақамда киритинг (масалан: 1995).",
        LANG_RU: "Пожалуйста, введите корректный год рождения (например: 1995).",
    },
    "reg_enter_phone": {
        LANG_UZ: "Telefon raqamingizni yuboring yoki kiriting:",
        LANG_OZ: "Телефон рақамингизни юборинг ёки киритинг:",
        LANG_RU: "Отправьте или введите ваш номер телефона:",
    },
    "reg_send_phone_btn": {
        LANG_UZ: "📱 Raqamni yuborish",
        LANG_OZ: "📱 Рақамни юбориш",
        LANG_RU: "📱 Отправить номер",
    },
    "reg_choose_disability_type": {
        LANG_UZ: "Nogironlik guruhingizni tanlang:",
        LANG_OZ: "Ногиронлик гуруҳингизни танланг:",
        LANG_RU: "Выберите группу инвалидности:",
    },
    "reg_choose_disability_state": {
        LANG_UZ: "Nogironlik holatingizni tanlang:",
        LANG_OZ: "Ногиронлик ҳолатингизни танланг:",
        LANG_RU: "Выберите форму инвалидности:",
    },
    "reg_choose_region": {
        LANG_UZ: "Yashash hududingizni tanlang:",
        LANG_OZ: "Яшаш ҳудудингизни танланг:",
        LANG_RU: "Выберите регион проживания:",
    },
    "reg_success": {
        LANG_UZ: "Tabriklaymiz, siz muvaffaqiyatli ro'yxatdan o'tdingiz!",
        LANG_OZ: "Табриклаймиз, сиз муваффақиятли рўйхатдан ўтдингиз!",
        LANG_RU: "Поздравляем, вы успешно зарегистрировались!",
    },
    "already_registered": {
        LANG_UZ: "Siz ro'yxatdan o'tgansiz",
        LANG_OZ: "Сиз рўйхатдан ўтгансиз",
        LANG_RU: "Вы уже зарегистрированы",
    },
    "user_not_found": {
        LANG_UZ: "Siz haqingizda ma'lumot topilmadi. Iltimos, botni qayta ishga tushirish uchun /start buyrug'ini bosing.",
        LANG_OZ: "Сиз ҳақингизда маълумот топилмади. Илтимос, ботни қайта ишга тушириш учун /start буйруғини босинг.",
        LANG_RU: "Информация о вас не найдена. Пожалуйста, перезапустите бота командой /start.",
    },

    # Profil
    "profile_title": {
        LANG_UZ: "<p>Sizning profilingiz.</p>",
        LANG_OZ: "<p>Сизнинг профилингиз.</p>",
        LANG_RU: "<p>Ваш профиль.</p>",
    },
    "profile_edit_btn": {
        LANG_UZ: "🪪 O‘zgartirish",
        LANG_OZ: "🪪 Ўзгартириш",
        LANG_RU: "🪪 Изменить",
    },

    # Murojaat (Inquiry)
    "inquiry_select_section": {
        LANG_UZ: "Savolingiz qaysi yo'nalishga tegishli ekanligini tanlang:",
        LANG_OZ: "Саволингиз қайси йўналишга тегишли эканлигини танланг:",
        LANG_RU: "Выберите направление вашего вопроса:",
    },
    "inquiry_send_prompt": {
        LANG_UZ: "❓O‘z savolingizni matn, ovozli yoki video xabar ko‘rinishida yuboring.",
        LANG_OZ: "❓Ўз саволингизни матн, овозли ёки видео хабар кўринишида юборинг.",
        LANG_RU: "❓Отправьте свой вопрос в виде текста, голосового или видеосообщения.",
    },
    "inquiry_sections_btn": {
        LANG_UZ: "📁 Boʻlimlar",
        LANG_OZ: "📁 Бўлимлар",
        LANG_RU: "📁 Разделы",
    },
    "inquiry_received": {
        LANG_UZ: (
            "<p>✅ Savolingiz muvaffaqiyatli qabul qilindi. Iltimos yuristlarimiz javobini kuting.</p>"
            "<p>⏳Odatda 1-2 ish kunida javob berishga harakat qilamiz.</p>"
            "<p>Telegram kanalimizga obuna boʻlishni unutmang:</p>"
            "<p>👉 https://t.me/huquqplus</p>"
        ),
        LANG_OZ: (
            "<p>✅ Саволингиз муваффақиятли қабул қилинди. Илтимос юристларимиз жавобини кутинг.</p>"
            "<p>⏳Одатда 1-2 иш кунида жавоб беришга ҳаракат қиламиз.</p>"
            "<p>Telegram каналимизга обуна бўлишни унутманг:</p>"
            "<p>👉 https://t.me/huquqplus</p>"
        ),
        LANG_RU: (
            "<p>✅ Ваш вопрос успешно принят. Пожалуйста, дождитесь ответа наших юристов.</p>"
            "<p>⏳Обычно мы стараемся ответить в течение 1-2 рабочих дней.</p>"
            "<p>Не забудьте подписаться на наш Telegram-канал:</p>"
            "<p>👉 https://t.me/huquqplus</p>"
        ),
    },
    "auto_inquiry_confirm_prompt": {
        LANG_UZ: "❓ <b>Ushbu xabaringizni mutaxassislarimizga murojaat sifatida yuboraylikmi?</b>",
        LANG_OZ: "❓ <b>Ушбу хабарингизни мутахассисларимизга мурожаат сифатида юборайликми?</b>",
        LANG_RU: "❓ <b>Отправить это сообщение как обращение к нашим специалистам?</b>",
    },
    "btn_auto_inquiry_yes": {
        LANG_UZ: "✅ Ha, yuborilsin",
        LANG_OZ: "✅ Ҳа, юборилсин",
        LANG_RU: "✅ Да, отправить",
    },
    "btn_auto_inquiry_no": {
        LANG_UZ: "❌ Yo'q",
        LANG_OZ: "❌ Йўқ",
        LANG_RU: "❌ Нет",
    },
    "inquiry_cancel_confirm": {
        LANG_UZ: "Amaldagi murojaatingiz o'chirib yuboriladi va ko'rib chiqilmaydi. Ishonchingiz komilmi?",
        LANG_OZ: "Амалдаги мурожаатингиз ўчириб юборилади ва кўриб чиқилмайди. Ишончингиз комилми?",
        LANG_RU: "Ваше текущее обращение будет удалено и не будет рассмотрено. Вы уверены?",
    },
    "inquiry_cancelled": {
        LANG_UZ: "Murojaatingiz muvoffaqiyatli bekor qilindi!",
        LANG_OZ: "Мурожаатингиз муваффақиятли бекор қилинди!",
        LANG_RU: "Ваше обращение успешно отменено!",
    },
    "inquiry_waiting": {
        LANG_UZ: "Savolingiz javob kutmoqda!",
        LANG_OZ: "Саволингиз жавоб кутмоқда!",
        LANG_RU: "Ваш вопрос ожидает ответа!",
    },
    "rate_received_thanks": {
        LANG_UZ: "✅ <b>Bahoyingiz qabul qilindi!</b> Fikr-mulohazangiz xizmat sifatini oshirishga yordam beradi.",
        LANG_OZ: "✅ <b>Баҳойингиз қабул қилинди!</b> Фикр-мулоҳазангиз хизмат сифатини оширишга ёрдам беради.",
        LANG_RU: "✅ <b>Ваша оценка принята!</b> Ваш отзыв поможет нам улучшить качество помощи.",
    },
    "rate_leave_feedback": {
        LANG_UZ: "✍️ <i>Xohlasangiz, javob yuzasidan qisqa izoh yoki fikringizni yozib qoldirishingiz mumkin:</i>",
        LANG_OZ: "✍️ <i>Хоҳласангиз, жавоб юзасидан қисқа изоҳ ёки фикрингизни ёзиб қолдиришингиз мумкин:</i>",
        LANG_RU: "✍️ <i>При желании вы можете написать краткий отзыв или комментарий:</i>",
    },
    "rate_low_ask_again": {
        LANG_UZ: "Agar savolingizga to'liq javob ololmagan bo'lsangiz, bemalol qayta savol yo'llashingiz mumkin:",
        LANG_OZ: "Агар саволингизга тўлиқ жавоб ололмаган бўлсангиз, бемалол қайта савол йўллашингиз мумкин:",
        LANG_RU: "Если вы не получили полный ответ на свой вопрос, вы можете задать уточняющий вопрос:",
    },
    "btn_ask_again": {
        LANG_UZ: "🔄 Qayta savol yo'llash",
        LANG_OZ: "🔄 Қайта савол йўллаш",
        LANG_RU: "🔄 Задать повторный вопрос",
    },
    "appointment_claimed_citizen": {
        LANG_UZ: "✅ <b>Xushxabar!</b> Sizning yurist qabuliga arizangiz yuristimiz <b>{lawyer_name}</b> qabul qildi. Tez orada siz bilan bog'lanadi.",
        LANG_OZ: "✅ <b>Хушхабар!</b> Сизнинг юрист қабулига аризангиз юристимиз <b>{lawyer_name}</b> қабул қилди. Тез орада сиз билан боғланади.",
        LANG_RU: "✅ <b>Хорошая новость!</b> Вашу заявку на прием принял наш юрист <b>{lawyer_name}</b>. С вами свяжутся в ближайшее время.",
    },
    "inquiry_escalated_to_lawyer_citizen": {
        LANG_UZ: "⚖️ <b>Hurmatli fuqaro!</b><br/><br/>Sizning №{id}-sonli murojaatingiz batafsil tahlilni talab etganligi sababli, <b>rasmiy yurist qabuliga</b> (masofaviy online suhbat shaklida) yo'naltirildi.<br/><br/>Tez orada sizga mas'ul yurist va qabul vaqti belgilanadi hamda bu haqda xabar yuboriladi.",
        LANG_OZ: "⚖️ <b>Ҳурматли фуқаро!</b><br/><br/>Сизнинг №{id}-сонли мурожаатингиз батафсил таҳлилни талаб этганлиги сабабли, <b>расмий юрист қабулига</b> (масофавий онлайн суҳбат шаклида) йўналтирилди.<br/><br/>Тез орада сизга масъул юрист ва қабул вақти белгиланади ҳамда бу ҳақда хабар юборилади.",
        LANG_RU: "⚖️ <b>Уважаемый пользователь!</b><br/><br/>Ваше обращение №{id} требует подробного рассмотрения и было направлено на <b>официальный прием юриста</b> (в формате дистанционной консультации).<br/><br/>В ближайшее время будет назначено время консультации и ответственный юрист, и вам будет отправлено уведомление.",
    },
    "appointment_confirmed_citizen": {
        LANG_UZ: "📅 <b>Yurist qabuli belgilandi!</b><br/><br/>Hurmatli fuqaro, sizning yurist qabuli bo'yicha uchrashuv ma'lumotlaringiz tasdiqlandi:<br/>• <b>Sana va vaqt:</b> <b>{scheduled_time}</b><br/>• <b>Mas'ul yurist:</b> <b>{lawyer_name}</b><br/>• <b>Shakli:</b> {app_type}<br/><br/>Belgilangan vaqtda yuristimiz siz bilan bog'lanadi yoki online uchrashuv havolasini yuboradi.",
        LANG_OZ: "📅 <b>Юрист қабули белгиланди!</b><br/><br/>Ҳурматли фуқаро, сизнинг юрист қабули бўйича учрашув маълумотларингиз тасдиқланди:<br/>• <b>Сана ва вақт:</b> <b>{scheduled_time}</b><br/>• <b>Масъул юрист:</b> <b>{lawyer_name}</b><br/>• <b>Шакли:</b> {app_type}<br/><br/>Белгиланган вақтда юристимиз сиз билан боғланади ёки онлайн учрашув ҳаволасини юборади.",
        LANG_RU: "📅 <b>Прием юриста назначен!</b><br/><br/>Уважаемый пользователь, детали вашей консультации с юристом подтверждены:<br/>• <b>Дата и время:</b> <b>{scheduled_time}</b><br/>• <b>Ответственный юрист:</b> <b>{lawyer_name}</b><br/>• <b>Формат:</b> {app_type}<br/><br/>В назначенное время наш юрист свяжется с вами или предоставит ссылку на онлайн-встречу.",
    },
    "appointment_lawyer_changed_citizen": {
        LANG_UZ: "👨‍⚖️ <b>Yurist qabuli yangilandi!</b><br/><br/>Hurmatli fuqaro, sizning qabulingiz bo'yicha mas'ul yurist o'zgardi:<br/>• <b>Yangi mas'ul yurist:</b> <b>{lawyer_name}</b><br/><br/>Belgilangan vaqtda yuristimiz siz bilan bog'lanadi.",
        LANG_OZ: "👨‍⚖️ <b>Юрист қабули янгиланди!</b><br/><br/>Ҳурматли фуқаро, сизнинг қабулингиз бўйича масъул юрист ўзгарди:<br/>• <b>Янги масъул юрист:</b> <b>{lawyer_name}</b><br/><br/>Белгиланган вақтда юристимиз сиз билан боғланади.",
        LANG_RU: "👨‍⚖️ <b>Запись к юристу обновлена!</b><br/><br/>Уважаемый пользователь, по вашей записи назначен другой юрист:<br/>• <b>Новый ответственный юрист:</b> <b>{lawyer_name}</b><br/><br/>В назначенное время юрист свяжется с вами.",
    },
    "appointment_time_changed_citizen": {
        LANG_UZ: "📅 <b>Qabul vaqti o'zgartirildi!</b><br/><br/>Hurmatli fuqaro, sizning yurist qabulingiz vaqti yangilandi:<br/>• <b>Yangi vaqt:</b> <b>{scheduled_time}</b><br/>• <b>Mas'ul yurist:</b> <b>{lawyer_name}</b><br/><br/>Iltimos, ushbu vaqtda aloqada bo'ling!",
        LANG_OZ: "📅 <b>Қабул вақти ўзгартирилди!</b><br/><br/>Ҳурматли фуқаро, сизнинг юрист қабулингиз вақти янгиланди:<br/>• <b>Янги вақт:</b> <b>{scheduled_time}</b><br/>• <b>Масъул юрист:</b> <b>{lawyer_name}</b><br/><br/>Илтимос, ушбу вақтда алоқада бўлинг!",
        LANG_RU: "📅 <b>Время приема изменено!</b><br/><br/>Уважаемый пользователь, время вашей консультации обновлено:<br/>• <b>Новое время:</b> <b>{scheduled_time}</b><br/>• <b>Ответственный юрист:</b> <b>{lawyer_name}</b><br/><br/>Пожалуйста, будьте на связи в назначенное время!",
    },
    "appointment_cancelled_citizen": {
        LANG_UZ: "⚠️ <b>Hurmatli fuqaro!</b> Sizning yurist qabuliga arizangiz (№{app_id}) bekor qilindi.{reason_text}<br/>Qayta yozilish uchun bot bosh menyusidan foydalanishingiz mumkin.",
        LANG_OZ: "⚠️ <b>Ҳурматли фуқаро!</b> Сизнинг юрист қабулига аризангиз (№{app_id}) бекор қилинди.{reason_text}<br/>Қайта ёзилиш учун бот бош менюсидан фойдаланишингиз мумкин.",
        LANG_RU: "⚠️ <b>Уважаемый пользователь!</b> Ваша запись к юристу (№{app_id}) отменена.{reason_text}<br/>Для повторной записи вы можете воспользоваться главным меню бота.",
    },
    "appointment_restored_citizen": {
        LANG_UZ: "✅ <b>Hurmatli fuqaro!</b> Sizning yurist qabuliga arizangiz (№{app_id}) ma'muriyat tomonidan qayta tiklandi!<br/>Tez orada mutaxassis siz bilan bog'lanadi yoki qabul vaqti belgilanadi.",
        LANG_OZ: "✅ <b>Ҳурматли фуқаро!</b> Сизнинг юрист қабулига аризангиз (№{app_id}) маъмурият томонидан қайта тикланди!<br/>Тез орада мутахассис сиз билан боғланади ёки қабул вақти белгиланади.",
        LANG_RU: "✅ <b>Уважаемый пользователь!</b> Ваша запись к юристу (№{app_id}) была восстановлена администрацией!<br/>Специалист свяжется с вами или будет назначено время приема.",
    },
    "appointment_media_limit_reached": {
        LANG_UZ: "⚠️ <b>Limitga yetildi:</b> Qabulga ko'pi bilan 10 ta fayl yuborishingiz mumkin. Qo'shimcha fayllar qabul qilinmaydi.",
        LANG_OZ: "⚠️ <b>Лимитга етилди:</b> Қабулга кўпи билан 10 та файл юборишингиз мумкин. Қўшимча файллар қабул қилинмайди.",
        LANG_RU: "⚠️ <b>Достигнут лимит:</b> К записи можно прикрепить не более 10 файлов. Дополнительные файлы не принимаются.",
    },

    "appointment_completed_rate_prompt": {
        LANG_UZ: "📞 <b>Hurmatli fuqaro!</b> Yuristimiz bilan online suhbatingiz yakunlandi.<br/><br/>Iltimos, o'tkazilgan suhbat va ko'rsatilgan huquqiy yordam sifatini <b>1 dan 5 gacha baholang:</b>",
        LANG_OZ: "📞 <b>Ҳурматли фуқаро!</b> Юристимиз билан онлайн суҳбатингиз якунланди.<br/><br/>Илтимос, ўтказилган суҳбат ва кўрсатилган ҳуқуқий ёрдам сифатини <b>1 дан 5 гача баҳоланг:</b>",
        LANG_RU: "📞 <b>Уважаемый пользователь!</b> Ваша онлайн-консультация с юристом завершена.<br/><br/>Пожалуйста, оцените качество консультации от <b>1 до 5:</b>",
    },
    "feedback_recorded": {
        LANG_UZ: "✅ Fikr-mulohazangiz saqlandi. Rahmat!",
        LANG_OZ: "✅ Фикр-мулоҳазангиз сақланди. Раҳмат!",
        LANG_RU: "✅ Ваш отзыв сохранен. Спасибо!",
    },

    # Yurist qabuli (Appointment)
    "appointment_remote_btn": {
        LANG_UZ: "📞 Masofaviy qabul",
        LANG_OZ: "📞 Масофавий қабул",
        LANG_RU: "📞 Дистанционный прием",
    },
    "appointment_in_person_btn": {
        LANG_UZ: "🏢 Yuzma-yuz qabul",
        LANG_OZ: "🏢 Юзма-юз қабул",
        LANG_RU: "🏢 Очный прием",
    },

    # Texnik yordam (Help)
    "help_start_text": {
        LANG_UZ: "❗️Agarda sizda botdan foydalanish va savolingizni yuborish bo‘yicha muammo yuzaga kelgan bo‘lsa, telefon raqamingizni qoldiring. Siz bilan bog‘lanib tushuntirish berib o‘tamiz!",
        LANG_OZ: "❗️Агарда сизда ботдан фойдаланиш ва саволингизни юбориш бўйича муаммо юзага келган бўлса, телефон рақамингизни қолдиринг. Сиз билан боғланиб тушунтириш бериб ўтамиз!",
        LANG_RU: "❗️Если у вас возникли трудности с использованием бота или отправкой вопроса, оставьте свой номер телефона. Мы свяжемся с вами и поможем разобраться!",
    },
    "help_problem_prompt": {
        LANG_UZ: "Botdan foydalanishda sizga yordam kerakmi? Muammoingizni yozing.",
        LANG_OZ: "Ботдан фойдаланишда сизга ёрдам керакми? Муаммоингизни ёзинг.",
        LANG_RU: "Вам нужна помощь по использованию бота? Опишите вашу проблему.",
    },
    "help_success": {
        LANG_UZ: "✅ Sizning murojaatingiz qabul qilindi. Tez orada sizga yordam beramiz.",
        LANG_OZ: "✅ Сизнинг мурожаатингиз қабул қилинди. Тез орада сизга ёрдам берамиз.",
        LANG_RU: "✅ Ваше обращение принято. Мы свяжемся с вами в ближайшее время.",
    },

    # Biriktirish (A bosqich)
    "assign_only_admins": {
        LANG_UZ: "⛔ Bu amal faqat adminlar uchun",
        LANG_OZ: "⛔ Бу амал фақат админлар учун",
        LANG_RU: "⛔ Это действие только для администраторов",
    },
    "assign_not_found": {
        LANG_UZ: "⚠️ Murojaat topilmadi.",
        LANG_OZ: "⚠️ Мурожаат топилмади.",
        LANG_RU: "⚠️ Обращение не найдено.",
    },
    "assign_vol_not_found": {
        LANG_UZ: "⚠️ Volontyor topilmadi.",
        LANG_OZ: "⚠️ Волонтёр топилмади.",
        LANG_RU: "⚠️ Волонтёр не найден.",
    },
    "assign_already": {
        LANG_UZ: "⚠️ Bu murojaat allaqachon {name} ga biriktirilgan.",
        LANG_OZ: "⚠️ Бу мурожаат аллақачон {name} га бириктирилган.",
        LANG_RU: "⚠️ Это обращение уже назначено: {name}.",
    },
    "assign_db_fail": {
        LANG_UZ: "❌ Biriktirish saqlanmadi ({reason}).",
        LANG_OZ: "❌ Бириктириш сақланмади ({reason}).",
        LANG_RU: "❌ Не удалось сохранить назначение ({reason}).",
    },
    "assign_retry_btn": {
        LANG_UZ: "🔁 Qaytadan urinish",
        LANG_OZ: "🔁 Қайтадан уриниш",
        LANG_RU: "🔁 Повторить",
    },
    "assign_sent_ok": {
        LANG_UZ: "✅ Yuborildi",
        LANG_OZ: "✅ Юборилди",
        LANG_RU: "✅ Отправлено",
    },
    "assign_dm_blocked": {
        LANG_UZ: "⚠️ Volontyor botni bloklagan — xabar yetmadi.",
        LANG_OZ: "⚠️ Волонтёр ботни блоклаган — хабар етмади.",
        LANG_RU: "⚠️ Волонтёр заблокировал бота — сообщение не доставлено.",
    },
    "assign_dm_nostart": {
        LANG_UZ: "⚠️ Volontyor botni hali ishga tushirmagan.",
        LANG_OZ: "⚠️ Волонтёр ботни ҳали ишга туширмаган.",
        LANG_RU: "⚠️ Волонтёр ещё не запускал бота.",
    },
    "assign_dm_fail": {
        LANG_UZ: "⚠️ Xabar yuborilmadi ({reason}).",
        LANG_OZ: "⚠️ Хабар юборилмади ({reason}).",
        LANG_RU: "⚠️ Не удалось отправить сообщение ({reason}).",
    },
    "assign_dm_text": {
        LANG_UZ: "📌 <b>Murojaat sizga biriktirildi</b> (№{id}, {section}).<br/>{link}<br/>Iltimos, fuqaroga guruhda reply qilib javob bering.",
        LANG_OZ: "📌 <b>Мурожаат сизга бириктирилди</b> (№{id}, {section}).<br/>{link}<br/>Илтимос, фуқарога гуруҳда reply қилиб жавоб беринг.",
        LANG_RU: "📌 <b>Обращение назначено вам</b> (№{id}, {section}).<br/>{link}<br/>Пожалуйста, ответьте гражданину в группе через reply.",
    },
    "assign_moved_dm": {
        LANG_UZ: "ℹ️ №{id}-sonli murojaat boshqa volontyorga o'tkazildi.",
        LANG_OZ: "ℹ️ №{id}-сонли мурожаат бошқа волонтёрга ўтказилди.",
        LANG_RU: "ℹ️ Обращение №{id} передано другому волонтёру.",
    },
    "assign_group_done": {
        LANG_UZ: "Ushbu murojaat biriktirildi.",
        LANG_OZ: "Ушбу мурожаат бириктирилди.",
        LANG_RU: "Это обращение назначено.",
    },
    "assign_list_title": {
        LANG_UZ: "📌 <b>№{id} biriktirish — volontyor tanlang</b><br/>📁 {section}",
        LANG_OZ: "📌 <b>№{id} бириктириш — волонтёр танланг</b><br/>📁 {section}",
        LANG_RU: "📌 <b>Назначение №{id} — выберите волонтёра</b><br/>📁 {section}",
    },
    "assign_current": {
        LANG_UZ: "Hozirgi mas'ul: {name}",
        LANG_OZ: "Ҳозирги масъул: {name}",
        LANG_RU: "Текущий ответственный: {name}",
    },
    "assign_open": {
        LANG_UZ: "{n} ochiq",
        LANG_OZ: "{n} очиқ",
        LANG_RU: "{n} откр.",
    },
    "assign_other_section": {
        LANG_UZ: "boshqa soha",
        LANG_OZ: "бошқа соҳа",
        LANG_RU: "другая сфера",
    },
    "assign_empty": {
        LANG_UZ: "Faol volontyor topilmadi.",
        LANG_OZ: "Фаол волонтёр топилмади.",
        LANG_RU: "Активные волонтёры не найдены.",
    },
    "vol_sections_title": {
        LANG_UZ: "🗂 <b>{name}</b> — sohalari (bosib qo'shing/olib tashlang):",
        LANG_OZ: "🗂 <b>{name}</b> — соҳалари (босиб қўшинг/олиб ташланг):",
        LANG_RU: "🗂 <b>{name}</b> — сферы (нажмите, чтобы добавить/убрать):",
    },

    # Biriktirish eslatmalari (B bosqich)
    "assign_remind_first": {
        LANG_UZ: "⏰ <b>Eslatma:</b> Iltimos, bu murojaatga javobni yuboring.<br/>{link}",
        LANG_OZ: "⏰ <b>Эслатма:</b> Илтимос, бу мурожаатга жавобни юборинг.<br/>{link}",
        LANG_RU: "⏰ <b>Напоминание:</b> Пожалуйста, отправьте ответ на это обращение.<br/>{link}",
    },
    "assign_remind_follow": {
        LANG_UZ: "⏰ <b>Eslatma:</b> fuqaro murojaatiga javobni tayyorlang, «✅ Javobni tasdiqlatish» orqali tekshiruvdan o'tkazing va fuqaroga yuboring.<br/>{link}",
        LANG_OZ: '⏰ <b>Эслатма:</b> фуқаро мурожаатига жавобни тайёрланг, «✅ Жавобни тасдиқлатиш» орқали текширувдан ўтказинг ва фуқарога юборинг.<br/>{link}',
        LANG_RU: '⏰ <b>Напоминание:</b> подготовьте ответ гражданину, проверьте его через «✅ Проверить ответ» и отправьте гражданину.<br/>{link}',
    },
    "assign_remind_blocked_admin": {
        LANG_UZ: "⚠️ {name} botni bloklagan — №{id} bo'yicha eslatma yetmayapti.",
        LANG_OZ: "⚠️ {name} ботни блоклаган — №{id} бўйича эслатма етмаяпти.",
        LANG_RU: "⚠️ {name} заблокировал(а) бота — напоминание по №{id} не доходит.",
    },

    # Volontyor menyusi (C bosqich)
    "menu_vol_result": {
        LANG_UZ: "📊 Mening natijam",
        LANG_OZ: "📊 Менинг натижам",
        LANG_RU: "📊 Мой результат",
    },
    "menu_vol_assigns": {
        LANG_UZ: "📌 Biriktirilgan murojaatlar",
        LANG_OZ: "📌 Бириктирилган мурожаатлар",
        LANG_RU: "📌 Назначенные обращения",
    },
    "menu_vol_review": {
        LANG_UZ: "✅ Javobni tasdiqlatish",
        LANG_OZ: "✅ Жавобни тасдиқлатиш",
        LANG_RU: "✅ Проверить ответ",
    },
    "inquiry_rate_prompt": {
        LANG_UZ: "⭐ <b>Yuristimiz bergan javobni 1 dan 5 gacha baholang:</b>",
        LANG_OZ: "⭐ <b>Юристимиз берган жавобни 1 дан 5 гача баҳоланг:</b>",
        LANG_RU: "⭐ <b>Оцените ответ юриста от 1 до 5:</b>",
    },
    "inquiry_type_prompt": {
        LANG_UZ: "Iltimos, murojaatingizni matn, ovozli xabar, video, rasm yoki hujjat ko'rinishida yuboring.",
        LANG_OZ: "Илтимос, мурожаатингизни матн, овозли хабар, видео, расм ёки ҳужжат кўринишида юборинг.",
        LANG_RU: "Пожалуйста, отправьте обращение текстом, голосовым сообщением, видео, фото или документом.",
    },
    "ai_answer_footer": {
        LANG_UZ: "<i>ℹ️ Ushbu javob sun'iy intellekt tomonidan yozilgan.</i>",
        LANG_OZ: "<i>ℹ️ Ушбу жавоб сунъий интеллект томонидан ёзилган.</i>",
        LANG_RU: "<i>ℹ️ Этот ответ написан искусственным интеллектом.</i>",
    },
    "btn_ask_lawyer": {
        LANG_UZ: "👨‍⚖️ Huquqshunosdan javob olish",
        LANG_OZ: "👨‍⚖️ Ҳуқуқшуносдан жавоб олиш",
        LANG_RU: "👨‍⚖️ Получить ответ юриста",
    },
    "ai_answer_wait": {
        LANG_UZ: "⏳ Savolingiz ko'rib chiqilmoqda...",
        LANG_OZ: "⏳ Саволингиз кўриб чиқилмоқда...",
        LANG_RU: "⏳ Ваш вопрос рассматривается...",
    },
    "btn_ai_useful": {
        LANG_UZ: "👍 Foydali",
        LANG_OZ: "👍 Фойдали",
        LANG_RU: "👍 Полезно",
    },
    "btn_ai_not_useful": {
        LANG_UZ: "👎 Foydali emas",
        LANG_OZ: "👎 Фойдали эмас",
        LANG_RU: "👎 Не помогло",
    },
    "ai_feedback_thanks": {
        LANG_UZ: "Rahmat, bahoingiz qabul qilindi.",
        LANG_OZ: "Раҳмат, баҳоингиз қабул қилинди.",
        LANG_RU: "Спасибо, ваша оценка принята.",
    },
    "ai_feedback_down_hint": {
        LANG_UZ: "Rahmat. Aniq javob olish uchun «Huquqshunosdan javob olish» tugmasini bosing.",
        LANG_OZ: "Раҳмат. Аниқ жавоб олиш учун «Ҳуқуқшуносдан жавоб олиш» тугмасини босинг.",
        LANG_RU: "Спасибо. Чтобы получить точный ответ, нажмите «Получить ответ юриста».",
    },
    "ai_escalate_already": {
        LANG_UZ: "Bu savol huquqshunoslarga allaqachon yuborilgan.",
        LANG_OZ: "Бу савол ҳуқуқшуносларга аллақачон юборилган.",
        LANG_RU: "Этот вопрос уже передан юристам.",
    },
    "app_active_warning": {
        LANG_UZ: "⚠️ <b>Sizda ushbu yo'nalish bo'yicha faol ariza mavjud!</b><br/><br/>📋 <b>Ariza raqami:</b> №{id}<br/>🏢 <b>Qabul shakli:</b> {app_type}<br/>📅 <b>Belgilangan vaqt:</b> <b>{time}</b><br/>👨‍⚖️ <b>Yurist:</b> {lawyer}<br/>🔄 <b>Holati:</b> {status}<br/><br/>ℹ️ <i>Har bir yo'nalish bo'yicha bir vaqtda faqat 1 ta faol ariza bo'lishi mumkin. Yangi ariza uchun avvalgisi yakunlanishi yoki bekor qilinishi kerak.</i>",
        LANG_OZ: "⚠️ <b>Сизда ушбу йўналиш бўйича фаол ариза мавжуд!</b><br/><br/>📋 <b>Ариза рақами:</b> №{id}<br/>🏢 <b>Қабул шакли:</b> {app_type}<br/>📅 <b>Белгиланган вақт:</b> <b>{time}</b><br/>👨‍⚖️ <b>Юрист:</b> {lawyer}<br/>🔄 <b>Ҳолати:</b> {status}<br/><br/>ℹ️ <i>Ҳар бир йўналиш бўйича бир вақтда фақат 1 та фаол ариза бўлиши мумкин. Янги ариза учун аввалгиси якунланиши ёки бекор қилиниши керак.</i>",
        LANG_RU: "⚠️ <b>У вас уже есть активная запись по этому направлению!</b><br/><br/>📋 <b>Номер заявки:</b> №{id}<br/>🏢 <b>Формат приема:</b> {app_type}<br/>📅 <b>Время приема:</b> <b>{time}</b><br/>👨‍⚖️ <b>Юрист:</b> {lawyer}<br/>🔄 <b>Статус:</b> {status}<br/><br/>ℹ️ <i>По каждому направлению одновременно возможна только одна активная запись. Для новой записи дождитесь завершения или отмените текущую.</i>",
    },
    "app_time_not_set": {LANG_UZ: "Belgilanmagan", LANG_OZ: "Белгиланмаган", LANG_RU: "Не назначено"},
    "app_status_pending": {LANG_UZ: "⏳ Ko'rib chiqilmoqda", LANG_OZ: "⏳ Кўриб чиқилмоқда", LANG_RU: "⏳ На рассмотрении"},
    "app_status_accepted": {LANG_UZ: "✅ Qabul qilingan", LANG_OZ: "✅ Қабул қилинган", LANG_RU: "✅ Принято"},
    "app_lawyer_any": {LANG_UZ: "Istalgan bo'sh yurist", LANG_OZ: "Исталган бўш юрист", LANG_RU: "Любой свободный юрист"},
    "app_lawyer_office": {LANG_UZ: "Bosh ofis navbatchi yuristlari", LANG_OZ: "Бош офис навбатчи юристлари", LANG_RU: "Дежурные юристы главного офиса"},
    "btn_app_cancel_mine": {LANG_UZ: "❌ Qabulni bekor qilish", LANG_OZ: "❌ Қабулни бекор қилиш", LANG_RU: "❌ Отменить прием"},
    "btn_send": {LANG_UZ: "📤 Yuborish", LANG_OZ: "📤 Юбориш", LANG_RU: "📤 Отправить"},
    "btn_app_confirm": {LANG_UZ: "✅ Qabulni tasdiqlash", LANG_OZ: "✅ Қабулни тасдиқлаш", LANG_RU: "✅ Подтвердить прием"},
    "app_problem_prompt": {
        LANG_UZ: "📌 <b>Muammoingizni bayon qiling va zarur hujjatlarni ilova qiling:</b><br/><br/>• ✍️ matn<br/>• 🎤 ovozli xabar<br/>• 📹 video yoki video-xabar (krujok)<br/>• 📄 PDF yoki Word hujjat (sud hujjati, ariza, tibbiy ma'lumotnoma)<br/>• 📷 hujjat surati<br/><br/>ℹ️ <i>Bir nechta xabar yoki fayl yuborishingiz mumkin (ko'pi bilan 10 ta fayl). Tugatgach, pastdagi <b>📤 Yuborish</b> tugmasini bosing.</i>",
        LANG_OZ: "📌 <b>Муаммоингизни баён қилинг ва зарур ҳужжатларни илова қилинг:</b><br/><br/>• ✍️ матн<br/>• 🎤 овозли хабар<br/>• 📹 видео ёки видео-хабар (кружок)<br/>• 📄 PDF ёки Word ҳужжат (суд ҳужжати, ариза, тиббий маълумотнома)<br/>• 📷 ҳужжат сурати<br/><br/>ℹ️ <i>Бир нечта хабар ёки файл юборишингиз мумкин (кўпи билан 10 та файл). Тугатгач, пастдаги <b>📤 Юбориш</b> тугмасини босинг.</i>",
        LANG_RU: "📌 <b>Опишите проблему и прикрепите нужные документы:</b><br/><br/>• ✍️ текст<br/>• 🎤 голосовое сообщение<br/>• 📹 видео или видеосообщение<br/>• 📄 PDF или Word документ<br/>• 📷 фото документа<br/><br/>ℹ️ <i>Можно отправить несколько сообщений или файлов (не более 10 файлов). Затем нажмите <b>📤 Отправить</b> внизу.</i>",
    },
    "app_preview": {
        LANG_UZ: "📋 <b>Qabul ma'lumotlarini tasdiqlang:</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>🏢 <b>Qabul shakli:</b> {app_type}<br/>📎 <b>Biriktirilgan fayllar:</b> {media}<br/><br/>📝 <b>Muammo mazmuni:</b><br/><blockquote>{desc}</blockquote>━━━━━━━━━━━━━━━━━━━━━<br/><i>Barcha ma'lumotlar to'g'rimi?</i>",
        LANG_OZ: "📋 <b>Қабул маълумотларини тасдиқланг:</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>🏢 <b>Қабул шакли:</b> {app_type}<br/>📎 <b>Бириктирилган файллар:</b> {media}<br/><br/>📝 <b>Муаммо мазмуни:</b><br/><blockquote>{desc}</blockquote>━━━━━━━━━━━━━━━━━━━━━<br/><i>Барча маълумотлар тўғрими?</i>",
        LANG_RU: "📋 <b>Подтвердите данные записи:</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>🏢 <b>Формат приема:</b> {app_type}<br/>📎 <b>Прикрепленные файлы:</b> {media}<br/><br/>📝 <b>Описание проблемы:</b><br/><blockquote>{desc}</blockquote>━━━━━━━━━━━━━━━━━━━━━<br/><i>Все данные верны?</i>",
    },
    "app_media_text_only": {LANG_UZ: "Faqat matn", LANG_OZ: "Фақат матн", LANG_RU: "Только текст"},
    "app_media_count": {LANG_UZ: "📎 {n} ta fayl ({names})", LANG_OZ: "📎 {n} та файл ({names})", LANG_RU: "📎 файлов: {n} ({names})"},
    "app_desc_by_media": {
        LANG_UZ: "(Muammo audio/video/fayl orqali bayon etilgan)",
        LANG_OZ: "(Муаммо аудио/видео/файл орқали баён этилган)",
        LANG_RU: "(Проблема описана в аудио/видео/файле)",
    },
    "app_confirm_prompt": {
        LANG_UZ: "Tasdiqlash uchun <b>✅ Qabulni tasdiqlash</b> tugmasini bosing:",
        LANG_OZ: "Тасдиқлаш учун <b>✅ Қабулни тасдиқлаш</b> тугмасини босинг:",
        LANG_RU: "Для подтверждения нажмите <b>✅ Подтвердить прием</b>:",
    },
    "media_voice": {LANG_UZ: "Ovozli xabar", LANG_OZ: "Овозли хабар", LANG_RU: "Голосовое сообщение"},
    "media_video_note": {LANG_UZ: "Video xabar (krujok)", LANG_OZ: "Видео хабар (кружок)", LANG_RU: "Видеосообщение"},
    "media_video": {LANG_UZ: "Video fayl", LANG_OZ: "Видео файл", LANG_RU: "Видеофайл"},
    "media_photo": {LANG_UZ: "Fotohujjat", LANG_OZ: "Фотоҳужжат", LANG_RU: "Фото документа"},
    "media_document": {LANG_UZ: "Hujjat", LANG_OZ: "Ҳужжат", LANG_RU: "Документ"},
    "app_unsupported_media": {
        LANG_UZ: "⚠️ Iltimos, matn, ovozli xabar, video, PDF hujjat yoki rasm yuboring.",
        LANG_OZ: "⚠️ Илтимос, матн, овозли хабар, видео, PDF ҳужжат ёки расм юборинг.",
        LANG_RU: "⚠️ Пожалуйста, отправьте текст, голосовое сообщение, видео, PDF документ или фото.",
    },
    "app_nothing_to_send": {
        LANG_UZ: "⚠️ <b>Avval muammoingizni yozing yoki fayl/audio yuboring.</b><br/>So'ng <b>📤 Yuborish</b> tugmasini bosing.",
        LANG_OZ: "⚠️ <b>Аввал муаммоингизни ёзинг ёки файл/аудио юборинг.</b><br/>Сўнг <b>📤 Юбориш</b> тугмасини босинг.",
        LANG_RU: "⚠️ <b>Сначала опишите проблему или отправьте файл/аудио.</b><br/>Затем нажмите <b>📤 Отправить</b>.",
    },
    "app_files_received": {
        LANG_UZ: "<br/>📎 <b>Qabul qilingan fayllar ({n} ta):</b> <i>{names}</i>",
        LANG_OZ: "<br/>📎 <b>Қабул қилинган файллар ({n} та):</b> <i>{names}</i>",
        LANG_RU: "<br/>📎 <b>Принятые файлы ({n}):</b> <i>{names}</i>",
    },
    "app_info_received": {
        LANG_UZ: "📥 <b>Qabul qilindi.</b>{files}<br/><br/>Yana ma'lumot yoki fayl yuborishingiz mumkin. Tugatgach, <b>📤 Yuborish</b> tugmasini bosing.",
        LANG_OZ: "📥 <b>Қабул қилинди.</b>{files}<br/><br/>Яна маълумот ёки файл юборишингиз мумкин. Тугатгач, <b>📤 Юбориш</b> тугмасини босинг.",
        LANG_RU: "📥 <b>Принято.</b>{files}<br/><br/>Можно отправить ещё текст или файлы. Затем нажмите <b>📤 Отправить</b>.",
    },
    "app_already_active_short": {
        LANG_UZ: "⚠️ Sizda ushbu yo'nalish bo'yicha faol ariza (№{id}) mavjud.",
        LANG_OZ: "⚠️ Сизда ушбу йўналиш бўйича фаол ариза (№{id}) мавжуд.",
        LANG_RU: "⚠️ У вас уже есть активная запись по этому направлению (№{id}).",
    },
    "app_submitted": {
        LANG_UZ: "✅ <b>Arizangiz qabul qilindi (№{id}).</b><br/><br/>🏢 <b>Qabul shakli:</b> {app_type}<br/>📋 <b>Holati:</b> ⏳ Ko'rib chiqilmoqda<br/><br/>ℹ️ <i>Yuristlarimiz arizangizni ko'rib chiqib, siz bilan bog'lanishadi yoki suhbat vaqtini belgilashadi.</i>",
        LANG_OZ: "✅ <b>Аризангиз қабул қилинди (№{id}).</b><br/><br/>🏢 <b>Қабул шакли:</b> {app_type}<br/>📋 <b>Ҳолати:</b> ⏳ Кўриб чиқилмоқда<br/><br/>ℹ️ <i>Юристларимиз аризангизни кўриб чиқиб, сиз билан боғланишади ёки суҳбат вақтини белгилашади.</i>",
        LANG_RU: "✅ <b>Ваша заявка принята (№{id}).</b><br/><br/>🏢 <b>Формат приема:</b> {app_type}<br/>📋 <b>Статус:</b> ⏳ На рассмотрении<br/><br/>ℹ️ <i>Юристы рассмотрят заявку и свяжутся с вами или назначат время беседы.</i>",
    },
    "app_not_found": {LANG_UZ: "Ariza topilmadi.", LANG_OZ: "Ариза топилмади.", LANG_RU: "Заявка не найдена."},
    "app_already_closed": {
        LANG_UZ: "Bu ariza allaqachon yakunlangan yoki bekor qilingan.",
        LANG_OZ: "Бу ариза аллақачон якунланган ёки бекор қилинган.",
        LANG_RU: "Эта заявка уже завершена или отменена.",
    },
    "btn_app_cancel_yes": {LANG_UZ: "✅ Ha, bekor qilinsin", LANG_OZ: "✅ Ҳа, бекор қилинсин", LANG_RU: "✅ Да, отменить"},
    "btn_app_cancel_no": {LANG_UZ: "⬅️ Yo'q, qolsin", LANG_OZ: "⬅️ Йўқ, қолсин", LANG_RU: "⬅️ Нет, оставить"},
    "app_cancel_confirm": {
        LANG_UZ: "❓ <b>№{id} qabul arizangizni bekor qilmoqchimisiz?</b>",
        LANG_OZ: "❓ <b>№{id} қабул аризангизни бекор қилмоқчимисиз?</b>",
        LANG_RU: "❓ <b>Отменить запись №{id}?</b>",
    },
    "app_cancelled_short": {LANG_UZ: "Qabul bekor qilindi.", LANG_OZ: "Қабул бекор қилинди.", LANG_RU: "Запись отменена."},
    "app_cancelled_by_citizen": {
        LANG_UZ: "✅ <b>№{id} qabul arizangiz bekor qilindi.</b><br/>Endi yangi ariza topshirishingiz mumkin.",
        LANG_OZ: "✅ <b>№{id} қабул аризангиз бекор қилинди.</b><br/>Энди янги ариза топширишингиз мумкин.",
        LANG_RU: "✅ <b>Запись №{id} отменена.</b><br/>Теперь можно оформить новую запись.",
    },
    "arch_title": {LANG_UZ: "📌 <b>MUROJAAT №{id}</b>", LANG_OZ: "📌 <b>МУРОЖААТ №{id}</b>", LANG_RU: "📌 <b>ОБРАЩЕНИЕ №{id}</b>"},
    "arch_followup_of": {
        LANG_UZ: "🔗 <i>№{id} murojaat bo'yicha qo'shimcha savol</i><br/><br/>",
        LANG_OZ: "🔗 <i>№{id} мурожаат бўйича қўшимча савол</i><br/><br/>",
        LANG_RU: "🔗 <i>Уточняющий вопрос по обращению №{id}</i><br/><br/>",
    },
    "arch_meta": {
        LANG_UZ: "📁 <b>Bo'lim:</b> {section}<br/>📅 <b>Yuborilgan sana:</b> {date}<br/>🔄 <b>Holati:</b> {status}",
        LANG_OZ: "📁 <b>Бўлим:</b> {section}<br/>📅 <b>Юборилган сана:</b> {date}<br/>🔄 <b>Ҳолати:</b> {status}",
        LANG_RU: "📁 <b>Раздел:</b> {section}<br/>📅 <b>Дата отправки:</b> {date}<br/>🔄 <b>Статус:</b> {status}",
    },
    "arch_assigned": {
        LANG_UZ: "👤 <b>Mas'ul mutaxassis biriktirilgan:</b> {date}",
        LANG_OZ: "👤 <b>Масъул мутахассис бириктирилган:</b> {date}",
        LANG_RU: "👤 <b>Назначен ответственный специалист:</b> {date}",
    },
    "arch_waiting_assign": {
        LANG_UZ: "👤 <i>Mas'ul mutaxassis tez orada biriktiriladi.</i>",
        LANG_OZ: "👤 <i>Масъул мутахассис тез орада бириктирилади.</i>",
        LANG_RU: "👤 <i>Ответственный специалист будет назначен в ближайшее время.</i>",
    },
    "arch_your_question": {LANG_UZ: "❓ <b>Sizning savolingiz:</b>", LANG_OZ: "❓ <b>Сизнинг саволингиз:</b>", LANG_RU: "❓ <b>Ваш вопрос:</b>"},
    "arch_answer_title": {LANG_UZ: "<b>💬 Mutaxassis javobi{date}:</b>", LANG_OZ: "<b>💬 Мутахассис жавоби{date}:</b>", LANG_RU: "<b>💬 Ответ специалиста{date}:</b>"},
    "arch_answer_voice": {
        LANG_UZ: "🎤 <i>Ovozli xabar orqali javob berildi</i>", LANG_OZ: "🎤 <i>Овозли хабар орқали жавоб берилди</i>",
        LANG_RU: "🎤 <i>Ответ голосовым сообщением</i>",
    },
    "arch_answer_video": {
        LANG_UZ: "📹 <i>Video xabar orqali javob berildi</i>", LANG_OZ: "📹 <i>Видео хабар орқали жавоб берилди</i>",
        LANG_RU: "📹 <i>Ответ видеосообщением</i>",
    },
    "arch_answer_file": {
        LANG_UZ: "📎 <i>Fayl orqali javob berildi</i>", LANG_OZ: "📎 <i>Файл орқали жавоб берилди</i>", LANG_RU: "📎 <i>Ответ файлом</i>",
    },
    "arch_pending_answer": {
        LANG_UZ: "⏳ <i>Savolingiz ko'rib chiqilmoqda. Javob tayyor bo'lishi bilan yuboriladi.</i>",
        LANG_OZ: "⏳ <i>Саволингиз кўриб чиқилмоқда. Жавоб тайёр бўлиши билан юборилади.</i>",
        LANG_RU: "⏳ <i>Вопрос рассматривается. Ответ будет отправлен, как только будет готов.</i>",
    },
    "arch_status_title": {LANG_UZ: "<b>💬 Murojaat holati:</b>", LANG_OZ: "<b>💬 Мурожаат ҳолати:</b>", LANG_RU: "<b>💬 Статус обращения:</b>"},
    "arch_cancelled": {
        LANG_UZ: "🔴 <i>Ushbu murojaat bekor qilingan.</i>", LANG_OZ: "🔴 <i>Ушбу мурожаат бекор қилинган.</i>", LANG_RU: "🔴 <i>Обращение отменено.</i>",
    },
    "arch_closed": {LANG_UZ: "Yakunlangan", LANG_OZ: "Якунланган", LANG_RU: "Закрыто"},
    "arch_rating": {LANG_UZ: "<b>⭐️ Bahongiz:</b> {stars}", LANG_OZ: "<b>⭐️ Баҳоингиз:</b> {stars}", LANG_RU: "<b>⭐️ Ваша оценка:</b> {stars}"},
    "arch_not_rated": {LANG_UZ: "<i>Baholanmagan</i>", LANG_OZ: "<i>Баҳоланмаган</i>", LANG_RU: "<i>Не оценено</i>"},
    "arch_cancel_done": {LANG_UZ: "Murojaatingiz bekor qilindi.", LANG_OZ: "Мурожаатингиз бекор қилинди.", LANG_RU: "Ваше обращение отменено."},
    "arch_cancel_impossible": {LANG_UZ: "Bu murojaatni bekor qilib bo'lmaydi.", LANG_OZ: "Бу мурожаатни бекор қилиб бўлмайди.", LANG_RU: "Это обращение нельзя отменить."},
    "block_reason_label": {LANG_UZ: "<b>Sabab:</b>", LANG_OZ: "<b>Сабаб:</b>", LANG_RU: "<b>Причина:</b>"},
    "auto_choose_section": {
        LANG_UZ: "📁 <b>Murojaatingiz qaysi sohaga tegishli? Tanlang:</b>",
        LANG_OZ: "📁 <b>Мурожаатингиз қайси соҳага тегишли? Танланг:</b>",
        LANG_RU: "📁 <b>К какой сфере относится ваше обращение? Выберите:</b>",
    },
    "auto_choose_section_again": {
        LANG_UZ: "📁 <b>Quyidagi bo'limlardan birini tanlang:</b>",
        LANG_OZ: "📁 <b>Қуйидаги бўлимлардан бирини танланг:</b>",
        LANG_RU: "📁 <b>Выберите один из разделов ниже:</b>",
    },
    "app_reminder_citizen": {
        LANG_UZ: "⏰ <b>Yurist qabuliga 1 soatdan kam vaqt qoldi (ariza №{id}).</b><br/><br/>📅 <b>Vaqt:</b> {time}<br/>👨‍⚖️ <b>Yurist:</b> {lawyer}<br/>{link}",
        LANG_OZ: "⏰ <b>Юрист қабулига 1 соатдан кам вақт қолди (ариза №{id}).</b><br/><br/>📅 <b>Вақт:</b> {time}<br/>👨‍⚖️ <b>Юрист:</b> {lawyer}<br/>{link}",
        LANG_RU: "⏰ <b>До приема у юриста осталось меньше часа (заявка №{id}).</b><br/><br/>📅 <b>Время:</b> {time}<br/>👨‍⚖️ <b>Юрист:</b> {lawyer}<br/>{link}",
    },
    "app_reminder_link": {LANG_UZ: "🔗 <b>Ulanish:</b> {url}", LANG_OZ: "🔗 <b>Уланиш:</b> {url}", LANG_RU: "🔗 <b>Подключение:</b> {url}"},
    "app_reminder_no_link": {
        LANG_UZ: "<i>Yurist belgilangan vaqtda siz bilan Telegram yoki telefon orqali bog'lanadi.</i>",
        LANG_OZ: "<i>Юрист белгиланган вақтда сиз билан Telegram ёки телефон орқали боғланади.</i>",
        LANG_RU: "<i>Юрист свяжется с вами в назначенное время через Telegram или по телефону.</i>",
    },
    "app_attend_ask": {
        LANG_UZ: "📅 <b>Yurist qabuli: {when}</b> (ariza №{id})<br/>Belgilangan vaqtda qabulga tayyor bo'lasizmi?",
        LANG_OZ: "📅 <b>Юрист қабули: {when}</b> (ариза №{id})<br/>Белгиланган вақтда қабулга тайёр бўласизми?",
        LANG_RU: "📅 <b>Прием у юриста: {when}</b> (заявка №{id})<br/>Сможете ли вы быть на приеме в назначенное время?",
    },
    "btn_attend_yes": {LANG_UZ: "✅ Ha, tayyorman", LANG_OZ: "✅ Ҳа, тайёрман", LANG_RU: "✅ Да, буду"},
    "btn_attend_no": {LANG_UZ: "❌ Yo'q, vaqtni o'zgartirish kerak", LANG_OZ: "❌ Йўқ, вақтни ўзгартириш керак", LANG_RU: "❌ Нет, нужно другое время"},
    "app_attend_yes_reply": {
        LANG_UZ: "✅ Rahmat! Belgilangan vaqtda yurist siz bilan bog'lanadi.",
        LANG_OZ: "✅ Раҳмат! Белгиланган вақтда юрист сиз билан боғланади.",
        LANG_RU: "✅ Спасибо! Юрист свяжется с вами в назначенное время.",
    },
    "app_attend_no_reply": {
        LANG_UZ: "Rahmat, yuristga xabar berdik. Siz bilan yangi vaqt kelishiladi.",
        LANG_OZ: "Раҳмат, юристга хабар бердик. Сиз билан янги вақт келишилади.",
        LANG_RU: "Спасибо, мы сообщили юристу. С вами согласуют новое время.",
    },
    "inquiry_closed_citizen": {
        LANG_UZ: "✅ Murojaatingiz yakunlandi. Sizga yordam bera olganimizdan xursandmiz!",
        LANG_OZ: "✅ Мурожаатингиз якунланди. Сизга ёрдам бера олганимиздан хурсандмиз!",
        LANG_RU: "✅ Ваше обращение закрыто. Рады, что смогли вам помочь!",
    },
    "menu_vol_sections": {
        LANG_UZ: "🗂 Sohalarim",
        LANG_OZ: "🗂 Соҳаларим",
        LANG_RU: "🗂 Мои направления",
    },
    "vol_sections_title": {
        LANG_UZ: "🗂 <b>Sohalaringiz</b><br/>✅ — siz shu soha a'zosisiz (murojaatlar sizga tavsiya qilinadi)<br/>⏳ — so'rovingiz admin ko'rigida<br/>➕ — qo'shilish uchun so'rov yuborish",
        LANG_OZ: "🗂 <b>Соҳаларингиз</b><br/>✅ — сиз шу соҳа аъзосисиз (мурожаатлар сизга тавсия қилинади)<br/>⏳ — сўровингиз админ кўригида<br/>➕ — қўшилиш учун сўров юбориш",
        LANG_RU: "🗂 <b>Ваши направления</b><br/>✅ — вы в этом направлении (обращения будут вам предлагаться)<br/>⏳ — запрос на рассмотрении<br/>➕ — отправить запрос на добавление",
    },
    "vol_section_requested": {
        LANG_UZ: "So'rovingiz adminga yuborildi.",
        LANG_OZ: "Сўровингиз админга юборилди.",
        LANG_RU: "Запрос отправлен администратору.",
    },
    "vol_section_approved": {
        LANG_UZ: "✅ Siz «{section}» sohasiga qo'shildingiz.",
        LANG_OZ: "✅ Сиз «{section}» соҳасига қўшилдингиз.",
        LANG_RU: "✅ Вы добавлены в направление «{section}».",
    },
    "vol_section_rejected": {
        LANG_UZ: "«{section}» sohasiga qo'shilish so'rovingiz rad etildi.",
        LANG_OZ: "«{section}» соҳасига қўшилиш сўровингиз рад этилди.",
        LANG_RU: "Запрос на добавление в «{section}» отклонён.",
    },
    "menu_vol_citizen": {
        LANG_UZ: "👤 Fuqaro menyusi",
        LANG_OZ: "👤 Фуқаро менюси",
        LANG_RU: "👤 Меню гражданина",
    },
    "menu_vol_panel": {
        LANG_UZ: "🧑‍⚖️ Volontyor paneli",
        LANG_OZ: "🧑‍⚖️ Волонтёр панели",
        LANG_RU: "🧑‍⚖️ Панель волонтёра",
    },
    "vol_panel_opened": {
        LANG_UZ: "🧑‍⚖️ Volontyor paneli. Quyidagi tugmalardan foydalaning.",
        LANG_OZ: "🧑‍⚖️ Волонтёр панели. Қуйидаги тугмалардан фойдаланинг.",
        LANG_RU: "🧑‍⚖️ Панель волонтёра. Используйте кнопки ниже.",
    },
    "vol_panel_not_volunteer": {
        LANG_UZ: "Siz faol volontyor sifatida ro'yxatdan o'tmagansiz.",
        LANG_OZ: "Сиз фаол волонтёр сифатида рўйхатдан ўтмагансиз.",
        LANG_RU: "Вы не зарегистрированы как активный волонтёр.",
    },
    "vol_assigns_title": {
        LANG_UZ: "📌 <b>Biriktirilgan murojaatlaringiz</b> ({n} ta):",
        LANG_OZ: "📌 <b>Бириктирилган мурожаатларингиз</b> ({n} та):",
        LANG_RU: "📌 <b>Ваши назначенные обращения</b> ({n}):",
    },
    "vol_assigns_empty": {
        LANG_UZ: "Sizga biriktirilgan ochiq murojaat yo'q.",
        LANG_OZ: "Сизга бириктирилган очиқ мурожаат йўқ.",
        LANG_RU: "У вас нет открытых назначенных обращений.",
    },
    "vol_assigns_row": {
        LANG_UZ: "№{id} • {section}<br/>🕓 {at}<br/>{link}",
        LANG_OZ: "№{id} • {section}<br/>🕓 {at}<br/>{link}",
        LANG_RU: "№{id} • {section}<br/>🕓 {at}<br/>{link}",
    },

    # AI nazoratchi + javob darvozasi (D bosqich)
    "review_ask": {
        LANG_UZ: "✅ <b>Javobni tasdiqlatish</b> — {link}<br/><blockquote>{q}</blockquote>Shu murojaatga tayyorlagan javobingiz matnini yuboring (faqat matn).",
        LANG_OZ: "✅ <b>Жавобни тасдиқлатиш</b> — {link}<br/><blockquote>{q}</blockquote>Шу мурожаатга тайёрлаган жавобингиз матнини юборинг (фақат матн).",
        LANG_RU: "✅ <b>Проверка ответа</b> — {link}<br/><blockquote>{q}</blockquote>Отправьте текст ответа на это обращение (только текст).",
    },
    "review_choose": {
        LANG_UZ: "✅ <b>Javobni tasdiqlatish</b><br/>Sizga {n} ta murojaat biriktirilgan. Qaysi biriga javob tayyorladingiz?",
        LANG_OZ: "✅ <b>Жавобни тасдиқлатиш</b><br/>Сизга {n} та мурожаат бириктирилган. Қайси бирига жавоб тайёрладингиз?",
        LANG_RU: "✅ <b>Проверка ответа</b><br/>Вам назначено обращений: {n}. На какое из них вы подготовили ответ?",
    },
    "btn_review_this": {
        LANG_UZ: "✅ №{id} javobini tasdiqlatish",
        LANG_OZ: "✅ №{id} жавобини тасдиқлатиш",
        LANG_RU: "✅ Проверить ответ №{id}",
    },
    "review_no_assign": {
        LANG_UZ: "Sizga biriktirilgan ochiq murojaat yo'q.",
        LANG_OZ: 'Сизга бириктирилган очиқ мурожаат йўқ.',
        LANG_RU: 'У вас нет открытых назначенных обращений.',
    },
    "review_only_text": {
        LANG_UZ: "Javobni faqat matn ko'rinishida yuboring.",
        LANG_OZ: 'Жавобни фақат матн кўринишида юборинг.',
        LANG_RU: 'Отправьте ответ только текстом.',
    },
    "review_unavailable": {
        LANG_UZ: "⚠️ Texnik xatolik yuz berdi. Iltimos, 10 daqiqadan keyin qayta urinib ko'ring.",
        LANG_OZ: "⚠️ Техник хатолик юз берди. Илтимос, 10 дақиқадан кейин қайта уриниб кўринг.",
        LANG_RU: "⚠️ Произошла техническая ошибка. Пожалуйста, повторите попытку через 10 минут.",
    },
    "review_needs_admin": {
        LANG_UZ: "⏳ Javobingiz adminga ko'rib chiqish uchun yuborildi. Iltimos, javobni kuting.",
        LANG_OZ: "⏳ Жавобингиз админга кўриб чиқиш учун юборилди. Илтимос, жавобни кутинг.",
        LANG_RU: "⏳ Ваш ответ отправлен администратору на рассмотрение. Пожалуйста, дождитесь ответа.",
    },
    "review_admin_escalation": {
        LANG_UZ: "🧑‍⚖️ <b>Javob admin ko'rigiga yuborildi</b><br/>Murojaat: {link} (№{id})<br/>Volontyor: {vol}<br/>Tekshiruv xulosasi: {summary}{hint}",
        LANG_OZ: "🧑‍⚖️ <b>Жавоб админ кўригига юборилди</b><br/>Мурожаат: {link} (№{id})<br/>Волонтёр: {vol}<br/>Текширув хулосаси: {summary}{hint}",
        LANG_RU: "🧑‍⚖️ <b>Ответ передан на проверку администратору</b><br/>Обращение: {link} (№{id})<br/>Волонтёр: {vol}<br/>Вывод проверки: {summary}{hint}",
    },
    "review_error_admin": {
        LANG_UZ: "⚠️ <b>Javobni tekshirishda texnik xatolik</b><br/>🕓 {ts}<br/>Murojaat: {link} (№{id})<br/>Volontyor: {vol}<br/>Xato turi: {kind}<br/>Kod: {code}<br/>{detail}<br/>Volontyorga 10 daqiqadan keyin qayta urinish aytildi.{extra}",
        LANG_OZ: "⚠️ <b>Жавобни текширишда техник хатолик</b><br/>🕓 {ts}<br/>Мурожаат: {link} (№{id})<br/>Волонтёр: {vol}<br/>Хато тури: {kind}<br/>Код: {code}<br/>{detail}<br/>Волонтёрга 10 дақиқадан кейин қайта уриниш айтилди.{extra}",
        LANG_RU: "⚠️ <b>Техническая ошибка при проверке ответа</b><br/>🕓 {ts}<br/>Обращение: {link} (№{id})<br/>Волонтёр: {vol}<br/>Тип ошибки: {kind}<br/>Код: {code}<br/>{detail}<br/>Волонтёру сказано повторить попытку через 10 минут.{extra}",
    },
    "review_error_admin_pending": {
        LANG_UZ: "<br/>Shu xatodan yana {n} ta (5 daqiqa ichida).",
        LANG_OZ: "<br/>Шу хатодан яна {n} та (5 дақиқа ичида).",
        LANG_RU: "<br/>Ещё {n} таких ошибок (за 5 минут).",
    },
    "review_rejected": {
        LANG_UZ: "❌ <b>Javob tasdiqlanmadi.</b><br/>Murojaatga javobni quyidagi qismlarni inobatga olib qaytadan yozib chiqing:<br/><br/>{issues}<br/><br/>Tuzatilgan javobni shu yerga yuboring.",
        LANG_OZ: "❌ <b>Жавоб тасдиқланмади.</b><br/>Мурожаатга жавобни қуйидаги қисмларни инобатга олиб қайтадан ёзиб чиқинг:<br/><br/>{issues}<br/><br/>Тузатилган жавобни шу ерга юборинг.",
        LANG_RU: "❌ <b>Ответ не одобрен.</b><br/>Перепишите ответ на обращение с учётом следующих пунктов:<br/><br/>{issues}<br/><br/>Отправьте исправленный ответ сюда.",
    },
    "review_approved": {
        LANG_UZ: '✅ <b>Javob tasdiqlandi.</b> {link}<br/>«📤 Fuqaroga yuborish» tugmasini bosing yoki guruhda murojaatga reply qilib shu matnni yuboring.{hint}',
        LANG_OZ: '✅ <b>Жавоб тасдиқланди.</b> {link}<br/>«📤 Фуқарога юбориш» тугмасини босинг ёки гуруҳда мурожаатга reply қилиб шу матнни юборинг.{hint}',
        LANG_RU: '✅ <b>Ответ одобрен.</b> {link}<br/>Нажмите «📤 Отправить гражданину» или ответьте в группе reply этим же текстом.{hint}',
    },
    "btn_send_approved": {
        LANG_UZ: "📤 Fuqaroga yuborish",
        LANG_OZ: "📤 Фуқарога юбориш",
        LANG_RU: "📤 Отправить гражданину",
    },
    "review_send_unavailable": {
        LANG_UZ: "Bu javobni endi yuborib bo'lmaydi: murojaat yopilgan, boshqaga biriktirilgan yoki javob qayta tekshirilgan.",
        LANG_OZ: "Бу жавобни энди юбориб бўлмайди: мурожаат ёпилган, бошқага бириктирилган ёки жавоб қайта текширилган.",
        LANG_RU: "Этот ответ уже нельзя отправить: обращение закрыто, передано другому или ответ проверен заново.",
    },
    "review_sent_ok": {
        LANG_UZ: "📤 <b>Javob fuqaroga yuborildi</b> va guruhda qayd etildi.",
        LANG_OZ: "📤 <b>Жавоб фуқарога юборилди</b> ва гуруҳда қайд этилди.",
        LANG_RU: "📤 <b>Ответ отправлен гражданину</b> и отмечен в группе.",
    },
    "review_send_failed": {
        LANG_UZ: "❌ Javob fuqaroga yetkazilmadi ({reason}). Birozdan so'ng qayta urinib ko'ring.",
        LANG_OZ: "❌ Жавоб фуқарога етказилмади ({reason}). Бироздан сўнг қайта уриниб кўринг.",
        LANG_RU: "❌ Ответ не доставлен гражданину ({reason}). Попробуйте немного позже.",
    },
    "review_hint": {
        LANG_UZ: "<br/>💡 Tavsiya: {hint}",
        LANG_OZ: "<br/>💡 Тавсия: {hint}",
        LANG_RU: "<br/>💡 Рекомендация: {hint}",
    },
    "gate_foreign": {
        LANG_UZ: "⛔ Bu murojaat {name} ga biriktirilgan.",
        LANG_OZ: "⛔ Бу мурожаат {name} га бириктирилган.",
        LANG_RU: "⛔ Это обращение назначено: {name}.",
    },
    "gate_unassigned": {
        LANG_UZ: "⏳ Bu murojaat hali biriktirilmagan, admin biriktirishini kuting.",
        LANG_OZ: "⏳ Бу мурожаат ҳали бириктирилмаган, админ бириктиришини кутинг.",
        LANG_RU: "⏳ Это обращение ещё не назначено, дождитесь назначения администратором.",
    },
    "gate_need_review": {
        LANG_UZ: "⚠️ Avval botda «Javobni tasdiqlatish» orqali tasdiqlating.",
        LANG_OZ: "⚠️ Аввал ботда «Жавобни тасдиқлатиш» орқали тасдиқлатинг.",
        LANG_RU: "⚠️ Сначала проверьте ответ через «Проверить ответ» в боте.",
    },
    "gate_changed": {
        LANG_UZ: "⚠️ Matn tasdiqlangandan keyin o'zgargan, qayta tasdiqlating.",
        LANG_OZ: "⚠️ Матн тасдиқлангандан кейин ўзгарган, қайта тасдиқлатинг.",
        LANG_RU: "⚠️ Текст изменён после проверки, проверьте снова.",
    },
}


def t(key: str, lang: str = LANG_UZ, **kwargs: Any) -> str:
    lang = lang if lang in [LANG_UZ, LANG_RU, LANG_OZ] else LANG_UZ
    trans_dict = TRANSLATIONS.get(key, {})
    text = trans_dict.get(lang) or trans_dict.get(LANG_UZ, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_about_us_text(lang: str = LANG_UZ, bot_name: str = "") -> str:
    b_name = f"@{bot_name}" if bot_name else "@huquqplus_bot"
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
    elif lang == LANG_OZ:
        return (
            f"{b_name} орқали БИЗ НИМАЛАРГА ЁРДАМ БЕРА ОЛАМИЗ:<br/><br/>"
            "➖Ногиронлиги бўлган шахслар ва уларнинг оила аъзоларига онлайн ҳуқуқий маслаҳат;<br/>"
            "➖Ҳуқуқлар ва уларни амалга ошириш тартиби бўйича тушунтириш бериш;<br/>"
            "➖Юрист қабулига ёзилиш орқали амалий ҳуқуқий ёрдам олиш;<br/>"
            "➖Қайси идорага мурожаат қилиш ва қандай ҳужжатлар кераклигини тушунтириш (зарурат бўлса, тайёрлашда ёрдам);<br/>"
            "➖Ариза ва шикоятлар намуналарини тақдим этиш;<br/>"
            "➖Сизнинг номингиздан ташкилотларга мурожаат ва ҳужжатларни тайёрлаб жўнатиш;<br/>"
            "➖Тошкент шаҳрида сизнинг номингиздан суд жараёнларида қатнашиш.<br/><br/>"
            "❗️Биз қуйидагиларни қила олмаймиз:<br/><br/>"
            "➖Вилоятларда судда иш юритиш;<br/>"
            "➖Расмий идораларга шахсан мурожаат қилиш;<br/>"
            "➖Натижага кафолат бериш.<br/><br/>"
            "⏳ Саволингизга 1–2 иш куни ичида жавоб берилади.<br/><br/>"
            "❓ Илтимос, саволингизни тўлиқ ва аниқ матн шаклида юборинг — бу бизга тезроқ ёрдам кўрсатишга имкон беради.<br/><br/>"
            "🤖 Ботни ногиронлиги бор, ҳуқуқий ёрдамга муҳтож танишларингиз билан улашинг.<br/><br/>"
            'HuquqPlus.uz — ногиронлиги бўлган шахслар учун махсус ҳуқуқий ахборот веб-портали Тошкент шаҳар "SHAROIT PLYUS" (https://sharoitplus.uz/) ногиронлар жамоат бирлашмаси томонидан яратилган.'
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
    elif lang == LANG_OZ:
        return (
            "Ҳурматли фойдаланувчи!<br/><br/>"
            "Юрист қабули масофавий ёки юзма-юз шаклда амалга оширилади.<br/><br/>"
            "📞 <b>Масофавий қабул</b> — юристларимиз сиз билан боғланиб, муаммоингизни ҳал этишда амалий ёрдам кўрсатади.<br/><br/>"
            "🏢 <b>Юзма-юз қабул</b>— ҳар шанба куни, соат 10:00 дан 17:00 гача, Тошкент шаҳар, Юнусобод тумани, Хиёбон кўчаси, 22-уй манзилдаги бош офисда ўтказилади.<br/><br/>"
            "📍Локация: https://yandex.com/maps/-/CHAD5P1f <br/><br/>"
            "Қуйидаги қабул туридан бирини танланг 👇"
        )
    return (
        "Hurmatli foydalanuvchi!<br/><br/>"
        "Yurist qabuli masofaviy yoki yuzma-yuz shaklda amalga oshiriladi.<br/><br/>"
        "📞 <b>Masofaviy qabul</b> — yuristlarimiz siz bilan bog‘lanib, muammoingizni hal etishda amaliy yordam ko‘rsatadi.<br/><br/>"
        "🏢 <b>Yuzma-yuz qabul</b>— har shanba kuni, soat 10:00 dan 17:00 gacha, Toshkent shahar, Yunusobod tumani, Xiyobon ko‘chasi, 22-uy manzildagi bosh ofisda o‘tkaziladi.<br/><br/>"
        "📍Lokatsiya: https://yandex.com/maps/-/CHAD5P1f <br/><br/>"
        "Quyidagi qabul turidan birini tanlang 👇"
    )
