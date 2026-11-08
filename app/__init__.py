import os

from flask import Flask, redirect, request, url_for

from . import models  # noqa: F401  (registers tables with SQLAlchemy)
from .config import Config
from .extensions import csrf, db, login_manager
from .utils import api_error_response, register_error_handlers

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        # Read-only filesystems (Vercel's function bundle) cannot create instance/.
        pass

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return api_error_response("Please log in to continue.", 401)
        return redirect(url_for("auth.login", next=request.path))

    from .routes import register_blueprints

    register_blueprints(app)
    register_error_handlers(app)

    @app.context_processor
    def inject_globals():
        return {"ai_enabled": bool(app.config.get("GEMINI_API_KEY"))}

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    with app.app_context():
        db.create_all()

    return app
