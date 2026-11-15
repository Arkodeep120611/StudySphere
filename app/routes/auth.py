import re
import secrets

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from google.auth.exceptions import TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import UNUSABLE_PASSWORD_PREFIX, User
from ..utils import api_error_response

bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next(target):
    """Only allow same-site relative redirects after login."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def _google_display_name(info, email):
    raw = info.get("name") or info.get("given_name") or email.split("@", 1)[0]
    return " ".join(str(raw).split())[:80] or "Student"


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(_safe_next(request.args.get("next")) or url_for("pages.dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@bp.post("/auth/google")
def google_login():
    """Sign in with a Google ID token obtained by the Google Identity Services button.

    The token is verified server-side (signature, audience, issuer and expiry). Accounts are
    matched by verified email. Existing password accounts are never taken over by Google sign-in.
    """
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id:
        return api_error_response("Google sign-in is not configured.", 404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("credential"), str):
        return api_error_response("Google sign-in did not return a credential. Please try again.", 400)

    try:
        info = google_id_token.verify_oauth2_token(data["credential"], google_requests.Request(), client_id)
    except ValueError:
        return api_error_response("Google sign-in could not be verified. Please try again.", 401)
    except TransportError:
        return api_error_response("Could not reach Google. Please try again shortly.", 503)

    email = str(info.get("email") or "").strip().lower()
    if not email or len(email) > 255 or not _EMAIL_RE.match(email):
        return api_error_response("Your Google account has no usable email address.", 400)
    if info.get("email_verified") not in (True, "true"):
        return api_error_response("Verify your email address with Google, then try again.", 403)

    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(
            name=_google_display_name(info, email),
            email=email,
            password_hash=UNUSABLE_PASSWORD_PREFIX + secrets.token_urlsafe(32),
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Another request created the same account first; sign in to that one.
            db.session.rollback()
            user = User.query.filter_by(email=email).first()
            if user is None:
                return api_error_response("Could not create your account. Please try again.", 409)

    if user.has_password:
        return api_error_response(
            "An account with this email already exists with a password. Log in with your password instead.",
            409,
        )

    login_user(user, remember=bool(data.get("remember")))
    next_url = _safe_next(data.get("next") if isinstance(data.get("next"), str) else None)
    return jsonify({"redirect": next_url or url_for("pages.dashboard")})


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    form = {"name": "", "email": ""}
    if request.method == "POST":
        name = " ".join((request.form.get("name") or "").split())
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        form = {"name": name, "email": email}

        error = None
        if not name or len(name) > 80:
            error = "Enter your name (up to 80 characters)."
        elif len(email) > 255 or not _EMAIL_RE.match(email):
            error = "Enter a valid email address."
        elif not 8 <= len(password) <= 128:
            error = "Password must be between 8 and 128 characters."
        elif password != confirm:
            error = "Passwords do not match."

        if error is None:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = "An account with this email already exists."
            else:
                login_user(user)
                flash("Welcome to StudySphere! Upload your first document to get started.", "success")
                return redirect(url_for("pages.dashboard"))

        flash(error, "error")

    return render_template("register.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
