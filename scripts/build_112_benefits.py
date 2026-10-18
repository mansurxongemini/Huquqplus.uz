#!/usr/bin/env python3
"""
scripts/build_112_benefits.py
Constructs the authoritative 112-benefit dataset in imtiyozlar_boshqaruvi/imtiyozlar.json
based strictly on the official register from advice.uz/document/3125.
"""

import os
import json
import re
from pathlib import Path
from src.database.enrich_benefits import lat_to_cyr
from src.database.enrich_guides import lat_to_cyr_html

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "imtiyozlar_boshqaruvi" / "imtiyozlar.json"
SEED_FILE = ROOT_DIR / "src" / "database" / "benefits_seed_data.json"
if not SEED_FILE.exists():
    SEED_FILE = OUTPUT_FILE
PARSED_ADVICE_FILE = ROOT_DIR / "advice_112_parsed.json"

# Load existing seed data
with open(SEED_FILE, "r", encoding="utf-8") as f:
    old_seed_data = json.load(f)
seed_by_order = {s["order_index"]: s for s in old_seed_data}

# Load parsed advice data
with open(PARSED_ADVICE_FILE, "r", encoding="utf-8") as f:
    advice_items = json.load(f)

# Mapping of advice.uz item index (1..112) -> old seed order_index
DIRECT_MAP = {
    1: 1, 2: 3, 3: 5, 4: 6, 5: 2, 6: 9, 7: 11, 8: 14,
    9: 16, 10: 17, 11: 21, 12: 24, 13: 23, 14: 25, 15: 20, 16: 26, 17: 27, 18: 28, 19: 22, 20: 29,
    21: 30, 22: 31, 23: 32, 24: 33, 26: 34, 27: 35, 28: 36, 29: 37, 30: 38,
    31: 39, 32: 40, 33: 37, 35: 41, 36: 42, 37: 43, 38: 44, 39: 45, 40: 46,
    41: 47, 42: 48, 43: 49, 44: 50, 45: 51, 46: 52, 47: 53, 48: 54, 49: 55, 50: 56,
    51: 57, 52: 57, 57: 108, 58: 109, 60: 110, 61: 111, 62: 112, 63: 113, 64: 114,
    70: 115, 71: 116, 72: 39, 73: 117, 74: 118, 75: 119, 76: 120, 77: 121,
    82: 102, 83: 103, 86: 122, 87: 123, 89: 124, 90: 126, 91: 125, 92: 127,
    93: 128, 95: 129, 96: 130, 97: 131, 98: 132, 99: 133, 100: 134, 105: 105
}

# Specific customized entries for the remaining 31 items from advice.uz
CUSTOM_ITEMS = {
    25: {
        "category": "health_rehab",
        "title_uz": "TJEK orqali nogironlikni belgilash yoki o‘zgartirish",
        "title_ru": "Установление или изменение инвалидности через ВТЭК",
        "description_uz": "Kimlarga: Fuqarolar va nogironligi bo‘lgan shaxslar\n\nImtiyoz: Tibbiy-ijtimoiy ekspert komissiyasi (TJEK) ko‘rigidan bepul o‘tish hamda nogironlik guruhini belgilash yoki o‘zgartirish kafolati beriladi.",
        "description_ru": "Кому: Граждане и лица с инвалидностью\n\nЛьгота: Бесплатное прохождение медико-социальной экспертной комиссии (ВТЭК) и установление или изменение группы инвалидности.",
        "amount_uz": "Davlat tomonidan bepul amalga oshiriladi",
        "amount_ru": "Предоставляется государством бесплатно",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, Tibbiy-ijtimoiy ekspertiza xizmati",
        "organization_ru": "Национальное агентство социальной защиты, Служба медико-социальной экспертизы",
        "legal_basis_uz": "«Nogironligi bo‘lgan shaxslarning huquqlari to‘g‘risida»gi Qonun O‘RQ-641, Vazirlar Mahkamasining 62-son qarori (08.02.2022-y.)",
        "legal_basis_ru": "Закон ЗРУ-641 «О правах лиц с инвалидностью», Постановление Кабинета Министров № 62 от 08.02.2022 г.",
        "lex_url": "https://lex.uz/docs/-5853147",
        "mygov_url": "https://my.gov.uz/uz/service/380",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nOila shifokori (poliklinika) yoki tuman (shahar) «Inson» ijtimoiy xizmatlar markazi hamda Yagona portal (my.gov.uz) orqali TJEKga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat (pasport/ID-karta), birlamchi tibbiy hujjatlar va kasallik tarixi ko‘chirmasi (088/h shakl).<br/><br/>🌐 <b>Murojaat usuli</b>\nOnlayn tarzda YaIDXP (my.gov.uz) orqali yoki bevosita yashash joyidagi oilaviy poliklinika yo‘llanmasi bilan.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nHujjatlar to‘liq topshirilgach, 10 ish kunida ekspertiza o‘tkaziladi va xulosa taqdim etiladi. Xizmat to‘liq bepul.<br/><br/>⚖️ <b>Huquqiy asos</b>\nO‘RQ-641 hamda VMQ-62.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК семейному врачу (поликлиника), в районный центр «Инсон» или через Единый портал (my.gov.uz) во ВТЭК.<br/><br/>📄 <b>Какие документы требуются?</b>\nДокумент, удостоверяющий личность (паспорт/ID-карта), первичные медицинские документы и форма 088/у.<br/><br/>🌐 <b>Способ обращения</b>\nВ онлайн-режиме через my.gov.uz или непосредственно по направлению семейной поликлиники.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЭкспертиза проводится в течение 10 рабочих дней после подачи документов. Услуга бесплатна.<br/><br/>⚖️ <b>Правовая основа</b>\nЗРУ-641 и ПКМ № 62."
    },
    34: {
        "category": "labor",
        "title_uz": "Kasanachilik yoki hunarmandchilik asbob-uskunalari uchun subsidiya",
        "title_ru": "Субсидия на оборудование для надомничества или ремесленничества",
        "description_uz": "Kimlarga: Kasanachilik yoki hunarmandchilik asosida uy sharoitida ishlayotgan nogironligi bo‘lgan shaxslar\n\nImtiyoz: Asbob-uskunalar va mehnat qurollarini xarid qilish xarajatlarining 50 foizigacha, biroq BHMning 15 baravarigacha subsidiya ajratiladi.",
        "description_ru": "Кому: Лица с инвалидностью, работающие на дому на основе надомничества или ремесленничества\n\nЛьгота: Субсидия до 50% стоимости инструментов и оборудования, но не более 15 БРВ.",
        "amount_uz": "BHMning 15 baravarigacha subsidiya",
        "amount_ru": "Субсидия до 15 БРВ",
        "organization_uz": "Kambag‘allikni qisqartirish va bandlik vazirligi, Mahalladagi hokim yordamchisi",
        "organization_ru": "Министерство сокращения бедности и занятости, Помощник хокима в махалле",
        "legal_basis_uz": "Prezident Farmoni PF-91 (12.06.2023-y.), Vazirlar Mahkamasining 307-son qarori (22.07.2023-y.)",
        "legal_basis_ru": "Указ Президента УП-91 от 12.06.2023 г., Постановление Кабинета Министров № 307 от 22.07.2023 г.",
        "lex_url": "https://lex.uz/docs/-6496229",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi hokim yordamchisi yoki tuman (shahar) Kambag‘allikni qisqartirish va bandlik bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, shaxsni tasdiqlovchi hujjat, nogironlik ma’lumotnomasi, kasanachilik shartnomasi yoki hunarmand guvohnomasi, asbob-uskuna hisob-fakturasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalladagi hokim yordamchisi orqali onlayn (onlinemahalla.uz) yoki yozma ariza topshiriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nArizani o‘rganish va subsidiya ajratish xulosasi 5 ish kunida qabul qilinadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPF-91 va VMQ-307.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК помощнику хокима в махалле или в районный отдел сокращения бедности и занятости.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, справка об инвалидности, договор надомничества или свидетельство ремесленника, счет-фактура на оборудование.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез помощника хокима (onlinemahalla.uz) или письменным заявлением.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЗаключение принимается в течение 5 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nУП-91 и ПКМ № 307."
    },
    53: {
        "category": "labor",
        "title_uz": "Nogironligi bo‘lgan xodimlarni ishga olgan ish beruvchiga ish haqi subsidiyasi",
        "title_ru": "Субсидия работодателю на оплату труда принятых работников с инвалидностью",
        "description_uz": "Kimlarga: Aholi bandligiga ko‘maklashish markazi yo‘llanmasi bilan nogironligi bo‘lgan shaxslarni ishga qabul qilgan ish beruvchilar\n\nImtiyoz: Har bir ishga qabul qilingan xodim uchun har oyda BHMning 2 baravari miqdorida ish haqi subsidiyasi to‘lanadi.",
        "description_ru": "Кому: Работодатели, принявшие на работу лиц с инвалидностью по направлению центра содействия занятости\n\nЛьгота: Ежемесячная субсидия в размере 2 БРВ за каждого трудоустроенного работника.",
        "amount_uz": "Har oyda BHMning 2 baravari miqdorida subsidiya",
        "amount_ru": "Ежемесячно в размере 2 БРВ",
        "organization_uz": "Kambag‘allikni qisqartirish va bandlik vazirligi, Tuman (shahar) ABKM",
        "organization_ru": "Министерство сокращения бедности и занятости, Районный ЦСЗН",
        "legal_basis_uz": "Prezident Qarori PQ-4850 (06.10.2020-y.), Adliya vazirligida ro‘yxatdan o‘tgan 3163-son nizom (31.05.2019-y.)",
        "legal_basis_ru": "Постановление Президента ПП-4850 от 06.10.2020 г., рег. Минюста № 3163 от 31.05.2019 г.",
        "lex_url": "https://lex.uz/docs/-5032512",
        "mygov_url": "https://my.mehnat.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": True,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) Aholi bandligiga ko‘maklashish markaziga (ABKM) yoki my.mehnat.uz portali orqali murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nIsh beruvchi arizasi, nogironligi bo‘lgan shaxs bilan tuzilgan mehnat shartnomasi va ishga qabul qilish to‘g‘risidagi buyruq.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.mehnat.uz elektron portali orqali elektron raqamli imzo (ERI) bilan tasdiqlangan holda.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 3 ish kuni ichida ko‘rib chiqiladi va subsidiya har oy to‘lab boriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPQ-4850 va Idoraviy ro‘yxat raqami 3163.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный Центр содействия занятости населения или через портал my.mehnat.uz.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление работодателя, трудовой договор с лицом с инвалидностью и приказ о приеме на работу.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал my.mehnat.uz с подтверждением ЭЦП.<br/><br/>⏱ <b>Срок рассмотрения</b>\nРассмотрение в течение 3 рабочих дней, выплата производится ежемесячно.<br/><br/>⚖️ <b>Правовая основа</b>\nПП-4850 и рег. № 3163."
    },
    54: {
        "category": "labor",
        "title_uz": "Nogironligi bo‘lgan shaxslarni ishga qabul qilgan ish beruvchiga 6 oylik subsidiya",
        "title_ru": "Субсидия работодателю на 6 месяцев за трудоустройство лиц с инвалидностью",
        "description_uz": "Kimlarga: Nogironligi bo‘lgan shaxslarni ishga qabul qilgan ish beruvchilar\n\nImtiyoz: Har bir ishga qabul qilingan xodim uchun 6 oy davomida har oy BHMning 1,5 baravari miqdorida subsidiya ajratiladi.",
        "description_ru": "Кому: Работодатели, принявшие на работу лиц с инвалидностью\n\nЛьгота: Субсидия в размере 1,5 БРВ ежемесячно в течение 6 месяцев за каждого работника.",
        "amount_uz": "6 oy davomida har oy BHMning 1,5 baravari",
        "amount_ru": "1,5 БРВ ежемесячно в течение 6 месяцев",
        "organization_uz": "Kambag‘allikni qisqartirish va bandlik vazirligi, Davlat bandlikka ko‘maklashish jamg‘armasi",
        "organization_ru": "Министерство сокращения бедности и занятости, Государственный фонд содействия занятости",
        "legal_basis_uz": "Prezident Qarori PQ-57 (21.12.2021-y.), Vazirlar Mahkamasining 203-son qarori (20.04.2022-y.)",
        "legal_basis_ru": "Постановление Президента ПП-57 от 21.12.2021 г., Постановление Кабинета Министров № 203 от 20.04.2022 г.",
        "lex_url": "https://lex.uz/docs/-5972828",
        "mygov_url": "https://my.mehnat.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": True,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) Kambag‘allikni qisqartirish va bandlik bo‘limiga yoki my.mehnat.uz orqali murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, mehnat daftarchasi ko‘chirmasi, mehnat shartnomasi va nogironlik ma’lumotnomasi nusxasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.mehnat.uz portali orqali ERI bilan tasdiqlangan holda onlayn yuboriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kunida ko‘rib chiqiladi va subsidiya har oy to‘lanadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPQ-57 va VMQ-203.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный отдел сокращения бедности и занятости или через портал my.mehnat.uz.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, выписка из трудовой книжки, трудовой договор и копия справки об инвалидности.<br/><br/>🌐 <b>Способ обращения</b>\nВ онлайн-режиме через my.mehnat.uz с подтверждением ЭЦП.<br/><br/>⏱ <b>Срок рассмотрения</b>\nРассмотрение в течение 5 рабочих дней, субсидия выплачивается ежемесячно.<br/><br/>⚖️ <b>Правовая основа</b>\nПП-57 и ПКМ № 203."
    },
    55: {
        "category": "labor",
        "title_uz": "Nogironligi bor yoshlarga asbob-uskuna va mehnat qurollari xaridi subsidiyasi",
        "title_ru": "Субсидия молодежи с инвалидностью на закупку оборудования и инструментов",
        "description_uz": "Kimlarga: Kasbga tayyorlash, qayta tayyorlash va malakasini oshirish kurslarini tamomlagan nogironligi bo‘lgan yoshlar\n\nImtiyoz: Asbob-uskunalar va mehnat qurollarini xarid qilish uchun BHMning 30 baravarigacha bo‘lgan miqdorda subsidiya ajratiladi.",
        "description_ru": "Кому: Молодежь с инвалидностью, окончившая курсы профессиональной подготовки и переподготовки\n\nЛьгота: Субсидия до 30 БРВ на закупку оборудования и орудий труда.",
        "amount_uz": "BHMning 30 baravarigacha subsidiya",
        "amount_ru": "Субсидия в размере до 30 БРВ",
        "organization_uz": "Yoshlar ishlari agentligi, Mahalladagi yoshlar yetakchisi",
        "organization_ru": "Агентство по делам молодежи, Молодежный лидер махалли",
        "legal_basis_uz": "Prezident Qarori PQ-57 (21.12.2021-y.), Vazirlar Mahkamasining 341-son qarori (21.06.2022-y.)",
        "legal_basis_ru": "Постановление Президента ПП-57 от 21.12.2021 г., Постановление Кабинета Министров № 341 от 21.06.2022 г.",
        "lex_url": "https://lex.uz/docs/-6077366",
        "mygov_url": "https://yoshlardaftari.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi yoshlar yetakchisiga yoki Yoshlar ishlari agentligi tuman bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, shaxsni tasdiqlovchi hujjat, kursni tamomlaganlik to‘g‘risida sertifikat, asbob-uskunaning narxnomasi/shartnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nyoshlardaftari.uz portali orqali yoki mahalladagi yoshlar yetakchisiga bevosita ariza beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kuni ichida o‘rganilib, vasiylik kengashi xulosasi bilan mablag‘ to‘g‘ridan-to‘g‘ri ta’minotchiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPQ-57 va VMQ-341.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК молодежному лидеру в махалле или в районный отдел Агентства по делам молодежи.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, сертификат об окончании курсов, счет-договор на оборудование.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал yoshlardaftari.uz или напрямую молодежному лидеру махалли.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЗаявление рассматривается в течение 5 рабочих дней, средства переводятся поставщику.<br/><br/>⚖️ <b>Правовая основа</b>\nПП-57 и ПКМ № 341."
    },
    56: {
        "category": "health_rehab",
        "title_uz": "«Ayollar daftari»dagi nogironligi bor ayollarga dori-darmon va operatsiya yordami",
        "title_ru": "Помощь на лекарства и операции женщинам с инвалидностью из «Женской тетради»",
        "description_uz": "Kimlarga: “Ayollar daftari”ga kiritilgan I va II guruh nogironligi bo‘lgan xotin-qizlar hamda nogiron bolali onalar\n\nImtiyoz: Dori-darmon olib berish yoki murakkab jarrohlik amaliyotlari xarajatlarini qoplash uchun BHMning 5 baravarigacha moddiy yordam ajratiladi.",
        "description_ru": "Кому: Женщины с инвалидностью I и II групп, а также матери детей с инвалидностью из «Женской тетради»\n\nЛьгота: Помощь на лекарства или сложные хирургические операции в размере до 5 БРВ.",
        "amount_uz": "BHMning 5 baravarigacha moddiy yordam",
        "amount_ru": "Материальная помощь до 5 БРВ",
        "organization_uz": "Oila va xotin-qizlar qo‘mitasi, Tuman (shahar) hokimligi, Mahalla xotin-qizlar faoli",
        "organization_ru": "Комитет семьи и женщин, Районный хокимият, Женский активист махалли",
        "legal_basis_uz": "Prezident Qarori PQ-5020 (05.03.2021-y.), Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Президента ПП-5020 от 05.03.2021 г., Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi xotin-qizlar faoliga yoki tuman (shahar) Oila va xotin-qizlar bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, shaxsni tasdiqlovchi hujjat, tibbiy xulosa (retsept yoki operatsiya zarurligi haqida ma’lumotnoma) va nogironlik guvohnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla xotin-qizlar faoli orqali «Ayollar daftari» tizimiga kiritilgan holda ariza beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nSektor rahbari va komissiya tomonidan 7 ish kunida o‘rganilib, to‘lov amalga oshiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPQ-5020 va VMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК женскому активисту в махалле или в районный отдел семьи и женщин.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, медицинское заключение (рецепт или показание к операции) и справка об инвалидности.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез женского активиста махалли в рамках системы «Женская тетрадь».<br/><br/>⏱ <b>Срок рассмотрения</b>\nКомиссия рассматривает заявление в течение 7 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПП-5020 и ПКМ № 145."
    },
    59: {
        "category": "other",
        "title_uz": "Davlat buyurtmachilari tomonidan nogironlar tashkilotlari tovarlarini xarid qilish",
        "title_ru": "Закупка товаров организаций лиц с инвалидностью государственными заказчиками",
        "description_uz": "Kimlarga: Nogironligi bo‘lgan shaxslarning jamoat birlashmalari va korxonalari\n\nImtiyoz: Davlat buyurtmachilari mazkur toifadagi korxonalar tomonidan ishlab chiqarilgan tovarlarni to‘g‘ridan-to‘g‘ri elektron do‘kon orqali xarid qilish huquqiga ega.",
        "description_ru": "Кому: Общественные объединения и предприятия лиц с инвалидностью\n\nЛьгота: Госзаказчики вправе закупать товары, произведенные данными предприятиями, напрямую через электронный магазин.",
        "amount_uz": "To‘g‘ridan-to‘g‘ri xarid qilish huquqi",
        "amount_ru": "Право прямого заключения договоров в электронном магазине",
        "organization_uz": "Iqtisodiyot va moliya vazirligi, Davlat xaridlari departamenti",
        "organization_ru": "Министерство экономики и финансов, Департамент государственных закупок",
        "legal_basis_uz": "Prezident Qarori PQ-57 (21.12.2021-y.)",
        "legal_basis_ru": "Постановление Президента ПП-57 от 21.12.2021 г.",
        "lex_url": "https://lex.uz/docs/-5789647",
        "mygov_url": "https://xarid.uzex.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": True,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMaxsus axborot portali (xarid.uzex.uz) yoki Iqtisodiyot va moliya vazirligining Davlat xaridlari departamentiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nYuridik shaxs guvohnomasi, nogironlar jamoat birlashmasi ishtirokchisi ekanligi tasdig‘i, tovarlar katalogi va sertifikatlari.<br/><br/>🌐 <b>Murojaat usuli</b>\nxarid.uzex.uz elektron savdo maydonchasida ro‘yxatdan o‘tib, elektron do‘konga tovarlarni joylashtirish orqali.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nElektron bitimlar tizimda real vaqt rejimida rasmiylashtiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nPQ-57.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nНа специальный информационный портал xarid.uzex.uz или в Департамент госзакупок Минэкономфина.<br/><br/>📄 <b>Какие документы требуются?</b>\nСвидетельство юрлица, подтверждение статуса организации инвалидов, каталог товаров.<br/><br/>🌐 <b>Способ обращения</b>\nРегистрация на портале xarid.uzex.uz и размещение товаров в электронном магазине.<br/><br/>⏱ <b>Срок рассмотрения</b>\nСделки оформляются в системе в режиме реального времени.<br/><br/>⚖️ <b>Правовая основа</b>\nПП-57."
    },
    65: {
        "category": "labor",
        "title_uz": "«Temir daftar»dagi nogironligi bor shaxslarni ish o‘rinlariga kafolatli joylashtirish",
        "title_ru": "Гарантированное трудоустройство лиц с инвалидностью из «Железной тетради»",
        "description_uz": "Kimlarga: “Temir daftar” ro‘yxatiga kiritilgan I va II guruh nogironligi bo‘lgan a’zolari mavjud oilalar\n\nImtiyoz: Tarmoq va hududiy investitsiya dasturlariga kiritilgan loyihalarda yaratilayotgan yangi ish o‘rinlariga birinchi navbatda joylashtirish kafolatlanadi.",
        "description_ru": "Кому: Семьи с лицами с инвалидностью I и II групп из «Железной тетради»\n\nЛьгота: Первоочередное трудоустройство на новые рабочие места в инвестиционных проектах.",
        "amount_uz": "Kafolatlangan ish o‘rniga joylashtirish",
        "amount_ru": "Гарантированное трудоустройство",
        "organization_uz": "Tuman (shahar) hokimliklari, Kambag‘allikni qisqartirish va bandlik bo‘limi",
        "organization_ru": "Районные хокимияты, Отдел сокращения бедности и занятости",
        "legal_basis_uz": "Vazirlar Mahkamasining 250-son qarori (28.04.2021-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 250 от 28.04.2021 г.",
        "lex_url": "https://lex.uz/docs/-5403215",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi hokim yordamchisi yoki tuman (shahar) Kambag‘allikni qisqartirish va bandlik bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport/ID-karta nusxasi, mehnat daftarchasi (agar bor bo‘lsa) va TJEK nogironlik ma’lumotnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla fuqarolar yig‘inidagi hokim yordamchisi orqali yozma yoki elektron shaklda.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza qabul qilingach, 7 ish kunida mos ish o‘rinlari bo‘yicha yo‘llanma beriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-250.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК помощнику хокима в махалле или в районный отдел сокращения бедности и занятости.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, трудовая книжка (при наличии) и справка об инвалидности ВТЭК.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез помощника хокима в сходе граждан махалли.<br/><br/>⏱ <b>Срок рассмотрения</b>\nНаправление выдается в течение 7 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 250."
    },
    66: {
        "category": "education",
        "title_uz": "Mehribonlik uylaridagi nogironligi bor bolalarga to‘liq davlat ta’minoti",
        "title_ru": "Полное государственное обеспечение детей с инвалидностью в домах «Мехрибонлик»",
        "description_uz": "Kimlarga: Bolalar uylarida tarbiyalanayotgan alohida ehtiyojli va nogironligi bo‘lgan bolalar\n\nImtiyoz: Ta’lim-tarbiya, sog‘lomlashtirish, kiyim-kechak, oziq-ovqat va reabilitatsiya xizmatlari to‘liq davlat hisobidan bepul ta’minlanadi.",
        "description_ru": "Кому: Воспитанники домов ребенка и детских домов с инвалидностью\n\nЛьгота: Полное государственное обеспечение воспитанием, питанием, лечением и реабилитацией.",
        "amount_uz": "100% to‘liq davlat ta’minoti",
        "amount_ru": "100% полное государственное обеспечение",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, Sog‘liqni saqlash vazirligi",
        "organization_ru": "Национальное агентство социальной защиты, Министерство здравоохранения",
        "legal_basis_uz": "Vazirlar Mahkamasining 171-son qarori (13.06.2012-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 171 от 13.06.2012 г.",
        "lex_url": "https://lex.uz/docs/-2024108",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markaziga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nTug‘ilganlik to‘g‘risida guvohnoma, tibbiy xulosa, vasiylik va homiylik organining qarori hamda PTPK xulosasi.<br/><br/>🌐 <b>Murojaat usuli</b>\n«Inson» markazi yoki tuman vasiylik organi orqali bevosita ariza beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nHujjatlar to‘liq bo‘lgach, 10 ish kunida yo‘llanma rasmiylashtiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-171.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный (городской) центр социальных услуг «Инсон».<br/><br/>📄 <b>Какие документы требуются?</b>\nСвидетельство о рождении, медицинское заключение, решение органа опеки и заключение ПМПК.<br/><br/>🌐 <b>Способ обращения</b>\nНепосредственно через центр «Инсон» или органы опеки.<br/><br/>⏱ <b>Срок рассмотрения</b>\nНаправление оформляется в течение 10 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 171."
    },
    67: {
        "category": "health_rehab",
        "title_uz": "«Temir daftar»dagi nogironligi bor shaxslarga bepul tibbiy xizmat va dori-darmon",
        "title_ru": "Бесплатная медпомощь и лекарства лицам с инвалидностью из «Железной тетради»",
        "description_uz": "Kimlarga: “Temir daftar” ro‘yxatiga kiritilgan I va II guruh nogironligi bo‘lgan shaxslar\n\nImtiyoz: Tibbiy xizmatlar ko‘rsatish, dori vositalari bilan bepul ta’minlash va zarurat bo‘lganda jarrohlik amaliyotlari xarajatlari to‘liq qoplab beriladi.",
        "description_ru": "Кому: Лица с инвалидностью I и II групп из «Железной тетради»\n\nЛьгота: Бесплатная медицинская помощь, обеспечение лекарственными средствами и покрытие расходов на лечение.",
        "amount_uz": "Bepul tibbiy xizmat va dori ta’minoti",
        "amount_ru": "Бесплатная медпомощь и обеспечение лекарствами",
        "organization_uz": "Tuman (shahar) hokimliklari, Sog‘liqni saqlash bo‘limi",
        "organization_ru": "Районные хокимияты, Отдел здравоохранения",
        "legal_basis_uz": "Vazirlar Mahkamasining 250-son qarori (28.04.2021-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 250 от 28.04.2021 г.",
        "lex_url": "https://lex.uz/docs/-5403215",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalla fuqarolar yig‘inidagi mas’ullarga yoki tuman markaziy ko‘p tarmoqli poliklinikasiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat, nogironlik ma’lumotnomasi, shifokor retsepti va «Temir daftar»da ro‘yxatda turganligi tasdig‘i.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla orqali yoki oilaviy shifokor yo‘llanmasi asosida yozma ariza topshiriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 3 ish kuni ichida ko‘rib chiqilib, tibbiy yordam ko‘rsatiladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-250.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК ответственным лицам в сходе махалли или в районную многопрофильную поликлинику.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт, справка об инвалидности, рецепт врача и подтверждение нахождения в «Железной тетради».<br/><br/>🌐 <b>Способ обращения</b>\nЧерез махаллю или по направлению семейного врача.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЗаявление рассматривается в течение 3 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 250."
    },
    68: {
        "category": "labor",
        "title_uz": "«Ayollar daftari»dagi nogironligi bor ayollarni investitsiya loyihalariga ishga joylashtirish",
        "title_ru": "Трудоустройство женщин с инвалидностью из «Женской тетради» в инвестпроекты",
        "description_uz": "Kimlarga: “Ayollar daftari” ro‘yxatiga kiritilgan I va II guruh nogironligi bo‘lgan xotin-qizlar\n\nImtiyoz: Tarmoq va hududiy investitsiya dasturlariga kiritilgan loyihalarda yangi ish o‘rinlariga birinchi navbatda ishga joylashtirish ta’minlanadi.",
        "description_ru": "Кому: Женщины с инвалидностью I и II групп из «Женской тетради»\n\nЛьгота: Первоочередное трудоустройство на новые рабочие места в инвестиционных проектах.",
        "amount_uz": "Kafolatlangan ish o‘rni",
        "amount_ru": "Гарантированное рабочее место",
        "organization_uz": "Oila va xotin-qizlar qo‘mitasi, Tuman (shahar) hokimligi",
        "organization_ru": "Комитет семьи и женщин, Районный хокимият",
        "legal_basis_uz": "Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False, "gender": "female",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi xotin-qizlar faoliga yoki tuman Kambag‘allikni qisqartirish va bandlik bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport nusxasi, nogironlik to‘g‘risida TJEK ma’lumotnomasi va ma’lumoti haqidagi hujjat.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla xotin-qizlar faoli orqali ro‘yxatga olinib, yo‘llanma beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kuni ichida ko‘rib chiqilib, ish o‘rni taklif qilinadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК женскому активисту в махалле или в районный отдел занятости.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, справка ВТЭК об инвалидности и документ об образовании.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез женского активиста махалли.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЗаявление рассматривается в течение 5 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 145."
    },
    69: {
        "category": "health_rehab",
        "title_uz": "«Ayollar daftari»dagi ehtiyojmand ayollarga bepul tibbiy xizmat va dori-darmon",
        "title_ru": "Бесплатная медпомощь женщинам из «Женской тетради»",
        "description_uz": "Kimlarga: “Ayollar daftari” ro‘yxatiga kiritilgan nogironligi bo‘lgan xotin-qizlar\n\nImtiyoz: Zarur tibbiy ko‘riklar, davolanish va dori-darmon vositalari bilan bepul ta’minlash kafolatlanadi.",
        "description_ru": "Кому: Женщины с инвалидностью из «Женской тетради»\n\nЛьгота: Бесплатное медицинское обслуживание, обследование и обеспечение необходимыми лекарствами.",
        "amount_uz": "Bepul tibbiy yordam",
        "amount_ru": "Бесплатная медицинская помощь",
        "organization_uz": "Oila va xotin-qizlar qo‘mitasi, Sog‘liqni saqlash vazirligi",
        "organization_ru": "Комитет семьи и женщин, Министерство здравоохранения",
        "legal_basis_uz": "Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False, "gender": "female",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalla xotin-qizlar faoliga yoki tuman markaziy poliklinikasiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat, nogironlik guvohnomasi va shifokor retsepti.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla xotin-qizlar faoli tavsiyasi bilan tibbiyot muassasasiga murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 3 ish kuni ichida o‘rganilib, tibbiy xizmat ko‘rsatiladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК женскому активисту махалли или в районную центральную поликлинику.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт, справка об инвалидности и рецепт врача.<br/><br/>🌐 <b>Способ обращения</b>\nПо рекомендации женского активиста махалли.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 3 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 145."
    },
    78: {
        "category": "pension_aid",
        "title_uz": "«Temir daftar»dagi nogironligi bor a’zolari mavjud oilalarga bir martalik moddiy yordam",
        "title_ru": "Единовременная матпомощь семьям с инвалидностью из «Железной тетради»",
        "description_uz": "Kimlarga: “Temir daftar” ro‘yxatiga kiritilgan nogironligi bo‘lgan a’zolari bor oilalar\n\nImtiyoz: Xalq deputatlari tuman Kengashi qarori bilan BHMning 2 baravaridan 5 baravarigacha miqdorda bir martalik moddiy yordam ajratiladi.",
        "description_ru": "Кому: Семьи с членами с инвалидностью из «Железной тетради»\n\nЛьгота: Единовременная материальная помощь в размере от 2 до 5 БРВ.",
        "amount_uz": "BHMning 2 baravaridan 5 baravarigacha",
        "amount_ru": "От 2 до 5 БРВ",
        "organization_uz": "Xalq deputatlari tuman (shahar) Kengashi, Tuman hokimligi",
        "organization_ru": "Кенгаш народных депутатов, Районный хокимият",
        "legal_basis_uz": "Vazirlar Mahkamasining 250-son qarori (28.04.2021-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 250 от 28.04.2021 г.",
        "lex_url": "https://lex.uz/docs/-5403215",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalla fuqarolar yig‘iniga (MFY) yoki tuman hokimligiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport nusxasi, oila tarkibi to‘g‘risida ma’lumot va nogironlik ma’lumotnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalla raisi yoki hokim yordamchisiga yozma ariza topshiriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 10 ish kunida Xalq deputatlari Kengashi tomonidan ko‘rib chiqilib, mablag‘ bank kartasiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-250.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ сход граждан махалли (СГМ) или в районный хокимият.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, копия паспорта, справка о составе семьи и справка об инвалидности.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез председателя махалли или помощника хокима.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 10 рабочих дней утверждается Кенгашем и перечисляется на карту.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 250."
    },
    79: {
        "category": "pension_aid",
        "title_uz": "«Yoshlar daftari»dagi I va II guruh yoshlarga bir martalik moddiy yordam",
        "title_ru": "Единовременная матпомощь молодежи I и II групп из «Молодежной тетради»",
        "description_uz": "Kimlarga: “Yoshlar daftari”ga kiritilgan I yoki II guruh nogironligi bo‘lgan yoshlar (14-30 yosh)\n\nImtiyoz: Vasiylik kengashi qarori bilan BHMning 4 baravari miqdorida bir martalik moddiy yordam to‘lanadi.",
        "description_ru": "Кому: Молодежь с инвалидностью I или II группы из «Молодежной тетради» (14-30 лет)\n\nЛьгота: Единовременная материальная помощь в размере 4 БРВ.",
        "amount_uz": "BHMning 4 baravari miqdorida (bir martalik)",
        "amount_ru": "В размере 4 БРВ (единовременно)",
        "organization_uz": "Tuman (shahar) “Yoshlar daftari” jamg‘armasi vasiylik kengashi, Yoshlar ishlari agentligi",
        "organization_ru": "Попечительский совет фонда «Молодежная тетрадь», Агентство по делам молодежи",
        "legal_basis_uz": "Vazirlar Mahkamasining 312-son qarori (07.06.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 312 от 07.06.2022 г.",
        "lex_url": "https://lex.uz/docs/-6054817",
        "mygov_url": "https://yoshlardaftari.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False, "min_age": 14, "max_age": 30,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi yoshlar yetakchisiga yoki Yoshlar ishlari agentligi tuman bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport/ID-karta va TJEK nogironlik ma’lumotnomasi nusxasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nyoshlardaftari.uz portali orqali yoki mahalladagi yoshlar yetakchisiga bevosita murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kunida ko‘rib chiqilib, yordam puli arizachining bank kartasiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-312.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК молодежному лидеру махалли или в районный отдел Агентства по делам молодежи.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт/ID-карта и копия справки об инвалидности ВТЭК.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал yoshlardaftari.uz или напрямую молодежному лидеру.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 5 рабочих дней средства перечисляются на банковскую карту.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 312."
    },
    80: {
        "category": "pension_aid",
        "title_uz": "Farzandida nogironlik bor yosh ota-onalarga bir martalik moddiy yordam",
        "title_ru": "Единовременная матпомощь молодым родителям детей с инвалидностью",
        "description_uz": "Kimlarga: “Yoshlar daftari”ga kiritilgan, qaramog‘ida I yoki II guruh nogironligi bo‘lgan farzandi bor yosh ota-onalar (14-30 yosh)\n\nImtiyoz: Vasiylik kengashi xulosasi bilan BHMning 4 baravari miqdorida bir martalik moddiy yordam beriladi.",
        "description_ru": "Кому: Молодые родители (14-30 лет) из «Молодежной тетради», воспитывающие ребенка с инвалидностью I или II группы\n\nЛьгота: Единовременная материальная помощь в размере 4 БРВ.",
        "amount_uz": "BHMning 4 baravari miqdorida (bir martalik)",
        "amount_ru": "В размере 4 БРВ (единовременно)",
        "organization_uz": "Tuman (shahar) “Yoshlar daftari” jamg‘armasi vasiylik kengashi, Yoshlar ishlari agentligi",
        "organization_ru": "Попечительский совет фонда «Молодежная тетрадь», Агентство по делам молодежи",
        "legal_basis_uz": "Vazirlar Mahkamasining 312-son qarori (07.06.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 312 от 07.06.2022 г.",
        "lex_url": "https://lex.uz/docs/-6054817",
        "mygov_url": "https://yoshlardaftari.uz",
        "for_first_group": False, "for_second_group": False, "for_third_group": False, "for_child": True, "for_parent": True, "is_for_organization": False, "min_age": 14, "max_age": 30,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi yoshlar yetakchisiga yoki Yoshlar ishlari agentligi tuman bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning pasporti, bolaning tug‘ilganlik guvohnomasi va nogironlik ma’lumotnomasi nusxasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nyoshlardaftari.uz portali orqali yoki mahalladagi yoshlar yetakchisiga bevosita ariza beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kunida ko‘rib chiqilib, yordam puli bank kartasiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-312.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК молодежному лидеру махалли или в районный отдел Агентства по делам молодежи.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт родителя, свидетельство о рождении ребенка и копия справки об инвалидности.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал yoshlardaftari.uz или напрямую молодежному лидеру.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 5 рабочих дней средства перечисляются на карту.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 312."
    },
    81: {
        "category": "health_rehab",
        "title_uz": "Bemor yoshlarga davolanish va jarrohlik xarajatlari uchun subsidiya",
        "title_ru": "Субсидия молодежи на лечение и проведение хирургических операций",
        "description_uz": "Kimlarga: “Yoshlar daftari”ga kiritilgan, og‘ir kasalligi yoki nogironligi bo‘lgan yoshlar (14-30 yosh)\n\nImtiyoz: Mamlakatimizda yoki xorijda davolanish hamda operatsiya o‘tkazish xarajatlari uchun BHMning 50 baravarigacha subsidiya ajratiladi.",
        "description_ru": "Кому: Молодежь (14-30 лет) из «Молодежной тетради» с тяжелыми заболеваниями или инвалидностью\n\nЛьгота: Субсидия до 50 БРВ на лечение или хирургическую операцию в стране или за рубежом.",
        "amount_uz": "BHMning 50 baravarigacha subsidiya",
        "amount_ru": "Субсидия до 50 БРВ",
        "organization_uz": "Tuman (shahar) “Yoshlar daftari” jamg‘armasi vasiylik kengashi, Yoshlar ishlari agentligi",
        "organization_ru": "Попечительский совет фонда «Молодежная тетрадь», Агентство по делам молодежи",
        "legal_basis_uz": "Vazirlar Mahkamasining 312-son qarori (07.06.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 312 от 07.06.2022 г.",
        "lex_url": "https://lex.uz/docs/-6054817",
        "mygov_url": "https://yoshlardaftari.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False, "min_age": 14, "max_age": 30,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi yoshlar yetakchisiga yoki Yoshlar ishlari agentligi tuman bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport, maxsus tibbiy komissiya xulosasi va davolash muassasasi hisob-varag‘i.<br/><br/>🌐 <b>Murojaat usuli</b>\nyoshlardaftari.uz portali orqali yoki mahalladagi yoshlar yetakchisiga bevosita ariza beriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 7 ish kunida Vasiylik kengashida ko‘rib chiqiladi va mablag‘ davolash muassasasiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-312.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК молодежному лидеру махалли или в районный отдел Агентства по делам молодежи.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, заключение врачебной комиссии и счет из медицинского учреждения.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал yoshlardaftari.uz или напрямую молодежному лидеру.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 7 рабочих дней, средства перечисляются напрямую в медучреждение.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 312."
    },
    84: {
        "category": "pension_aid",
        "title_uz": "«Ayollar daftari»dagi nogironligi bor ayollarga dehqonchilik yerlarini birinchi navbatda ajratish",
        "title_ru": "Первоочередное выделение земель женщинам с инвалидностью из «Женской тетради»",
        "description_uz": "Kimlarga: “Ayollar daftari” ro‘yxatiga kiritilgan nogironligi bo‘lgan xotin-qizlar\n\nImtiyoz: Qishloq xo‘jaligi yer uchastkalarini uzoq muddatli ijara asosida dehqonchilik uchun birinchi navbatda ajratish ta’minlanadi.",
        "description_ru": "Кому: Женщины с инвалидностью из «Женской тетради»\n\nЛьгота: Первоочередное предоставление сельскохозяйственных земель в аренду для дехканства.",
        "amount_uz": "Yer uchastkasini ijara asosida birinchi navbatda ajratish",
        "amount_ru": "Первоочередное предоставление земельного участка",
        "organization_uz": "Oila va xotin-qizlar qo‘mitasi, Qishloq xo‘jaligi vazirligi, Hokim yordamchisi",
        "organization_ru": "Комитет семьи и женщин, Министерство сельского хозяйства, Помощник хокима",
        "legal_basis_uz": "Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False, "gender": "female",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi hokim yordamchisi yoki tuman Qishloq xo‘jaligi bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport nusxasi, nogironlik ma’lumotnomasi va «Ayollar daftari»da ro‘yxatda turganlik tasdig‘i.<br/><br/>🌐 <b>Murojaat usuli</b>\nMahalladagi hokim yordamchisi tavsiyasi bilan onlayn auksion (e-auksion.uz) orqali imtiyozli asosda.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 10 ish kunida ko‘rib chiqilib, yer ajratish jarayoni boshlanadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК помощнику хокима в махалле или в районный отдел сельского хозяйства.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, справка об инвалидности и подтверждение нахождения в «Женской тетради».<br/><br/>🌐 <b>Способ обращения</b>\nПо рекомендации помощника хокима через аукцион на льготной основе.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 10 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 145."
    },
    85: {
        "category": "pension_aid",
        "title_uz": "«Ayollar daftari»dagi nogironligi bor ayollarga issiqxona va tomorqa subsidiyasi",
        "title_ru": "Субсидия на теплицу и приусадебный участок женщинам с инвалидностью",
        "description_uz": "Kimlarga: “Ayollar daftari” ro‘yxatiga kiritilgan nogironligi bo‘lgan xotin-qizlar\n\nImtiyoz: Shaxsiy tomorqada yengil konstruksiyali issiqxona o‘rnatish, urug‘lik va ko‘chatlar xarid qilish uchun subsidiya ajratiladi.",
        "description_ru": "Кому: Женщины с инвалидностью из «Женской тетради»\n\nЛьгота: Субсидия на установку легкой теплицы на приусадебном участке, закупку семян и саженцев.",
        "amount_uz": "BHMning 30 baravarigacha subsidiya",
        "amount_ru": "Субсидия до 30 БРВ",
        "organization_uz": "Oila va xotin-qizlar qo‘mitasi, Tuman hokimligi, Mahalladagi hokim yordamchisi",
        "organization_ru": "Комитет семьи и женщин, Районный хокимият, Помощник хокима",
        "legal_basis_uz": "Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False, "gender": "female",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nMahalladagi hokim yordamchisiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport, nogironlik guvohnomasi va tomorqa yeri mavjudligi haqida ma’lumotnoma.<br/><br/>🌐 <b>Murojaat usuli</b>\nHokim yordamchisi orqali onlinemahalla.uz tizimida ariza shakllantiriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kuni ichida ko‘rib chiqilib, issiqxona qurilishi moliyalashtiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК помощнику хокима в махалле.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, справка об инвалидности и документ на приусадебный участок.<br/><br/>🌐 <b>Способ обращения</b>\nОформление через помощника хокима в системе onlinemahalla.uz.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 5 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 145."
    },
    88: {
        "category": "labor",
        "title_uz": "Nogironligi bor ayollarni ishga olgan tadbirkorlarga ish o‘rnini moslashtirish subsidiyasi",
        "title_ru": "Субсидия предпринимателям на адаптацию рабочих мест для женщин с инвалидностью",
        "description_uz": "Kimlarga: “Ayollar daftari”dagi nogironligi bor ayollarni ishga qabul qilgan tadbirkorlik subyektlari\n\nImtiyoz: Ish o‘rinlari va sharoitlarini nogironligi bo‘lgan xodimlarga moslashtirish uchun sarflangan xarajatlar qoplab beriladi.",
        "description_ru": "Кому: Предприниматели, трудоустроившие женщин с инвалидностью из «Женской тетради»\n\nЛьгота: Покрытие расходов на адаптацию рабочих мест и условий труда под нужды работников.",
        "amount_uz": "Xarajatlarning belgilangan qismi qoplanadi",
        "amount_ru": "Возмещение установленной части расходов",
        "organization_uz": "Kambag‘allikni qisqartirish va bandlik vazirligi, Oila va xotin-qizlar qo‘mitasi",
        "organization_ru": "Министерство сокращения бедности и занятости, Комитет семьи и женщин",
        "legal_basis_uz": "Vazirlar Mahkamasining 145-son qarori (31.03.2022-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 145 от 31.03.2022 г.",
        "lex_url": "https://lex.uz/docs/-5937968",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": True,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) Kambag‘allikni qisqartirish va bandlik bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, xodim bilan tuzilgan mehnat shartnomasi, moslashtirish xarajatlari smetasi va to‘lov hujjatlari.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.mehnat.uz portali orqali yoki bandlik bo‘limiga bevosita yozma murojaat bilan.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 10 ish kunida o‘rganilib, mablag‘ tadbirkor hisob raqamiga o‘tkaziladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-145.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный отдел сокращения бедности и занятости.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, трудовой договор с работником, смета и подтверждающие платежные документы.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал my.mehnat.uz или письменным обращением.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 10 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 145."
    },
    94: {
        "category": "education",
        "title_uz": "Ko‘zi ojiz abituriyentlarni OTMga imtiyozli qabul qilish",
        "title_ru": "Льготный прием незрячих абитуриентов в высшие образовательные учреждения",
        "description_uz": "Kimlarga: Maxsus maktab-internatlarni tamomlagan ko‘zi ojiz abituriyentlar\n\nImtiyoz: Oliy ta’lim muassasalariga qabulda ular uchun alohida imtihonlar o‘tkaziladi va davlat granti asosida qo‘shimcha kvota beriladi.",
        "description_ru": "Кому: Незрячие абитуриенты, окончившие специализированные школы-интернаты\n\nЛьгота: Проведение отдельных экзаменов и зачисление на основе государственного гранта.",
        "amount_uz": "Davlat granti asosida imtiyozli qabul",
        "amount_ru": "Льготное поступление на основе государственного гранта",
        "organization_uz": "Oliy ta’lim, fan va innovatsiyalar vazirligi, Bilim va malakalarni baholash agentligi",
        "organization_ru": "Министерство высшего образования, науки и инноваций, Агентство оценки знаний",
        "legal_basis_uz": "Vazirlar Mahkamasining 393-son qarori (20.06.2017-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 393 от 20.06.2017 г.",
        "lex_url": "https://lex.uz/docs/-3245415",
        "mygov_url": "https://my.uzbmb.uz",
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False, "disability_state": "vision",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nBilim va malakalarni baholash agentligi (my.uzbmb.uz) yoki tanlangan OTM qabul komissiyasiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nPasport/ID-karta, attestat/diplom, ko‘rish bo‘yicha I yoki II guruh nogironlik ma’lumotnomasi va brayl yozuvini bilish to‘g‘risida ma’lumot.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.uzbmb.uz yoki my.gov.uz portali orqali onlayn ro‘yxatdan o‘tiladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nImtihonlar qabul mavsumida alohida jadval asosida o‘tkaziladi. Xizmat bepul.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-393.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ Агентство по оценке знаний (my.uzbmb.uz) или в приемную комиссию выбранного вуза.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт/ID-карта, аттестат/диплом, справка об инвалидности по зрению (I или II группа).<br/><br/>🌐 <b>Способ обращения</b>\nВ онлайн-режиме через my.uzbmb.uz или my.gov.uz.<br/><br/>⏱ <b>Срок рассмотрения</b>\nЭкзамены проводятся в период приема по отдельному графику. Услуга бесплатна.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 393."
    },
    101: {
        "category": "transport",
        "title_uz": "Avtoturargohlarda nogironlar transporti uchun bepul to‘xtash joylari",
        "title_ru": "Бесплатные парковочные места для транспорта лиц с инвалидностью",
        "description_uz": "Kimlarga: I va II guruh nogironligi bo‘lgan haydovchilar hamda ularni tashuvchi transport vositalari\n\nImtiyoz: Bozorlar, savdo majmualari va jamoat joylari yaqinidagi barcha avtoturargohlarda kamida 10% joylar nogironlar transporti uchun ajratiladi va to‘xtash bepul hisoblanadi.",
        "description_ru": "Кому: Водители с инвалидностью I и II групп и лица, перевозящие их\n\nЛьгота: На всех автостоянках у рынков и ТЦ выделяется не менее 10% бесплатных мест для их транспорта.",
        "amount_uz": "Avtoturargohlarda bepul to‘xtash (joylarning kamida 10 foizi)",
        "amount_ru": "Бесплатная парковка (не менее 10% мест)",
        "organization_uz": "Ichki ishlar vazirligi, Transport vazirligi, Mahalliy hokimliklar",
        "organization_ru": "Министерство внутренних дел, Министерство транспорта, Местные хокимияты",
        "legal_basis_uz": "Adliya vazirligida ro‘yxatdan o‘tgan 3048-son buyruq (07.08.2018-y.)",
        "legal_basis_ru": "Приказ, рег. Минюстом № 3048 от 07.08.2018 г.",
        "lex_url": "https://lex.uz/docs/-3852028",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nAvtoturargoh ma’muriyatiga yoki Ichki ishlar organi YHXX xodimlariga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nHaydovchilik guvohnomasi, texnik pasport, «Nogiron» tanish belgisi va TJEK nogironlik ma’lumotnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nAvtotransport vositasida maxsus «Nogiron» belgisini o‘rnatgan holda to‘g‘ridan-to‘g‘ri joylashish orqali.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nDarhol to‘xtash joyidan bepul foydalanish ta’minlanadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nIdoraviy ro‘yxat raqami 3048.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nК администрации автостоянки или сотрудникам СБДД МВД.<br/><br/>📄 <b>Какие документы требуются?</b>\nВодительское удостоверение, техпаспорт, знак «Инвалид» и справка об инвалидности ВТЭК.<br/><br/>🌐 <b>Способ обращения</b>\nНепосредственно при въезде на автостоянку со знаком «Инвалид».<br/><br/>⏱ <b>Срок рассмотрения</b>\nПредоставляется незамедлительно и бесплатно.<br/><br/>⚖️ <b>Правовая основа</b>\nРег. № 3048."
    },
    102: {
        "category": "education",
        "title_uz": "Alohida ta’lim ehtiyojli bolalar ota-onalariga axborot va maslahat xizmati",
        "title_ru": "Консультационные услуги родителям детей с особыми образовательными потребностями",
        "description_uz": "Kimlarga: Jismoniy, aqliy, sensor yoki ruhiy nuqsonlari bo‘lgan bolalarning ota-onalari\n\nImtiyoz: Mavjud ta’lim shakllari hamda Psixologik-tibbiy-pedagogik komissiya (PTPK) faoliyati yuzasidan bepul axborot va konsultatsiya beriladi.",
        "description_ru": "Кому: Родители детей с физическими, умственными, сенсорными или психическими нарушениями\n\nЛьгота: Бесплатное информирование и консультации по формам обучения и деятельности ПМПК.",
        "amount_uz": "Bepul axborot va metodik maslahat",
        "amount_ru": "Бесплатные консультации",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» ijtimoiy xizmatlar markazlari",
        "organization_ru": "Национальное агентство социальной защиты, Центры социальных услуг «Инсон»",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markaziga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning shaxsini tasdiqlovchi hujjati, bolaning tug‘ilganlik guvohnomasi va tibbiy tashxis ma’lumotlari.<br/><br/>🌐 <b>Murojaat usuli</b>\n«Inson» markaziga bevosita borib yoki ijtimoiy xodim orqali murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nMaslahat va yo‘naltirish murojaat kuni darhol amalga oshiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный (городской) центр социальных услуг «Инсон».<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт родителя, свидетельство о рождении ребенка и медицинские выписки.<br/><br/>🌐 <b>Способ обращения</b>\nНепосредственно в центре «Инсон» или через социального работника.<br/><br/>⏱ <b>Срок рассмотрения</b>\nКонсультация оказывается в день обращения.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    103: {
        "category": "other",
        "title_uz": "Nogironligi bor shaxsga qarab turish haqiqiy holatini tekshirish dalolatnomasi",
        "title_ru": "Оформление акта проверки фактического ухода за лицом с инвалидностью",
        "description_uz": "Kimlarga: I guruh nogironligi bo‘lgan shaxsga yoki 18 yoshgacha nogiron bolaga qarab turuvchilar\n\nImtiyoz: Qarab turish haqiqiy holatini tasdiqlovchi dalolatnoma rasmiylashtirilib, qarab turuvchiga mehnat staji va nafaqalar hisoblanishi ta’minlanadi.",
        "description_ru": "Кому: Лица, осуществляющие уход за лицом с инвалидностью I группы или ребенком с инвалидностью до 18 лет\n\nЛьгота: Составление акта подтверждения ухода для начисления стажа и пособий.",
        "amount_uz": "Bepul dalolatnoma rasmiylashtirish",
        "amount_ru": "Бесплатное составление акта",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» markazlari, MFY",
        "organization_ru": "Национальное агентство социальной защиты, Центры «Инсон», СГМ",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": False, "for_third_group": False, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markazi yoki mahalladagi ijtimoiy xodimga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nAriza, pasport, I guruh nogironlik ma’lumotnomasi va tibbiy xulosa.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.gov.uz orqali yoki «Inson» markaziga bevosita yozma ariza bilan.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nIjtimoiy xodim 3 ish kunida xonadonga borib dalolatnoma tuzadi va tizimga kiritadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или к социальному работнику в махалле.<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление, паспорт, справка об инвалидности I группы и медицинское заключение.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез my.gov.uz или письменным заявлением в центр «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nСоциальный работник составляет акт с выездом на дом в течение 3 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    104: {
        "category": "education",
        "title_uz": "PTPK xulosasini olish uchun ariza topshirish va ko‘rikdan o‘tish",
        "title_ru": "Подача заявления и прохождение комиссии ПМПК",
        "description_uz": "Kimlarga: Alohida ta’lim ehtiyojlari bo‘lgan bolalar va ularning ota-onalari\n\nImtiyoz: Psixologik-tibbiy-pedagogik komissiya (PTPK) xulosasini bepul olish va mos ta’lim dasturiga yo‘llanma beriladi.",
        "description_ru": "Кому: Дети с особыми образовательными потребностями и их родители\n\nЛьгота: Бесплатное прохождение ПМПК и получение заключения для направления на обучение.",
        "amount_uz": "Davlat tomonidan bepul amalga oshiriladi",
        "amount_ru": "Бесплатно государством",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» markazlari, PTPK",
        "organization_ru": "Национальное агентство социальной защиты, Центры «Инсон», ПМПК",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» markazi yoki YaIDXP (my.gov.uz) orqali PTPKga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning pasporti, bolaning tug‘ilganlik guvohnomasi va ambulatoriya kartasi ko‘chirmasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.gov.uz orqali elektron ariza yuboriladi yoki «Inson» markazida ro‘yxatdan o‘tiladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nKomissiya ko‘rigi 5 ish kunida o‘tkaziladi va xulosa taqdim etiladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или через my.gov.uz в комиссию ПМПК.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт родителя, свидетельство о рождении ребенка и выписка из амбулаторной карты.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал my.gov.uz или непосредственно в центре «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nКомиссия проводится в течение 5 рабочих дней.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    106: {
        "category": "health_rehab",
        "title_uz": "Parasport bilan shug‘ullanish bo‘yicha sport majmualariga yo‘naltirish",
        "title_ru": "Направление в спортивные комплексы для занятий параспортом",
        "description_uz": "Kimlarga: Parasport bilan shug‘ullanish istagida bo‘lgan nogironligi bor shaxslar\n\nImtiyoz: Tasnif qoidalari va tibbiy tavsiyalarga asosan davlat sport inshootlariga bepul yo‘llanma beriladi.",
        "description_ru": "Кому: Лица с инвалидностью, желающие заниматься параспортом\n\nЛьгота: Бесплатное направление в государственные спортивные объекты по правилам параспорта.",
        "amount_uz": "Bepul yo‘llanma va mashg‘ulotlar",
        "amount_ru": "Бесплатное направление и занятия",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, O‘zbekiston Milliy paralimpiya qo‘mitasi",
        "organization_ru": "Национальное агентство социальной защиты, Национальный паралимпийский комитет",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» markazi yoki Paralimpiya qo‘mitasi hududiy bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat, nogironlik ma’lumotnomasi va sport bilan shug‘ullanishga ruxsat beruvchi tibbiy xulosa.<br/><br/>🌐 <b>Murojaat usuli</b>\n«Inson» markazidagi ijtimoiy xodim orqali ariza topshiriladi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 3 ish kuni ichida ko‘rib chiqilib, sport ob’ektiga yo‘llanma beriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или в региональное отделение Паралимпийского комитета.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт, справка об инвалидности и медицинское заключение о допуске к спорту.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез социального работника в центре «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 3 рабочих дней выдается направление.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    107: {
        "category": "health_rehab",
        "title_uz": "Kattalar uchun «Muruvvat» internat uylariga joylashtirish murojaatlarini qabul qilish",
        "title_ru": "Прием обращений о размещении в дома-интернаты «Мурувват» для взрослых",
        "description_uz": "Kimlarga: Ruhiyatida og‘ir nuqsoni bor, o‘zgalar parvarishiga muhtoj I va II guruh nogironligi bo‘lgan shaxslar (18 yoshdan katta)\n\nImtiyoz: «Muruvvat» internat uylariga doimiy yoki vaqtinchalik joylashtirish va to‘liq davlat ta’minotida ijtimoiy-tibbiy xizmatlar ko‘rsatiladi.",
        "description_ru": "Кому: Лица с инвалидностью I и II групп старше 18 лет с тяжелыми психическими расстройствами\n\nЛьгота: Постоянное или временное размещение в домах «Мурувват» на полном гособеспечении.",
        "amount_uz": "To‘liq davlat ta’minotida bepul xizmat",
        "amount_ru": "Полное государственное обеспечение",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» markazlari",
        "organization_ru": "Национальное агентство социальной защиты, Центры «Инсон»",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": False, "for_parent": False, "is_for_organization": False, "disability_state": "mental",
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markaziga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nQonuniy vakil arizasi, shaxsni tasdiqlovchi hujjat, TJEK nogironlik ma’lumotnomasi va psixonevrologik dispanser xulosasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.gov.uz portali orqali yoki «Inson» markaziga bevosita murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nHujjatlar to‘liq o‘rganilgach, 10 ish kunida yo‘llanma beriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр социальных услуг «Инсон».<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление законного представителя, паспорт, справка ВТЭК и заключение психоневрологического диспансера.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез my.gov.uz или непосредственно в центре «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 10 рабочих дней оформляется направление.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    108: {
        "category": "health_rehab",
        "title_uz": "Nogiron bolalar uchun tuman tibbiyot birlashmasida bepul reabilitatsiya tadbirlari",
        "title_ru": "Бесплатная реабилитация детей с инвалидностью в районном медобъединении",
        "description_uz": "Kimlarga: Nogironligi bo‘lgan bolalar va ularning oilalari\n\nImtiyoz: Yosh xususiyatlari va moyilliklariga mos ravishda tuman tibbiyot birlashmasida bepul reabilitatsiya tadbirlari o‘tkaziladi.",
        "description_ru": "Кому: Дети с инвалидностью и их семьи\n\nЛьгота: Бесплатные реабилитационные мероприятия в районном медобъединении в соответствии с возрастом.",
        "amount_uz": "Bepul tibbiy reabilitatsiya",
        "amount_ru": "Бесплатная медицинская реабилитация",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, Tuman tibbiyot birlashmasi",
        "organization_ru": "Национальное агентство социальной защиты, Районное медицинское объединение",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman markaziy poliklinikasiga yoki «Inson» ijtimoiy xizmatlar markaziga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning pasporti, bolaning tug‘ilganlik guvohnomasi va yakka tartibdagi reabilitatsiya dasturi (YARD).<br/><br/>🌐 <b>Murojaat usuli</b>\nOilaviy shifokor yo‘llanmasi asosida tuman tibbiyot birlashmasiga murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nYo‘llanma berilgach, navbat asosida 3 ish kunida reabilitatsiya boshlanadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районную центральную поликлинику или центр «Инсон».<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт родителя, свидетельство о рождении ребенка и индивидуальная программа реабилитации (ИПР).<br/><br/>🌐 <b>Способ обращения</b>\nПо направлению семейного врача.<br/><br/>⏱ <b>Срок рассмотрения</b>\nРеабилитация начинается в течение 3 рабочих дней в порядке очереди.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    109: {
        "category": "health_rehab",
        "title_uz": "Sport majmualarida basseyn va LFK zallaridan bepul foydalanish",
        "title_ru": "Бесплатное посещение бассейнов и залов ЛФК в спорткомплексах",
        "description_uz": "Kimlarga: Nogironligi bo‘lgan shaxslar va bolalar\n\nImtiyoz: Davlat sport majmualarida basseyn-davolash va jismoniy tarbiya (LFK) zallaridan bepul foydalanish tashkil etiladi.",
        "description_ru": "Кому: Лица и дети с инвалидностью\n\nЛьгота: Бесплатное посещение бассейнов и залов лечебной физкультуры (ЛФК) в государственных спорткомплексах.",
        "amount_uz": "Bepul foydalanish huquqi",
        "amount_ru": "Право бесплатного посещения",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, Sport vazirligi",
        "organization_ru": "Национальное агентство социальной защиты, Министерство спорта",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markazi yoki davlat sport majmuasi ma’muriyatiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat, nogironlik to‘g‘risida ma’lumotnoma va LFK/basseynga ruxsat beruvchi tibbiy ma’lumotnoma.<br/><br/>🌐 <b>Murojaat usuli</b>\n«Inson» markazi yo‘llanmasi bilan sport ob’ektiga murojaat qilinadi.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 2 ish kunida ko‘rib chiqilib, bepul abonement taqdim etiladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или в администрацию государственного спорткомплекса.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт, справка об инвалидности и медсправка с допуском к ЛФК/бассейну.<br/><br/>🌐 <b>Способ обращения</b>\nПо направлению центра «Инсон» в спортивный объект.<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 2 рабочих дней оформляется бесплатный абонемент.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    110: {
        "category": "education",
        "title_uz": "PTPK komissiyasi tekshiruvidan o‘tkazish va xulosa taqdim etish",
        "title_ru": "Освидетельствование комиссией ПМПК и предоставление заключения",
        "description_uz": "Kimlarga: Alohida ta’lim ehtiyojlari bo‘lgan bolalar\n\nImtiyoz: Psixologik-tibbiy-pedagogik komissiya tekshiruvidan bepul o‘tkazish hamda keyingi yig‘ilish bo‘yicha to‘liq axborot beriladi.",
        "description_ru": "Кому: Дети с особыми образовательными потребностями\n\nЛьгота: Бесплатное освидетельствование комиссией ПМПК и предоставление рекомендаций по обучению.",
        "amount_uz": "Davlat tomonidan bepul xizmat",
        "amount_ru": "Бесплатно государством",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» ijtimoiy xizmatlar markazi",
        "organization_ru": "Национальное агентство социальной защиты, Центр «Инсон»",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": True, "for_child": True, "for_parent": True, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» markazi yoki YaIDXP (my.gov.uz) orqali murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning pasporti, bolaning tug‘ilganlik guvohnomasi va tibbiy tashxis ma’lumotnomasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.gov.uz portali orqali yoki «Inson» markazida qabulga yozilish orqali.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nKomissiya navbatdagi majlisida 5 ish kunida ko‘rib chiqadi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или через Единый портал my.gov.uz.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт родителя, свидетельство о рождении ребенка и медицинские выписки.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез портал my.gov.uz или записью на прием в центре «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 5 рабочих дней на очередном заседании комиссии.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    111: {
        "category": "labor",
        "title_uz": "Mehnatga layoqatli nogironlarni bandligini ta’minlash yoki kasbga tayyorlash",
        "title_ru": "Трудоустройство или профессиональное обучение трудоспособных лиц с инвалидностью",
        "description_uz": "Kimlarga: Mehnatga layoqatli nogironligi bo‘lgan shaxslar\n\nImtiyoz: TJEK tavsiyasi va yo‘llanmasiga asosan bandligini ta’minlash yoki tuman kambag‘allikni qisqartirish bo‘limi orqali bepul kasbga o‘rgatish amalga oshiriladi.",
        "description_ru": "Кому: Трудоспособные лица с инвалидностью\n\nЛьгота: Трудоустройство по рекомендации ВТЭК или бесплатное профессиональное обучение через отдел занятости.",
        "amount_uz": "Kafolatlangan bandlik va bepul o‘qitish",
        "amount_ru": "Гарантированная занятость и бесплатное обучение",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, Kambag‘allikni qisqartirish va bandlik bo‘limi",
        "organization_ru": "Национальное агентство социальной защиты, Отдел сокращения бедности и занятости",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": "https://my.mehnat.uz",
        "for_first_group": False, "for_second_group": True, "for_third_group": True, "for_child": False, "for_parent": False, "is_for_organization": False,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» markazi yoki Kambag‘allikni qisqartirish va bandlik bo‘limiga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nShaxsni tasdiqlovchi hujjat, TJEK tavsiyanomasi va ma’lumoti haqidagi hujjat.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.mehnat.uz orqali yoki «Inson» markazi ijtimoiy xodimi yo‘llanmasi bilan.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nAriza 5 ish kuni ichida ko‘rib chiqilib, ish o‘rni yoki bepul o‘quv kursi taklif etiladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный центр «Инсон» или в отдел сокращения бедности и занятости.<br/><br/>📄 <b>Какие документы требуются?</b>\nПаспорт, трудовая рекомендация ВТЭК и документ об образовании.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез my.mehnat.uz или по направлению центра «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 5 рабочих дней предлагается вакансия или учебный курс.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    },
    112: {
        "category": "health_rehab",
        "title_uz": "Bolalar uchun «Muruvvat» internat uylariga joylashtirish murojaatlarini qabul qilish",
        "title_ru": "Прием обращений о размещении в дома-интернаты «Мурувват» для детей",
        "description_uz": "Kimlarga: O‘zgalar parvarishiga muhtoj 4 yoshdan 18 yoshgacha bo‘lgan nogironligi bor bolalar\n\nImtiyoz: Bolalar uchun «Muruvvat» internat uylariga doimiy yoki kunduzgi parvarishlash uchun joylashtirish va to‘liq davlat ta’minotida reabilitatsiya xizmatlari ko‘rsatiladi.",
        "description_ru": "Кому: Дети с инвалидностью в возрасте от 4 до 18 лет, нуждающиеся в постоянном уходе\n\nЛьгота: Размещение в детские дома-интернаты «Мурувват» на полное государственное обеспечение.",
        "amount_uz": "To‘liq davlat ta’minotida bepul xizmat",
        "amount_ru": "Полное государственное обеспечение",
        "organization_uz": "Ijtimoiy himoya milliy agentligi, «Inson» ijtimoiy xizmatlar markazlari",
        "organization_ru": "Национальное агентство социальной защиты, Центры социальных услуг «Инсон»",
        "legal_basis_uz": "Vazirlar Mahkamasining 539-son qarori (14.10.2023-y.)",
        "legal_basis_ru": "Постановление Кабинета Министров № 539 от 14.10.2023 г.",
        "lex_url": "https://lex.uz/docs/-6634898",
        "mygov_url": None,
        "for_first_group": True, "for_second_group": True, "for_third_group": False, "for_child": True, "for_parent": True, "is_for_organization": False, "max_age": 18,
        "guide_uz": "🏢 <b>Kimga murojaat qilinadi?</b>\nTuman (shahar) «Inson» ijtimoiy xizmatlar markaziga murojaat qilinadi.<br/><br/>📄 <b>Qanday hujjatlar talab etiladi?</b>\nOta-onaning arizasi, bolaning tug‘ilganlik guvohnomasi, TJEK nogironlik ma’lumotnomasi va tibbiy karta ko‘chirmasi.<br/><br/>🌐 <b>Murojaat usuli</b>\nmy.gov.uz orqali yoki «Inson» markaziga bevosita yozma murojaat bilan.<br/><br/>⏱ <b>Ko‘rib chiqish muddati</b>\nHujjatlar to‘liq bo‘lgach, 10 ish kunida yo‘llanma rasmiylashtiriladi.<br/><br/>⚖️ <b>Huquqiy asos</b>\nVMQ-539.",
        "guide_ru": "🏢 <b>Куда обращаться?</b>\nВ районный (городской) центр социальных услуг «Инсон».<br/><br/>📄 <b>Какие документы требуются?</b>\nЗаявление родителей, свидетельство о рождении, справка ВТЭК и выписка из медицинской карты.<br/><br/>🌐 <b>Способ обращения</b>\nЧерез my.gov.uz или в центр «Инсон».<br/><br/>⏱ <b>Срок рассмотрения</b>\nВ течение 10 рабочих дней оформляется направление.<br/><br/>⚖️ <b>Правовая основа</b>\nПКМ № 539."
    }
}


def build_112_dataset():
    final_items = []

    for idx in range(1, 113):
        adv = advice_items[idx - 1]
        
        if idx in DIRECT_MAP:
            old_order = DIRECT_MAP[idx]
            old_item = dict(seed_by_order[old_order])
            
            # Update order_index and align with advice.uz
            old_item["order_index"] = idx
            
            # Align organization if advice.uz has updated names
            adv_org = adv.get("organization")
            if adv_org and len(adv_org) > 3:
                old_item["organization_uz"] = adv_org
                old_item["organization_oz"] = lat_to_cyr(adv_org)
            
            final_items.append(old_item)
        else:
            custom = CUSTOM_ITEMS[idx]
            
            # Generate Cyrillic fields
            title_oz = lat_to_cyr(custom["title_uz"])
            desc_oz = lat_to_cyr(custom["description_uz"])
            amount_oz = lat_to_cyr(custom["amount_uz"]) if custom.get("amount_uz") else None
            org_oz = lat_to_cyr(custom["organization_uz"]) if custom.get("organization_uz") else None
            legal_oz = lat_to_cyr(custom["legal_basis_uz"]) if custom.get("legal_basis_uz") else None
            guide_oz = lat_to_cyr_html(custom["guide_uz"])

            item = {
                "order_index": idx,
                "category": custom["category"],
                "for_first_group": custom.get("for_first_group", True),
                "for_second_group": custom.get("for_second_group", True),
                "for_third_group": custom.get("for_third_group", False),
                "for_child": custom.get("for_child", False),
                "for_parent": custom.get("for_parent", False),
                "is_for_organization": custom.get("is_for_organization", False),
                "min_age": custom.get("min_age"),
                "max_age": custom.get("max_age"),
                "gender": custom.get("gender"),
                "disability_state": custom.get("disability_state"),
                "title_uz": custom["title_uz"],
                "description_uz": custom["description_uz"],
                "amount_uz": custom.get("amount_uz"),
                "organization_uz": custom.get("organization_uz"),
                "legal_basis_uz": custom.get("legal_basis_uz"),
                "title_oz": title_oz,
                "description_oz": desc_oz,
                "amount_oz": amount_oz,
                "organization_oz": org_oz,
                "legal_basis_oz": legal_oz,
                "title_ru": custom.get("title_ru"),
                "description_ru": custom.get("description_ru"),
                "amount_ru": custom.get("amount_ru"),
                "organization_ru": custom.get("organization_ru"),
                "legal_basis_ru": custom.get("legal_basis_ru"),
                "guide_uz": custom["guide_uz"],
                "guide_oz": guide_oz,
                "guide_ru": custom["guide_ru"],
                "lex_url": custom.get("lex_url"),
                "mygov_url": custom.get("mygov_url")
            }
            final_items.append(item)

    assert len(final_items) == 112, f"Expected 112 items, got {len(final_items)}"
    assert [x["order_index"] for x in final_items] == list(range(1, 113))

    # Write to OUTPUT_FILE
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_items, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated 112 benefits in {OUTPUT_FILE}")

    # Also sync to SEED_FILE so backwards compatibility is maintained
    with open(SEED_FILE, "w", encoding="utf-8") as f:
        json.dump(final_items, f, ensure_ascii=False, indent=2)
    print(f"Synced to {SEED_FILE}")


if __name__ == "__main__":
    build_112_dataset()
