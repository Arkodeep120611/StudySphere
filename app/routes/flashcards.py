from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Deck, Flashcard
from ..services.activity import record_activity
from ..services.generation import generate_flashcards
from ..utils import ApiError, clamp_int, json_body
from .documents import owned_document

decks_bp = Blueprint("decks", __name__, url_prefix="/api/decks")
cards_bp = Blueprint("cards", __name__, url_prefix="/api/cards")


def owned_deck(deck_id):
    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.user_id != current_user.id:
        raise ApiError("Deck not found.", 404)
    return deck


def _counts(cards):
    counts = {status: 0 for status in Flashcard.STATUSES}
    for card in cards:
        counts[card.status] += 1
    return counts


def _summary(deck):
    counts = _counts(deck.cards)
    return {
        "id": deck.id,
        "title": deck.title,
        "subject": deck.subject,
        "document_id": deck.document_id,
        "document_title": deck.document.title,
        "card_count": len(deck.cards),
        "known_count": counts["known"],
        "revise_count": counts["revise"],
        "created_at": deck.created_at.isoformat() + "Z",
    }


def _detail(deck):
    return {
        **_summary(deck),
        "cards": [
            {
                "id": card.id,
                "position": card.position,
                "question": card.question,
                "answer": card.answer,
                "status": card.status,
            }
            for card in deck.cards
        ],
    }


@decks_bp.get("")
@login_required
def list_decks():
    decks = Deck.query.filter_by(user_id=current_user.id).order_by(Deck.created_at.desc()).all()
    return jsonify([_summary(d) for d in decks])


@decks_bp.post("")
@login_required
def create_deck():
    data = json_body()
    doc = owned_document(clamp_int(data.get("document_id"), "Document", 1, 2**31 - 1))
    count = clamp_int(data.get("count", 15), "Number of cards", 3, 40)

    cards = generate_flashcards(doc.text_content, count, current_app.config["AI_CONTEXT_CHARS"])
    deck = Deck(
        user_id=current_user.id,
        document_id=doc.id,
        title=f"{doc.title} flashcards"[:200],
        subject=doc.subject,
    )
    for position, item in enumerate(cards):
        deck.cards.append(
            Flashcard(position=position, question=item["question"], answer=item["answer"])
        )
    db.session.add(deck)
    db.session.flush()
    record_activity(current_user.id, "flashcards", f"Created deck: {doc.title}", doc.subject)
    db.session.commit()
    return jsonify(_detail(deck)), 201


@decks_bp.get("/<int:deck_id>")
@login_required
def get_deck(deck_id):
    return jsonify(_detail(owned_deck(deck_id)))


@decks_bp.delete("/<int:deck_id>")
@login_required
def delete_deck(deck_id):
    db.session.delete(owned_deck(deck_id))
    db.session.commit()
    return jsonify({"ok": True})


@decks_bp.post("/<int:deck_id>/reset")
@login_required
def reset_deck(deck_id):
    deck = owned_deck(deck_id)
    for card in deck.cards:
        card.status = "unseen"
    db.session.commit()
    return jsonify(_detail(deck))


@cards_bp.patch("/<int:card_id>")
@login_required
def update_card(card_id):
    card = db.session.get(Flashcard, card_id)
    if card is None or card.deck.user_id != current_user.id:
        raise ApiError("Card not found.", 404)
    status = json_body().get("status")
    if status not in Flashcard.STATUSES:
        raise ApiError("Status must be unseen, known or revise.")
    card.status = status
    db.session.commit()
    return jsonify({"id": card.id, "status": card.status})
