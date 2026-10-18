"""Volontyor javoblarini tekshirish tarixidan sifat profili (o'qitish va nazorat uchun)."""
import json
from collections import Counter
from datetime import datetime

from sqlmodel import select

from src.models.assignment import ReviewAttempt
from src.routes.deps.db_session import DBSession

ISSUE_LABELS = {
    "wrong_norm": "Noto'g'ri norma",
    "repealed_act": "Kuchini yo'qotgan hujjat",
    "unsupported_claim": "Asossiz da'vo",
    "missing_norm": "Norma ko'rsatilmagan",
    "no_basis": "Huquqiy asos yo'q",
    "incomplete": "Savolning bir qismi javobsiz",
    "tone": "Muloqot ohangi",
    "other": "Kamchilik",
}
SCORE_LABELS = {
    "legal_accuracy": "Huquqiy to'g'rilik",
    "citation_basis": "Norma va havolalar",
    "completeness": "To'liqlik",
    "tone": "Muloqot",
}


def record_review_attempt(db_session: DBSession, assignment, inquiry, volunteer_user_id: int, result: dict) -> None:
    issues = [i for i in (result.get("issues") or []) if isinstance(i, dict)]
    issue_types = ",".join(f"{i.get('type', 'other')}:{i.get('severity', 'major')}" for i in issues)[:500]
    db_session.add(ReviewAttempt(
        assignment_id=getattr(assignment, "id", None),
        inquiry_id=inquiry.id,
        volunteer_user_id=volunteer_user_id,
        verdict=str(result.get("verdict") or "unknown")[:20],
        confidence=result.get("confidence"),
        scores_json=json.dumps(result.get("scores") or {}),
        issue_types=issue_types or None,
    ))
    db_session.commit()


def review_quality(db_session: DBSession, volunteer_user_id: int, since: datetime | None = None) -> dict | None:
    query = select(ReviewAttempt).where(ReviewAttempt.volunteer_user_id == volunteer_user_id)
    if since:
        query = query.where(ReviewAttempt.created_at >= since)
    rows = db_session.exec(query.order_by(ReviewAttempt.created_at)).all()
    if not rows:
        return None
    first_verdict: dict[int, str] = {}
    approved: set[int] = set()
    score_sum: Counter = Counter()
    score_n = 0
    major_issues: Counter = Counter()
    for row in rows:
        first_verdict.setdefault(row.inquiry_id, row.verdict)
        if row.verdict == "approve":
            approved.add(row.inquiry_id)
        try:
            scores = json.loads(row.scores_json or "{}")
        except ValueError:
            scores = {}
        if scores:
            score_sum.update({k: float(v) for k, v in scores.items() if k in SCORE_LABELS})
            score_n += 1
        for item in (row.issue_types or "").split(","):
            kind, _, severity = item.partition(":")
            if kind and severity != "minor":
                major_issues[kind] += 1
    inquiries = len(first_verdict)
    return {
        "attempts": len(rows),
        "inquiries": inquiries,
        "first_try_rate": round(100 * sum(1 for v in first_verdict.values() if v == "approve") / inquiries),
        "approved_inquiries": len(approved),
        "avg_scores": {k: round(score_sum[k] / score_n, 1) for k in SCORE_LABELS if score_n},
        "top_issues": major_issues.most_common(3),
    }


def format_quality_block(stats: dict | None) -> str:
    if not stats:
        return "🧪 <b>Javoblar tekshiruvi:</b> <i>hali tekshiruv bo'lmagan</i>"
    lines = [
        "🧪 <b>Javoblar tekshiruvi:</b>",
        f"• Tekshirilgan murojaatlar: <b>{stats['inquiries']}</b> ta ({stats['attempts']} ta urinish)",
        f"• Birinchi urinishda tasdiqlangan: <b>{stats['first_try_rate']}%</b>",
    ]
    if stats["avg_scores"]:
        scores = ", ".join(f"{SCORE_LABELS[k]} {v}" for k, v in stats["avg_scores"].items())
        lines.append(f"• O'rtacha ballar (5 dan): {scores}")
    if stats["top_issues"]:
        issues = ", ".join(f"{ISSUE_LABELS.get(k, k)} ({n})" for k, n in stats["top_issues"])
        lines.append(f"• Ko'p uchragan kamchiliklar: {issues}")
    return "<br/>".join(lines)
