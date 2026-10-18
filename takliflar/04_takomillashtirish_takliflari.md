# Huquq+ boti: takomillashtirish va xatolarni tuzatish bo'yicha takliflar

> 2026-10-18 holatiga. Bugungi ishlar davomida kod, loglar va sinovlar asosida tuzildi.
> Har bir taklif: **nima**, **nega**, **qiyinlik** (S — kichik, M — o'rta, L — katta).

## 1. Darhol bajarilishi kerak (ish to'xtab qolishi mumkin)

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 1.1 | OpenRouter hisobini to'ldirish va **qoldiq kamayganda adminlarga ogohlantirish** (RAG tomonida `HTTP 402` ni ushlab, kuniga 1 marta xabar) | 2026-10-18 da balans tugadi: javobni tekshirish va avtomatik javob ishlamay qoldi, faqat log orqali bilindi | S |
| 1.2 | `.env` o'zgarganda konteynerni **qayta yaratish** (`podman compose up -d`), `restart` emas — `deploy.sh` ga qo'shish | `restart` muhit o'zgaruvchilarini yangilamaydi: guruh ID o'zgargach bot eski ID bilan ishlab turdi | S |
| 1.3 | Bot ishga tushganda **sozlamalarni tekshirish**: har bir guruh ID superguruh (`-100…`) ekanini va botning shu guruhlarda admin (xabar o'chirish huquqi) ekanini tekshirib, xato bo'lsa adminlarga yozish | Oddiy guruhda xabar havolasi bo'lmaydi; guruh ko'chsa murojaatlar tushmay qoladi; bot admin bo'lmasa ruxsatsiz javoblarni o'chira olmaydi | M |
| 1.4 | Lokal ishga tushirishda ham **migratsiya avtomatik** bo'lsin (`docker-compose.local-ai.yaml` dagi `command` `prestart.sh` ni chetlab o'tadi) | Har yangi ustunda bot yiqilish xavfi; hozir qo'lda `alembic upgrade head` qilinyapti | S |
| 1.5 | Guruh ko'chishidan oldingi **9 ta eski murojaatni yopish** (admin paneldan yoki bir martalik skript) | Ularning kartalariga reply qilib javob berib bo'lmaydi, volontyor ro'yxatida osilib turibdi | S |
| 1.6 | MariaDB **kunlik zaxira nusxasi** (cron + `mysqldump`, 7 kun saqlash) | Hozir zaxira yo'q; ma'lumot yo'qolsa tiklab bo'lmaydi | S |

## 2. Avtomatik javob va javobni tekshirish

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 2.1 | Balans to'ldirilgach **oltin to'plamni qayta o'lchash** (`scripts/review_eval.py`, 26 ta namuna) va chegaralarni sozlash | Tekshiruv kuchaytirildi (har qanday jiddiy kamchilik — rad), yangi qoidaning xato tasdiq/noto'g'ri rad ulushi hali o'lchanmagan | S |
| 2.2 | Oltin to'plamni **50–60 taga** yetkazish: ruscha, uzun, ko'p qismli savollar; haqiqiy volontyor javoblaridan admin baholagan 20–30 ta | Kichik to'plam chegaralarni ishonchli sozlashga yetmaydi | M |
| 2.3 | **Kunlik limit**: bitta fuqaroga kuniga ko'pi bilan N ta avtomatik javob (masalan 5), umumiy kunlik byudjet chegarasi | Har avtomatik javob 2 ta LLM chaqiruvi (javob + tekshiruv) — xarajat nazorati | S |
| 2.4 | Avtomatik javobga **baho tugmalari** (👍/👎) va hisobotda "huquqshunosga o'tish ulushi" | Qaysi sohada avtomatik javob yaxshi ishlashini o'lchash; yomon sohalarda o'chirish | M |
| 2.5 | Sohalar bo'yicha **avtomatik javobni yoqish/o'chirish** (admin paneldan) | Masalan, sud ishlari kabi murakkab sohalarda faqat huquqshunos javob bersin | M |
| 2.6 | Tekshiruv natijalaridan **volontyor sifat profili**: xato turlari bo'yicha statistika (noto'g'ri norma, asossiz da'vo, to'liq emas) `/myresult` va admin hisobotida | `review_json` da ma'lumot yig'ilyapti, lekin hali ishlatilmayapti — o'qitish uchun eng foydali manba | M |
| 2.7 | Rad etilgan javoblar tarixini saqlash (har urinish alohida) | Hozir faqat oxirgi tekshiruv saqlanadi; volontyorning o'sishini ko'rib bo'lmaydi | M |

## 3. Volontyor va admin ish jarayoni

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 3.1 | Admin uchun **"Biriktirishlar paneli"**: kimda nechta ochiq murojaat, eng uzog'i qancha kutyapti, bir tugmada qayta biriktirish | Hozir bu ma'lumot faqat guruhdagi kartalar orasida tarqoq | M |
| 3.2 | Volontyor **soha a'zoligi**ni volontyorning o'zi so'rashi, admin tasdiqlashi | Hozir hammasini bitta koordinator qo'lda kiritadi | M |
| 3.3 | Ruxsatsiz guruh javobi o'chirilganda **adminlarga haftalik xulosa** (kim necha marta) | Qoidani tushunmagan volontyorlarni aniqlash | S |
| 3.4 | Eslatmalar uchun **dam olish kunlari** sozlamasi | Hozir faqat tungi sukunat bor | S |

## 4. Fuqaro tajribasi

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 4.1 | Barcha matnlarni **bitta tarjima faylida** jamlash: kodda hali ham uch tilda qattiq yozilgan matnlar bor (qabul kartasi, ogohlantirishlar, admin xabarlari) | Bir tilda tuzatilganda boshqasi eskicha qoladi; nomuvofiqlik | M |
| 4.2 | Murojaat holatini fuqaro **o'zi kuzata olishi** ("Murojaatlarim" da: kimga biriktirilgan, qachon) | Fuqarolar "javob qachon" deb qayta yozadi | S |
| 4.3 | Qabul vaqti yaqinlashganda fuqaroga **tasdiqlash tugmasi** ("kela olaman / kela olmayman") | Yuristning bo'sh qolgan vaqtini kamaytirish | M |

## 5. Maxfiylik va xavfsizlik

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 5.1 | Guruh kartasida **telefon raqamini yashirish** (faqat biriktirilgan volontyor/admin shaxsiyda ko'radi) | 77 kishilik guruhda har bir fuqaroning telefoni va nogironlik ma'lumoti ochiq turibdi | M |
| 5.2 | RAG kalitini **faqat kerakli huquqlar** bilan cheklash va yiliga bir almashtirish | Bot kaliti `ask`, `feedback`, `review` ga ega — boshqasi kerak emas | S |
| 5.3 | `.env` dagi sirlarni (bot tokeni, DB paroli) ombordan tashqarida saqlash, zaxira nusxalarda shifrlash | Hozir loyiha papkasida `.zip` nusxalar bor | S |

## 6. Kod sifati va barqarorlik

| # | Taklif | Nega | Qiyinlik |
|---|---|---|---|
| 6.1 | `admin.py` (≈4000 qator) ni bo'limlarga ajratish: adminlar, kanallar, imtiyozlar, broadcast, CRM, hisobotlar | Katta faylda xato topish va o'zgartirish qiyin | L |
| 6.2 | `scripts/simulate_update.py` asosida **oqim testlari**: murojaat → biriktirish → tekshiruv → yuborish, qabul → tasdiq | Bugungi xatolarning aksariyati (jim qolgan tugmalar, guruh ID) shunday testlarda darhol ko'rinardi | M |
| 6.3 | Xatolarni markaziy kuzatish (Sentry yoki kunlik xato xulosasi adminlarga) | Xatolar faqat konteyner logida qolib ketyapti | S |
| 6.4 | Kodga commit qilish odatini tiklash: hozir yuzlab o'zgarish commit qilinmagan | Xato chiqsa qaysi o'zgarish sabab bo'lganini topib bo'lmaydi; qaytarish qiyin | S |
