import json
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
        "/dashboard",
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
    assert b"AI features are off" in client.get("/dashboard").data


def test_static_assets_are_served(client):
    for asset in ["/static/css/style.css", "/static/js/common.js", "/static/js/theme-init.js"]:
        assert client.get(asset).status_code == 200, asset


def test_homepage_is_public_and_has_seo_metadata(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "<title>StudySphere: AI Study Tool for Quizzes, Flashcards and Notes</title>" in html
    assert 'name="description"' in html
    assert '<link rel="canonical" href="https://studysphere-hub.vercel.app/">' in html
    assert 'property="og:url" content="https://studysphere-hub.vercel.app/"' in html
    assert html.count("<h1") == 1
    assert 'href="/login"' in html and 'href="/register"' in html
    # Structured data must be valid JSON and the CSP forbids inline scripts.
    assert "<script>" not in html
    start = html.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
    data = json.loads(html[start:html.index("</script>", start)])
    types = {item["@type"] for item in data["@graph"]}
    assert {"WebSite", "SoftwareApplication", "FAQPage"} <= types


def test_homepage_does_not_show_app_shell(client):
    html = client.get("/").get_data(as_text=True)
    assert 'class="sidebar"' not in html
    assert "Log out" not in html


def test_signed_in_user_visiting_home_is_sent_to_dashboard(user_client):
    response = user_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
