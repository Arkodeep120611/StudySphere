from unittest.mock import patch

from google.auth.exceptions import TransportError

from app.models import User
from conftest import register


def test_register_logs_in_and_redirects_to_dashboard(client):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_duplicate_email_is_rejected(client):
    register(client)
    client.post("/logout")
    response = register(client)
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_short_password_is_rejected(client):
    response = client.post(
        "/register",
        data={"name": "Bo", "email": "bo@example.com", "password": "short", "confirm_password": "short"},
    )
    assert b"Password must be between 8 and 128" in response.data


def test_login_with_wrong_password_fails(client):
    register(client)
    client.post("/logout")
    response = client.post("/login", data={"email": "ada@example.com", "password": "nope-nope"})
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_rejects_external_next_redirect(client):
    register(client)
    client.post("/logout")
    response = client.post(
        "/login?next=https://evil.example.com/",
        data={"email": "ada@example.com", "password": "correct-horse"},
    )
    assert response.headers["Location"].endswith("/dashboard")


def test_protected_pages_redirect_to_login(client):
    response = client.get("/documents")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_protected_api_returns_json_401(client):
    response = client.get("/api/documents")
    assert response.status_code == 401
    assert response.get_json()["error"]


def test_logout_requires_post(user_client):
    assert user_client.get("/logout").status_code == 405


def test_password_change(user_client):
    bad = user_client.post(
        "/api/account/password", json={"current_password": "wrong-one", "new_password": "brand-new-pass"}
    )
    assert bad.status_code == 400
    good = user_client.post(
        "/api/account/password", json={"current_password": "correct-horse", "new_password": "brand-new-pass"}
    )
    assert good.status_code == 200
    user_client.post("/logout")
    assert user_client.post("/login", data={"email": "ada@example.com", "password": "brand-new-pass"}).status_code == 302


# --- Sign in with Google -----------------------------------------------------------------

GOOGLE_VERIFY = "app.routes.auth.google_id_token.verify_oauth2_token"


def google_claims(email="grace@example.com", verified=True, name="Grace Hopper"):
    return {"email": email, "email_verified": verified, "name": name}


def google_post(client, credential="token", remember=False, next_url=""):
    return client.post(
        "/auth/google",
        json={"credential": credential, "remember": remember, "next": next_url},
    )


def test_google_sign_in_creates_account_and_logs_in(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims()):
        response = google_post(client)
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200
    with client.application.app_context():
        user = User.query.filter_by(email="grace@example.com").one()
        assert user.name == "Grace Hopper"
        assert not user.has_password


def test_google_sign_in_passes_client_id_to_verifier(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims()) as verify:
        google_post(client, credential="abc")
    args = verify.call_args.args
    assert args[0] == "abc"
    assert args[2] == client.application.config["GOOGLE_CLIENT_ID"]


def test_google_sign_in_again_reuses_same_account(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims()):
        google_post(client)
        client.post("/logout")
        response = google_post(client)
    assert response.status_code == 200
    with client.application.app_context():
        assert User.query.filter_by(email="grace@example.com").count() == 1


def test_google_sign_in_rejects_invalid_token(client):
    with patch(GOOGLE_VERIFY, side_effect=ValueError("Token expired")):
        response = google_post(client)
    assert response.status_code == 401
    assert client.get("/dashboard").status_code == 302


def test_google_sign_in_reports_unreachable_google(client):
    with patch(GOOGLE_VERIFY, side_effect=TransportError("down")):
        response = google_post(client)
    assert response.status_code == 503


def test_google_sign_in_requires_verified_email(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims(verified=False)):
        response = google_post(client)
    assert response.status_code == 403
    with client.application.app_context():
        assert User.query.count() == 0


def test_google_sign_in_refuses_to_take_over_password_account(app, client):
    # Someone registered this email with a password first. Google sign-in must not log in to it.
    register(client, email="grace@example.com")
    client.post("/logout")
    with patch(GOOGLE_VERIFY, return_value=google_claims()):
        response = google_post(client)
    assert response.status_code == 409
    assert b"already exists with a password" in response.data
    assert client.get("/dashboard").status_code == 302
    with app.app_context():
        assert User.query.filter_by(email="grace@example.com").one().check_password("correct-horse")


def test_google_only_account_cannot_log_in_with_password(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims()):
        google_post(client)
    client.post("/logout")
    response = client.post("/login", data={"email": "grace@example.com", "password": ""})
    assert b"Invalid email or password" in response.data
    response = client.post("/login", data={"email": "grace@example.com", "password": "anything-at-all"})
    assert b"Invalid email or password" in response.data


def test_google_sign_in_ignores_external_next(client):
    with patch(GOOGLE_VERIFY, return_value=google_claims()):
        response = google_post(client, next_url="https://evil.example.com/")
    assert response.get_json()["redirect"].endswith("/dashboard")


def test_google_sign_in_rejects_missing_credential(client):
    response = client.post("/auth/google", json={})
    assert response.status_code == 400


def test_google_sign_in_hidden_when_not_configured(no_ai_app):
    no_ai_app.config["GOOGLE_CLIENT_ID"] = ""
    client = no_ai_app.test_client()
    assert b'id="google-signin"' not in client.get("/login").data
    response = client.post("/auth/google", json={"credential": "x"})
    assert response.status_code == 404


def test_google_button_rendered_on_login_and_register(client):
    for path in ("/login", "/register"):
        page = client.get(path).data
        assert b'id="google-signin"' in page
        assert b"accounts.google.com/gsi/client" in page
        assert b"472558590499-7rrcapd4aeq5ccu27h2374ggoefnikj9.apps.googleusercontent.com" in page


def test_csp_allows_google_sign_in(client):
    csp = client.get("/login").headers["Content-Security-Policy"]
    assert "https://accounts.google.com" in csp
    assert "frame-src https://accounts.google.com" in csp
