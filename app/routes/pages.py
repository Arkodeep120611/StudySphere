from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Deck, Document, Quiz

bp = Blueprint("pages", __name__)


def _owned_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None or obj.user_id != current_user.id:
        abort(404)
    return obj


@bp.get("/")
def home():
    """Public landing page. Signed-in users go straight to their dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    return render_template("landing.html")


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@bp.get("/documents")
@login_required
def documents():
    return render_template("documents.html")


@bp.get("/documents/<int:doc_id>")
@login_required
def document_detail(doc_id):
    doc = _owned_or_404(Document, doc_id)
    return render_template("document_detail.html", doc=doc)


@bp.get("/quizzes")
@login_required
def quizzes():
    return render_template("quizzes.html", preselect=request.args.get("document", type=int))


@bp.get("/quizzes/<int:quiz_id>")
@login_required
def quiz_detail(quiz_id):
    quiz = _owned_or_404(Quiz, quiz_id)
    return render_template("quiz.html", quiz=quiz)


@bp.get("/flashcards")
@login_required
def flashcards():
    return render_template("flashcards.html", preselect=request.args.get("document", type=int))


@bp.get("/flashcards/<int:deck_id>")
@login_required
def deck_detail(deck_id):
    deck = _owned_or_404(Deck, deck_id)
    return render_template("deck.html", deck=deck)


@bp.get("/assistant")
@login_required
def assistant():
    return render_template("assistant.html", preselect=request.args.get("document", type=int))


@bp.get("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@bp.get("/settings")
@login_required
def settings():
    return render_template("settings.html")
