from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.extensions import db
from app.services import turnstile

SITE_KEY = "0x4AAAAAAGDmnUDGhRim2PYn"
SECRET = "test-secret-key"
HOST = "studysphere-hub.vercel.app"


@pytest.fixture()
def tt_app():
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "GEMINI_API_KEY": "",
            "TURNSTILE_SITE_KEY": SITE_KEY,
            "TURNSTILE_SECRET_KEY": SECRET,
            "SITE_URL": f"https://{HOST}",
            "TURNSTILE_HOSTNAMES": "",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _siteverify(success=True, action="login", hostname=HOST):
    response = MagicMock()
    response.json.return_value = {"success": success, "action": action, "hostname": hostname}
    return response


def test_widget_rendered_on_login_and_register(tt_app):
    client = tt_app.test_client()
    for path, action in (("/login", "login"), ("/register", "register")):
        html = client.get(path).get_data(as_text=True)
        assert 'class="cf-turnstile' in html
        assert f'data-sitekey="{SITE_KEY}"' in html
        assert f'data-action="{action}"' in html
        assert "challenges.cloudflare.com/turnstile/v0/api.js" in html


def test_login_blocked_without_token(tt_app):
    client = tt_app.test_client()
    with patch("app.services.turnstile.requests.post") as post:
        response = client.post("/login", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 200
    post.assert_not_called()
    assert "Security check failed" in response.get_data(as_text=True)


def test_login_allowed_when_siteverify_passes(tt_app):
    client = tt_app.test_client()
    with patch("app.services.turnstile.requests.post", return_value=_siteverify()) as post:
        client.post(
            "/login",
            data={"email": "a@example.com", "password": "x", "cf-turnstile-response": "tok"},
        )
    sent = post.call_args.kwargs["data"]
    assert sent["secret"] == SECRET
    assert sent["response"] == "tok"
    assert "Security check failed" not in client.get("/login").get_data(as_text=True)


def test_register_rejected_on_wrong_action(tt_app):
    client = tt_app.test_client()
    with patch("app.services.turnstile.requests.post", return_value=_siteverify(action="login")):
        response = client.post(
            "/register",
            data={
                "name": "Ada",
                "email": "ada@example.com",
                "password": "correct-horse",
                "confirm_password": "correct-horse",
                "cf-turnstile-response": "tok",
            },
        )
    assert "Security check failed" in response.get_data(as_text=True)


def test_fails_closed_on_network_error(tt_app):
    import requests

    with tt_app.app_context():
        with patch(
            "app.services.turnstile.requests.post", side_effect=requests.ConnectionError("down")
        ):
            assert turnstile.verify("tok", "login", tt_app.config) is False


def test_rejects_unexpected_hostname(tt_app):
    with tt_app.app_context():
        with patch("app.services.turnstile.requests.post", return_value=_siteverify(hostname="evil.example")):
            assert turnstile.verify("tok", "login", tt_app.config) is False


def test_disabled_when_secret_missing():
    assert turnstile.is_enabled({"TURNSTILE_SITE_KEY": SITE_KEY, "TURNSTILE_SECRET_KEY": ""}) is False
    assert turnstile.is_enabled({"TURNSTILE_SITE_KEY": "", "TURNSTILE_SECRET_KEY": SECRET}) is False
