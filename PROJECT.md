# Project: HuquqPlus Imtiyozlar & Yo'riqnomalar Tizimi

## Architecture
HuquqPlus is a Telegram bot ecosystem for legal rights and benefits of persons with disabilities in Uzbekistan.
- **Backend / Bot Framework**: Python 3.10+, Aiogram v3.10.0, SQLModel (SQLAlchemy 2.0 + Pydantic v2), MariaDB (MySQL), Redis (FSM & caching), Sulguk HTML parser.
- **Data Layer**:
  - `tg_bot_benefits`: Core benefits table with multilingual fields (`title`, `description`, `amount`, `organization`, `legal_basis`), category, disability group flags (`for_first_group`, `for_second_group`, `for_third_group`, `for_child`, `for_parent`), age/gender constraints, guide fields, and URLs.
  - `tg_bot_inquiries`: Citizen inquiries table with `benefit_id` link, user context, status, and responses.
  - `imtiyozlar_boshqaruvi/imtiyozlar.json`: Authoritative Single Source of Truth containing all 112 official benefits (Advice.uz / document 3125).
  - `imtiyozlar jadvali/Ro'yxat Imtiyozlar NBSH.docx`: Reference legal matrix source.
- **Presentation Layer**:
  - `src/routes/aiogram/benefits.py`: Catalog browsing, category pagination, 5-block benefit detail view, keyword search, inquiry trigger.
  - `src/routes/aiogram/group_router.py`: Lawyer response flow preserving benefit ID and title context.

## Feature Inventory
| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| F-SYS-01 | Fix 10 Orphan Benefits | Set correct disability group flags for IDs 54, 55, 56, 66, 79, 103, 104, 108, 109, 115, 130 | M1 | R3 | DONE |
| F-SYS-02 | Remove Unjustified max_age=18 | Remove blanket 18-year restriction on adult benefits (wheelchairs ID 34, 2% quota ID 42, etc.) | M1 | R3 | DONE |
| F-SYS-03 | Clean Legal String Duplications | Deduplicate triple prefixes ("Prezident Qarori", "Qonun") in legal bases across all benefits | M1 | R3 | DONE |
| F-SYS-04 | Database Schema Migration | Add 5-block guide fields & URLs to `Benefit` and add `benefit_id` FK to `Inquiry` (`e2f3a4b5c6d7`) | M1 | R1, R4 | DONE |
| F-PKG-01 | 1-to'plam: Tibbiyot va reabilitatsiya (15) | 5-block guides for wheelchairs, prosthetics, vouchers (VMQ-253), meds, sanatorium (IDs 30, 34, 37, 73, 74, 75, 76, 80, 81, 111, 112, 113, 114, 128, 134) | M2 | R1, R2 | DONE |
| F-PKG-02 | 2-to'plam: Nafaqa va moddiy yordam (14) | 5-block guides for pensions, allowances, notebook aid, caregiver aid (IDs 39, 40, 52, 53, 54, 57, 58, 59, 60, 61, 62, 63, 64, 65) | M2 | R1, R2 | DONE |
| F-PKG-03 | 3-to'plam: Ta'lim va yoshlar (29) | 5-block guides for 2% university quota, kindergartens, stipends, IT grants, exam fee waivers (IDs 31, 32, 33, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 55, 56, 77, 78, 79, 87, 88, 89, 90, 103, 104, 105, 106, 107, 108, 109, 115) | M2 | R1, R2 | DONE |
| F-PKG-04 | 4-to'plam: Mehnat va bandlik (17) | 5-block guides for shortened work week, leaves, 3% hiring quota, workplace adaptations (IDs 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 35, 71, 72) | M2 | R1, R2 | DONE |
| F-PKG-05 | 5-to'plam: Uy-joy va kommunal (9) | 5-block guides for utility compensations, housing subsidies, land allotments (IDs 38, 66, 67, 68, 69, 70, 82, 86, 91) | M2 | R1, R2 | DONE |
| F-PKG-06 | 6-to'plam: Transport va yo'l haqi (13) | 5-block guides for free public transit, train/air discounts, priority ticketing, wheelchair transport (IDs 36, 41, 110, 122, 123, 124, 125, 126, 127, 129, 130, 131, 132) | M2 | R1, R2 | DONE |
| F-PKG-07 | 7-to'plam: Soliq va davlat bojlari (37) | 5-block guides for property, land, turnover, income tax exemptions and state duty discounts (IDs 1-15, 83, 84, 85, 92-102, 116-121, 133) | M2 | R1, R2 | DONE |
| F-UX-01 | 5-Block Benefit Card Layout | Render Kimga murojaat, Hujjatlar, Murojaat usuli, Muddat va to'lov, Huquqiy asos with Lex.uz & my.gov.uz buttons | M3 | R1 | DONE |
| F-UX-02 | Keyword Search System | Interactive keyword search across benefit names, descriptions, and 5-block guides via /search and category keyboard | M3 | R4 | DONE |
| F-UX-03 | Lawyer Inquiry Benefit Linkage | Pass and persist `benefit_id` in `Inquiry`, display benefit context in lawyer group and replies | M3 | R4 | DONE |
| F-UX-04 | Russian Localization | Complete Russian translation for all 134 benefits and 5-block guides (`title_ru`, `description_ru`, `guide_ru`, etc.) | M4 | R4 | DONE |
| F-VER-01 | E2E Verification & Forensic Audit | Comprehensive verification of all 134 benefits, zero orphans, zero regressions, full test suite pass, clean forensic audit | M5 | Acceptance | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Database & System Bug Fixes | Resolve 10 orphan benefits, remove max_age=18 locks, clean duplicate legal prefixes, add schema migrations | none | DONE |
| M2 | 5-Block Standardized Guides (134 Benefits) | Complete 5-block guides for all 7 packages (134 benefits) with verified Lex.uz & my.gov.uz references and 2024 regulations | M1 | DONE |
| M3 | Bot UX, Search & Lawyer Inquiry Linkage | Implement keyword search, update benefit card rendering with 5-block guide & action buttons, link `benefit_id` to inquiries | M1, M2 | DONE |
| M4 | Russian Translation & Bilingual Support | Translate all 134 benefit titles, details, and 5-block guides into Russian (`_ru` fields) | M2, M3 | DONE |
| M5 | E2E Testing, Hardening & Forensic Audit | Verification across all test tiers, adversarial testing, and forensic audit gate | M1, M2, M3, M4 | DONE |

## Interface Contracts
### Benefit Model ↔ Handlers Contract
- `Benefit` fields:
  - `guide_uz`: Text containing the 5-block standardized guide (formatted with HTML tags).
  - `guide_oz`: Cyrillic equivalent.
  - `guide_ru`: Russian equivalent.
  - `mygov_url`: Optional direct link to my.gov.uz service.
  - `lex_url`: Direct link to Lex.uz enactment.
- `Inquiry` fields:
  - `benefit_id`: Optional Integer FK linking inquiry to `tg_bot_benefits.id`.

### Search Contract
- Function signature: `Benefit.search_benefits(db_session, query: str, lang: str, user: User | None = None) -> list[Benefit]`
- Matches against: `title_{lang}`, `description_{lang}`, `legal_basis_{lang}`, `guide_{lang}`.

## Code Layout
- `src/models/benefit.py`: Benefit model definition, filtering and search methods
- `src/models/inquiry.py`: Inquiry model definition with `benefit_id`
- `imtiyozlar_boshqaruvi/imtiyozlar.json`: Master JSON dataset of 112 benefits (Single Source of Truth)
- `src/database/seed_benefits.py`: Seeding script populating DB exclusively from imtiyozlar_boshqaruvi/imtiyozlar.json
- `src/database/enrich_benefits.py`: Data enrichment script
- `src/database/alembic/versions/`: Database migrations
- `src/routes/aiogram/benefits.py`: Benefits browsing, search, and card formatting
- `src/routes/aiogram/group_router.py`: Lawyer inquiry response handling
- `src/app/keyboards.py`: Telegram inline keyboards (categories, list, detail, search)
