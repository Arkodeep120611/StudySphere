import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture(autouse=True)
def block_real_gemini():
    """Fail loudly if any test reaches the real Gemini SDK. pytest.fail is a BaseException,
    so the AI wrapper's `except Exception` cannot hide it."""

    def _blocked(*args, **kwargs):
        pytest.fail("Unmocked Gemini client construction inside a test")

    with patch("app.services.ai.genai.Client", side_effect=_blocked):
        yield


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "test-model",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def no_ai_app():
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "GEMINI_API_KEY": "",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="ada@example.com", name="Ada", password="correct-horse"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password, "confirm_password": password},
    )


@pytest.fixture()
def user_client(app):
    """A test client logged in as a fresh user."""
    client = app.test_client()
    register(client)
    return client


def upload_txt(client, text="Photosynthesis converts light energy into chemical energy in plants.", title=None, subject=None):
    data = {"file": (io.BytesIO(text.encode("utf-8")), "notes.txt")}
    if title:
        data["title"] = title
    if subject:
        data["subject"] = subject
    return client.post("/api/documents", data=data, content_type="multipart/form-data")
