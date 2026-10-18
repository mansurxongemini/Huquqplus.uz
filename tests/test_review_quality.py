import json
from unittest.mock import MagicMock

from src.app.review_quality import format_quality_block, review_quality
from src.models.assignment import ReviewAttempt


def _row(inq, verdict, issues=None, scores=None):
    return ReviewAttempt(inquiry_id=inq, volunteer_user_id=5, verdict=verdict, issue_types=issues,
                         scores_json=json.dumps(scores or {"legal_accuracy": 4, "citation_basis": 3, "completeness": 4, "tone": 5}))


def test_quality_profile_counts_first_try_and_major_issues():
    rows = [
        _row(1, "reject", "wrong_norm:major,tone:minor"),
        _row(1, "approve"),
        _row(2, "approve"),
        _row(3, "reject", "wrong_norm:major,incomplete:major"),
    ]
    db = MagicMock()
    db.exec.return_value.all.return_value = rows
    stats = review_quality(db, 5)
    assert stats["inquiries"] == 3 and stats["attempts"] == 4
    assert stats["first_try_rate"] == 33  # faqat №2 birinchi urinishda
    assert stats["top_issues"][0] == ("wrong_norm", 2)
    assert ("tone", 1) not in stats["top_issues"]  # kichik kamchiliklar hisobga olinmaydi
    text = format_quality_block(stats)
    assert "Noto'g'ri norma (2)" in text and "33%" in text


def test_quality_block_without_history():
    db = MagicMock()
    db.exec.return_value.all.return_value = []
    assert "hali tekshiruv bo'lmagan" in format_quality_block(review_quality(db, 5))
