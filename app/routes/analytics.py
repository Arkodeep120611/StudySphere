from collections import Counter, defaultdict
from datetime import timedelta

from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Deck, Document, Flashcard, QuizAttempt, StudyActivity, utcnow

bp = Blueprint("analytics", __name__, url_prefix="/api")


def _percent(score, total):
    return round(score * 100 / total, 1) if total else 0.0


def _average(values):
    return round(sum(values) / len(values), 1) if values else None


def _flashcard_counts(user_id):
    rows = (
        db.session.query(Flashcard.status, func.count(Flashcard.id))
        .join(Deck, Flashcard.deck_id == Deck.id)
        .filter(Deck.user_id == user_id)
        .group_by(Flashcard.status)
        .all()
    )
    counts = {status: 0 for status in Flashcard.STATUSES}
    for status, count in rows:
        counts[status] = count
    return counts


@bp.get("/dashboard")
@login_required
def dashboard():
    uid = current_user.id
    since = utcnow() - timedelta(days=7)

    attempts = QuizAttempt.query.filter_by(user_id=uid).order_by(QuizAttempt.id).all()
    week = StudyActivity.query.filter(
        StudyActivity.user_id == uid, StudyActivity.created_at >= since
    ).all()
    cards = _flashcard_counts(uid)
    recent_activity = (
        StudyActivity.query.filter_by(user_id=uid)
        .order_by(StudyActivity.created_at.desc(), StudyActivity.id.desc())
        .limit(8)
        .all()
    )
    recent_docs = (
        Document.query.options(db.defer(Document.text_content))
        .filter_by(user_id=uid)
        .order_by(Document.created_at.desc())
        .limit(4)
        .all()
    )

    return jsonify(
        {
            "stats": {
                "documents": Document.query.filter_by(user_id=uid).count(),
                "quizzes_completed": len(attempts),
                "average_score": _average([a.percent for a in attempts]),
                "flashcards_known": cards["known"],
                "flashcards_total": sum(cards.values()),
                "active_days_7d": len({a.created_at.date() for a in week}),
                "activity_7d": len(week),
            },
            "recent_activity": [a.to_dict() for a in recent_activity],
            "recent_documents": [d.to_dict() for d in recent_docs],
        }
    )


@bp.get("/analytics")
@login_required
def analytics():
    uid = current_user.id
    now = utcnow()

    attempts = QuizAttempt.query.filter_by(user_id=uid).order_by(QuizAttempt.id).all()
    score_history = [
        {
            "date": a.created_at.strftime("%Y-%m-%d"),
            "percent": a.percent,
            "subject": a.subject,
        }
        for a in attempts[-30:]
    ]

    subjects = defaultdict(
        lambda: {
            "subject": "",
            "documents": 0,
            "quizzes_taken": 0,
            "scores": [],
            "flashcards_total": 0,
            "flashcards_known": 0,
        }
    )

    def bucket(name):
        entry = subjects[name]
        entry["subject"] = name
        return entry

    for doc in Document.query.options(db.defer(Document.text_content)).filter_by(user_id=uid):
        bucket(doc.subject)["documents"] += 1
    for attempt in attempts:
        entry = bucket(attempt.subject)
        entry["quizzes_taken"] += 1
        entry["scores"].append(attempt.percent)

    card_rows = (
        db.session.query(Deck.subject, Flashcard.status, func.count(Flashcard.id))
        .join(Flashcard, Flashcard.deck_id == Deck.id)
        .filter(Deck.user_id == uid)
        .group_by(Deck.subject, Flashcard.status)
        .all()
    )
    for subject, status, count in card_rows:
        entry = bucket(subject)
        entry["flashcards_total"] += count
        if status == "known":
            entry["flashcards_known"] += count

    subject_rows = []
    for entry in sorted(subjects.values(), key=lambda e: e["subject"].lower()):
        subject_rows.append(
            {
                "subject": entry["subject"],
                "documents": entry["documents"],
                "quizzes_taken": entry["quizzes_taken"],
                "average_score": _average(entry["scores"]),
                "flashcards_total": entry["flashcards_total"],
                "flashcards_known": entry["flashcards_known"],
            }
        )

    start = (now - timedelta(days=13)).date()
    day_counts = Counter(
        a.created_at.date() for a in StudyActivity.query.filter(
            StudyActivity.user_id == uid, StudyActivity.created_at >= now - timedelta(days=14)
        ).all()
    )
    activity_daily = [
        {
            "date": (start + timedelta(days=offset)).isoformat(),
            "count": day_counts.get(start + timedelta(days=offset), 0),
        }
        for offset in range(14)
    ]

    return jsonify(
        {
            "score_history": score_history,
            "subjects": subject_rows,
            "activity_daily": activity_daily,
            "flashcard_status": _flashcard_counts(uid),
        }
    )
