from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from ..extensions import db
from ..services.ai import ai_enabled
from ..utils import ApiError, clean_str, json_body

bp = Blueprint("account", __name__, url_prefix="/api/account")


@bp.get("/status")
@login_required
def status():
    return jsonify(
        {
            "ai_enabled": ai_enabled(),
            "model": current_app.config["GEMINI_MODEL"],
            "user": current_user.to_dict(),
        }
    )


@bp.patch("/profile")
@login_required
def update_profile():
    name = clean_str(json_body().get("name"), 80, "Name", required=True)
    current_user.name = name
    db.session.commit()
    return jsonify(current_user.to_dict())


@bp.post("/password")
@login_required
def change_password():
    data = json_body()
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    if not current_user.check_password(current_password):
        raise ApiError("Your current password is incorrect.", 400)
    if not 8 <= len(new_password) <= 128:
        raise ApiError("New password must be between 8 and 128 characters.")
    if new_password == current_password:
        raise ApiError("New password must be different from the current password.")
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True})
