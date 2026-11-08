from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Document
from ..services.activity import record_activity
from ..services.extraction import extract_text
from ..utils import ApiError, clean_str, json_body, like_pattern

bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def owned_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None or doc.user_id != current_user.id:
        raise ApiError("Document not found.", 404)
    return doc


def _snippet(text, term, radius=90):
    index = text.lower().find(term.lower())
    if index == -1:
        return None
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + " ".join(text[start:end].split()) + suffix


@bp.get("")
@login_required
def list_documents():
    term = (request.args.get("q") or "").strip()[:200]
    base = Document.query.filter_by(user_id=current_user.id)

    if term:
        pattern = like_pattern(term)
        docs = (
            base.filter(
                or_(
                    Document.title.ilike(pattern, escape="\\"),
                    Document.subject.ilike(pattern, escape="\\"),
                    Document.text_content.ilike(pattern, escape="\\"),
                )
            )
            .order_by(Document.created_at.desc())
            .limit(100)
            .all()
        )
        results = []
        for doc in docs:
            item = doc.to_dict()
            item["snippet"] = _snippet(doc.text_content, term)
            results.append(item)
        return jsonify(results)

    # Listing does not need the full text; defer it to keep responses small.
    docs = (
        base.options(db.defer(Document.text_content))
        .order_by(Document.created_at.desc())
        .limit(500)
        .all()
    )
    return jsonify([doc.to_dict() for doc in docs])


@bp.post("")
@login_required
def upload_document():
    file = request.files.get("file")
    if file is None or not file.filename:
        raise ApiError("Choose a PDF, TXT or DOCX file to upload.")

    original = secure_filename(file.filename) or "document"
    extension = Path(original).suffix.lstrip(".").lower()
    if extension not in current_app.config["ALLOWED_EXTENSIONS"]:
        raise ApiError("Unsupported file type. Upload a PDF, TXT or DOCX file.")

    data = file.read()
    text = extract_text(data, extension, current_app.config["MAX_DOCUMENT_CHARS"])

    title = clean_str(request.form.get("title"), 200, "Title") or Path(original).stem[:200]
    subject = clean_str(request.form.get("subject"), 100, "Subject") or "General"

    doc = Document(
        user_id=current_user.id,
        title=title,
        subject=subject,
        original_name=original[:255],
        file_type=extension,
        size_bytes=len(data),
        char_count=len(text),
        text_content=text,
    )
    db.session.add(doc)
    db.session.flush()
    record_activity(current_user.id, "upload", f"Uploaded {title}", subject)
    db.session.commit()
    return jsonify(doc.to_dict(include_text=True)), 201


@bp.get("/<int:doc_id>")
@login_required
def get_document(doc_id):
    return jsonify(owned_document(doc_id).to_dict(include_text=True))


@bp.patch("/<int:doc_id>")
@login_required
def update_document(doc_id):
    doc = owned_document(doc_id)
    data = json_body()
    if "title" in data:
        doc.title = clean_str(data.get("title"), 200, "Title", required=True)
    if "subject" in data:
        doc.subject = clean_str(data.get("subject"), 100, "Subject") or "General"
    db.session.commit()
    return jsonify(doc.to_dict(include_text=True))


@bp.delete("/<int:doc_id>")
@login_required
def delete_document(doc_id):
    doc = owned_document(doc_id)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"ok": True})
