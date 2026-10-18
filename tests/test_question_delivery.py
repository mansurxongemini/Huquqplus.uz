from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app import question_delivery as qd
from src.app.inquiry_card import InquiryPayload
from src.config.settings import settings
from src.models.inquiry import InquiryMediaType
from src.models.user import User

ASK_OK = {"answer": "<b>Javob</b> 427-modda [1]", "parts": ["<b>Javob</b> 427-modda [1]"], "citations": [{"n": 1}], "is_refusal": False}
REVIEW_OK = {"verdict": "approve", "confidence": 0.95, "scores": {"legal_accuracy": 5, "citation_basis": 5, "completeness": 4, "tone": 5}}


def _user():
    return User(user_id=10, first_name="Ali", language="uz")


@pytest.mark.parametrize("ask, review, ok", [
    (ASK_OK, REVIEW_OK, True),
    ({**ASK_OK, "is_refusal": True}, REVIEW_OK, False),
    ({**ASK_OK, "citations": []}, REVIEW_OK, False),
    (ASK_OK, {**REVIEW_OK, "verdict": "needs_admin"}, False),
    (ASK_OK, {**REVIEW_OK, "confidence": 0.6}, False),
    (ASK_OK, {**REVIEW_OK, "scores": {**REVIEW_OK["scores"], "completeness": 3}}, False),
])
def test_only_fully_trusted_answers_go_to_citizen(ask, review, ok):
    assert qd.ai_answer_is_trusted(ask, review) is ok


@pytest.mark.asyncio
async def test_trusted_answer_sent_with_lawyer_button_and_ai_footer(monkeypatch):
    monkeypatch.setattr(settings, "AI_CITIZEN_ANSWERS", True)
    db = MagicMock()
    db.refresh.side_effect = lambda rec: setattr(rec, "id", 55)
    message = MagicMock()
    message.answer = AsyncMock()
    message.chat.id = 10
    sent = []

    async def fake_send(**kw):
        sent.append(kw)

    with patch.object(qd, "try_ai_answer", AsyncMock(return_value=(ASK_OK, REVIEW_OK))), \
         patch.object(qd, "post_inquiry_to_group", AsyncMock()) as to_group, \
         patch("src.routes.aiogram.ai_assistant.send_ai_part", side_effect=fake_send), \
         patch("src.app.keyboards.get_role_menu", return_value=None):
        rec = await qd.deliver_citizen_question(
            MagicMock(), message, db, _user(), "Mehnat", "-100123",
            InquiryPayload(InquiryMediaType.text, text="Ish haftasi necha soat?"), 7,
        )
    to_group.assert_not_awaited()
    assert rec.id == 55 and rec.question == "Ish haftasi necha soat?"
    assert "sun'iy intellekt" in sent[-1]["text"]
    kb = sent[-1]["reply_markup"].inline_keyboard
    assert [b.callback_data for b in kb[0]] == ["aifb:55:up", "aifb:55:down"] and kb[1][0].callback_data == "aiesc:55"


@pytest.mark.asyncio
async def test_untrusted_or_media_question_goes_to_group(monkeypatch):
    monkeypatch.setattr(settings, "AI_CITIZEN_ANSWERS", True)
    message = MagicMock()
    message.answer = AsyncMock()
    with patch.object(qd, "try_ai_answer", AsyncMock(return_value=None)), \
         patch.object(qd, "post_inquiry_to_group", AsyncMock()) as to_group, \
         patch("src.app.keyboards.get_role_menu", return_value=None):
        await qd.deliver_citizen_question(MagicMock(), message, MagicMock(), _user(), "Mehnat", "-100123",
                                          InquiryPayload(InquiryMediaType.text, text="Murakkab savol"), 7)
        await qd.deliver_citizen_question(MagicMock(), message, MagicMock(), _user(), "Mehnat", "-100123",
                                          InquiryPayload(InquiryMediaType.voice, file_id="V"), 8)
    assert to_group.await_count == 2


@pytest.mark.asyncio
async def test_escalation_marks_inquiry_as_ai_unsatisfied():
    record = qd.AiAnswer(id=55, user_id=10, section_name="Mehnat", group_id="-100123", question="Savol?",
                         private_question_id=7, answer_html="...")
    with patch.object(qd, "post_inquiry_to_group", AsyncMock(return_value=SimpleNamespace(id=99))) as to_group:
        inq = await qd.escalate_ai_answer(MagicMock(), MagicMock(), record, _user())
    kwargs = to_group.await_args.kwargs
    assert kwargs["header"] == qd.AI_ESCALATION_HEADER and kwargs["from_ai_answer_id"] == 55
    assert inq.id == 99 and record.escalated_inquiry_id == 99


def test_escalated_card_shows_header():
    from src.app.inquiry_card import render_inquiry_card
    from src.models.inquiry import Inquiry
    inq = Inquiry(id=1, user_id=10, section_name="Mehnat", question="Savol?", question_mediatype=InquiryMediaType.text,
                  group_id="-100123", group_question_id=5, from_ai_answer_id=55)
    text, _ = render_inquiry_card(inq, None, user=_user())
    assert text.startswith(qd.AI_ESCALATION_HEADER)
