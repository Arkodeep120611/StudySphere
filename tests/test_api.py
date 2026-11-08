from unittest.mock import patch

from conftest import register, upload_txt

QUIZ_PAYLOAD = {
    "questions": [
        {"type": "mcq", "question": "What does chlorophyll absorb?", "options": ["Green", "Red and blue", "UV", "Infrared"], "answer_index": 1, "explanation": "Chlorophyll absorbs red and blue light."},
        {"type": "true_false", "question": "Plants produce oxygen.", "options": ["True", "False"], "answer_index": 0, "explanation": "Photosynthesis releases oxygen."},
    ]
}

CARD_PAYLOAD = {
    "cards": [
        {"question": "What is photosynthesis?", "answer": "Converting light into chemical energy."},
        {"question": "Where does it happen?", "answer": "In chloroplasts."},
        {"question": "What gas is released?", "answer": "Oxygen."},
    ]
}


def test_upload_list_view_search_delete(user_client):
    response = upload_txt(user_client, title="Biology Notes", subject="Biology")
    assert response.status_code == 201
    doc = response.get_json()
    assert doc["title"] == "Biology Notes"
    assert doc["char_count"] > 0
    assert "text" in doc

    listing = user_client.get("/api/documents").get_json()
    assert len(listing) == 1 and "text" not in listing[0]

    found = user_client.get("/api/documents?q=photosynthesis").get_json()
    assert found and "snippet" in found[0] and "Photosynthesis" in found[0]["snippet"]
    assert user_client.get("/api/documents?q=zzz-no-match").get_json() == []
    # LIKE wildcards in the search term are matched literally, not as patterns.
    assert user_client.get("/api/documents?q=%25").get_json() == []

    detail = user_client.get(f"/api/documents/{doc['id']}").get_json()
    assert "Photosynthesis" in detail["text"]

    assert user_client.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert user_client.get("/api/documents").get_json() == []


def test_upload_rejects_unsupported_extension(user_client):
    from io import BytesIO

    response = user_client.post(
        "/api/documents",
        data={"file": (BytesIO(b"<script>x</script>"), "page.html")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.get_json()["error"]


def test_upload_requires_a_file(user_client):
    response = user_client.post("/api/documents", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_documents_are_isolated_between_users(app, user_client):
    doc_id = upload_txt(user_client).get_json()["id"]

    other = app.test_client()
    register(other, email="grace@example.com", name="Grace")

    assert other.get("/api/documents").get_json() == []
    assert other.get(f"/api/documents/{doc_id}").status_code == 404
    assert other.delete(f"/api/documents/{doc_id}").status_code == 404
    assert other.get(f"/documents/{doc_id}").status_code == 404
    assert other.get(f"/api/documents/{doc_id}/chat").status_code == 404


def test_quiz_generation_attempt_and_scoring(user_client):
    doc_id = upload_txt(user_client).get_json()["id"]

    with patch("app.services.generation.generate_json", return_value=QUIZ_PAYLOAD):
        created = user_client.post(
            "/api/quizzes", json={"document_id": doc_id, "difficulty": "easy", "question_type": "mixed", "count": 5}
        )
    assert created.status_code == 201
    quiz = created.get_json()
    assert len(quiz["questions"]) == 2
    # Correct answers must not leak to the client before submission.
    assert all("answer_index" not in q and "correct_index" not in q for q in quiz["questions"])

    quiz_id = quiz["id"]
    bad = user_client.post(f"/api/quizzes/{quiz_id}/attempts", json={"answers": [1]})
    assert bad.status_code == 400

    result = user_client.post(f"/api/quizzes/{quiz_id}/attempts", json={"answers": [1, 1]})
    assert result.status_code == 201
    body = result.get_json()
    assert body["score"] == 1 and body["total"] == 2 and body["percent"] == 50.0
    assert body["results"][0]["is_correct"] is True
    assert body["results"][1]["correct_index"] == 0
    assert body["results"][1]["explanation"]

    summary = user_client.get("/api/quizzes").get_json()[0]
    assert summary["attempt_count"] == 1 and summary["best_percent"] == 50.0


def test_quiz_rejects_invalid_options(user_client):
    doc_id = upload_txt(user_client).get_json()["id"]
    with patch("app.services.generation.generate_json", return_value=QUIZ_PAYLOAD):
        quiz_id = user_client.post("/api/quizzes", json={"document_id": doc_id, "count": 5}).get_json()["id"]
    response = user_client.post(f"/api/quizzes/{quiz_id}/attempts", json={"answers": [9, 0]})
    assert response.status_code == 400


def test_quiz_generation_without_ai_key_returns_503(no_ai_app):
    client = no_ai_app.test_client()
    register(client)
    doc_id = upload_txt(client).get_json()["id"]
    response = client.post("/api/quizzes", json={"document_id": doc_id, "count": 5})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.get_json()["error"]


def test_flashcard_deck_and_status_tracking(user_client):
    doc_id = upload_txt(user_client).get_json()["id"]
    with patch("app.services.generation.generate_json", return_value=CARD_PAYLOAD):
        deck = user_client.post("/api/decks", json={"document_id": doc_id, "count": 3}).get_json()
    assert len(deck["cards"]) == 3

    card_id = deck["cards"][0]["id"]
    assert user_client.patch(f"/api/cards/{card_id}", json={"status": "known"}).get_json()["status"] == "known"
    assert user_client.patch(f"/api/cards/{card_id}", json={"status": "bogus"}).status_code == 400

    summary = user_client.get("/api/decks").get_json()[0]
    assert summary["known_count"] == 1

    reset = user_client.post(f"/api/decks/{deck['id']}/reset").get_json()
    assert all(c["status"] == "unseen" for c in reset["cards"])


def test_chat_answers_are_saved_and_cleared(user_client):
    doc_id = upload_txt(user_client).get_json()["id"]
    with patch("app.services.generation.chat", return_value="Plants use light to make sugar.") as mocked:
        response = user_client.post(f"/api/documents/{doc_id}/chat", json={"message": "What do plants use?"})
    assert response.status_code == 201
    assert response.get_json()["assistant"]["content"] == "Plants use light to make sugar."
    system_instruction = mocked.call_args.args[0]
    assert "Photosynthesis" in system_instruction  # excerpts are grounded in the document
    assert "Answer ONLY" in system_instruction

    history = user_client.get(f"/api/documents/{doc_id}/chat").get_json()
    assert [m["role"] for m in history] == ["user", "assistant"]

    assert user_client.delete(f"/api/documents/{doc_id}/chat").status_code == 200
    assert user_client.get(f"/api/documents/{doc_id}/chat").get_json() == []


def test_failed_ai_call_does_not_store_partial_chat(user_client):
    from app.utils import ApiError

    doc_id = upload_txt(user_client).get_json()["id"]
    with patch("app.services.generation.chat", side_effect=ApiError("down", 502)):
        response = user_client.post(f"/api/documents/{doc_id}/chat", json={"message": "hello?"})
    assert response.status_code == 502
    assert user_client.get(f"/api/documents/{doc_id}/chat").get_json() == []


def test_dashboard_and_analytics_reflect_activity(user_client):
    doc_id = upload_txt(user_client, subject="Biology").get_json()["id"]
    with patch("app.services.generation.generate_json", return_value=QUIZ_PAYLOAD):
        quiz_id = user_client.post("/api/quizzes", json={"document_id": doc_id, "count": 5}).get_json()["id"]
    user_client.post(f"/api/quizzes/{quiz_id}/attempts", json={"answers": [1, 0]})

    dash = user_client.get("/api/dashboard").get_json()
    assert dash["stats"]["documents"] == 1
    assert dash["stats"]["quizzes_completed"] == 1
    assert dash["stats"]["average_score"] == 100.0
    assert dash["recent_activity"]

    analytics = user_client.get("/api/analytics").get_json()
    assert analytics["score_history"][0]["percent"] == 100.0
    assert analytics["subjects"][0]["subject"] == "Biology"
    assert len(analytics["activity_daily"]) == 14


def test_api_errors_are_json(user_client):
    response = user_client.get("/api/decks/9999")
    assert response.status_code == 404
    assert response.is_json and response.get_json()["error"]


def test_security_headers_present(user_client):
    response = user_client.get("/api/dashboard")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
