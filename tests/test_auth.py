from conftest import register


def test_register_logs_in_and_redirects_to_dashboard(client):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert client.get("/").status_code == 200


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
    assert response.headers["Location"].endswith("/")


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
