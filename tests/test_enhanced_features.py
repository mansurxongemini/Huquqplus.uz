"""
tests/test_enhanced_features.py
Tests verifying the new requirements:
1. Guide format clean, readable, no mechanical "1-blok:" labels, no static boilerplate
2. Guide button renamed to "📝 Qanday ariza topshiriladi" (across uz, oz, ru)
3. Lex.uz button removed from inline keyboard and placed into card text as numbered HTML links
4. Dynamic online portal application buttons (yoshlardaftari.uz, my.gov.uz, etc.)
5. Admin panel edit interface for benefits (✏️ Tahrirlash, build_benefit_edit_menu, field editing)
"""

import html
import pytest
from src.app.keyboards import (
    get_benefit_detail_keyboard,
    get_benefit_guide_keyboard,
    get_portal_button_label,
)
from src.routes.aiogram.benefits import (
    format_benefit_card,
    format_guide_html,
    format_legal_basis_section,
    split_legal_basis,
)
from src.routes.aiogram.admin import (
    build_admin_benefits_page,
    build_benefit_edit_menu,
)
from src.models.benefit import Benefit, BenefitCategory


class MockBenefit:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.order_index = kwargs.get("order_index", 1)
        self.category = kwargs.get("category", BenefitCategory.TAX_FEE)
        self.title_uz = kwargs.get("title_uz", "Yer solig‘i imtiyozi")
        self.title_oz = kwargs.get("title_oz", "Ер солиғи имтиёзи")
        self.title_ru = kwargs.get("title_ru", "Льгота по земельному налогу")
        self.description_uz = kwargs.get("description_uz", "Kimlarga: Nogironligi bo‘lgan shaxslar\n\nMiqdori: 50 foiz")
        self.description_oz = kwargs.get("description_oz", "Кимларга: Ногиронлиги бўлган шахслар\n\nМиқдори: 50 фоиз")
        self.description_ru = kwargs.get("description_ru", "Кому: Лица с инвалидностью\n\nРазмер: 50 процентов")
        self.amount_uz = kwargs.get("amount_uz", "50 foiz chegirma")
        self.amount_oz = kwargs.get("amount_oz", "50 фоиз чегирма")
        self.amount_ru = kwargs.get("amount_ru", "Скидка 50 процентов")
        self.organization_uz = kwargs.get("organization_uz", "Soliq qo‘mitasi")
        self.organization_oz = kwargs.get("organization_oz", "Солиқ қўмитаси")
        self.organization_ru = kwargs.get("organization_ru", "Налоговый комитет")
        self.legal_basis_uz = kwargs.get("legal_basis_uz", "Soliq kodeksi 429-moddasi")
        self.legal_basis_oz = kwargs.get("legal_basis_oz", "Солиқ кодекси 429-моддаси")
        self.legal_basis_ru = kwargs.get("legal_basis_ru", "Налоговый кодекс, статья 429")
        self.lex_url = kwargs.get("lex_url", "https://lex.uz/docs/4674902")
        self.mygov_url = kwargs.get("mygov_url", "https://my.gov.uz/uz/service/972")
        self.guide_uz = kwargs.get("guide_uz", "🏢 <b>Kimga murojaat qilinadi?</b>\nDXM\n\n📄 <b>Qanday hujjatlar talab etiladi?</b>\nPasport")
        self.guide_oz = kwargs.get("guide_oz", "🏢 <b>Кимга мурожаат қилинади?</b>\nДХМ\n\n📄 <b>Қандай ҳужжатлар талаб этилади?</b>\nПаспорт")
        self.for_first_group = kwargs.get("for_first_group", True)
        self.for_second_group = kwargs.get("for_second_group", True)
        self.for_third_group = kwargs.get("for_third_group", False)
        self.for_child = kwargs.get("for_child", True)
        self.for_parent = kwargs.get("for_parent", False)
        self.is_for_organization = kwargs.get("is_for_organization", False)
        self.is_active = kwargs.get("is_active", True)


def test_guide_button_renamed_to_qanday_ariza():
    """Requirement 2: 'Qadam-baqadam yo'riqnoma' changed to 'Qanday ariza topshiriladi'."""
    b = MockBenefit()
    # Uzbek Latin
    kb_uz = get_benefit_detail_keyboard(1, "tax_fee", 1, lang="uz", benefit=b)
    all_btn_texts_uz = [btn.text for row in kb_uz.inline_keyboard for btn in row]
    assert "📝 Qanday ariza topshiriladi" in all_btn_texts_uz
    assert not any("Qadam-baqadam" in t for t in all_btn_texts_uz)

    # Uzbek Cyrillic
    kb_oz = get_benefit_detail_keyboard(1, "tax_fee", 1, lang="oz", benefit=b)
    all_btn_texts_oz = [btn.text for row in kb_oz.inline_keyboard for btn in row]
    assert "📝 Қандай ариза топширилади" in all_btn_texts_oz
    assert not any("Қадам-бақадам" in t for t in all_btn_texts_oz)

    # Russian
    kb_ru = get_benefit_detail_keyboard(1, "tax_fee", 1, lang="ru", benefit=b)
    all_btn_texts_ru = [btn.text for row in kb_ru.inline_keyboard for btn in row]
    assert "📝 Как подать заявление" in all_btn_texts_ru
    assert not any("Пошаговая" in t for t in all_btn_texts_ru)


def test_lex_uz_button_removed_from_keyboards():
    """Requirement 3: Lex.uz button removed completely from inline keyboards."""
    b = MockBenefit(lex_url="https://lex.uz/docs/4674902")

    # Detail keyboard
    kb_detail = get_benefit_detail_keyboard(1, "tax_fee", 1, lang="uz", benefit=b)
    all_detail_texts = [btn.text for row in kb_detail.inline_keyboard for btn in row]
    assert not any("Lex.uz" in t or "қонун" in t.lower() or "qonun" in t.lower() for t in all_detail_texts)
    all_detail_urls = [btn.url for row in kb_detail.inline_keyboard for btn in row if btn.url]
    assert not any("lex.uz" in (u or "") for u in all_detail_urls)

    # Guide keyboard
    kb_guide = get_benefit_guide_keyboard(1, "tax_fee", 1, lang="uz", benefit=b)
    all_guide_texts = [btn.text for row in kb_guide.inline_keyboard for btn in row]
    assert not any("Lex.uz" in t or "қонун" in t.lower() or "qonun" in t.lower() for t in all_guide_texts)
    all_guide_urls = [btn.url for row in kb_guide.inline_keyboard for btn in row if btn.url]
    assert not any("lex.uz" in (u or "") for u in all_guide_urls)


def test_portal_button_dynamic_naming():
    """Requirement 5: Online application button dynamically adapts to URL destination."""
    # yoshlardaftari.uz
    assert get_portal_button_label("https://yoshlardaftari.uz", "uz") == "🌐 Yoshlar daftari orqali ariza"
    assert get_portal_button_label("https://yoshlardaftari.uz", "oz") == "🌐 Ёшлар дафтари орқали ариза"
    assert get_portal_button_label("https://yoshlardaftari.uz", "ru") == "🌐 Заявка через Yoshlar daftari"

    # my.gov.uz
    assert get_portal_button_label("https://my.gov.uz/uz/service/972", "uz") == "🌐 My.gov.uz orqali ariza"
    assert get_portal_button_label("https://my.gov.uz/uz/service/972", "oz") == "🌐 My.gov.uz орқали ариза"
    assert get_portal_button_label("https://my.gov.uz/uz/service/972", "ru") == "🌐 Заявка на My.gov.uz"

    # uzairways.com
    assert get_portal_button_label("https://www.uzairways.com", "uz") == "🌐 UzAirways orqali chipta"

    # eticket.railway.uz
    assert get_portal_button_label("https://eticket.railway.uz", "uz") == "🌐 Temir yo‘l chiptasi (eticket)"

    # Keyboard test with yoshlardaftari.uz
    b_yd = MockBenefit(mygov_url="https://yoshlardaftari.uz")
    kb_yd = get_benefit_detail_keyboard(55, "youth", 1, lang="uz", benefit=b_yd)
    yd_texts = [btn.text for row in kb_yd.inline_keyboard for btn in row]
    assert "🌐 Yoshlar daftari orqali ariza" in yd_texts
    assert not any("my.gov.uz" in t for t in yd_texts)


def test_legal_basis_numbered_html_in_card():
    """Requirement 3: Legal basis displayed in card text with numbers and HTML links."""
    # 1 document
    b1 = MockBenefit(
        legal_basis_uz="Prezident Farmoni PF-6195 (25.03.2021)",
        lex_url="https://lex.uz/docs/-4674902#-6032725"
    )
    card_text1 = format_benefit_card(b1, "uz")
    assert "⚖️ <b>Asos bo‘luvchi hujjat:</b>" in card_text1
    assert '1. <a href="https://lex.uz/docs/-4674902#-6032725">Prezident Farmoni PF-6195 (25.03.2021)</a>' in card_text1

    # Multiple documents
    b2 = MockBenefit(
        legal_basis_uz="Qonun O‘RQ-641 (15.10.2020) 34-moddasi, Vazirlar Mahkamasining 253-son qarori (30.04.2024)",
        lex_url="https://lex.uz/docs/-5049511#-5054355"
    )
    card_text2 = format_benefit_card(b2, "uz")
    assert "⚖️ <b>Asos bo‘luvchi hujjat:</b>" in card_text2
    assert '1. <a href="https://lex.uz/docs/-5049511#-5054355">Qonun O‘RQ-641 (15.10.2020) 34-moddasi</a>' in card_text2
    assert "2." in card_text2
    assert "Vazirlar Mahkamasining 253-son qarori" in card_text2


def test_split_legal_basis_robustness():
    """Test splitting legal basis into discrete enactments."""
    s1 = "Soliq kodeksi 429-moddasi (6-qismi)"
    assert split_legal_basis(s1) == ["Soliq kodeksi 429-moddasi (6-qismi)"]

    s2 = "Prezident Farmoni PF-74 (18.02.2022) , Vazirlar Mahkamasining 119-son qarori (23.03.2023)"
    res2 = split_legal_basis(s2)
    assert len(res2) == 2
    assert "PF-74" in res2[0]
    assert "119-son" in res2[1]

    s3 = "Prezident Farmoni PF-213 (31.08.2022) ,"
    res3 = split_legal_basis(s3)
    assert len(res3) == 1
    assert "PF-213" in res3[0]


def test_format_guide_html_cleans_mechanical_labels_and_boilerplate():
    """Requirement 1 & 4: Mechanical '1-blok:' and static boilerplate stripped, clean HTML produced."""
    raw_guide = (
        "1-blok: 🏢 <b>Kimga murojaat qilinadi?</b>\n"
        "DXM markazi.\n\n"
        "2-blok: 📄 <b>Qanday hujjatlar talab etiladi?</b>\n"
        "ID-karta va ariza.\n"
        "<i>(Eslatma: «Yagona milliy ijtimoiy himoya», TIB, Pensiya jamg‘armasi ma’lumotlarini fuqarodan qog‘oz shaklida talab qilish qat’iyan taqiqlanadi).</i>\n\n"
        "3-blok: 🌐 <b>Murojaat usuli:</b>\n"
        "my.gov.uz orqali."
    )
    formatted = format_guide_html(raw_guide, "uz")
    assert "1-blok:" not in formatted
    assert "2-blok:" not in formatted
    assert "3-blok:" not in formatted
    assert "talab qilish qat’iyan taqiqlanadi" not in formatted
    assert "<br/><br/>" in formatted
    assert "🏢 <b>Kimga murojaat qilinadi?</b>" in formatted
    assert "📄 <b>Qanday hujjatlar talab etiladi?</b>" in formatted


def test_admin_panel_benefits_has_edit_button():
    """Requirement 6: Admin benefits list includes '✏️' button."""
    benefits = [MockBenefit(id=10, order_index=1), MockBenefit(id=11, order_index=2)]
    text, markup = build_admin_benefits_page(benefits, page=1, total_pages=1, total_count=2)
    all_btn_texts = [btn.text for row in markup.inline_keyboard for btn in row]
    assert "✏️" in all_btn_texts

    all_callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "admin:b_edit:10:1" in all_callbacks
    assert "admin:b_edit:11:1" in all_callbacks


def test_build_benefit_edit_menu_fields():
    """Requirement 6: Edit menu provides inline buttons for all benefit fields."""
    b = MockBenefit(id=42, title_uz="Subsidiyalangan ta'lim")
    text, markup = build_benefit_edit_menu(b, page=2)

    assert "Subsidiyalangan ta'lim" in html.unescape(text)
    assert "ID: 42" in text

    all_callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "admin:b_mod:42:title:2" in all_callbacks
    assert "admin:b_mod:42:category:2" in all_callbacks
    assert "admin:b_mod:42:audience:2" in all_callbacks
    assert "admin:b_mod:42:desc:2" in all_callbacks
    assert "admin:b_mod:42:amount:2" in all_callbacks
    assert "admin:b_mod:42:org:2" in all_callbacks
    assert "admin:b_mod:42:legal:2" in all_callbacks
    assert "admin:b_mod:42:lex:2" in all_callbacks
    assert "admin:b_mod:42:mygov:2" in all_callbacks
    assert "admin:b_mod:42:guide:2" in all_callbacks
    assert "admin:benefits_page:2" in all_callbacks


def test_build_benefit_audience_menu_toggles():
    """Admin can toggle target audience categories (groups, child, parent, org)."""
    from src.routes.aiogram.admin import build_benefit_audience_menu
    b = MockBenefit(
        id=7,
        title_uz="Test imtiyoz",
        for_first_group=True,
        for_second_group=False,
        for_third_group=True,
        for_child=False,
        for_parent=True,
        is_for_organization=False
    )
    text, markup = build_benefit_audience_menu(b, page=1)

    assert "Test imtiyoz" in text
    all_btns = {btn.callback_data: btn.text for row in markup.inline_keyboard for btn in row}

    assert "admin:b_aud_tog:7:first:1" in all_btns
    assert "✅" in all_btns["admin:b_aud_tog:7:first:1"]

    assert "admin:b_aud_tog:7:second:1" in all_btns
    assert "❌" in all_btns["admin:b_aud_tog:7:second:1"]

    assert "admin:b_aud_tog:7:third:1" in all_btns
    assert "✅" in all_btns["admin:b_aud_tog:7:third:1"]

    assert "admin:b_aud_tog:7:child:1" in all_btns
    assert "❌" in all_btns["admin:b_aud_tog:7:child:1"]

    assert "admin:b_aud_tog:7:parent:1" in all_btns
    assert "✅" in all_btns["admin:b_aud_tog:7:parent:1"]

    assert "admin:b_aud_tog:7:org:1" in all_btns
    assert "❌" in all_btns["admin:b_aud_tog:7:org:1"]

    assert "admin:b_edit:7:1" in all_btns


def test_split_legal_basis_with_article_continuation():
    """Do not split legal basis when comma is followed by article/clause continuation."""
    s1 = "Qonun (15.10.2020), 34-moddasi"
    res1 = split_legal_basis(s1)
    assert len(res1) == 1
    assert res1[0] == "Qonun (15.10.2020), 34-moddasi"

    s2 = "Prezident Farmoni (2021), 1-bandi"
    res2 = split_legal_basis(s2)
    assert len(res2) == 1
    assert res2[0] == "Prezident Farmoni (2021), 1-bandi"


def test_multi_enactments_accurate_lex_url_assignment():
    """Ensure multi-enactment benefits resolve correct URLs without cross-linking or false matches."""
    # Order 32: Doc 1 is O'RQ-641, Doc 2 is PQ-389. lex_url is for PQ-389.
    b32 = MockBenefit(
        legal_basis_uz="Qonun O‘RQ-641 (15.10.2020) 27-moddasi, Prezident Qarori PQ-389 (08.11.2024)",
        lex_url="https://lex.uz/docs/-7215989#-7216081"
    )
    card32 = format_benefit_card(b32, "uz")
    # Doc 1 (O'RQ-641) must link to -5049511
    assert '1. <a href="https://lex.uz/docs/-5049511">Qonun O‘RQ-641 (15.10.2020) 27-moddasi</a>' in card32
    # Doc 2 (PQ-389) must link to -7215989#-7216081
    assert '2. <a href="https://lex.uz/docs/-7215989#-7216081">Prezident Qarori PQ-389 (08.11.2024)</a>' in card32
    # Doc 1 must NOT be falsely linked to PQ-389
    assert '1. <a href="https://lex.uz/docs/-7215989#-7216081">' not in card32

    # Order 37: VMQ-264 must NOT falsely match PQ-64 (-7386982)
    b37 = MockBenefit(
        legal_basis_uz="Prezident Qarori PQ-3214 (26.02.2003) , Vazirlar Mahkamasining 264-son qarori -son (08.06.2004)",
        lex_url="https://lex.uz/docs/-170143#-6104868"
    )
    card37 = format_benefit_card(b37, "uz")
    assert "-7386982" not in card37
    assert "https://lex.uz/docs/-170143#-6104868" in card37


def test_uzbek_cyrillic_and_russian_enactment_resolution():
    """Ensure enactments in Uzbek Cyrillic (with special chars қ, ғ, ҳ, ў) and Russian resolve properly."""
    # Uzbek Cyrillic
    b_oz = MockBenefit(
        legal_basis_oz="Қонун ЎРҚ-641 (15.10.2020) 27-моддаси, Президент Қарори ПҚ-389 (08.11.2024)",
        lex_url="https://lex.uz/docs/-7215989#-7216081"
    )
    card_oz = format_benefit_card(b_oz, "oz")
    assert '1. <a href="https://lex.uz/docs/-5049511">Қонун ЎРҚ-641 (15.10.2020) 27-моддаси</a>' in card_oz
    assert '2. <a href="https://lex.uz/docs/-7215989#-7216081">Президент Қарори ПҚ-389 (08.11.2024)</a>' in card_oz

    # Russian
    b_ru = MockBenefit(
        legal_basis_ru="Закон Республики Узбекистан ЗРУ-641 (15.10.2020) статья 27, Постановление Президента Республики Узбекистан ПП-389 (08.11.2024)",
        lex_url="https://lex.uz/docs/-7215989#-7216081"
    )
    card_ru = format_benefit_card(b_ru, "ru")
    assert '1. <a href="https://lex.uz/docs/-5049511">Закон Республики Узбекистан ЗРУ-641 (15.10.2020) статья 27</a>' in card_ru
    assert '2. <a href="https://lex.uz/docs/-7215989#-7216081">Постановление Президента Республики Узбекистан ПП-389 (08.11.2024)</a>' in card_ru


def test_url_normalization_in_keyboards():
    """Ensure URLs lacking http(s) scheme are properly normalized for inline buttons."""
    b = MockBenefit(mygov_url="yoshlardaftari.uz")
    kb = get_benefit_detail_keyboard(1, "all", 1, lang="uz", benefit=b)
    urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
    assert "https://yoshlardaftari.uz" in urls
    assert get_portal_button_label("yoshlardaftari.uz", "uz") == "🌐 Yoshlar daftari orqali ariza"


@pytest.mark.asyncio
async def test_admin_save_cancel_and_url_normalization():
    """Verify admin save handler cancels on /cancel, handles non-text, and normalizes URLs."""
    from unittest.mock import AsyncMock, MagicMock
    from src.routes.aiogram.admin import admin_benefit_save_field_value
    from src.config.settings import settings

    # Setup mock admin message
    mock_msg = AsyncMock()
    mock_msg.from_user.id = 12345
    mock_msg.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(return_value={"b_id": 999, "field": "lex", "page": 1})
    mock_state.clear = AsyncMock()

    mock_benefit = MockBenefit(id=999, lex_url="https://lex.uz/old")
    mock_db = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Benefit, "get_by_id", lambda b_id, s: mock_benefit)
        mp.setattr(type(settings), "is_admin", lambda self, uid: True)

        # 1. Non-text message
        mock_msg.text = None
        await admin_benefit_save_field_value(mock_msg, mock_state, mock_db)
        mock_msg.answer.assert_called_with("⚠️ Iltimos, yangi qiymatni faqat matn ko'rinishida yuboring yoki quyidagi bekor qilish tugmasini bosing.")
        assert mock_benefit.lex_url == "https://lex.uz/old"

        # 2. Cancel command
        mock_msg.text = "/cancel"
        await admin_benefit_save_field_value(mock_msg, mock_state, mock_db)
        assert mock_benefit.lex_url == "https://lex.uz/old"
        assert mock_state.clear.called

        # 3. URL without scheme -> normalized to https://
        mock_msg.text = "lex.uz/docs/6905541"
        await admin_benefit_save_field_value(mock_msg, mock_state, mock_db)
        assert mock_benefit.lex_url == "https://lex.uz/docs/6905541"


def test_sync_benefits_to_json_real_session(tmp_path):
    """Verify sync_benefits_to_json exports all active/inactive benefits to JSON."""
    from src.routes.aiogram.admin import sync_benefits_to_json
    from sqlmodel import Session
    from src.database.mysql import engine
    import json
    import os

    with Session(engine) as session:
        test_json_file = str(tmp_path / "imtiyozlar_test.json")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "os.path.abspath",
                lambda p: test_json_file if "imtiyozlar_boshqaruvi" in p else os.path.abspath(p)
            )
            success = sync_benefits_to_json(session)
            assert success is True
            assert os.path.exists(test_json_file)

            with open(test_json_file, "r", encoding="utf-8") as f:
                saved_items = json.load(f)

            assert len(saved_items) == 112
            assert saved_items[0]["order_index"] == 1
            assert "title_uz" in saved_items[0]
            assert "is_active" in saved_items[0]


