# Imtiyozlar Boshqaruvi (Single Source of Truth)

Ushbu katalog loyihadagi barcha imtiyozlar, yo'riqnomalar, huquqiy asoslar va havolalarni yagona markazdan boshqarish uchun mo'ljallangan.

Butun dastur (ma'lumotlar bazasi seed skriptlari, Telegram bot, qidiruv tizimi, admin panel va testlar) faqat va faqat `imtiyozlar_boshqaruvi/imtiyozlar.json` faylidan ma'lumotlarni o'qiydi.

---

## 📁 Katalog tarkibi
- **`imtiyozlar.json`**: O'zbekiston Respublikasi Adliya vazirligi («Madad» NNT / advice.uz) tomonidan belgilangan rasmiy 112 ta imtiyozlarning to'liq ma'lumotlar bazasi.
- **`README.md`**: Imtiyozlarni tahrirlash va boshqarish bo'yicha qo'llanma.

---

## 🛠 `imtiyozlar.json` tuzilmasi va maydonlar tavsifi

Har bir imtiyoz obyekti quyidagi maydonlardan iborat:

| Maydon | Turi | Tavsif |
|---|---|---|
| `order_index` | Son (1-112) | Imtiyozning rasmiy tartib raqami (advice.uz ro'yxatiga muvofiq) |
| `category` | Matn | Imtiyoz sohasi: `tax_fee` (soliq), `labor` (mehnat), `education` (ta'lim), `health_rehab` (tibbiyot), `pension_aid` (nafaqa), `transport` (transport), `housing_communal` (uy-joy), `other` (boshqa) |
| `title_uz` / `oz` / `ru` | Matn | Imtiyoz nomi (3 tilda: Lotin, Kirill, Rus) |
| `description_uz` / `oz` / `ru` | Matn | Kimlarga berilishi va imtiyoz tafsilotlari |
| `amount_uz` / `oz` / `ru` | Matn | Imtiyoz miqdori, foizi yoki taqdim etish sharti |
| `organization_uz` / `oz` / `ru` | Matn | Mas'ul vazirlik, qo'mita yoki idora |
| `legal_basis_uz` / `oz` / `ru` | Matn | Normativ-huquqiy asosi (Qonun, Farmon, Qaror) |
| `lex_url` | Havola (URL) | Lex.uz dagi to'g'ridan-to'g'ri modda/band havolasi (masalan: `https://lex.uz/docs/-6257288#-6263028`) |
| `mygov_url` | Havola (URL) | Onlayn ariza topshirish portali (my.gov.uz, yoshlardaftari.uz va h.k.) |
| `guide_uz` / `oz` / `ru` | Matn (HTML) | «Qanday ariza topshiriladi» 5-blokli standart yo'riqnomasi |
| `for_first_group` | Boolean | I guruh nogironligi bo'lgan shaxslar uchun mosligi (`true` / `false`) |
| `for_second_group` | Boolean | II guruh nogironligi bo'lgan shaxslar uchun mosligi (`true` / `false`) |
| `for_third_group` | Boolean | III guruh nogironligi bo'lgan shaxslar uchun mosligi (`true` / `false`) |
| `for_child` | Boolean | 18 yoshgacha nogironligi bo'lgan bolalar uchun mosligi |
| `for_parent` | Boolean | Nogironligi bo'lgan bolani parvarishlovchi ota-onalar uchun mosligi |
| `is_for_organization` | Boolean | Nogironlar jamoat birlashmalari yoki korxonalari uchun mosligi |
| `min_age` / `max_age` | Son / null | Yosh chegaralari (masalan, yoshlar uchun 14-30 yosh) |
| `gender` | Matn / null | Jins cheklovi (`male`, `female` yoki `null`) |
| `disability_state` | Matn / null | Maxsus nuqson turi (`vision`, `hearing`, `mental` yoki `null`) |

---

## 📝 5-blokli Yo'riqnoma standarti
`guide_uz`, `guide_oz`, `guide_ru` maydonlarida 5 ta standart semantik blok qo'llaniladi:
1. 🏢 **Kimga murojaat qilinadi?**
2. 📄 **Qanday hujjatlar talab etiladi?**
3. 🌐 **Murojaat usuli**
4. ⏱ **Ko‘rib chiqish muddati**
5. ⚖️ **Huquqiy asos**

Bloklar orasi vizual qulaylik va xabarlarni to'g'ri formatlash uchun `<br/><br/>` bilan ajratiladi.

---

## 🔄 Tahrirlash va ma'lumotlar bazasini yangilash

`imtiyozlar.json` fayliga o'zgartirish kiritilgandan so'ng, o'zgarishlarni ma'lumotlar bazasiga o'tkazish uchun terminalda quyidagi buyruq ishga tushiriladi:

```bash
python3 -m src.database.seed_benefits
```

Ushbu buyruq:
1. `imtiyozlar_boshqaruvi/imtiyozlar.json` faylini o'qiydi.
2. Ma'lumotlar bazasidagi 112 ta imtiyoz yozuvlarini yangilaydi va sinxronlashtiradi.
3. Yangi kiritilgan havolalar va matnlar darhol botda aks etadi.
