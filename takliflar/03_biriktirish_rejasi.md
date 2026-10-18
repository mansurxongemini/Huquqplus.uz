# ADMIN biriktirish rejasi (C): guruh kartochkasidan volontyorga biriktirish, eslatmalar, AI nazorat

> FAQAT TAHLIL VA REJA. Kod yozilmagan, mavjud fayllar o'zgartirilmagan.
> Barcha xulosalar repo'dagi fayllarni o'qishga tayanadi.
> Qamrov: `src/routes/aiogram/group_router.py`, `inquiry.py`, `src/models/inquiry.py`,
> `src/models/volunteer.py`, `src/models/db_models.py`, `src/app/keyboards.py`,
> `src/routes/aiogram/private_router.py`, `volunteer_result.py`, `src/app/volunteer_analytics.py`,
> `src/tasks/volunteer_leaderboard.py`, `src/tasks/close_inquiry.py`, `src/worker.py`,
> `src/routes/aiogram/ai_assistant.py`, `src/app/rag_client.py`, `src/routes/aiogram/admin.py`,
> `src/app/filters.py`, `src/app/translations.py`, `src/app/enums.py`,
> `src/app/link_utils.py`, `src/models/user.py`, `src/routes/aiogram/registration.py`,
> `src/config/settings.py`, `src/tasks/daily_reminder.py`.

Asosiy qoida (foydalanuvchi talabi): ADMIN biriktiradi; volontyor o'zi olmaydi;
avto-tayinlash YO'Q; volontyor tomonidan "qaytarish" YO'Q.

---

## 0. Mavjud holat — tayanch faktlar (reja shularga tayanadi)

- Murojaat yaratish: `src/routes/aiogram/inquiry.py` → `send_custom_question`.
  Savol `settings.get_inquiry_groups()` dagi soha guruhiga yuboriladi, `Inquiry` yoziladi
  (`group_question_id`, `group_id`, `bot_id`, `section_name`, `user_id`).
  Kartochkada hozir FAQAT `get_block_button_markup` dagi "Bloklash" tugmasi bor —
  "Biriktirish" tugmasi YO'Q.
- Guruhda javob: `src/routes/aiogram/group_router.py` → `handle_response`
  (`is_group_message` + `reply_to_my_message`, `/` bilan boshlanmaydigan).
  Hozir har qanday faol volontyor/yurist/admin reply qilsa javob
  `send_answer_to_citizen` orqali DARHOL fuqaroga yuboriladi, `responder_id`,
  `replied_at` yoziladi, `status=replied` bo'ladi. Hech qanday biriktirish
  tekshiruvi, AI darvozasi YO'Q.
- `send_answer_to_citizen` (o'sha fayl, 77-qator atrofi) allaqachon xato
  tasnifiga ega: `blocked / restricted / network_error / bad_request`.
  Buni 2-banddagi biriktirish xabari uchun QAYTA ISHLATISH mumkin.
- `Inquiry` (`src/models/inquiry.py`): `assigned_volunteer_id` YO'Q,
  `answer_status/draft/review` YO'Q, eslatma holati YO'Q.
  Borlari: `status (active/replied/closed/cancelled)`, `responder_id`,
  `replied_at`, `rating`, `group_question_id`, `group_id` (VARCHAR, `get_group_id`
  dagi `@username` yoki `chat.id` stringi saqlanadi), `section_name`,
  `user_id`, `parent_id`, `benefit_id`.
- `Volunteer` (`src/models/volunteer.py`): faqat `user_id`, `first_name`,
  `last_name`, `study_or_work`, `birth_year`, `phone_number`, `is_active`.
  Soha a'zoligi YO'Q, KPI YO'Q, oxirgi biriktirish vaqti YO'Q.
  `get_active_volunteers` bor — ro'yxat manbai sifatida ishlatiladi.
- Soha → guruh bog'lanishi: `src/app/keyboards.py` da 12 ta soha
  (`inquiry_sections_uz`: Ijtimoiy himoya, Ta'lim, Mehnat, Uy-joy, Tibbiy,
  Sud-huquq, Transport, Bolalar, Yoshlar, Ayollar, Daftarlar, Tadbirkorlik),
  lekin `src/config/settings.py` `get_inquiry_groups()` da faqat 6 ta kalit
  (`GROUP_IJTIMOIY_HIMOYA/TALIM/MEHNAT/UY_JOY/TIBBIY/BOSHQA`, qolganlari
  `Boshqa` guruhiga tushadi). Demak "murojaat sohasi" = `Inquiry.section_name`
  (to'liq matn, masalan "🏘 Uy-joy"), "qaysi guruhga tushgani" =
  `Inquiry.group_id`. Volontyorning "qaysi soha guruhlarida" ekanini
  ko'rsatadigan BIROR joy YO'Q (DB da ham, kodda ham).
- Havola: `src/app/link_utils.py` → `build_group_message_link(group_id, message_id)`
  tayyor (`@user` va `-100...` ikkalasini ham qiladi). `group_router.py` dagi
  `get_message_link` va `daily_reminder.py` dagi lokal `build_group_message_link`
  uning dublikatlari. Yangi xabar uchun `link_utils` ni ishlatish kerak.
- Ruxsat tekshiruvi namunasi: `is_coordinator_or_lawyer_or_admin`
  (`group_router.py`, 616-qator) — `settings.is_admin` + `OfficialLawyer` +
  `Volunteer.is_active` + guruh admini. "Biriktirish" callback'ida adminni
  ajratish uchun shu funksiya toraytiriladi (faqat admin shoxi).
- Claim namunasi: `claim_appointment_callback` (`group_router.py`, 1414-qator) —
  appointment'ni yuristga biriktiradi, kartani `edit_text` bilan yangilaydi,
  fuqaroga DM yuboradi. Inquiry uchun BIRIKTIRISH tugmasi shu andozada
  qilinadi, lekin farqlari bor: bosuvchi ADMIN bo'lishi shart; tanlov
  paginatsiyali ro'yxatdan bo'ladi; DM fuqaroga emas, VOLONTYORGA boradi.
- Rol menyusi: `get_main_menu` (`keyboards.py`, 81-qator) HAMMA uchun bitta
  (Profil, Imtiyozlar, AI, Savol yuborish, Qabul, ...). Rolga qarab menyu
  ajratish YO'Q. `/myresult` (`volunteer_result.py` → `myresult_command_handler`)
  hozir faqat o'qish (statistika kartasi); FSM YO'Q.
- Eslatmalar (Celery, `src/worker.py` `setup_periodic_tasks`):
  `daily_reminder` 09:00 (guruhga javobsizlar dayjesti),
  `close_idle_inquiries` har daqiqa, `check_appointment_reminders` har 10 daq,
  `send_pending_appointment_reminders` 09:15, oylik/har haftalik hisobotlar,
  `post_weekly_volunteer_leaderboard` yak 16:00 (guruhga Top-5),
  `send_weekly_volunteer_personal_digest` yak 21:00 (shaxsiy dayjest).
  Biriktirish eslatmasi (24 soat + har 6 soat) uchun YANGI task kerak;
  `async_celery_task` (`src/tasks/utils.py`) dekoratori tayyor andoza.
- AI: `rag_client.ask(question, user_id, conversation_id, language)` —
  FAQAT MATN qabul qiladi (str). `ai_chat_non_text_handler`
  (`ai_assistant.py`, 453-qator) media kelganda `ai_only_text` deb rad etadi —
  bu 6-banddagi "audio TAQIQ" uchun tayyor andoza.
  Guruhdagi AI qoralamasi: `send_lawyer_ai_draft` (faqat matnli savollarda,
  `AI_LAWYER_DRAFTS` bayrog'i bilan).
- Nogironlik: `User` (`src/models/user.py`) da `disability_type`
  (guruh: 1/2/3/4/yo'q) va `disability_state` (shakl: physical/vision/hearing/
  mental/psychological/parent/aids/other) BOR; `registration.py`
  (`get_disability_type`, `get_disability_state`) da ro'yxatda majburiy
  yig'iladi. Demak "qanday olish" muammosi YO'Q — maydonlar tayyor.
  Lekin `create_user_info` (`enums.py`, 142-qator) bularni + telefonni GURUH
  kartochkasiga to'liq yozadi (maxfiylik riski — 6-bandga qarang).
- Leaderboard: `post_weekly_volunteer_leaderboard` guruhga
  (`VOLUNTEER_GROUP_ID`) oylik kesimda Top-5; shaxsiy dayjest
  `dispatch_weekly_volunteer_digest` (`volunteer_analytics.py`, 303-qator)
  orqali har bir faol volontyorga DM. `/myresult` kartasi ham shaxsiy.

---

## 1. "Biriktirish" tugmasi + paginatsiya (5 tadan) + tavsiya algoritmi

- **Hozirgi holat:** `inquiry.py:send_custom_question` (karta yaratish),
  `inquiry.py:get_block_button_markup` (kartadagi yagona tugma — "Bloklash").
  Biriktirish tugmasi, ro'yxat, tavsiya — YO'Q.
- **Nimani o'zgartirish:**
  - Karta yaratilganda (matnli va media barcha shoxlarida) inline tugma
    qo'shish: `🔗 Biriktirish` (`callback_data=f"inq_assign:{inquiry.id}:0"`).
    Mavjud `get_block_button_markup` yoniga `get_inquiry_card_markup(inquiry_id,
    user_id)` chiqarish; eski kartochkalar (tugmasiz) uchun reply-ga `/biriktir`
    admin buyrug'i zaxira sifatida (ixtiyoriy, lekin tavsiya etiladi).
  - `group_router.py` ga yangi callback'lar (namuna `claim_appointment_callback`):
    `inq_assign:{id}:{page}` — ro'yxat chizish; `inq_assign_pick:{id}:{vol_id}` —
    tasdiqlash; `inq_assign_retry:{id}:{vol_id}` — 2-banddagi qayta urinish.
  - Bosgan odam admin emasligini 2 bosqichda tekshirish:
    avval `settings.is_admin` + guruh `creator/administrator`
    (`block_user_callback` dagi andoza), keyin `OfficialLawyer`?
    Talab aniq: yurist/kordinator ham BOSA OLMAYDIMI yoki faqat
    volontyorlarga "faqat admin" ko'rsatiladimi — ochiq savollarga qarang.
    Tavsiya: faqat `settings.is_admin` + guruh admini/creator o'tadi;
    qolgan HAMMA (volontyor, yurist, oddiy a'zo) "⛔ Bu amal faqat
    adminlar uchun" alert oladi.
  - Ro'yxat: sahifada 5 ta volontyor (ism + ochiq ishlar soni, masalan
    `"A. Valiyev • 2 ochiq"`), ostida `⬅️ ➡️` (`inq_assign:{id}:{page}`),
    har bir qatorda tanlash tugmasi (`inq_assign_pick:{id}:{vol_id}`).
    Faqat `Volunteer.is_active=True` lar chiqadi.
  - 1-sahifa tarkibi (talab bo'yicha): 1-o'rin — shu fuqaro (`inquiry.user_id`)
    ning oldingi murojaatiga ENG OXIRI javob bergan volontyor
    (so'rov: `Inquiry.user_id=X AND responder_id IS NOT NULL ORDER BY
    replied_at DESC LIMIT 1` — `responder_id` volontyorlar jadvalida ham
    bo'lishi shart, aks holda u 1-o'ringa qo'yilmaydi); 2-5-o'rinlar —
    tavsiya algoritmi bo'yicha shu sohaning kandidatlari.
    Keyingi sahifalar: tavsiya tartibida qolgan soha a'zolari, keyin
    sohadan tashqari faol volontyorlar (belgi bilan, masalan "🌐 boshqa soha").
  - Tavsiya algoritmi (faqat `is_active` lar orasida, ketma-ket filtr):
    1. Soha a'zoligi — SHART (a'zo bo'lmagan tavsiya qilinmaydi);
    2. Shu sohada eng uzoq biriktirish olmagan (soha kesimida navbat —
       `volunteer_sections.last_assigned_at`, NULL eng birinchi);
    3. Ochiq ishlari soni kam (`assigned` holatdagi biriktirishlar soni);
    4. Faollik (`responder_id` bo'yicha oxirgi 30 kundagi javoblar soni).
    "Kecha ijtimoiy soha oldi, uy-joyda 10 kun olmagan" holati:
    navbat SOHA ICHIDA yuritilgani uchun ijtimoiy murojaatda u navbat
    oxiriga tushadi, uy-joy murojaatida esa umuman nomzod emas
    (a'zo bo'lmasa) yoki uy-joy navbati bo'yicha chiqadi.
- **Soha a'zoligini aniqlash — tahlil va tavsiya:**
  - Variant A (tavsiya etiladi): admin belgilaydi. Yangi jadval
    `volunteer_sections (volunteer_user_id, section_name, added_by,
    added_at)`; admin panelga (`admin.py` → `admin:...` menyusi)
    "sohaga qo'shish/olib tashlash" bo'limi. Sababi: kodda a'zolik
    HECH QAYERDA saqlanmaydi, guruh a'zoligini Telegram API orqali
    tekshirish (`get_chat_member` har safar) sekin va ishonchsiz
    (volontyor guruhda bo'lmasligi ham mumkin; bitta odam bir nechta
    guruhda). Admin belgilashi — yagona aniq manba.
  - Variant B (rad etiladi): guruh a'zoligini jonli tekshirish.
    Har tavsiyada 10+ guruhga API so'rov → sekin, rate-limit, kesh
    murakkabligi. Faqat A dagi ma'lumotni vaqti-vaqti bilan
    tekshirish (audit) uchun yaroqli.
  - Qo'shimcha: `settings.get_inquiry_groups()` dagi 6 kalit vs
    `keyboards.py` dagi 12 soha nomuvofiqligi shu ish doirasida
    to'g'rilanishi shart — `section_name` normalizatsiya qilinmasa
    tavsiya noto'g'ri sohaga yoziladi (masalan "Bolalar" murojaati
    "Boshqa" guruhiga tushadi; a'zolik "Bolalar" bo'yicha bo'lishi kerak,
    guruh bo'yicha emas).
- **DB o'zgarishi (alembic, `src/database/alembic/versions/` ga yangi versiya):**
  - `inquiries` ga: `assigned_volunteer_id` (BigInteger, nullable, index),
    `assigned_at` (nullable), `assign_source` (VARCHAR, default `"admin"`;
    `"admin"` dan boshqa qiymat yozilmaydi — avto/claim manbalari
    talab bo'yicha taqiqlangan), `assign_message_id` (guruhdagi biriktirish
    xabari ID si, ixtiyoriy).
  - Yangi `volunteer_sections`: `(volunteer_user_id BigInteger,
    section_name VARCHAR(255), added_by BigInteger, added_at)` —
    PK `(volunteer_user_id, section_name)`.
  - Yangi `inquiry_assignments` (tarix + navbat manbai):
    `(id, inquiry_id FK+index, volunteer_user_id index, section_name,
    assigned_by, assigned_at, status, created_at)`.
    `status`: `assigned / replied / reminded / expired_note` (javob
    berilganda `replied` ga o'tadi — eslatma to'xtashi uchun kalit).
  - `volunteer_sections.last_assigned_at` (nullable) — soha kesimidagi
    navbat ko'rsatkichi (yoki `inquiry_assignments` dan har safar
    `MAX(assigned_at)` hisoblanadi; hajm kichik bo'lgani uchun ustunsiz
    ham bo'ladi — tavsiya: ustunsiz boshlash, sekinlashsa qo'shish).
- **Qiyinlik:** M (tugma + ro'yxat + 3 jadval; algoritmning o'zi oddiy
  SQL tartiblash).
- **Xavf:** 12 soha vs 6 guruh nomuvofiqligi (noto'g'ri tavsiya);
  bitta murojaatni 2 admin bir vaqtda 2 volontyorga biriktirishi (poyga) —
  `assigned_volunteer_id IS NULL` sharti bilan optimistik UPDATE + takroriy
  biriktirishda "allaqachon X ga biriktirilgan" ogohlantirishi shart;
  callback 64-bayt limiti (`inq_assign_pick:{id}:{vol}` sig'adi, lekin
  matnli section_name ni callback'ga yozmaslik).

---

## 2. Biriktirishda xato boshqarish (DB / bloklangan bot / yuborilmaslik)

- **Hozirgi holat:** `group_router.py:send_answer_to_citizen` —
  `(success, reason, exc)` qaytaradi (`blocked/restricted/network/bad_request`),
  fuqaroga yuborishda ishlatiladi. `claim_appointment_callback` da DM
  muvaffaqiyatsizligi jim o'tib ketadi (`print` xolos) — biriktirishda
  BUNDAY BO'LMASLIGI kerak.
- **Nimani o'zgartirish (tartib qat'iy):**
  1. DB ga yozish (`assigned_volunteer_id`, `inquiry_assignments` qatori)
     `try/except` ichida; yozilmasa — adminga DARHOL:
     `"❌ Biriktirish saqlanmadi (DB xato: ...)"` + `🔁 Qaytadan urinish`
     (`inq_assign_retry:{id}:{vol_id}`).
  2. Volontyorga DM: `"📌 Murojaat sizga biriktirildi"` (murojaat matni/
     havolasi + nima qilish kerakligi) — `send_answer_to_citizen` dagi
     tasnif QAYTA ISHLATILADI (`bot.send_message` handler sifatida).
  3. DM yuborilmasa — adminga DARHOL sabab bilan:
     `Forbidden: bot blocked` → "volontyor botni bloklagan";
     `chat not found` → "volontyor bot bilan hech qachon start
     bosmagan / akkaunt o'chirilgan"; DB xato → matni bilan.
     Har birida `🔁 Qaytadan urinish` tugmasi.
     Muhim: DM yuborilmasa ham BIRIKTIRISH DB da qoladi (bekor qilinmaydi),
     faqat `inquiry_assignments.status="notify_failed"` + `notify_error`
     yoziladi — aks holda admin "biriktirildi" deb o'ylaydi-yu, volontyor
     bexabar qoladi.
  - Qayta urinish tugmasi faqat ADMIN bosa oladi; muvaffaqiyatli
    urinishdan keyin admin xabari tahrirlanadi ("✅ Yuborildi").
- **DB o'zgarishi:** `inquiry_assignments` ga `status` (`assigned /
  notify_failed / notified / replied`), `notify_error` (VARCHAR/Text,
  nullable), `notify_attempts` (int, default 0), `last_notify_at`.
  (`inquiries.assigned_*` ga qo'shimcha ustun kerak emas.)
- **Qiyinlik:** S (andoza tayyor, faqat ketma-ketlik va matnlar).
- **Xavf:** Admin "qaytadan urining" ni bosib DM ni 2 marta yuborishi
  (idempotentlik: `notified` dan keyin retry tugmasi o'chiriladi);
  Telegram `RetryAfter` (flood) — `send_answer_to_citizen` uni ichida
  kutadi, admin xabarida "biroz kuting" ko'rsatiladi.

---

## 3. Guruhga biriktirish xabari (avtomatik, qo'lda yozuv o'rniga)

- **Hozirgi holat:** `group_router.py:replied_context` + `edit_message`
  (javobdan keyin karta tahriri), `mark_inquiry_escalated_in_group`
  (qabulga yo'naltirishda karta tahriri). Biriktirish xabari YO'Q —
  adminlar qo'lda yozadi.
- **Nimani o'zgartirish:**
  - Muvaffaqiyatli biriktirishdan keyin guruhga YANGI xabar
    (mavjud kartani tahrirlash EMAS — talabda "rasmdagidek xabar" deyilgan,
    ya'ni alohida xabar; karta tahriri qo'shimcha bo'lishi mumkin):
    1-qator: `@username` (bo'lsa; `Volunteer` da username YO'Q —
    `User.username` dan olinadi; bo'lmasa `<a href="tg://user?id=...">Ism
    Familiya</a>` — `Volunteer.full_name`);
    2-qator: murojaat havolasi (`build_group_message_link(group_id,
    group_question_id)` — `src/app/link_utils.py`; `group_id` string
    (`@...` yoki `-100...`) bo'lgani uchun ishlaydi; `None` qaytsa
    "havola mavjud emas" matni);
    3-qator: `Ushbu murojaat biriktirildi.`
    Xabar asl karta xabariga reply qilib yuboriladi
    (`reply_to_message_id=group_question_id`).
  - `link_utils.build_group_message_link` dan foydalanish (dublikatsiya
    qilmaslik: `get_message_link` va `daily_reminder.build_group_message_link`
    kelajakda shu funksiyaga o'raladi — shu reja doirasida faqat YANGI
    kod `link_utils` ni chaqiradi, eskilariga tegilmaydi).
- **DB o'zgarishi:** `inquiries.assign_message_id` (nullable) — xabar
  o'chirilganda/adminga ko'rsatishda kerak; shart emas, lekin tavsiya.
- **Qiyinlik:** S.
- **Xavf:** `User.username` eskirgan bo'lishi (odam username almashtirganda
  `@...` ishlamaydi — shuning uchun fallback `tg://user?id=` MENTIONI
  asosiy, `@username` faqat ko'rinish uchun); havola faqat supergroup/
  public uchun ishlaydi (oddiy `group` da `None` — matn fallback shart).

---

## 4. Eslatmalar (Celery): 24 soat + har 6 soat, javobda to'xtash

- **Hozirgi holat:** `worker.py:setup_periodic_tasks` (beat jadvali),
  `tasks/daily_reminder.py:daily_reminder` (09:00, guruhga umumiy),
  `tasks/close_inquiry.py:close_idle_inquiries` (har daqiqa).
  Biriktirishga bog'langan SHAXSIY eslatma YO'Q.
- **Nimani o'zgartirish:**
  - Yangi task `tasks/assignment_reminders.py` (andoza: `async_celery_task`,
    `Session(engine)`, `bot.send_message`):
    `check_assignment_reminders` — har 30 daqiqada (yoki har 10 daqiqada,
    `check_appointment_reminders` kabi) yuradi; shart:
    `inquiry_assignments.status IN (assigned, notified, notify_failed→? )`
    va `inquiries.status=active` (javob berilmagan).
    - `assigned_at + 24 soat` o'tgan va hali 1-eslatma yuborilmagan →
      shaxsiyga: `"Iltimos, bu xabarga javobni yuboring"` (+ murojaat
      havolasi/matni).
    - Shundan keyin har 6 soatda → shaxsiyga: `"Iltimos, fuqaro murojaatiga
      javobni tayyorlab, mendan (AI nazoratchidan) tasdiqlatib, fuqaroga
      guruhda reply qilib yuboring"`.
  - To'xtash sharti (muhim): `handle_response` da javob `assigned_volunteer_id`
    ga teng odamdan kelsa (8-banddagi darvoza) →
    `inquiry_assignments.status="replied"`, eslatma to'xtaydi.
    Shuningdek `status=replied/closed/cancelled` bo'lgan inquiry'lar
    eslatmadan avtomatik chiqadi.
  - Bloklangan volontyor: DM `blocked` qaytsa — eslatma to'xtatilmaydi,
    lekin `notify_failed` + ADMINga bir marta xabar ("volontyor botni
    bloklagan, eslatma yetmayapti") — 2-banddagi mexanizm qayta ishlatiladi.
  - Tungi cheklov (taklif): 22:00–08:00 (Toshkent) da eslatma YUBORILMAYDI,
    ertalab 08:00 dan keyin to'plangan eslatma bitta bo'lib boradi.
    Sababi: tungi DM norozilik va bloklashga olib keladi. Beat ichida
    soat tekshiruvi (`datetime.now(tz)`, `timeutils.tz` tayyor) —
    sozlama sifatida (`ASSIGN_REMINDER_QUIET_HOURS`), qattiq kod emas.
- **DB o'zgarishi:** `inquiry_assignments` ga `first_reminded_at`,
  `last_reminded_at`, `remind_count`. (Redis emas, DB — qayta startda
  yo'qolmasligi uchun.)
- **Beat (`worker.py`):** `check_assignment_reminders` har 30 daqiqada
  (yoki 10 daqiqada — 6-soatlik qadam uchun 30 daqiqa yetadi, arzonroq).
  Mavjud `daily_reminder` (09:00 guruh dayjesti) BIRIKTIRILGAN murojaatlarni
  ro'yxatdan CHIQARISHI kerak (ikki eslatma to'qnashmasligi uchun) —
  kichik o'zgarish.
- **Qiyinlik:** M (yangi task + beat + to'xtash integratsiyasi).
- **Xavf:** Soat mintaqasi xatosi (server UTC vs Toshkent — `timeutils.tz`
  ishlatish shart); eslatma "har 6 soat" ni o'tkazib yubormasligi uchun
  `last_reminded_at + 6h <= now` sharti (tenglik emas, "o'tgan" mantiq);
  javob media (ovozli) bilan berilsa ham to'xtashi kerak (matn sharti emas,
  `responder_id` sharti).

---

## 5. Volontyor pastki (reply) klaviaturasi + "Javobni tasdiqlatish"

- **Hozirgi holat:** `keyboards.py:get_main_menu` — hamma uchun bitta menyu;
  `private_router.py` — routerlar to'plami; `volunteer_result.py` —
  faqat `/myresult` + inline tugmalar; FSM faqat ro'yxatdan o'tish va
  so'rov oqimlarida. Rolga qarab menyu YO'Q.
- **Nimani o'zgartirish:**
  - Rol aniqlash funksiyasi (`is_coordinator_or_lawyer_or_admin` dagi
    mantiqning private-versiyasi, yangi `src/app/roles.py` yoki
    `keyboards.py` ichida): `admin (settings.is_admin)` → admin menyusi
    (o'zgarishsiz); `Volunteer.is_active` → volontyor menyusi (YANGI);
    `OfficialLawyer.is_active` → hozircha umumiy menyu (yuristlar bu
    rejada alohida menyu OLMAYDI — ochiq savol); qolganlar → fuqaro
    menyusi (hozirgi `get_main_menu`).
  - Yangi `get_volunteer_menu(lang)`: 3 ta tugma —
    `📊 Mening natijam`, `📌 Biriktirilgan murojaatlar`,
    `✅ Javobni tasdiqlatish`. (Nomlar `translations.py` ga `uz/oz/ru`
    da qo'shiladi; hozir bu kalitlar YO'Q.)
  - `Mening natijam` → mavjud `get_volunteer_result_view` ni chizadi
    (qayta ishlatiladi, yangi kod emas).
  - `Biriktirilgan murojaatlar` → `inquiry_assignments.status=assigned/
    notified` dagi o'z murojaatlari ro'yxati (har biri: ID, soha,
    biriktirilgan vaqt, havola; ko'pi bilan 10 ta + paginatsiya ixtiyoriy).
  - `Javobni tasdiqlatish` → avtomatik ENG OXIRGI biriktirilgan murojaat
    (`assigned_at DESC LIMIT 1`, ochiq holatdagi) tanlanadi; volontyor
    JAVOB MATNINI yuboradi (FSM: `VolunteerReviewState.waiting_for_draft`);
    matn AI nazoratchiga (`rag_client.ask` maxsus tekshiruv prompti bilan)
    yuboriladi; natija: tasdiq → "fuqaroga guruhda reply qilib yuborish
    ruxsati berildi" (+ qaysi xabarga reply qilish havolasi);
    rad → kamchilik ro'yxati + qayta yuborish taklifi.
    MUHIM: tasdiq — FAQAT shu volontyorga, FAQAT shu murojaatga, BIR MARTALIK
    ruxsat (`inquiry_assignments.review_passed_at` + `review_draft_hash`);
    boshqa murojaatga o'tmaydi.
  - FSM holatlari yangi routerda (`volunteer_assign.py` yoki
    `volunteer_result.py` ichida): menyu tugmalari matn bo'lgani uchun
    `cancel_or_main_menu` (`registration.py`) kabi "orqaga" oqimi ham
    qo'shiladi. `AiChatState.chatting` bilan to'qnashmasligi uchun
    state'lar alohida guruhda bo'ladi.
  - `/myresult` O'ZGARISHsiz qoladi (eski odat saqlanadi).
- **DB o'zgarishi:** `inquiry_assignments` ga `review_status`
  (`none/pending/passed/failed`), `review_draft_hash`, `review_passed_at`,
  `review_json` (nullable). Yangi jadval shart emas.
- **Qiyinlik:** M (yangi keyboard + 1 router + FSM + AI chaqiruvi).
- **Xavf:** "Eng oxirgi" noaniqligi — volontyorda 2 ochiq biriktirish
  bo'lsa noto'g'ri murojaatga tasdiq yozilishi mumkin → tasdiq xabarida
  murojaat ID/havolasi ANIQ ko'rsatiladi; menyu matni tilga bog'liq
  (`F.text.in_` ro'yxati 3 tilda — `ai_assistant.py` dagi andoza);
  tasdiqsiz guruhga reply qilgan volontyorni darvoza (8-band) to'sadi —
  ikkalasi birga loyihalanishi shart.

---

## 6. AI nazoratchi: faqat MATN; nogironlikka mos TAVSIYA; maxfiylik

- **Hozirgi holat:**
  - Kirish: `rag_client.ask(question: str, ...)` — faqat matn.
    `ai_chat_non_text_handler` (`ai_assistant.py`, 453-qator) media kelganda
    `ai_only_text` bilan rad etadi — andoza tayyor.
  - Nogironlik: `User.disability_type/disability_state` (`models/user.py`)
    ro'yxatda yig'iladi (`registration.py:get_disability_type/state`);
    qiymatlar: guruh (`first/second/third/forth/none`) + shakl
    (`physical/vision/hearing/mental/psychological/parent/aids/other`).
  - Maxfiylik muammosi: `create_user_info` (`enums.py`) guruh kartochkasiga
    ism, ID, tug'ilgan yil, jins, hudud, NOGIRONLIK GURUHI+SHAKLI, telefon,
    username havolasini TO'LIQ yozadi.
- **Nimani o'zgartirish:**
  - "Javobni tasdiqlatish" oqimida (5-band) media (voice/video_note/video/
    document/photo) kelsa — RAD ETISH + tushuntirish:
    "AI nazoratchiga faqat MATN yuboriladi. Ovozli/media javobni avval
    matn ko'rinishida yozing, tasdiqlangandan keyin xohlasangiz
    ovozli qilib guruhga yuborasiz" (matn→ovozga ruxsat siyosati ochiq
    savollarda — biriktirilgan volontyorning guruhdagi reply formati
    8-bandda hal qilinadi).
  - Nogironlik TAVSIYASI (qaror emas, faqat tavsiya matni volontyorga):
    tekshiruv promptiga fuqaroning `disability_state` (FAQAT shakl, guruh
    raqamisiz — masalan `vision`) qo'shiladi; AI tasdiq/rad qaroridan
    ALOHIDA `delivery_hint` qaytaradi, masalan ko'rish bo'yicha nogironlikda
    "matnni ovozli xabar bilan to'ldirishni tavsiya qilamiz", eshitish
    bo'yicha nogironlikda "faqat matn, ovozli yubormang".
    `disability_type` (1/2/3-guruh) AI ga YUBORILMAYDI — tavsiya uchun
    keraksiz sezgir ma'lumot.
  - Maxfiylik (RAG ga nima boradi): tekshiruv so'roviga fuqaroning
    ISM/FAMILIYA/TELEFON/ID/USERNAME/MANZILI KIRMAYDI — faqat:
    murojaat matni + `section_name` + `disability_state` shakli (masalan
    `"vision"`) + volontyor qoralamasi. `create_user_info` ning to'liq
    matni RAG ga yuborilmaydi. (`rag_client.ask` da `user_id` texnik
    maydon sifatida qoladi — RAG provayder talab qilsa, anonim
    `inquiry:{id}` kaliti bilan almashtirish varianti ochiq savollarda.)
- **DB o'zgarishi:** YO'Q (maydonlar `users` da tayyor). Ixtiyoriy audit:
  `inquiry_assignments.review_json` ichida `delivery_hint` saqlanadi
  (alohida ustun shart emas).
- **Qiyinlik:** S (rad etish) / M (tavsiya prompti + `delivery_hint`
  sxemasi; RAG servisi `delivery_hint` ni qaytarishi shart — tashqi
  bog'liqlik).
- **Xavf:** RAG `delivery_hint` ni qo'llamasa — promptdagi qat'iy format
  talab qilinadi, bo'lmasa hint sukut bo'yicha ko'rsatilmaydi (fail-open
  faqat TAVSIYA uchun; tasdiq/rad ga ta'sir qilmaydi); `vision` kabi
  shakl ham sezgir ma'lumot — guruh kartochkasida allaqachon ochiq
  (`create_user_info`), lekin RAG ga minimal uzatish printsipi saqlanadi;
  volontyor tavsiyani "majburiyat" deb o'qimasligi uchun matn
  "tavsiya" deb belgilanadi.

---

## 7. Haftalik OMMAVIY leaderboard'ni o'chirish (shaxsiy dayjest qoladi)

- **Hozirgi holat:** `tasks/volunteer_leaderboard.py` da 2 ta task:
  `post_weekly_volunteer_leaderboard` (guruhga Top-5, oylik kesim) va
  `send_weekly_volunteer_personal_digest` (har biriga shaxsiy DM,
  `dispatch_weekly_volunteer_digest` orqali). Beat (`worker.py`):
  leaderboard yak 16:00, dayjest yak 21:00.
- **Nimani o'chirish/o'chirib qo'yish:**
  - `worker.py` da `post_weekly_volunteer_leaderboard` beat qatori
    O'CHIRILADI (yoki kommentga olinadi) — guruhga Top-5 BORMaydi.
  - Funksiyaning o'zi (`post_weekly_volunteer_leaderboard`) o'chirilmaydi —
    qo'lda/admin buyrug'i bilan qayta yoqish imkoniyati qoladi
    (masalan, kelajakda `admin:...` tugmasi yoki sozlama bayrog'i).
    Tavsiya: `settings` ga `VOLUNTEER_LEADERBOARD_PUBLIC: bool = False`
    bayrog'i qo'shib, task boshida tekshirish — to'liq o'chirishdan
    ko'ra xavfsiz (rollback bir env o'zgarishi bilan).
  - Qo'shimcha: `admin.py` dagi `admin:vol_leaderboard:month/all`
    tugmalari (staff_stats ichida) SAQLANADI — bu adminning SHAXSIY
    ko'rishi, ommaviy emas.
- **Shaxsiy dayjest qoladimi — tahlil va tavsiya:**
  - QOLADI (tavsiya): `send_weekly_volunteer_personal_digest` (yak 21:00)
    va `/myresult` — ikkalasi ham SHAXSIY, norozilik manbai emas.
    Aksincha, biriktirish tizimi bilan dayjestga "ochiq biriktirishlaringiz:
    N ta" qatori QO'SHILADI (`dispatch_weekly_volunteer_digest` ga kichik
    qo'shimcha) — eslatma yukini kamaytiradi.
  - `calculate_volunteer_stats` / `get_volunteer_result_view` dagi "o'rningiz:
    N-o'rin (jami M ichida)" qatori shaxsiy bo'lgani uchun qoladi; lekin
    ommaviy post o'chgach, o'rin raqamining ishonchliligi savol tug'dirmasligi
    uchun matn o'zgarishsiz qoldiriladi (faqat manba — shaxsiy statistika).
- **DB o'zgarishi:** YO'Q (faqat beat + bayroq).
- **Qiyinlik:** S.
- **Xavf:** Deyarli yo'q. Yagona e'tibor: beat qatori o'chirilgach Celery
  beat restart talab qiladi (deploy eslatmasi); `VOLUNTEER_GROUP_ID`
  sozlamasi boshqa xabarlar uchun ishlatilmasligi tekshiriladi
  (faqat leaderboard ishlatadi — tasdiqlandi).

---

## 8. 02-taklifning bekor qilinadigan qismlari + javob darvozasi bog'lanishi

`takliflar/02_ai_va_volontyor_nazorati.md` dagi quyidagilar ushbu talablar
bilan ALMASHTIRILADI (bekor):

- 4-bo'lim (Claim/assign) TO'LIQ bekor: volontyorning "✋ Men javob beraman"
  tugmasi, `self_claim` manbai, taymautdan keyin "qayta ochiq", `/release`,
  `/extend` buyruqlari, `claim_expires_at` ustuni — HAMMASI keraksiz.
  O'rniga: faqat `assign_source="admin"` (1-band). Poyga muammosi claim
  poygasi emas, "2 admin bir vaqtda" poygasi bo'ladi (1-banddagi yechim).
- `assign_source` dagi `"auto"` qiymati bekor (avto-tayinlash YO'Q).
- 5-bo'lim variantlaridan V3 ("Ball yig'uvchi ishonch" — avtomatik bypass)
  bekor: avtomatik tayinlash/bypass bo'lmagani kabi, ball bo'yicha
  avtomatik ruxsat ham YO'Q.
- 8-bo'lim ustuvorlikdagi "Birinchi navbatda claim, keyin darvoza" tartibi
  bekor — o'rniga "Birinchi navbatda biriktirish (1-3-bandlar), keyin
  darvoza" (pastdagi bosqichlar).
- 2-bo'limdagi `assigned_volunteer_id` (claim bilan bog'lash) SAQLANADI,
  lekin ma'nosi o'zgaradi: claim emas, ADMIN biriktiruvi.
- QOLGANI kuchda qoladi: 1-bo'lim (AI ni fuqaro panelidan olib tashlash),
  2+3-bo'limlar (darvoza + rubrika/eskalatsiya), 6-bo'lim (sifat analitikasi),
  7-bo'lim (adolat/maxfiylik — 6-banddagi RAG minimalizmi bilan birga).
- **Javob darvozasi bilan bog'lanish (02 dagi 2-bo'lim + ushbu reja):**
  `handle_response` (`group_router.py`) ga BIR shart qo'shiladi:
  reply qilgan odam `inquiry.assigned_volunteer_id` ga teng bo'lishi kerak;
  teng bo'lmasa → "bu murojaat X ga biriktirilgan" deb rad etiladi.
  Teng bo'lsa → AI tasdiqi tekshiriladi (`inquiry_assignments.review_status=
  passed` + xesh mosligi); tasdiqsiz → "avval botda Javobni tasdiqlatish
  tugmasi orqali tasdiqlating". ADMINlar (`settings.is_admin` + guruh
  admini) ikkala shartdan ham OZOD (hozirgi `is_admin_user` shoxi kengayadi).
  Yuristlar (`OfficialLawyer`) ozodmi — ochiq savol (pastga qarang).

---

## 9. Bosqichlar (har biri mustaqil deploy qilinadi)

- **Bosqich A — Biriktirish o'zagi (1+2+3-bandlar).** Jadval/migatsiya
  (`inquiries.assigned_*`, `volunteer_sections`, `inquiry_assignments`),
  karta tugmasi, paginatsiyali ro'yxat, tavsiya algoritmi, DM + xato matnlari
  + retry, guruh xabari. Darvozasiz: biriktirilgan volontyor hozirgidek
  javob bera oladi (faqat mas'uliyat belgilanadi). Mustaqil qiymat: qo'lda
  yozuv yo'qoladi, mas'ul aniq bo'ladi.
- **Bosqich B — Eslatmalar (4-band).** Yangi task + beat + tungi cheklov +
  `daily_reminder` dan biriktirilganlarni chiqarish. A siz ham deploy
  bo'ladi (eslatiladigan biriktirish bo'lmasa task bo'sh yuradi), lekin
  A bilan birga chiqishi tavsiya etiladi.
- **Bosqich C — Volontyor menyusi (5-band).** Rol menyusi + 3 tugma +
  FSM. A dagi "oxirgi biriktirish"ni o'qiydi; AI tasdig'i Hozircha
  faqat MASLAHAT rejimida (ruxsat mexanikasi ishlamaydi — darvoza yo'q).
- **Bosqich D — AI nazoratchi (6-band + 02 dagi darvoza).** Media rad etish,
  `delivery_hint`, RAG minimal payload, `handle_response` dagi
  `assigned_volunteer_id` + AI tasdiq sharti, admin ozodligi. C siz
  to'liq ishlamaydi (tasdiq manbai C), shuning uchun C→D ketma-ket.
- **Bosqich E — Leaderboard o'chirish (7-band).** Istalgan vaqtda, mustaqil
  (1 qator beat + bayroq). Eng erta ham chiqarish mumkin — alohida deploy.
- Har bosqichda: alembic upgrade/downgrade tekshiruvi, 1 soha guruhida
  pilot, keyin barcha guruhlarga.

---

## 10. Aniq savollar (kodda javob topilmadi — qaror kerak)

1. "Biriktirish" tugmasini yurist (`OfficialLawyer`) yoki guruh koordinatori
   bosa oladimi yoki faqat `settings.ADMIN_IDS` + guruh admini/creatori?
   (Kodda ikkala toifa ham ruxsatli; talabda "admin" noaniq.)
2. Bir volontyorda bir vaqtda nechta ochiq biriktirish bo'lishi mumkin?
   Limit bormi (masalan 5 ta) yoki cheksiz? (Kodda limit yo'q.)
3. Biriktirilgan volontyor javob bermasa, admin biriktirishni BEKOR qilishi/
   BOSHQAGA o'tkazishi kerakmi? ("Qaytarish" volontyor tomonidan yo'q, lekin
   admin tomonidan qayta tayinlash — kodda ham, talabda ham yo'q.)
4. Eslatma matnlaridagi "AI nazoratchi" nomi — botning hozirgi nomi bilan
   bir xilmi yoki alohida shaxs ("mendan (AI nazoratchidan)") sifatida
   tanishtiriladimi? (Kodda bunday persona yo'q.)
5. Tungi sukunat soati (taklif 22:00–08:00 Toshkent) ma'qulmi yoki boshqa
   oraliq? Dam olish kunlari ham sukunatmi?
6. "Javobni tasdiqlatish" dagi AI tasdig'idan keyin volontyor guruhga
   MATN bilan reply qilishi shartmi yoki ovozli/media ham mumkin?
   (6-bandda nazoratchiga faqat matn kiradi; guruhdagi yakuniy format
   belgilanmagan.)
7. `OfficialLawyer` lar javob darvozasidan ozodmi (adminlar kabi) yoki
   ular ham biriktirish + AI tasdig'idan o'tadimi? (Kodda ular hozir erkin.)
8. Soha a'zoligini kim yuritadi — bitta bosh adminmi yoki har bir soha
   guruhining o'z admini o'z sohasiga qo'shadimi?
9. Tavsiya ro'yxatida volontyorning telefon raqami ko'rinsinmi (admin
   qo'ng'iroq qilishi uchun) yoki faqat ism + ochiq ishlar soni?
   (`Volunteer` da telefon bor; maxfiylik nuqtai nazaridan so'raladi.)
10. RAG tekshiruv prompti va `delivery_hint` sxemasi — RAG servisi
    (tashqi jamoa) bu formatni qo'llaydimi yoki avval ular bilan
    kelishish kerakmi? (Kodda tekshiruv endpointi yo'q — faqat `ask` bor.)
11. Eski (biriktiruvsiz) ochiq murojaatlarga nima bo'ladi — ular darvozadan
    ozod qoladimi yoki deploy paytida barchasiga admin biriktiradimi?
12. 12 soha vs 6 guruh nomuvofiqligi (`keyboards.py` vs `settings.py`) —
    qaysi ro'yxat haqiqat (masalan, "Bolalar" alohida guruhmi yoki
    "Boshqa" ichidami)?

---

## 11. QABUL QILINGAN QARORLAR (foydalanuvchi javoblari, 2026-10-18)

1. **Sohalar:** 10+ soha, lekin guruh 6 ta (4-5 soha uchun alohida guruh, qolganlari umumiy). Soha a'zoligi guruhdan emas, `volunteer_sections` jadvalidan olinadi. Hozirgacha biriktirishni bitta koordinator yuritgan, shuning uchun sohalarni belgilash admin paneldagi bitta joydan (koordinator/admin) qilinadi. `section_name` ni normalizatsiya qilish (12 soha ro'yxati yagona manba) A bosqichiga kiradi.
2. **Biriktirish:** FAQAT adminlar (`settings.is_admin`). Yuristlar va koordinator-yuristlar tugmani bosa olmaydi. (Soha a'zoligini belgilovchi koordinator ham admin bo'lishi kerak.)
3. **Qayta tayinlash:** admin biriktirishni boshqa volontyorga o'tkaza oladi (eski biriktirish `reassigned` holatiga o'tadi, tarixda qoladi; yangi volontyorga DM, eskisiga "murojaat boshqaga o'tkazildi" xabari, eslatmalar yangisiga o'tadi).
4. **Limit yo'q:** bir volontyorda ochiq biriktirishlar soni cheklanmaydi.
5. **Eski murojaatlar:** majburiy nazoratga kirmaydi. Faqat yangilanish deployidan KEYIN yaratilgan murojaatlarga biriktirish, darvoza, eslatmalar qo'llanadi. Amalda: sozlamada `ASSIGN_ENFORCE_FROM` (deploy sanasi/vaqti); `Inquiry.created_at` shundan kichik bo'lsa eski xulq-atvor (har kim reply qila oladi, eslatma yo'q) saqlanadi.
6. **Tungi sukunat:** 22:00-06:00 (Toshkent) bot ESLATMA yubormaydi; 06:00 da to'plangan eslatma bitta bo'lib boradi. Admin biriktirgan paytdagi "murojaat sizga biriktirildi" xabari VA admin xabarlari soat nechchi bo'lsa ham DARHOL yuboriladi (sukunat faqat avtomatik eslatmalarga).
7. **Ozod toifalar:** adminlar va yuristlar (`OfficialLawyer`) biriktirish, AI tasdig'i va barcha cheklovlardan to'liq ozod.
8. **AI nazoratchi kirishi (YANGI aniqlik):** volontyor nazoratchidan murojaatchiga javob yuborilmaguncha ISTAGANCHA marta foydalana oladi (cheksiz qayta tekshiruv). Biriktirilgan ochiq (javobi fuqaroga yuborilmagan) murojaati YO'Q volontyor nazoratchidan umuman foydalana olmaydi ("Sizga biriktirilgan murojaat yo'q"). Shuning uchun 5-banddagi "bir martalik ruxsat" o'zgaradi: tasdiq har bir qoralama xeshiga bog'lanadi (`review_draft_hash`); volontyor qayta-qayta tekshirtiradi, oxirgi TASDIQLANGAN qoralamaga mos reply ketadi; javob fuqaroga yuborilgach murojaat yopiladi va nazoratchi o'sha murojaat uchun yopiladi.

Bu qarorlar yuqoridagi 10-bo'limdagi 1, 2, 3, 5, 7, 11-savollarga javob; qolganlari (4-persona nomi, 6 reply formati, 8, 9, 10, 12) hali ochiq.
