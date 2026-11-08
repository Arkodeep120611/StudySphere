from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Quiz, QuizAttempt, QuizQuestion
from ..services.activity import record_activity
from ..services.generation import DIFFICULTIES, QUESTION_TYPES, generate_quiz_questions
from ..utils import ApiError, clamp_int, json_body
from .documents import owned_document

bp = Blueprint("quizzes", __name__, url_prefix="/api/quizzes")


def owned_quiz(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != current_user.id:
        raise ApiError("Quiz not found.", 404)
    return quiz


def _percent(score, total):
    return round(score * 100 / total, 1) if total else 0.0


def _summary(quiz):
    percents = [_percent(a.score, a.total) for a in quiz.attempts]
    return {
        "id": quiz.id,
        "title": quiz.title,
        "subject": quiz.subject,
        "difficulty": quiz.difficulty,
        "question_type": quiz.question_type,
        "document_id": quiz.document_id,
        "document_title": quiz.document.title,
        "question_count": len(quiz.questions),
        "attempt_count": len(percents),
        "best_percent": max(percents) if percents else None,
        "last_percent": percents[-1] if percents else None,
        "created_at": quiz.created_at.isoformat() + "Z",
    }


def _detail(quiz):
    # Correct answers are never included here; they are revealed only after an attempt.
    attempts = [
        {
            "id": a.id,
            "score": a.score,
            "total": a.total,
            "percent": _percent(a.score, a.total),
            "created_at": a.created_at.isoformat() + "Z",
        }
        for a in reversed(quiz.attempts[-10:])
    ]
    return {
        "id": quiz.id,
        "title": quiz.title,
        "subject": quiz.subject,
        "difficulty": quiz.difficulty,
        "question_type": quiz.question_type,
        "document_id": quiz.document_id,
        "document_title": quiz.document.title,
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "type": q.question_type,
                "question": q.question_text,
                "options": q.options,
            }
            for q in quiz.questions
        ],
        "attempts": attempts,
    }


@bp.get("")
@login_required
def list_quizzes():
    quizzes = (
        Quiz.query.filter_by(user_id=current_user.id).order_by(Quiz.created_at.desc()).all()
    )
    return jsonify([_summary(q) for q in quizzes])


@bp.post("")
@login_required
def create_quiz():
    data = json_body()
    doc = owned_document(clamp_int(data.get("document_id"), "Document", 1, 2**31 - 1))
    difficulty = data.get("difficulty", "medium")
    question_type = data.get("question_type", "mixed")
    if difficulty not in DIFFICULTIES:
        raise ApiError("Difficulty must be easy, medium or hard.")
    if question_type not in QUESTION_TYPES:
        raise ApiError("Question type must be mcq, true_false or mixed.")
    count = clamp_int(data.get("count", 10), "Number of questions", 1, 20)

    questions = generate_quiz_questions(
        doc.text_content, count, difficulty, question_type, current_app.config["AI_CONTEXT_CHARS"]
    )

    quiz = Quiz(
        user_id=current_user.id,
        document_id=doc.id,
        title=f"{doc.title} quiz"[:200],
        subject=doc.subject,
        difficulty=difficulty,
        question_type=question_type,
    )
    for position, item in enumerate(questions):
        quiz.questions.append(
            QuizQuestion(
                position=position,
                question_type=item["type"],
                question_text=item["question"],
                options=item["options"],
                correct_index=item["answer_index"],
                explanation=item["explanation"],
            )
        )
    db.session.add(quiz)
    db.session.flush()
    record_activity(current_user.id, "quiz", f"Generated quiz: {doc.title}", doc.subject)
    db.session.commit()
    return jsonify(_detail(quiz)), 201


@bp.get("/<int:quiz_id>")
@login_required
def get_quiz(quiz_id):
    return jsonify(_detail(owned_quiz(quiz_id)))


@bp.delete("/<int:quiz_id>")
@login_required
def delete_quiz(quiz_id):
    db.session.delete(owned_quiz(quiz_id))
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/<int:quiz_id>/attempts")
@login_required
def submit_attempt(quiz_id):
    quiz = owned_quiz(quiz_id)
    data = json_body()
    answers = data.get("answers")
    if not isinstance(answers, list) or len(answers) != len(quiz.questions):
        raise ApiError("Answer every question before submitting.")

    selected = []
    for answer, question in zip(answers, quiz.questions):
        if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer < len(question.options):
            raise ApiError("Each answer must be one of the listed options.")
        selected.append(answer)

    results, score = [], 0
    for answer, question in zip(selected, quiz.questions):
        is_correct = answer == question.correct_index
        score += int(is_correct)
        results.append(
            {
                "question_id": question.id,
                "position": question.position,
                "question": question.question_text,
                "options": question.options,
                "selected": answer,
                "correct_index": question.correct_index,
                "is_correct": is_correct,
                "explanation": question.explanation,
            }
        )

    total = len(quiz.questions)
    percent = _percent(score, total)
    db.session.add(
        QuizAttempt(
            quiz_id=quiz.id,
            user_id=current_user.id,
            subject=quiz.subject,
            score=score,
            total=total,
            answers=selected,
        )
    )
    record_activity(current_user.id, "quiz", f"Quiz: {quiz.title}", quiz.subject, score=percent)
    db.session.commit()
    return jsonify({"score": score, "total": total, "percent": percent, "results": results}), 201
