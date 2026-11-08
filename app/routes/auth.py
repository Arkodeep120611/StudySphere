import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next(target):
    """Only allow same-site relative redirects after login."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


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
