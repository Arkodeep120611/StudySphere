from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from ..extensions import db
from ..models import ChatMessage
from ..services.activity import record_activity
from ..services.generation import answer_question
from ..utils import ApiError, clean_str, json_body
from .documents import owned_document

bp = Blueprint("chat", __name__, url_prefix="/api/documents/<int:doc_id>/chat")

HISTORY_TURNS = 8
HISTORY_CHARS = 1500


def _history(doc_id):
    rows = (
        ChatMessage.query.filter_by(user_id=current_user.id, document_id=doc_id)
        .order_by(ChatMessage.id.desc())
        .limit(HISTORY_TURNS)
        .all()
    )
    return [(row.role, row.content[:HISTORY_CHARS]) for row in reversed(rows)]


@bp.get("")
@login_required
def list_messages(doc_id):
    doc = owned_document(doc_id)
    messages = (
        ChatMessage.query.filter_by(user_id=current_user.id, document_id=doc.id)
        .order_by(ChatMessage.id)
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@bp.post("")
@login_required
def send_message(doc_id):
    doc = owned_document(doc_id)
    message = clean_str(json_body().get("message"), 2000, "Message", required=True)

    # Generate the reply first so a failed AI call does not leave a dangling user message.
    reply = answer_question(
        doc.title,
        doc.text_content,
        message,
        _history(doc.id),
        current_app.config["AI_CONTEXT_CHARS"],
    )
    user_msg = ChatMessage(user_id=current_user.id, document_id=doc.id, role="user", content=message)
    bot_msg = ChatMessage(user_id=current_user.id, document_id=doc.id, role="assistant", content=reply)
    db.session.add_all([user_msg, bot_msg])
    record_activity(current_user.id, "chat", f"Asked about {doc.title}", doc.subject)
    db.session.commit()
    return jsonify({"user": user_msg.to_dict(), "assistant": bot_msg.to_dict()}), 201


@bp.delete("")
@login_required
def clear_messages(doc_id):
    doc = owned_document(doc_id)
    ChatMessage.query.filter_by(user_id=current_user.id, document_id=doc.id).delete()
    db.session.commit()
    return jsonify({"ok": True})
