# Huquq+ AI yordamchini ichki yordamchiga aylantirish va volontyor nazorati (B)

> Faqat tahlil va taklif. Kod o'zgartirilmagan. Barcha xulosalar repo'dagi mavjud fayllarni o'qishga tayanadi.

## 0. Mavjud holat (tayanch nuqtalar)

- Fuqaro oqimi: `src/routes/aiogram/inquiry.py` — `start_inquiry` → `select_section` → `send_custom_question`. Savol guruhga yuboriladi, `Inquiry` yoziladi (`group_question_id`, `group_id`, `bot_id`), matnli savollarda `spawn_lawyer_ai_draft` chaqiriladi.
- Guruhda javob: `src/routes/aiogram/group_router.py` — `handle_response` (`is_group_message` + `reply_to_my_message`, `/` bilan boshlanmaydigan). Hozir volontyor reply qilsa, `send_answer_to_citizen` orqali javob **darhol fuqaroga yuboriladi**, keyin `Inquiry.status=replied`, `responder_id`, `replied_at` yoziladi, reyting so'raladi. **Hech qanday AI tekshiruv, claim majburiyligi yo'q** — faqat `is_admin_user / is_lawyer / is_volunteer` tekshiruvi bor.
- AI fuqaro panelida: `src/app/keyboards.py` — `get_main_menu` ichida `rag_client.is_enabled()` bo'lsa `menu_ai` tugmasi chiqadi; `src/routes/aiogram/ai_assistant.py` — `enter_ai_assistant_mode`, `AiChatState.chatting`, `process_ai_query` → `rag_client.ask`, `ai_to_lawyer` orqali savol yuristga o'tadi.
- AI guruhda: `ai_assistant.send_lawyer_ai_draft` — murojaatdan keyin guruhga "AI tavsiyasi (loyiha, fuqaroga yuborilmagan)" sarlavhali qoralama yuboradi. `settings.AI_LAWYER_DRAFTS` va `rag_client.is_enabled()` bilan o'chadi. Redis'da `inquiry_cont:{group_id}:{msg_id}` bog'lanadi.
- RAG: `src/app/rag_client.py` — `RagClient.ask(question, user_id, conversation_id, language)`, `feedback(answer_id, rating)`, `delete_conversation`. Sozlamalar: `src/config/settings.py` — `AI_ASSISTANT_ENABLED`, `AI_LAWYER_DRAFTS`, `RAG_API_URL/KEY/TIMEOUT`.
- Analitika: `src/app/volunteer_analytics.py` — `calculate_volunteer_stats` (KPI = javob×10 + 5★×15 + 4★×10 − 1-2★×10 + tez<1s×5; faqat `responder_id`, `rating`, `created_at/replied_at` ga tayanadi, javob **sifati** o'lchanmaydi). `src/tasks/volunteer_leaderboard.py` — haftalik Top-5 guruhga, shaxsiy dayjest volontyorga. `src/routes/aiogram/volunteer_result.py` — `/myresult`. `src/routes/aiogram/admin.py` — admin menyu (`admin:staff_stats` va boshqalar).
- Modellar: `src/models/inquiry.py` (`Inquiry`: `status`, `answer`, `responder_id`, `replied_at`, `rating`, `feedback`), `src/models/volunteer.py` (`Volunteer`: `user_id`, `is_active`, KPI yo'q).

## 1. Taklif: AI ni fuqaro panelidan olib tashlash, faqat jamoa uchun qoldirish

- **Nima:** `menu_ai` tugmasi va `/ai` kirishi fuqarolardan yopiladi. AI faqat volontyor/admin uchun ichki yordamchi bo'lib qoladi (guruhdagi qoralama + tekshiruv).
- **Qanday ishlaydi:**
  - Fuqaro: asosiy menyuda "AI yordamchi" tugmasini ko'rmaydi; `AiChatState.chatting` ga kira olmaydi; eski xabarlar bo'lsa "mavjud emas, Savol yuborish'dan foydalaning" javobi chiqadi.
  - Volontyor: guruhda AI qoralamasini ko'rishda davom etadi; tekshiruv natijasini guruhda yoki lichkada oladi.
  - Admin: AI ni to'liq o'chirish/qayta yoqish kalitiga ega bo'ladi.
- **Tegishli fayllar:** `src/app/keyboards.py` (`get_main_menu`), `src/routes/aiogram/ai_assistant.py` (`enter_ai_assistant_mode`, `ai_chat_text_handler`, `process_ai_query`), `src/routes/aiogram/private_router.py` (router ulanishi), `src/config/settings.py` (`AI_ASSISTANT_ENABLED`), `src/app/translations.py` (`menu_ai`, `ai_intro`).
- **DB o'zgarishi:** Yo'q (faqat sozlama/kod). Ixtiyoriy: `settings` ga `AI_CITIZEN_ENABLED=False` alohida bayroq qo'shish — jadval kerak emas.
- **Xavf/kamchilik:** AI ni yoqtirgan fuqarolar norozi bo'lishi mumkin; `ai_to_lawyer` orqali kelgan savollar oqimi to'xtaydi — "Savol yuborish" yuklamasi oshadi. `get_main_menu` da `rag_client.is_enabled()` sharti borligi uchun uni ehtiyotlik bilan ajratish kerak, aks holda ichki AI ham o'chib qoladi.
- **Qiyinlik:** S.

## 2. Taklif: Javob darvozasi — "tasdiqsiz javob fuqaroga bormaydi" (asosiy talab, a)

- **Nima:** Volontyorning guruhdagi reply'i avval `qoralama` sifatida ushlanadi. AI rubrika bo'yicha tekshiradi (norma aniqligi, havola, mantiqiy asos, RAG tekshiruvi). Tasdiqlansa — fuqaroga yuboriladi; aks holda — kamchilik sharhi bilan volontyorga qaytariladi. Adminlar bu cheklovdan ozod.
- **Qanday ishlaydi:**
  - Volontyor: reply qiladi → bot "Qabul qilindi, AI tekshirmoqda ⏳" deb javob beradi; tasdiqda "Fuqaroga yuborildi ✅", rad etilganda "Qaytarildi: aniq sabab + nima tuzatish kerak" sharhini oladi; tuzatib yana reply qiladi.
  - Fuqaro: faqat tasdiqlangan javobni oladi (+ mavjud reyting so'rovi o'zgarishsiz). Kutilayotgan paytda xohishga ko'ra "javobingiz tekshiruvda" holatini ko'radi.
  - Admin: tasdiqsiz ham yubora oladi (bypass); AI ishonchsiz bo'lsa navbatga tushgan qoralamani ko'rib, "tasdiqlash / rad etish / tahrirlab yuborish" (override) qiladi.
- **Tegishli fayllar:** `src/routes/aiogram/group_router.py` (`handle_response`, `send_answer_to_citizen` — yuborish nuqtasi shu yerda to'siladi; `is_coordinator_or_lawyer_or_admin` — admin istisnosi uchun), `src/app/rag_client.py` (`ask` — tekshiruv chaqiruvi), `src/routes/aiogram/ai_assistant.py` (`send_lawyer_ai_draft` — qoralama formati bilan birlashtirish), `src/models/inquiry.py` (`Inquiry` holatlari).
- **DB o'zgarishi:** `inquiries` jadvaliga ustunlar: `answer_status` (`draft/pending_approved/approved/rejected/escalated/sent`), `draft_text` (yoki `answer` qoralama sifatida ishlatilib, yuborilganda `sent_at` qo'yiladi), `assigned_volunteer_id` (claim bilan bog'lanish, 3-bo'lim), `ai_review_json` (ballar, topilgan xatolar, RAG iqtiboslari), `ai_score`, `reviewed_at`, `reviewed_by` (`ai`/`admin_id`). Yangi jadval varianti: `inquiry_reviews` (`id, inquiry_id, draft_hash, verdict, scores_json, comment, reviewer, created_at`) — tarix saqlash uchun tavsiya etiladi. Migatsiya: `src/database/alembic/versions/` ga yangi versiya.
- **Xavf/kamchilik:** Eng katta xavf — kechikish: hozir `handle_response` sinxron yuboradi; AI/RAG sekin yoki o'lik bo'lsa javoblar tiqilib qoladi → taymaut + escalation shart. Ikkinchi xavf — AI noto'g'ri "tasdiqlash" (yolg'on musbat): rubrika qat'iy bo'lmasa sifatsiz javob o'tib ketadi. Medianing ovoz/video hujjat turlari matnli rubrikaga to'liq sig'maydi — transkripsiyasiz tekshirib bo'lmaydi.
- **Qiyinlik:** M (oddiy ketma-ket gate) / L (RAG iqtibosli qattiq rubrika + escalation bilan).

## 3. Taklif: AI tekshiruv rubrikasi va eskalatsiya qoidalari (a-davomi)

- **Nima:** Tekshiruv 4 o'lchamda ballanadi, har biri uchun "o'tish chegarasi" belgilanadi: (1) norma aniqligi — modda/band raqami va mazmuni RAG manbasiga mosmi; (2) havola — Lex.uz / Huquq+ maqolasi / hujjat havolasi mavjud va ochiqmi; (3) mantiqiy asos — yechim savol faktiga bog'langanmi, "umimiy gap" emasmi; (4) RAG mosligi — da'volar RAG iqtiboslari bilan tasdiqlanganmi. AI ishonchsiz bo'lsa — avtomatik admanga (eskalatsiya), admin override qiladi.
- **Qanday ishlaydi:**
  - Volontyor: rad javobida faqat "yomon" emas, balki "2-modda noto'g'ri: to'g'risi X; Lex havolasi ochilmaydi; asosda Y fakti e'tiborga olinmagan" kabi punktli sharh oladi.
  - Fuqaro: hech narsa ko'rmaydi (faqat yakuniy tasdiqlangan javob).
  - Admin: eskalatsiya navbatida AI sharhi + ishonch darajasi + RAG iqtiboslarini ko'radi; bir tugma bilan tasdiqlaydi/rad etadi/tahrirlab yuboradi; uning qarori AI bahosidan ustun yoziladi.
- **Tegishli fayllar:** `src/app/rag_client.py` (`ask` — tekshiruv so'rovi; javob sxemasiga `verdict/scores/confidence/citations` maydonlari kerak bo'ladi), `src/routes/aiogram/group_router.py` (`handle_response` — verdict bo'yicha tarmoqlanish), `src/routes/aiogram/admin.py` (eskalatsiya navbati tugmalari).
- **DB o'zgarishi:** `inquiry_reviews` jadvali: `scores_json` (`{norma: 0-5, havola: 0-5, mantiq: 0-5, rag: 0-5}`), `confidence` (0-1), `citations_json`, `error_types` (`[notori_norma, eskirgan_norma, yolgan_havola, asossiz_xulosa, ...]`), `verdict`, `reviewer`. Eskalatsiya chegarasi kodda emas, sozlamada saqlanadi (masalan `AI_APPROVE_THRESHOLD`, `AI_ESCALATE_BELOW`).
- **Xavf/kamchilik:** RAG bazasi eskirgan bo'lsa AI "to'g'ri" javobni ham rad etadi (RAG — yagona haqiqat manbai bo'lib qoladi). Qat'iy rubrika dastlab ko'p rad etishga olib keladi → volontyorlar tushkunlikka tushadi; chegaralarni yumshoq boshlash kerak.
- **Qiyinlik:** M.

## 4. Taklif: Claim/assign — murojaat kimniki ekanini biriktirish (talab b)

- **Nima:** Har bir murojaat bitta mas'ul volontyorga biriktiriladi. Faqat biriktirilgan volontyor (va admin) javobi AI tekshiruviga kiradi va fuqaroga boradi; begona volontyor reply qilsa "bu murojaat X da, /claim orqali oling" deb rad etiladi.
- **Qanday ishlaydi:**
  - Volontyor: guruh kartochkasidagi "✋ Men javob beraman" tugmasini bosadi (claim) → karta "Mas'ul: Ism (15:20 gacha)" ga yangilanadi; ulgurmasa taymautdan keyin murojaat bo'shaydi va guruhga "qayta ochiq" xabari chiqadi; `/release`, `/extend` buyruqlari.
  - Fuqaro: o'zgarish sezmaydi (faqat javob biroz kechikishi mumkin).
  - Admin: istalgan murojaatni istalgan volontyorga majburiy tayinlaydi (`/assign`), taymautni uzaytiradi/qisqartiradi, tortishuvda qayta tayinlaydi; guruhda barcha holatlarni ko'radi.
- **Tegishli fayllar:** `src/routes/aiogram/group_router.py` (`handle_response` — claim tekshiruvi shu yerga qo'shiladi; `claim_appointment_callback` — appointment uchun mavjud namuna, inquiry uchun o'xshash tugma kerak; `edit_message` — karta holatini yangilash), `src/routes/aiogram/inquiry.py` (`send_custom_question` — karta yaratilganda claim tugmasini qo'shish), `src/database/redisdb.py` (taymaut/qulf uchun Redis kalitlari), `src/tasks/close_inquiry.py` (taymaut vazifasi uchun namuna).
- **DB o'zgarishi:** `inquiries` ga: `assigned_volunteer_id` (BigInteger, nullable, index), `assigned_at`, `claim_expires_at`, `assign_source` (`self_claim/admin/auto`). Ixtiyoriy `inquiry_claims` tarix jadvali (`inquiry_id, volunteer_id, action, created_at`). Redis'da `inquiry_claim:{id}` qalti (qulf), lekin haqiqat DB da bo'lishi shart.
- **Xavf/kamchilik:** Taymaut noto'g'ri tanlansa: qisqa bo'lsa volontyor ulgurmaydi, uzun bo'lsa murojaat kutib qoladi. Ikkita volontyor bir vaqtda claim bosishi (poyga) — DB unique/optimistik qulf kerak. Claim majburiyligi shoshilinch savollarda sekinlashtiradi → admin bypass va "shoshilinch" belgisi shart.
- **Qiyinlik:** M.

## 5. Arxitektura variantlari (talab c) — kamida 3 ta, solishtirma

### Variant 1. "Ketma-ket darvoza" (eng oddiy, tavsiya etiladi)

- **Nima:** `handle_response` ichida tartib: claim tekshiruvi → qoralamani saqlash → RAG tekshiruvi → verdict → yuborish/rad/eskalatsiya. Hammasi bitta oqimda, alohida navbat tizimisiz.
- **Fuqaro/volontyor/admin:** 2-bo'limdagi kabi; admin bypass to'g'ridan-to'g'ri `send_answer_to_citizen` ga o'tadi.
- **Tegishli fayllar:** deyarli faqat `group_router.py` + `rag_client.py` + 1 migatsiya.
- **DB:** 2-bo'limdagi ustunlar yetadi.
- **Xavf:** RAG sekin bo'lsa handler bloklanadi (taymaut 60 s — `RAG_TIMEOUT_SECONDS`); uzoq tekshiruvda Telegram qayta urinishlar bo'lishi mumkin. Fon vazifaga (`spawn_lawyer_ai_draft` kabi `asyncio.Task`) chiqarish shart.
- **Qiyinlik:** M.

### Variant 2. "Moderatsiya navbati" (ajratilgan tekshiruv kanali)

- **Nima:** Qoralamalar alohida yopiq "Tekshiruv" guruhiga/kanaliga tushadi; AI sharhi o'sha yerda chiqadi; admin/mas'ul volontyor tugma bilan tasdiqlaydi; tasdiq callback'i fuqaroga yuboradi.
- **Fuqaro/volontyor/admin:** Volontyor o'z qoralamasi holatini alohida kanalda kuzatadi (asosiy guruh toza qoladi); admin uchun bitta markaziy navbat paydo bo'ladi — nazorat eng oson.
- **Tegishli fayllar:** `group_router.py` (qoralama yo'naltirish), `admin.py` (navbat tugmalari), yangi `review_router` yoki admin ichida callback'lar, `settings` ga `REVIEW_GROUP_ID`.
- **DB:** Variant 1 + `review_message_id` (navbat xabari ID si).
- **Xavf:** Ikki guruh sinxroni (asosiy karta ↔ navbat kartasi) murakkablashadi; xabar ID lar adashsa noto'g'ri murojaat yuborilishi mumkin. Qo'shimcha guruh boshqaruvi kerak.
- **Qiyinlik:** L.

### Variant 3. "Ball yig'uvchi ishonch" (bosqichli yumshoq start)

- **Nima:** Dastlab AI faqat baholaydi, to'smaydi: barcha javoblar hozirgidek yuboriladi, lekin AI ball qo'yadi. Volontyor ishonch bali past bo'lsa keyingi javoblari avtomatik "qattiq darvoza"ga o'tadi; bali yuqori bo'lsa to'g'ridan-to'g'ri yuboradi (admin kabi, lekin avtomatik).
- **Fuqaro/volontyor/admin:** Fuqaro hech qanday kechikish sezmaydi (boshlang'ich bosqichda); volontyor o'z ishonch balini `/myresult` da ko'radi; admin chegaralarni sozlaydi.
- **Tegishli fayllar:** `volunteer_analytics.py`, `volunteer_result.py`, `group_router.py` (shartli bypass), `admin.py` (chegara sozlamalari).
- **DB:** `volunteers` ga `trust_score`, `trust_level` (`open/gated/bypass`); `inquiry_reviews` tarixi shart.
- **Xavf:** Boshlang'ich davrda sifatsiz javoblar fuqaroga borishda davom etadi (nazorat kechikadi). "Yuqori ball = nazoratsiz" rejimi suiiste'mol qilinishi mumkin (bitta yaxshi volontyor keyin sustlashsa).
- **Qiyinlik:** M.

### Solishtirma jadval

| Mezon | V1 Ketma-ket darvoza | V2 Moderatsiya navbati | V3 Ishonch bali |
|---|---|---|---|
| Nazorat kuchi | Yuqori (hamma to'siladi) | Eng yuqori (markaziy navbat) | Past → o'rtacha (bosqichli) |
| Volontyor uchun osonlik | O'rtacha (kutish bor) | O'rtacha (2 kanal) | Eng oson (o'zgarishsiz start) |
| Admin uchun osonlik | O'rtacha | Eng oson | Oson |
| Kechikish riski | O'rtacha | Yuqori (2 xabar aylanishi) | Yo'q (startda) |
| Kod murakkabligi | M | L | M |
| Tavsiya | **Boshlash uchun** | Keyingi bosqich | V1 bilan parallel |

**Tavsiya:** V1 dan boshlash (talab (a) ni to'liq yopadi, eng kam yangi infratuzilma). V2 ni yuklama oshganda (kuniga o'nlab tekshiruv) qo'shish. V3 ning ishonch bali g'oyasini V1 ustiga "imtiyoz" sifatida qo'shish (7-bo'lim), mustaqil rejim sifatida emas.

## 6. Taklif: Volontyor salohiyat nazorati — AI baholar, profil, dashboard (talab d)

- **Nima:** Har bir AI tekshiruvi volontyor profiliga yoziladi: o'rtacha ball, norma aniqligi, takrorlanuvchi xato turlari, tendentsiya (o'sish/pasayish). Admin dashboard'da ko'radi, volontyor `/myresult` da o'zini ko'radi.
- **Qanday ishlaydi:**
  - Volontyor: `/myresult` da hozirgi KPI yonida "AI sifati: 4.2/5, kuchli: havolalar; o'stirish kerak: modda aniqligi; oxirgi 3 xato: ..." va "tavsiya etilgan o'quv: ..." ni ko'radi; haftalik dayjestga AI xulosasi qo'shiladi.
  - Fuqaro: bevosita ko'rmaydi; bilvosita — sifatsiz javoblar kamayadi.
  - Admin: `/admin` → xodimlar statistikasi yonida "sifat" ustuni, xato turlari kesimi, pasayayotgan volontyorlar ro'yxati, o'qitish tavsiyalari; haftalik/oylik hisobotga AI sifati bo'limi qo'shiladi.
- **Tegishli fayllar:** `src/app/volunteer_analytics.py` (`calculate_volunteer_stats` — hozir faqat son/tezlik/reyting; `ai_avg`, `error_types`, `trend` qo'shiladi), `src/tasks/volunteer_leaderboard.py` (dayjest va leaderboard matniga sifat qo'shish), `src/routes/aiogram/volunteer_result.py` (`get_volunteer_result_view`, `get_volunteer_feedbacks_page`), `src/routes/aiogram/admin.py` (`admin:staff_stats`), `src/app/generate_staff_report.py` (hisobotga sifat bo'limi).
- **DB o'zgarishi:** `volunteers` ga agregatlar: `ai_avg_score`, `reviews_count`, `last_error_types_json`, `trend` — yoki har safar `inquiry_reviews` dan hisoblash (kichik masshtabda join yetadi, katta masshtabda agregat ustunlar tezroq). Tavsiya: tarix `inquiry_reviews` da, tez ko'rsatish uchun `volunteers` da keshlangan agregat.
- **Xavf/kamchilik:** AI bahosi "xolis hakam" emas — baholash xatosi reytingga kirsa adolatsizlik bo'ladi (quyidagi 7-bo'lim). Hozirgi KPI formulasi sifatni umuman hisobga olmaydi, uni o'zgartirish eski reytinglarni siljitadi — o'tish davri e'lon qilinishi kerak.
- **Qiyinlik:** M.

## 7. Taklif: Adolatlilik va maxfiylik himoyasi (talab d-davomi)

- **Nima:** AI baholar inson ustidan yakuniy hukm bo'lmasligi uchun: (1) baho faqat tavsiya, jazolash (faolsizlantirish) faqat admin qarori bilan; (2) baholashda shaxsiy ma'lumotlar RAG ga ketmasligi; (3) apellyatsiya tugmasi.
- **Qanday ishlaydi:**
  - Volontyor: past bahoga "E'tiroz bildirish" bosadi → admin qayta ko'radi; baholash mezonlari ochiq (`/myresult` da rubrika ko'rinadi).
  - Admin: avtomatik faolsizlantirish yo'q; faqat ketma-ket past baholarda ogohlantirish/o'qitish rejasi.
  - Fuqaro: shaxsiy ma'lumoti AI tekshiruviga yuborilayotganda `create_user_info` dagi telefon/ID kabi maydonlar kesiladi (anonimlashtirish).
- **Tegishli fayllar:** `src/app/enums.py` (`create_user_info`), `src/app/rag_client.py` (so'rov payloadi), `src/models/volunteer.py` (`is_active` — uni AI emas, faqat admin o'zgartirishi qoidasi), `src/routes/aiogram/admin.py` (apellyatsiya ko'rib chiqish).
- **DB o'zgarishi:** `inquiry_reviews` ga `appeal_status` (`none/filed/upheld/overturned`), `appealed_at`.
- **Xavf/kamchilik:** Anonimlashtirish juda agressiv bo'lsa AI kontekstni yo'qotadi (masalan, imtiyoz huquqi shaxs toifasiga bog'liq). Muvozanat: faqat tekshiruv uchun zarur faktlar yuboriladi.
- **Qiyinlik:** S.

## 8. Ustuvorlik tartibi

1. **1-bo'lim** (AI ni paneldan olib tashlash) — S, mustaqil, darhol. Ichki AI (`AI_LAWYER_DRAFTS`) o'chmasligiga e'tibor berish shart.
2. **4-bo'lim** (claim/assign) — M. 2-bo'lim darvozasi claim'siz ma'nosiz ("kim javob berdi" aniq bo'lmasa tekshiruvni kimga yozish noma'lum). Birinchi navbatda claim, keyin darvoza.
3. **2 + 3-bo'lim** (darvoza + rubrika/eskalatsiya, V1) — asosiy qiymat. Yumshoq chegaralardan boshlash (dastlab ko'p eskalatsiya, kam avtomatik rad).
4. **6-bo'lim** (sifat analitikasi) — darvoza ishlab, `inquiry_reviews` to'lgandan keyin mazmunli bo'ladi.
5. **7-bo'lim** (adolat/maxfiylik) — 2-3-bo'limlar bilan bir vaqtda loyihalash, kechiktirmaslik.
6. **V2 navbat kanali** — yuklama asosida, keyingi bosqich.

