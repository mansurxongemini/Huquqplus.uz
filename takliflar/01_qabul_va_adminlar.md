# Huquq+ Yurist qabuli boshqaruvi, media cheklovi va Adminlar boshqaruvi (Takliflar to'plami A)

> **Holati:** Faqat tahlil va arxitekturaviy taklif. Mavjud kod o'zgartirilmagan.  
> **Asos:** Repozitoriydagi mavjud modellar, handlerlar, klaviaturalar va vazifalar tahlili (`src/routes/aiogram/appointment.py`, `src/models/appointment.py`, `src/tasks/appointment_reminders.py`, `src/routes/aiogram/admin.py`, `src/config/settings.py`, `src/app/filters.py`, `src/app/enums.py`).

---

## 0. Mavjud holat tahlili (Tayanch nuqtalar)

1. **Yurist qabuli oqimi va modellari:**
   - `src/models/appointment.py`: `Appointment` modeli (`id`, `user_id`, `appointment_type`, `problem_description`, `lawyer_id`, `group_message_id`, `status` (`pending`, `accepted`, `completed`, `cancelled`), `scheduled_at`, `completed_at`, `media_type`, `media_file_id`, `media_name`, `media_meta`, `meeting_link`, `cancellation_reason`, `reminder_sent`, `rating`, `feedback`).
   - Fuqaro qabulga yozilishi: `src/routes/aiogram/appointment.py` — `start_appointment` → `choosing_appointment_type` → `entering_problem_and_media` → `confirming_booking` → `execute_appointment_submission`. Ariza `pending` holatida yaratilib, `settings.LAWYER_APPOINTMENT_GROUP_ID` guruhiga yuboriladi (`group_message_id` saqlanadi).
   - Yuristlar guruhida qabulni olish: `src/routes/aiogram/group_router.py` dagi `appointment:claim:{app.id}` callback'i. Yurist arizani olganda `appointment.status = AppointmentStatus.accepted`, `appointment.lawyer_id = query.from_user.id` bo'ladi va fuqaroga shaxsiy chatda xabar boradi.

2. **Admin panel va mavjud CRM imkoniyatlari:**
   - `src/routes/aiogram/admin.py`: `admin:crm_appointments` dashboard'i mavjud (bugungi, kutilayotgan, biriktirilmagan va barcha qabullar soni).
   - `admin:crm_view:{app.id}` orqali ariza tafsilotlari ko'riladi.
   - Hozirgi imkoniyatlar:
     - `admin:crm_set_link` — online uchrashuv havolasini kiritish/yangilash;
     - `admin:crm_assign` — ro'yxatdan yurist tanlab biriktirish;
     - `admin:crm_cancel` — sabab kiritib arizani bekor qilish.
   - **Tizimdagi jiddiy bo'shliqlar:**
     - Bekor bo'lgan arizani tiklash uchun **hech qanday funksiya yoki tugma yo'q**.
     - Yuristni boshqasiga almashtirishda: eski yuristga xabar bormaydi, guruhdagi xabar yangilanmaydi, vaqt to'qnashuvi (conflict) tekshirilmaydi.
     - Qabulga aniq vaqt belgilash (`scheduled_at`) yoki uni o'zgartirish uchun **admin panelda birorta ham handler/menyu mavjud emas**.
     - Admin harakatlari bo'yicha **Audit log (tarix) saqlanmaydi**.

3. **Eslatmalar tizimi (Celery fon vazifalari):**
   - `src/tasks/appointment_reminders.py`:
     - `check_appointment_reminders` — har 10 daqiqada ishga tushib, keyingi 60 daqiqa ichida bo'ladigan (`scheduled_at >= now`, `<= now + 65 min`, `reminder_sent == False`) qabullarni topadi va fuqaro hamda yuristga 1 soatlik eslatma yuboradi, so'ng `reminder_sent = True` qiladi.
     - `send_pending_appointment_reminders` — har 3 kunda yuristlar guruhiga ochiq (`pending`) va muddati o'tgan (`overdue`) qabullar eslatmasini yuboradi.
   - **Xavf:** Agar admin qabul vaqtini o'zgartirsa (kelajakka sursa), lekin `reminder_sent` ni qayta `False` qilmasa, Celery yangi vaqt uchun eslatma yubormaydi!

4. **Media fayllarni qabul qilish holati:**
   - `src/routes/aiogram/appointment.py` dagi `handle_appointment_media_input`:
     - Foydalanuvchi ovoz, video, dumaloq video, rasm yoki hujjat yuborishi mumkin.
     - `_user_appointment_locks[user_id]` mutex va `_pending_media_ack_tasks` (0.7s debounced xabar) mavjud.
     - **Kamchilik:** Hech qanday miqdoriy chegara (limit) yo'q. Fuqaro 20-30 ta fayl yuborishi mumkin, bu botni sekinlashtiradi, guruhga 30 ta xabar jo'natilishiga va ma'lumotlar bazasida ortiqcha yuklamaga sabab bo'ladi.

5. **Adminlar va xavfsizlik arxitekturasi:**
   - `src/config/settings.py`: Adminlar faqat statik `.env` o'zgaruvchisi `ADMIN_IDS` (masalan `"12345,67890"`) orqali belgilanadi.
   - `src/app/filters.py`: Adminlar uchun alohida Filter klassi mavjud emas, har bir handlerda inline `settings.is_admin(...)` chaqiriladi.
   - `src/models/user.py`: `User` jadvalida hech qanday `is_admin` yoki `role` ustuni yo'q.
   - **Kamchilik:** Yangi admin qo'shish yoki o'chirish uchun har safar serverga kirib, `.env` faylini o'zgartirib, bot konteynerini qayta ishga tushirish talab qilinadi. Superadmin va oddiy admin darajalari ajratilmagan.

---

## 1. 1-YO'NALISh: Yurist qabuli bo'yicha ADMINLAR boshqaruvini takomillashtirish

### 1.1. Bekor bo'lgan qabullarni qayta tiklash (Restore cancelled appointment)

- **Nima:** Fuqaro yoki yurist tomonidan adashib yoki shoshilinch bekor qilingan arizalarni admin panel orqali qayta jonlantirish (tiklash) imkoniyati.
- **Qanday ishlaydi:**
  - **Admin nuqtai nazaridan:**
    1. Admin CRM ro'yxatidan bekor qilingan qabul kartochkasini ochadi (`admin:crm_view:{app_id}`).
    2. Agar `app.status == AppointmentStatus.cancelled` bo'lsa, kartochkada "♻️ Qabulni qayta tiklash" (`admin:crm_restore:{app_id}`) inline tugmasi ko'rinadi.
    3. Bosilganda admin tanlov qiladi:
       - *"⏳ Ochiq holatga qaytarish (Pending)"* — yuristlar guruhiga qayta yuboriladi yoki ochiq qilinadi;
       - *"🔵 Qabul qilingan holatga qaytarish (Accepted)"* — avvalgi yuristga biriktirilgan holda tiklanadi.
    4. Tasdiqlash oynasi chiqadi: *"№{app_id} arizani qayta tiklashni tasdiqlaysizmi?"* → [✅ Ha, tiklansin] / [❌ Bekor qilish].
    5. Tiklangach, `cancellation_reason = None` bo'ladi, `status` tanlangan qiymatga o'tadi, guruhdagi kartochka yangilanadi.
  - **Yurist nuqtai nazaridan:** Agar ariza unga biriktirilgan holda tiklansa, unga shaxsiy xabar boradi: *"🔔 №{app.id} qabul arizasi admin tomonidan qayta tiklandi va sizga qaytarildi."*
  - **Fuqaro nuqtai nazaridan:** Shaxsiy xabar boradi: *"✅ Sizning yurist qabuliga arizangiz (№{app.id}) ma'muriyat tomonidan qayta ko'rib chiqilib, tiklandi! Tez orada mutaxassis siz bilan bog'lanadi."*
- **Tegishli fayllar:**
  - `src/routes/aiogram/admin.py`: `admin_crm_view_callback`, yangi `admin_crm_restore_start`, `admin_crm_restore_confirm` handlerlari.
  - `src/routes/aiogram/appointment.py`: `execute_appointment_submission` dagi guruh xabari yangilanishi.
  - `src/routes/aiogram/group_router.py`: Guruhdagi xabarni `edit_message_text` orqali qayta faollashtirish.
- **DB o'zgarishi:**
  - `hp_appointments` jadvalida mavjud ustunlar yetarli (`status`, `cancellation_reason`, `updated_at`).
  - Audit log jadvali (1.5-bo'limga qarang).
- **Xavf/kamchilik:** Fuqaro ariza bekor bo'lgach yangi ariza topshirib qo'ygan bo'lishi mumkin (bitta yo'nalishda faol arizalar to'qnashuvi). **Yechim:** Tiklashdan oldin `db_session` orqali fuqaroda ayni shu yo'nalish bo'yicha boshqa faol (`pending`/`accepted`) ariza bor-yo'qligi tekshiriladi; agar bo'lsa, adminga ogohlantirish berilib, avval unisini hal qilish so'raladi.
- **Qiyinlik:** S.

---

### 1.2. Istalgan qabulni olgan yuristni boshqasiga almashtirish (Reassign / Switch lawyer)

- **Nima:** Qabulni qabul qilib olgan yurist kasal bo'lib qolsa, boshqa soha yuristiga o'tkazish kerak bo'lsa yoki admin qarori bilan istalgan qabulni bir yuristdan boshqasiga xavfsiz qayta biriktirish.
- **Qanday ishlaydi:**
  - **Admin nuqtai nazaridan:**
    1. Kartochkada (`admin:crm_view:{app_id}`) har doim "🔄 Yuristni almashtirish" (`admin:crm_reassign:{app_id}`) tugmasi bo'ladi.
    2. Faol yuristlar ro'yxati (`OfficialLawyer.get_active_lawyers()`) chiqadi. Hozirgi biriktirilgan yurist yonida `[Hozirgi]` belgisi turadi.
    3. Yangi yurist tanlangach, admindan sabab so'raladi (masalan: *"Yurist bandligi sababli"* yoki *"Mutaxassislikka ko'ra"*).
    4. Tasdiqlash oynasi: *"№{app_id} qabulni {Eski_Yurist} dan ➡️ {Yangi_Yurist} ga o'tkazishni tasdiqlaysizmi?"*.
    5. Tasdiqlangach, yangilanish amalga oshiriladi.
  - **Eski yurist nuqtai nazaridan:** Shaxsiy chatiga bildirishnoma boradi: *"⚠️ Sizga biriktirilgan №{app.id} qabul admin tomonidan boshqa mutaxassisga o'tkazildi. Sabab: {sabab}."* Shuningdek, uning eslatma navbatidan olib tashlanadi.
  - **Yangi yurist nuqtai nazaridan:** Shaxsiy chatiga fuqaro kartochkasi, belgilangan vaqt va muammo matni bilan to'liq ma'lumot boradi: *"🔔 Sizga admin tomonidan yangi qabul (№{app.id}) biriktirildi."*
  - **Fuqaro nuqtai nazaridan:** Shaxsiy chatiga xabar boradi: *"👨‍⚖️ Sizning qabulingiz bo'yicha mas'ul yurist o'zgardi: {Yangi_Yurist_FIO}. Belgilangan vaqt o'zgarishsiz qoladi."*
  - **Guruh kartochkasi:** `settings.LAWYER_APPOINTMENT_GROUP_ID` dagi `group_message_id` xabari tahrirlanib, mas'ul yurist ismi yangilanadi.
- **Tegishli fayllar:**
  - `src/routes/aiogram/admin.py`: `admin_crm_reassign_start`, `admin_crm_reassign_selected`, `admin_crm_reassign_confirm`.
  - `src/models/lawyer.py`: `OfficialLawyer.get_active_lawyers`.
  - `src/routes/aiogram/group_router.py`: Guruh xabari render funksiyasi.
- **DB o'zgarishi:**
  - `hp_appointments` jadvalida: `lawyer_id`, `updated_at`.
- **Xavf/kamchilik:** Yangi tanlangan yuristda ayni shu vaqtda boshqa qabul bo'lishi mumkin. **Yechim:** 1.3-bo'limdagi vaqt to'qnashuvi tekshiruvi bu yerda ham ishga tushadi.
- **Qiyinlik:** M.

---

### 1.3. Istalgan qabulga vaqt belgilash va o'zgartirish (Schedule / Reschedule & Conflict detection)

- **Nima:** Qabul arizasiga aniq suhbat vaqtini belgilash (`scheduled_at`) yoki mavjud vaqtni boshqa sanaga/soatga ko'chirish, shu bilan birga yuristning bandligini tekshirish.
- **Qanday ishlaydi:**
  - **Admin nuqtai nazaridan:**
    1. Kartochkada "📅 Vaqt belgilash / o'zgartirish" (`admin:crm_reschedule:{app_id}`) tugmasi bo'ladi.
    2. FSM oqimi (dialog):
       - 1-qadam: Sana tanlash (Tezkor tugmalar: `[Bugun]`, `[Ertaga]`, `[Indinga]` yoki `[✍️ Boshqa sana: DD.MM.YYYY]`).
       - 2-qadam: Vaqt slotini tanlash (Standart tugmalar: `09:00`, `10:00`, `11:00`, `12:00`, `14:00`, `15:00`, `16:00`, `17:00` yoki erkin `HH:MM`).
    3. **Vaqt to'qnashuvini tekshirish (Conflict Detection Engine):**
       - Tizim tekshiradi: Agar qabulga `lawyer_id` biriktirilgan bo'lsa, ushbu yuristda tanlangan vaqtdan +/- 60 daqiqa (yoki `lawyer.slot_duration`) oralig'ida boshqa faol (`status == accepted`) qabul mavjudmi?
       - Agar to'qnashuv aniqlansa: Adminga qizil ogohlantirish chiqadi:  
         *"⚠️ DIQQAT: Yurist {lawyer_name} ayni shu vaqtda ({vaqt}) boshqa №{boshqa_id}-sonli qabul suhbatiga ega! Qabullar bir vaqtga to'g'ri kelib qoladi."*  
         Tugmalar: `[🔄 Boshqa vaqt tanlash]` / `[⚠️ Baribir belgilansin (Majburiy)]`.
    4. Tasdiqlash: *"№{app_id} qabul vaqti: {Eski_Vaqt} ➡️ {Yangi_Vaqt}. Tasdiqlaysizmi?"*.
  - **Yurist nuqtai nazaridan:** Shaxsiy xabar: *"📅 №{app.id} qabul suhbati vaqti belgilandi/o'zgartirildi: {yangi_vaqt}."*
  - **Fuqaro nuqtai nazaridan:** Shaxsiy xabar: *"📅 Sizning yurist qabulingiz vaqti belgilandi/o'zgartirildi: <b>{yangi_vaqt}</b>. Iltimos, ushbu vaqtda aloqada bo'ling!"*
  - **Guruh kartochkasi:** Guruhdagi asosiy xabarda belgilangan vaqt yangilanadi.
- **Tegishli fayllar:**
  - `src/routes/aiogram/admin.py`: `AdminCrmState` ga `waiting_for_date`, `waiting_for_time` holatlari, vaqt tekshirish utilitalari.
  - `src/app/calendar_utils.py`: Vaqtlarni formatlash va solishtirish funksiyalari.
  - `src/models/appointment.py`: `check_lawyer_conflict(lawyer_id, scheduled_at, duration_minutes, exclude_app_id)` yordamchi metodi.
- **DB o'zgarishi:**
  - `hp_appointments` jadvali: `scheduled_at` (DATETIME, index), `reminder_sent = False` (1.4-bo'limga qarang).
- **Xavf/kamchilik:** Vaqt zonalari (Timezone) chalkashligi. Server UTC da ishlasa, foydalanuvchiga Toshkent vaqti (UTC+5) ko'rsatilishi shart. Loyihadagi `datetime.now()` va formatlashlar Toshkent vaqtiga mosligini qat'iy tekshirish kerak.
- **Qiyinlik:** M.

---

### 1.4. Eslatma tasklarini qayta rejalashtirish va sinxronizatsiya (Celery reminder sync)

- **Nima:** Qabul vaqti o'zgartirilganda yoki bekor qilinganda Celery fon eslatmalari to'g'ri ishlashini ta'minlash.
- **Qanday ishlaydi:**
  - **Mavjud mantiq:** `src/tasks/appointment_reminders.py` dagi `check_appointment_reminders` har 10 daqiqada ishlaydi va `scheduled_at <= now + 65 min` hamda `reminder_sent == False` bo'lgan qabullarga eslatma yuborib, `reminder_sent = True` qilib qo'yadi.
  - **Muammo:** Agar qabul vaqti 14:00 bo'lib, unga soat 13:00 da eslatma yuborilgan bo'lsa (`reminder_sent = True`), admin esa soat 13:30 da qabul vaqtini ertangi kunga ko'chirsa, `reminder_sent` maydoni `True` ligicha qolib ketadi va ertaga yangi vaqt uchun eslatma UMUMAN BORMAYDI!
  - **Yechim (Avtomatik reset):**
    - Har safar qabul vaqti (`scheduled_at`) o'zgartirilganda (agar yangi vaqt `now + 65 daqiqa` dan uzoqroqda bo'lsa), kod avtomatik tarzda:  
      `app.reminder_sent = False` qilishi SHART!
    - Agar qabul bekor qilinsa (`cancelled`), Celery uni o'zi e'tiborsiz qoldiradi (chunki Celery faqat `status == accepted` ni qidiradi).
    - Agar qabul bekor holatdan tiklansa (`restore`), yana `reminder_sent = False` tekshirilib, qayta rejalashtiriladi.
- **Tegishli fayllar:**
  - `src/tasks/appointment_reminders.py`: `check_appointment_reminders` (o'zgarishsiz qoladi, chunki arxitektura DB-driven polling asosida).
  - `src/routes/aiogram/admin.py`: Vaqt o'zgartirish va tiklash amallarida `reminder_sent` ni boshqarish.
- **DB o'zgarishi:** Qo'shimcha ustun shart emas (`hp_appointments.reminder_sent` mavjud).
- **Xavf/kamchilik:** Agar admin yangi vaqtni 15 daqiqadan keyingi muddatga belgilasa, keyingi 10 daqiqalik Celery tsikli kelguncha kechikish bo'lishi mumkin. **Yechim:** Agar yangi vaqt `< 60 min` bo'lsa, admin o'zgartirgan paytning o'zida to'g'ridan-to'g'ri bildirishnoma yuboriladi va `reminder_sent = True` qilib qo'yiladi.
- **Qiyinlik:** S.

---

### 1.5. Qabullar o'zgarishlari bo'yicha Audit log tizimi (Appointment Audit Trail)

- **Nima:** Qaysi admin, qaysi qabulni, qachon, nimadan nimaga o'zgartirgani (yurist almashinuvi, vaqt ko'chirilishi, bekor qilish/tiklash) va qanday sabab kiritganini to'liq saqlab boruvchi audit tizimi.
- **Qanday ishlaydi:**
  - **Admin nuqtai nazaridan:**
    - Kartochkada (`admin:crm_view:{app_id}`) "📜 O'zgarishlar tarixi" (`admin:crm_audit:{app_id}`) tugmasi paydo bo'ladi.
    - Bosilganda qabul bo'yicha barcha amallar xronologik ko'rinadi:
      ```text
      📜 Ariza №42 o'zgarishlar tarixi:
      • 18.10.2026 14:15 — Admin Sardor (ID: 102938):
        Amal: Yurist almashtirildi
        Eski: Rustam Qosimov ➡️ Yangi: Nodira Aliyeva
        Sabab: Mutaxassislikka ko'ra
      • 18.10.2026 14:20 — Admin Sardor:
        Amal: Vaqt o'zgartirildi
        Eski: 19.10 10:00 ➡️ Yangi: 20.10 15:00
      • 17.10.2026 18:00 — Fuqaro tomonidan bekor qilingan
      • 18.10.2026 12:00 — Admin Sardor:
        Amal: Qayta tiklandi (Pending)
      ```
- **Tegishli fayllar:**
  - `src/models/appointment.py`: Yangi `AppointmentAuditLog` modeli.
  - `src/routes/aiogram/admin.py`: Barcha CRM harakatlarida log yozish yordamchi funksiyasi (`log_appointment_action`) va tarixni ko'rish handleri.
- **DB o'zgarishi:**
  - Yangi jadval: `hp_appointment_audit_logs`
    - `id`: int (Primary Key, Auto Increment)
    - `appointment_id`: int (Foreign Key -> `hp_appointments.id`, Index)
    - `admin_id`: BigInteger (Index)
    - `action`: VARCHAR(50) (`restore`, `reassign`, `reschedule`, `cancel`, `set_link`)
    - `old_values`: JSON / Text (eski holat, eski vaqt, eski yurist)
    - `new_values`: JSON / Text (yangi holat, yangi vaqt, yangi yurist)
    - `reason`: Text (nullable)
    - `created_at`: DATETIME (default=now)
- **Xavf/kamchilik:** Bazada yozuvlar ko'payishi. Ammo qabullar soni o'n minglab bo'lmagani sababli joy deyarli egallamaydi.
- **Qiyinlik:** S.

---

## 2. 2-YO'NALISh: Fuqaro yurist qabuliga 10 tadan ortiq media fayl yuborishini cheklash

### 2.1. Media fayllar sonini 10 tagacha qat'iy cheklash va hisoblagich (Counter: X/10)

- **Nima:** Fuqaroning bitta ariza doirasida yuklaydigan jami media fayllari (rasm, PDF, hujjat, video, audio, krujok) sonini 10 tadan oshmasligini kafolatlash va fuqaroga har qadamda aniq hisoblagichni ko'rsatish.
- **Qanday ishlaydi:**
  - **Fuqaro nuqtai nazaridan:**
    1. Qabul turini tanlab, `entering_problem_and_media` holatiga o'tganda boshlang'ich yo'riqnoma chiqadi:  
       *"📌 Endi muammoingizni bayon qiling va zarur hujjatlarni ilova qiling (Maksimal 10 tagacha fayl yuborishingiz mumkin):"*
    2. Fuqaro 1 ta yoki bir nechta fayl yuboradi.
    3. Bot javob beradi:  
       `📥 Ma'lumot qabul qilindi!`  
       `📎 Biriktirilgan fayllar: 3/10 ta (Ariza.pdf, Sud_qarori.pdf, Rasm.jpg)`  
       `ℹ️ Yana 7 ta fayl biriktirishingiz mumkin.`
    4. Agar fuqaro yana fayllar yuborib, jami son 10 taga yetsa:  
       `📎 Biriktirilgan fayllar: 10/10 ta (Maksimal limitga yetdi)`  
       `⚠️ Siz maksimal 10 ta media fayl biriktirdingiz. Yangi fayllar qabul qilinmaydi. Endi muammoni matn orqali to'ldirishingiz yoki '📤 Yuborish' tugmasini bosishingiz mumkin.`
    5. Agar fuqaro 10 tadan keyin ham yana fayl yuborishga urinsa: fayl FSM xotirasiga **qo'shilmaydi** va ogohlantirish beriladi:  
       `⛔️ Limit to'lgan: Ushbu qabul uchun 10 ta fayl qabul qilib bo'lingan. Qo'shimcha fayl qabul qilinmaydi.`
- **Tegishli fayllar:**
  - `src/routes/aiogram/appointment.py`: `handle_appointment_media_input`, `extra_media_in_confirming`, `render_confirmation_card`.
- **DB o'zgarishi:** DB o'zgarishi shart emas (hozirgi `hp_appointments.media_meta` JSON ustuni 10 ta fayl ma'lumotlarini bemalol sig'diradi).
- **Xavf/kamchilik:** Foydalanuvchi faqat matn yuborganda uni fayl deb hisoblab qo'ymaslik kerak. Matn `problem_description` ga ulanadi, `media_items` esa faqat fayl bo'lganda ortadi.
- **Qiyinlik:** S.

---

### 2.2. Telegram Albomlari (media_group_id) bilan ishlash va debounced xabarlar mantiqi

- **Nima:** Foydalanuvchi Telegram da bir vaqtda 5-10 ta rasmni "albom" (media group) qilib jo'natganda botning poyga holatiga (race condition) tushmasligi, limitdan ortiq qismini to'g'ri kesishi va yagona chiroyli xabar bilan tushuntirishi.
- **Qanday xususiyatga ega:**
  - Telegram albom yuborilganda uni alohida-alohida `Message` obyekti qilib, har biriga bir xil `media_group_id` beradi. Bular botga deyarli bir vaqtda (millisekundlar farqi bilan) parallel keladi.
  - Loyihada hozir `_user_appointment_locks[user_id]` mutex va 0.7 soniyalik `_send_debounced_ack` mavjud.
  - **Yangi taklif etilayotgan albom chegarasi mantiqi:**
    - Masalan, fuqaroda 8 ta fayl bor edi. U 5 ta rasmli albom yubordi (jami 13 ta bo'lishi kerak).
    - Har bir kelgan albom xabari `get_appointment_user_lock(user_id)` orqali navbatma-navbat tekshiriladi:
      - 1-xabar (9-fayl): `len(media_items) < 10` → Qabul qilinadi;
      - 2-xabar (10-fayl): `len(media_items) < 10` → Qabul qilinadi;
      - 3, 4, 5-xabarlar: `len(media_items) >= 10` → Qabul qilinmaydi (`rejected_in_batch` hisoblagichi 1 tadan 3 tagacha oshadi).
    - 0.7 soniyadan so'ng bitta umumiy debounced xabar chiqariladi:  
      *"📥 Albomdan 2 ta fayl qabul qilindi va jami limit (10/10) to'ldi.<br/>⚠️ Albomdagi qolgan 3 ta fayl qabul qilinmadi (maksimal chegara 10 ta)."*
    - Natijada fuqaroning chati takroriy xabarlarga to'lmaydi (spam bo'lmaydi) va Telegram API FloodWait yuzaga kelmaydi.
- **Tegishli fayllar:**
  - `src/routes/aiogram/appointment.py`: `handle_appointment_media_input` ichidagi lock bloki va `_send_debounced_ack`.
- **DB o'zgarishi:** Yo'q.
- **Xavf/kamchilik:** Foydalanuvchi albom jo'natayotganda qaysi fayllar kirganini va qaysilari tushib qolganini tushunmay qolishi mumkin. **Yechim:** Debounced xabarda qabul qilingan va rad etilgan fayllar soni va nomlari aniq ajratib ko'rsatiladi.
- **Qiyinlik:** M.

---

### 2.3. Biriktirilgan fayllarni tahrirlash va tozalash mexanizmi (Clear / Reset media)

- **Nima:** Fuqaro adashib boshqa shaxsiy yoki noto'g'ri hujjatni yuklab qo'ysa, butun arizani bekor qilib boshidan boshlamasdan, yuklangan fayllarni tozalash va qayta yuklash imkoniyati.
- **Qanday ishlaydi:**
  - **Fuqaro nuqtai nazaridan:**
    1. Kamida 1 ta fayl yuklangach, klaviaturada yoki tasdiqlash kartochkasi ostida "🗑 Fayllarni tozalash" (`app_clear_media`) inline tugmasi paydo bo'ladi.
    2. Bosilganda fuqarodan tasdiq so'raladi: *"Biriktirilgan barcha {N} ta faylni o'chirib, qaytadan yuklamoqchimisiz? (Kiritilgan matningiz saqlanib qoladi)"*.
    3. Tasdiqlansa: `media_items = []`, `media_file_id = None`, `media_meta = None` qilinadi.
    4. Xabar chiqadi: *"🗑 Barcha biriktirilgan fayllar tozalandi. Endi qaytadan to'g'ri fayllarni yuborishingiz mumkin (10 tagacha)."*
    5. Natijada fuqaro o'zi yozgan uzun matnini yo'qotmaydi, faqat fayllarni yangitdan yuklaydi.
- **Tegishli fayllar:**
  - `src/routes/aiogram/appointment.py`: yangi `app_clear_media_prompt` va `app_clear_media_confirm` handlerlari.
- **DB o'zgarishi:** Yo'q.
- **Xavf/kamchilik:** Fuqaro bitta faylni alohida o'chirmoqchi bo'lishi mumkin. Lekin Telegram inline interfeysida har bir fayl uchun alohida o'chirish menyusini qilish UX ni haddan tashqari murakkablashtiradi va xabarlar limitiga uriladi. "Barchasini tozalash va qayta tashlash" eng sodda, tushunarli va ishonchli yechim hisoblanadi.
- **Qiyinlik:** S.

---

## 3. 3-YO'NALISh: Admin panelda adminlarni Telegram ID orqali qo'shish/o'chirish

### 3.1. Superadmin va oddiy adminlar tabaqalanishi (Role hierarchy & Break-glass access)

- **Nima:** Tizimda ikki xil boshqaruv darajasini joriy etish:
  1. **Bosh admin (Superadmin):** Barcha huquqlarga ega — adminlarni qo'shish, o'chirish, rollarini belgilash, tizim sozlamalari, tahliliy hisobotlar.
  2. **Oddiy admin (Admin):** Operatsion boshqaruv — qabullar CRM, imtiyozlar tahriri, foydalanuvchini bloklash/ochish, broadcast. Lekin boshqa adminlarni ko'ra olmaydi va boshqara olmaydi!
- **Break-glass (Favqulodda kirish kafolati):**
  - `.env` faylidagi `SUPER_ADMIN_ID` (yoki mavjud `settings.ADMIN_IDS` ning birinchi ID si) har doim eng yuqori darajadagi superadmin hisoblanadi.
  - Agar ma'lumotlar bazasi o'chib ketsa, buzilsa yoki tasodifan barcha adminlar DB dan o'chirib yuborilsa ham, `.env` dagi Superadmin har qanday holatda botga admin sifatida kira oladi va tizimni tiklay oladi.
- **O'z-o'zini va Superadminni himoyalash qoidalari:**
  - Superadmin o'zini o'zi adminlikdan o'chira olmaydi.
  - Oddiy admin superadminni o'chira olmaydi yoki tahrirlay olmaydi.
  - Hech bir admin boshqa teng darajadagi adminni o'chira olmaydi (faqat Superadmin o'chira oladi).
- **Qiyinlik:** S.

---

### 3.2. Ma'lumotlar bazasi arxitekturasi: Alohida `Admin` modeli (Tavsiya) vs `User.role`

- **Solishtirma tahlil:**
  - *A-variant: `User` modeliga `role` qo'shish (`User.role`):*
    - Kamchiligi: Yangi admin tayinlash uchun u avval botdan fuqaro sifatida to'liq ro'yxatdan o'tgan bo'lishi shart bo'lib qoladi. Adminlikka oid qo'shimcha maydonlar (`added_by`, `permissions`, `is_active`) `User` modelini ortiqcha yuklaydi.
  - *B-variant: Alohida `AdminUser` jadvali yaratish (TAVSIYA ETILADI):*
    - Afzalligi: Loyihadagi mavjud `OfficialLawyer` (`src/models/lawyer.py`) va `Volunteer` (`src/models/volunteer.py`) me'moriy andozasiga 100% mos tushadi! Alohida jadval mustaqil, xavfsiz va boshqarish oson.
- **Tavsiya etilayotgan model (`src/models/admin.py`):**
  ```python
  class AdminRole(str, Enum):
      super_admin = "super_admin"
      admin = "admin"

  class AdminUser(BaseModel, table=True):
      __tablename__ = table_prefix + "admins"

      user_id: int = Field(sa_type=BigInteger, unique=True, index=True)
      full_name: str = Field(sa_type=VARCHAR(255))
      username: str | None = Field(default=None, sa_type=VARCHAR(255))
      role: AdminRole = Field(default=AdminRole.admin, index=True)
      is_active: bool = Field(default=True, index=True)
      added_by: int | None = Field(default=None, sa_type=BigInteger)
      created_at: datetime = Field(default_factory=datetime.now)
      updated_at: datetime = Field(default_factory=datetime.now)
  ```
- **DB o'zgarishi:**
  - Yangi jadval: `hp_admins`
    - `id`: int (PK, AI)
    - `user_id`: BIGINT (Unique, Index)
    - `full_name`: VARCHAR(255)
    - `username`: VARCHAR(255), nullable
    - `role`: VARCHAR(50) (default="admin")
    - `is_active`: BOOLEAN (default=True)
    - `added_by`: BIGINT, nullable
    - `created_at`: DATETIME
    - `updated_at`: DATETIME
- **Qiyinlik:** S.

---

### 3.3. Telegram ID kiritish, tekshirish va xavfsizlik filtrlari

- **Nima:** Admin Telegram ID sini kiritganda uni ko'r-ko'rona saqlamasdan, to'liq tekshirish va xavfsizlik choralarini ko'rish.
- **Qanday tekshiriladi:**
  1. **Format tekshiruvi:** Kiritilgan qiymat faqat musbat son bo'lishi kerak (`^\d{5,15}$`).
  2. **Mavjudlik tekshiruvi:**
     - Avval `hp_users` jadvalidan qidiriladi: agar foydalanuvchi botdan foydalangan bo'lsa, uning ismi va username'i avtomatik olinadi.
     - Agar `hp_users` da topilmasa: Telegram API orqali `bot.get_chat(target_id)` qilinadi.
     - Agar foydalanuvchi botga umuman `/start` bosmagan bo'lsa: Telegram bot unga shaxsiy xabar yubora olmaydi. Shuning uchun Superadminga ogohlantirish ko'rsatiladi:  
       *"⚠️ Ushbu ID egasi hali botga /start bosmagan. U admin panelga kira oladi, lekin bot unga shaxsiy bildirishnoma yubora olmaydi. Davom etilsinmi?"*
  3. **Takroriylik tekshiruvi:** Agar bu ID allaqachon adminlar ro'yxatida bo'lsa, xato beriladi.
- **Filtrlar va Kesh:**
  - `src/app/filters.py`:
    - `class IsAdmin(Filter)`: Foydalanuvchi `settings.SUPER_ADMIN_IDS` da bormi YOKI `hp_admins` jadvalida `is_active == True` holatidami?
    - `class IsSuperAdmin(Filter)`: Faqat superadminlar uchun.
  - **Kesh:** Har bir xabarda bazaga so'rov yubormaslik uchun adminlar ID lari to'plami Redis yoki xotirada 60 soniya TTL bilan kesRecordlanadi. Yangi admin qo'shilganda yoki o'chirilganda kesh darhol tozalanadi (`cache invalidate`).
- **Qiyinlik:** M.

---

### 3.4. Admin panel UI/UX oqimi: Adminlar ro'yxati, qo'shish (FSM) va o'chirish

- **Nima:** Admin panel bosh menyusida (`src/routes/aiogram/admin.py`) faqat Superadminga ko'rinadigan qulay boshqaruv bo'limi.
- **Qanday ishlaydi:**
  - **Superadmin nuqtai nazaridan:**
    1. Bosh menyuda: `[👥 Adminlar boshqaruvi]` tugmasi (oddiy adminlarda bu tugma ko'rinmaydi).
    2. Ro'yxat ko'rinishi (`admin:admins_list`):
       ```text
       👥 Tizim adminlari ro'yxati:
       1. ⭐️ Mansurxon (ID: 1234567) — Superadmin
       2. 🟢 Sardor Aliyev (@sardor, ID: 9876543) — Admin
       3. 🔴 Jamshid (@jamshid, ID: 5554433) — Nofaol
       ```
       Inline tugmalar:
       - `[🟢 Sardor Aliyev]` -> Admin kartochkasi
       - `[➕ Yangi admin qo'shish]`
       - `[⬅️ Admin menyu]`
    3. Admin kartochkasi:
       - FIO, ID, Roli, Qo'shilgan vaqti, Kim qo'shgani.
       - Tugmalar: `[🔴 Faolsizlantirish / 🟢 Faollashtirish]`, `[🗑 Butunlay o'chirish]`, `[⬅️ Ortga]`.
    4. Yangi admin qo'shish oqimi (`AdminAddState`):
       - 1-qadam: Telegram ID so'raladi;
       - 2-qadam: ID tekshirilib, topilgan profil ma'lumotlari ko'rsatiladi;
       - 3-qadam: Rol tanlanadi (`[Admin]` yoki `[Superadmin]`);
       - 4-qadam: Tasdiqlash bosiladi.
       - Yangi adminga tabrik va yo'riqnoma xabari yuboriladi: *"Tabriklaymiz! Siz Huquq+ boti admini etib tayinlandingiz. Boshqaruv paneliga kirish uchun /admin buyrug'ini bosing."*
- **Tegishli fayllar:**
  - `src/routes/aiogram/admin.py`: `get_admin_menu_keyboard` ga shartli tugma, yangi callbacklar: `admin:admins_list`, `admin:admin_view:{id}`, `admin:admin_toggle:{id}`, `admin:admin_delete:{id}`, `admin:admin_add`.
- **DB o'zgarishi:** `hp_admins` jadvali.
- **Qiyinlik:** M.

---

### 3.5. `settings.py`, `filters.py` va `enums.py` arxitekturasini yangilash

- **`src/app/enums.py`:**
  - `AdminRole` enumi qo'shiladi:
    ```python
    class AdminRole(str, Enum):
        super_admin = "super_admin"
        admin = "admin"
    ```
- **`src/config/settings.py`:**
  - Yangi maydonlar:
    ```python
    SUPER_ADMIN_IDS: str = ""  # .env dagi asosiy superadminlar
    
    @property
    def super_admin_ids_list(self) -> list[int]:
        # SUPER_ADMIN_IDS yoki ADMIN_IDS ning birinchi ID si
        ...
    ```
  - `is_super_admin(self, user_id: int) -> bool` metodi.
- **`src/app/filters.py`:**
  - `is_admin_user(event, db_session)` yordamchi filtri:
    1. Agar `user_id in settings.super_admin_ids_list` bo'lsa -> `True`.
    2. Aks holda `db_session` (yoki kesh) orqali `AdminUser.get_by_user_id(user_id)` tekshiriladi (`is_active == True`).
- **Qiyinlik:** S.

---

## 4. Arxitektura variantlari va integratsiya tahlili

### Solishtirma tahlil jadvali

| Mezon | 1. Qabullar boshqaruvi (Tiklash/Almashtirish/Vaqt) | 2. Media cheklovi (10 ta limit + Albom) | 3. Adminlar boshqaruvi (DB + Superadmin) |
| :--- | :--- | :--- | :--- |
| **Asosiy maqsad** | Qabullarni to'liq nazorat qilish, inson omili va xatolarni tuzatish | Bot barqarorligi, spamdan himoya, guruh yuklamasini kamaytirish | Serverga kirmasdan xavfsiz admin qo'shish va huquqlarni ajratish |
| **Admin tajribasi** | CRM kartochkasidan barcha amallarni inline tugmalar bilan bajarish | Qabullarda toza, tartibli va maksimal 10 ta fayl ko'rish | Telegram orqali 1 daqiqada yangi admin tayinlash/o'chirish |
| **Fuqaro tajribasi** | Har bir o'zgarish bo'yicha aniq bildirishnomalar olish | Foydalanuvchi do'stona hisoblagich (X/10) va fayllarni tozalash | Hech qanday chalkashliksiz xavfsiz xizmat |
| **Tizim xavfsizligi** | Audit log, to'qnashuvlar tekshiruvi, Celery qayta rejalashtirish | Telegram FloodWait va DB haddan tashqari to'lishining oldi olinadi | Superadmin daxlsizligi, Break-glass kirish kafolati |
| **Qiyinlik darajasi** | **M** | **S** | **M** |

---

## 5. Umumiy ustuvorlik tartibi (Implementation Roadmap)

Tizimning xavfsizligi, barqarorligi va foydalanuvchi ehtiyojlaridan kelib chiqqan holda amalga oshirish ketma-ketligi:

1. **1-O'RIN: Fuqaro yurist qabuliga 10 ta media limitini o'rnatish (2-yo'nalish — S / M):**
   - *Sabab:* Bu botning jonli ishlab turishidagi eng katta texnik xavf (vulnerability). Agar foydalanuvchi 20-30 ta og'ir media tashlasa, guruhga ketma-ket so'rovlar yuborilib bot Telegram API tomonidan vaqtincha bloklanadi (FloodWait). Buni darhol joriy etish zarur.
   - *Ketma-ketlik:* Limit tekshiruvi → Debounced xabar yangilanishi → "Fayllarni tozalash" tugmasi.

2. **2-O'RIN: Adminlar boshqaruvi va Superadmin ajratish (3-yo'nalish — S / M):**
   - *Sabab:* Loyiha jamoasi kengayishi, adminlar almashishi serverga bog'liq bo'lmasligi kerak. Superadmin va oddiy admin chegarasi tizim xavfsizligining fundamenti hisoblanadi.
   - *Ketma-ketlik:* `AdminUser` modeli va Alembic migratsiyasi → `settings.py` va `filters.py` yangilanishi → Admin panelda `admin:admins_list` interfeysi.

3. **3-O'RIN: Qabullarni tiklash va yuristni almashtirish (1.1, 1.2, 1.5-bo'limlar — S / M):**
   - *Sabab:* Qabullar bilan ishlashda noto'g'ri bekor bo'lgan arizalarni qaytarish va kasal bo'lgan yurist o'rniga boshqasini tayinlash kundalik CRM zarurati.
   - *Ketma-ketlik:* Audit log jadvali yaratish → Bekor bo'lgan arizalarni tiklash tugmasi → Yuristni almashtirish oqimi va bildirishnomalar.

4. **4-O'RIN: Qabul vaqtini belgilash, o'zgartirish va Celery sinxronizatsiyasi (1.3, 1.4-bo'limlar — M):**
   - *Sabab:* FSM orqali sana/vaqt kiritish, yuristning boshqa qabullari bilan to'qnashuvini (conflict) tekshirish va Celery eslatmalarini reset qilish nisbatan ko'proq sinov va ehtiyotkorlik talab qiladi.
   - *Ketma-ketlik:* Vaqt kiritish FSM dialogi → To'qnashuv tekshiruvi → `reminder_sent = False` avtomatik boshqaruvi.
