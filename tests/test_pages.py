from unittest.mock import patch

from conftest import upload_txt

QUIZ_PAYLOAD = {
    "questions": [
        {"type": "true_false", "question": "Plants produce oxygen.", "options": ["True", "False"], "answer_index": 0, "explanation": "Photosynthesis."},
    ]
}
CARD_PAYLOAD = {"cards": [{"question": "What is photosynthesis?", "answer": "Light to chemical energy."}]}


def test_every_page_renders_for_logged_in_user(user_client):
    doc_id = upload_txt(user_client).get_json()["id"]
    with patch("app.services.generation.generate_json", return_value=QUIZ_PAYLOAD):
        quiz_id = user_client.post("/api/quizzes", json={"document_id": doc_id, "count": 1}).get_json()["id"]
    with patch("app.services.generation.generate_json", return_value=CARD_PAYLOAD):
        deck_id = user_client.post("/api/decks", json={"document_id": doc_id, "count": 3}).get_json()["id"]

    pages = [
        "/",
        "/documents",
        f"/documents/{doc_id}",
        "/quizzes",
        "/quizzes?document=%d" % doc_id,
        f"/quizzes/{quiz_id}",
        "/flashcards",
        f"/flashcards/{deck_id}",
        "/assistant",
        f"/assistant?document={doc_id}",
        "/analytics",
        "/settings",
    ]
    for url in pages:
        response = user_client.get(url)
        assert response.status_code == 200, url
        assert b"StudySphere" in response.data, url
        assert b'name="csrf-token"' in response.data, url
        # The CSP forbids inline scripts, so every <script> must reference a file.
        assert b"<script>" not in response.data, url


def test_ai_banner_shows_when_key_missing(no_ai_app):
    client = no_ai_app.test_client()
    client.post(
        "/register",
        data={"name": "Ada", "email": "ada@example.com", "password": "correct-horse", "confirm_password": "correct-horse"},
    )
    assert b"AI features are off" in client.get("/").data


def test_static_assets_are_served(client):
    for asset in ["/static/css/style.css", "/static/js/common.js", "/static/js/theme-init.js"]:
        assert client.get(asset).status_code == 200, asset
