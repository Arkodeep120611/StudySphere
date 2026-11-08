from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Raised inside API handlers; rendered as a JSON error response."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def api_error_response(message, status):
    return jsonify({"error": message}), status


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def clean_str(value, max_len, field, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(f"{field} must be text.")
    value = " ".join(value.split())
    if required and not value:
        raise ApiError(f"{field} is required.")
    if len(value) > max_len:
        raise ApiError(f"{field} must be at most {max_len} characters.")
    return value


def clamp_int(value, field, lo, hi, default=None):
    if value in (None, ""):
        if default is None:
            raise ApiError(f"{field} is required.")
        return default
    if isinstance(value, bool):
        raise ApiError(f"{field} must be a whole number.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a whole number.")
    if not lo <= number <= hi:
        raise ApiError(f"{field} must be between {lo} and {hi}.")
    return number


def like_pattern(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return api_error_response(err.message, err.status)

    @app.errorhandler(Exception)
    def handle_exception(err):
        is_api = request.path.startswith("/api/")
        if isinstance(err, HTTPException):
            if err.code == 413 and is_api:
                return api_error_response("File is too large. The maximum upload size is 10 MB.", 413)
            if is_api:
                return api_error_response(err.description, err.code)
            return err.get_response()
        app.logger.exception("Unhandled error")
        from .extensions import db

        db.session.rollback()
        if is_api:
            return api_error_response("Something went wrong on the server. Please try again.", 500)
        return "Something went wrong on the server.", 500
