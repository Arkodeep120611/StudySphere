# StudySphere

An AI-powered study platform for students. Upload your notes (PDF, TXT or DOCX), then generate quizzes, flashcards and document-grounded answers with Google Gemini, and track your progress.

**Stack:** Flask · SQLite + SQLAlchemy · Flask-Login · Flask-WTF (CSRF) · Google Gemini via the official `google-genai` SDK · PyMuPDF · python-docx · Chart.js · Lucide icons · plain HTML/CSS/JavaScript with `fetch()`.

## Features

| Area | What it does |
| --- | --- |
| Authentication | Register, log in, log out, scrypt-hashed passwords, "keep me logged in", password change, profile name. |
| Dashboard | Document count, quiz attempts, average score, flashcards known, 7-day activity, recent activity and documents. |
| Documents | Upload PDF/TXT/DOCX (10 MB max), extracted-text view, search across titles, subjects and text with highlighted snippets, edit, delete. |
| AI quizzes | Multiple-choice, true/false or mixed; easy/medium/hard; 1–20 questions. Scoring, per-question explanations, retakes and attempt history. |
| Flashcards | AI-generated decks, 3D flip animation, previous/next, Known/Revise tracking, filters, reset, keyboard shortcuts (←/→, Space, K, R). |
| AI assistant | Chat grounded in one document. Quick actions for summaries and key concepts. Says so when the answer isn't in the notes. |
| Analytics | Score trend, 14-day activity, average score by subject, flashcard mastery, subject table. |
| Settings | Profile, light/dark theme (saved in the browser), password change, AI status. |

## Quick start

Requires Python 3.12+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env          # Windows: copy .env.example .env
# Edit .env and set GEMINI_API_KEY (get one at https://aistudio.google.com/app/apikey)
# and a SECRET_KEY, for example: python -c "import secrets; print(secrets.token_hex(32))"

# 4. Run
python run.py                 # http://127.0.0.1:5000
```

The SQLite database is created automatically in `instance/studysphere.db` on first start.

Without `GEMINI_API_KEY` the app still works for uploads, search, analytics and manual review. AI features (quizzes, flashcards, assistant) show a clear "not configured" error. They never return made-up content.

## Configuration

All settings come from environment variables or `.env` (see `.env.example`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | _(empty)_ | Gemini API key. Read on the server only; never sent to the browser. |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Model used for generation. Change if a newer Flash model is preferred. |
| `SECRET_KEY` | random per process | Signs session cookies. Set it, or sessions reset on every restart. |
| `DATABASE_URL` | `instance/studysphere.db` | Any SQLAlchemy URL. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` when serving over HTTPS. |
| `HOST`, `PORT`, `FLASK_DEBUG` | `127.0.0.1`, `5000`, `0` | Used by `run.py`. Keep debug off outside development. |

## Tests

```bash
pip install pytest
python -m pytest
```

The suite (42 tests) covers authentication, file extraction (including renamed and corrupt files), context selection, AI output validation, the JSON API, per-user data isolation, security headers and the rendering of every page. Gemini is mocked at the service boundary, and an autouse fixture fails any test that reaches the real SDK, so the suite runs offline.

## Project structure

```
run.py                       Entry point
app/
  __init__.py                App factory, security headers, error wiring
  config.py                  Settings (reads .env)
  extensions.py              db, login manager, CSRF
  models.py                  SQLAlchemy models (every row has an owner)
  utils.py                   ApiError, input helpers, JSON error handlers
  routes/
    auth.py                  /login, /register, /logout
    pages.py                 Server-rendered pages (login required, owner-checked)
    documents.py             /api/documents
    quizzes.py               /api/quizzes (generate, attempt, score)
    flashcards.py            /api/decks, /api/cards
    chat.py                  /api/documents/<id>/chat
    analytics.py             /api/dashboard, /api/analytics
    account.py               /api/account (profile, password, AI status)
  services/
    extraction.py            PDF/DOCX/TXT text extraction with validation
    context.py               Chooses document excerpts that fit the model budget
    ai.py                    Thin wrapper around google-genai
    generation.py            Prompts + strict validation of AI output
    activity.py              Records study activity
  templates/                 Jinja2 pages
  static/css/style.css       Theme (light + dark), responsive layout
  static/js/                 One script per page, plus common.js (fetch helper)
tests/                       pytest suite
```

## Security

- **Authentication:** scrypt password hashing (Werkzeug), Flask-Login sessions, HttpOnly and SameSite=Lax cookies, safe `next` redirects.
- **Authorization:** every document, quiz, deck, card and chat query is filtered by the logged-in user. Other users' IDs return 404.
- **CSRF:** Flask-WTF protects all state-changing requests. The JavaScript sends the token in the `X-CSRFToken` header.
- **Uploads:** extension allow-list, magic-byte checks (a renamed file is rejected), 10 MB request limit, encrypted-PDF and page-count limits, ZIP size check for DOCX. Files are parsed in memory and only the extracted text is stored, so no user files are served back.
- **Output safety:** all user content is HTML-escaped in templates and in the JavaScript renderer. AI output is validated item by item and malformed items are dropped.
- **Headers:** Content-Security-Policy (no inline scripts), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Cache-Control: no-store` on API responses.
- **Secrets:** the Gemini key is read on the server only. `.env` is git-ignored.
- **Prompt injection:** notes are passed inside delimiters and the model is told to treat them as data. This reduces the risk but cannot remove it entirely.

## Known limitations

- **Scanned PDFs** (images without text) are rejected. OCR is not included.
- **Original files are not kept.** Only the extracted text is stored. Re-upload if you need the original.
- **No migrations.** The schema is created with `db.create_all()`. Schema changes need a migration tool such as Flask-Migrate, or deleting the database during development.
- **No login rate limiting.** Add it (for example with Flask-Limiter) before exposing the app publicly.
- **Single-process server.** `run.py` uses the Flask development server. For production, use a WSGI server such as gunicorn, with a fixed `SECRET_KEY`.
- **AI accuracy.** Answers are grounded in the document excerpts, but generated content can still be wrong. Check important material against your notes.
- **Charts** load Chart.js and Lucide from public CDNs (jsdelivr and unpkg), so those pages need internet access.
