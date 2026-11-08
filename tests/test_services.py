import io
import zipfile
from unittest.mock import patch

import fitz
import pytest
from docx import Document as DocxDocument

from app.services.context import build_context, is_summary_request
from app.services.extraction import extract_text
from app.services.generation import generate_flashcards, generate_quiz_questions
from app.utils import ApiError

MAX = 300_000


def _pdf_bytes(text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(paragraphs):
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ---------- extraction ----------

def test_extracts_txt_and_normalises_whitespace():
    text = extract_text(b"\xef\xbb\xbfHello\r\n\r\n\r\n\r\nWorld\x07!", "txt", MAX)
    assert text == "Hello\n\nWorld!"


def test_extracts_pdf_text():
    text = extract_text(_pdf_bytes("Mitochondria are the powerhouse of the cell"), "pdf", MAX)
    assert "Mitochondria" in text


def test_extracts_docx_text():
    text = extract_text(_docx_bytes(["Newton's second law states F = ma."]), "docx", MAX)
    assert "Newton" in text


def test_renamed_file_is_rejected():
    # A plain text file uploaded with a .pdf extension must not be parsed as a PDF.
    with pytest.raises(ApiError, match="valid PDF"):
        extract_text(b"just some notes", "pdf", MAX)


def test_binary_txt_is_rejected():
    with pytest.raises(ApiError, match="binary"):
        extract_text(b"\x00\x01\x02\x03", "txt", MAX)


def test_empty_text_is_rejected():
    with pytest.raises(ApiError, match="No readable text"):
        extract_text(b"   \n\n  ", "txt", MAX)


def test_oversized_text_is_rejected():
    with pytest.raises(ApiError, match="maximum is 10"):
        extract_text(b"a" * 50, "txt", 10)


def test_zip_without_word_document_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "hi")
    with pytest.raises(ApiError, match="valid DOCX"):
        extract_text(buffer.getvalue(), "docx", MAX)


# ---------- context selection ----------

def test_short_text_is_returned_whole():
    assert build_context("short notes", 1000) == "short notes"


def test_long_text_is_trimmed_to_budget():
    text = "x" * 50_000
    assert len(build_context(text, 10_000)) <= 10_000


def test_focus_prefers_relevant_chunk():
    filler = "lorem ipsum dolor sit amet " * 200
    text = filler + "\n" + "The mitochondria produces ATP through respiration. " * 40 + filler
    context = build_context(text, 6000, focus="How does mitochondria make energy?")
    assert "mitochondria" in context


def test_summary_requests_are_detected():
    assert is_summary_request("Please summarise this")
    assert is_summary_request("Give me an overview")
    assert not is_summary_request("What is osmosis?")


# ---------- AI output validation ----------

@pytest.fixture()
def ai_app(app):
    return app


def test_quiz_validation_drops_malformed_items(ai_app):
    payload = {
        "questions": [
            {"type": "mcq", "question": "Good?", "options": ["a", "b", "c", "d"], "answer_index": 2, "explanation": "Because."},
            {"type": "mcq", "question": "Duplicate options", "options": ["a", "a", "c", "d"], "answer_index": 0, "explanation": ""},
            {"type": "mcq", "question": "Answer out of range", "options": ["a", "b", "c", "d"], "answer_index": 9, "explanation": ""},
            {"type": "true_false", "question": "True statement?", "options": ["x"], "answer_index": 0, "explanation": "Yes."},
            "not a dict",
        ]
    }
    with ai_app.app_context(), patch("app.services.generation.generate_json", return_value=payload):
        questions = generate_quiz_questions("notes", 10, "medium", "mixed", 60000)
    assert [q["question"] for q in questions] == ["Good?", "True statement?"]
    assert questions[1]["options"] == ["True", "False"]


def test_quiz_rejects_when_nothing_usable(ai_app):
    with ai_app.app_context(), patch("app.services.generation.generate_json", return_value={"questions": []}):
        with pytest.raises(ApiError) as info:
            generate_quiz_questions("notes", 5, "easy", "mcq", 60000)
    assert info.value.status == 502


def test_quiz_type_filter_is_enforced(ai_app):
    payload = {"questions": [{"type": "true_false", "question": "A statement?", "options": ["True", "False"], "answer_index": 0, "explanation": ""}]}
    with ai_app.app_context(), patch("app.services.generation.generate_json", return_value=payload):
        with pytest.raises(ApiError):
            generate_quiz_questions("notes", 5, "easy", "mcq", 60000)


def test_flashcards_dedupe_and_skip_empty(ai_app):
    payload = {
        "cards": [
            {"question": "What is ATP?", "answer": "Energy currency of the cell."},
            {"question": "what is atp?", "answer": "Duplicate."},
            {"question": "", "answer": "No question."},
            {"question": "Define osmosis", "answer": ""},
        ]
    }
    with ai_app.app_context(), patch("app.services.generation.generate_json", return_value=payload):
        cards = generate_flashcards("notes", 15, 60000)
    assert cards == [{"question": "What is ATP?", "answer": "Energy currency of the cell."}]


def test_missing_api_key_gives_503_not_fake_output(no_ai_app):
    with no_ai_app.app_context():
        with pytest.raises(ApiError) as info:
            generate_quiz_questions("notes", 5, "easy", "mcq", 60000)
    assert info.value.status == 503
    assert "GEMINI_API_KEY" in info.value.message
