import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _database_uri():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Hosted Postgres providers hand out postgres:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url
    if os.environ.get("VERCEL"):
        # The project directory is read-only on Vercel. This SQLite file is temporary and is
        # lost when the function instance is recycled. Set DATABASE_URL for persistent data.
        return "sqlite:////tmp/studysphere.db"
    return f"sqlite:///{(BASE_DIR / 'instance' / 'studysphere.db').as_posix()}"


class Config:
    # Set SECRET_KEY in .env for stable sessions. Without it, a random key is used per process.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads are parsed in memory and only the extracted text is stored.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = frozenset({"pdf", "txt", "docx"})
    MAX_DOCUMENT_CHARS = 300_000

    # Maximum characters of notes sent to Gemini in one request.
    AI_CONTEXT_CHARS = 60_000

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_TIME_LIMIT = None
