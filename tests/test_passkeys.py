"""Passkey tests using a software authenticator.

The authenticator generates a real P-256 key and produces the same attestation and assertion
structures a browser would, so the full py_webauthn verification path runs. A real browser or
hardware key is still needed to confirm the UI prompts (see the README testing notes).
"""

import base64
import hashlib
import json
import os
from urllib.parse import urlparse

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.models import PasskeyCredential


def _b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class SoftwareAuthenticator:
    def __init__(self, rp_id):
        self.rp_id = rp_id
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = os.urandom(16)
        self.sign_count = 0

    def _cose_public_key(self):
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}
        )

    def _rp_hash(self):
        return hashlib.sha256(self.rp_id.encode()).digest()

    def register(self, options, origin):
        client_data = json.dumps(
            {"type": "webauthn.create", "challenge": options["challenge"], "origin": origin, "crossOrigin": False}
        ).encode()
        auth_data = (
            self._rp_hash()
            + bytes([0x45])  # user present, user verified, attested credential data included
            + (0).to_bytes(4, "big")
            + bytes(16)  # AAGUID
            + len(self.cred_id).to_bytes(2, "big")
            + self.cred_id
            + self._cose_public_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": _b64u(self.cred_id),
            "rawId": _b64u(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64u(client_data),
                "attestationObject": _b64u(attestation),
                "transports": [],
            },
            "clientExtensionResults": {},
        }

    def assert_login(self, options, origin, sign_count=None):
        self.sign_count += 1
        count = self.sign_count if sign_count is None else sign_count
        client_data = json.dumps(
            {"type": "webauthn.get", "challenge": options["challenge"], "origin": origin, "crossOrigin": False}
        ).encode()
        auth_data = self._rp_hash() + bytes([0x05]) + count.to_bytes(4, "big")  # user present + verified
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": _b64u(self.cred_id),
            "rawId": _b64u(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64u(client_data),
                "authenticatorData": _b64u(auth_data),
                "signature": _b64u(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        }


def _site(app):
    parsed = urlparse(app.config["SITE_URL"])
    return parsed.hostname, f"{parsed.scheme}://{parsed.netloc}"


def _enrol(app, client, name="Laptop"):
    rp_id, origin = _site(app)
    authenticator = SoftwareAuthenticator(rp_id)
    options = client.post("/api/account/passkeys/options").get_json()
    response = client.post(
        "/api/account/passkeys/verify",
        json={"credential": authenticator.register(options, origin), "name": name},
    )
    return authenticator, response


def _login_with(app, authenticator, sign_count=None):
    _, origin = _site(app)
    client = app.test_client()
    options = client.post("/auth/passkey/options").get_json()
    return client, client.post(
        "/auth/passkey/verify",
        json={"credential": authenticator.assert_login(options, origin, sign_count), "remember": False},
    )


def test_passkey_can_be_added_and_used_to_log_in(app, user_client):
    authenticator, enrol = _enrol(app, user_client)
    assert enrol.status_code == 201
    assert enrol.get_json()["name"] == "Laptop"

    listed = user_client.get("/api/account/passkeys").get_json()
    assert [item["name"] for item in listed] == ["Laptop"]

    client, response = _login_with(app, authenticator)
    assert response.status_code == 200
    assert response.get_json()["redirect"] == "/dashboard"
    assert client.get("/api/account/status").status_code == 200


def test_passkey_login_does_not_accept_external_next(app, user_client):
    authenticator, _ = _enrol(app, user_client)
    _, origin = _site(app)
    client = app.test_client()
    options = client.post("/auth/passkey/options").get_json()
    response = client.post(
        "/auth/passkey/verify",
        json={
            "credential": authenticator.assert_login(options, origin),
            "next": "https://evil.example.com/",
        },
    )
    assert response.get_json()["redirect"] == "/dashboard"


def test_passkey_challenge_cannot_be_reused(app, user_client):
    authenticator, _ = _enrol(app, user_client)
    _, origin = _site(app)
    client = app.test_client()
    options = client.post("/auth/passkey/options").get_json()
    assertion = authenticator.assert_login(options, origin)
    assert client.post("/auth/passkey/verify", json={"credential": assertion}).status_code == 200

    # Replaying the same assertion (or using a fresh session without a challenge) must fail.
    assert app.test_client().post("/auth/passkey/verify", json={"credential": assertion}).status_code == 400


def test_passkey_login_rejects_wrong_origin(app, user_client):
    authenticator, _ = _enrol(app, user_client)
    client = app.test_client()
    options = client.post("/auth/passkey/options").get_json()
    assertion = authenticator.assert_login(options, "https://evil.example.com")
    response = client.post("/auth/passkey/verify", json={"credential": assertion})
    assert response.status_code == 401


def test_unregistered_passkey_is_rejected(app, user_client):
    _enrol(app, user_client)
    stranger = SoftwareAuthenticator(_site(app)[0])
    _, response = _login_with(app, stranger)
    assert response.status_code == 401


def test_sign_count_rollback_is_rejected(app, user_client):
    authenticator, _ = _enrol(app, user_client)
    _login_with(app, authenticator)  # stored sign count is now 1
    _, response = _login_with(app, authenticator, sign_count=1)
    assert response.status_code == 401


def test_passkey_login_failure_does_not_log_in(app, user_client):
    authenticator, _ = _enrol(app, user_client)
    client, response = _login_with(app, SoftwareAuthenticator(_site(app)[0]))
    assert response.status_code == 401
    assert client.get("/api/account/status").status_code == 401


def test_passkey_registration_requires_login(client):
    assert client.post("/api/account/passkeys/options").status_code == 401
    assert client.get("/api/account/passkeys").status_code == 401


def test_user_cannot_delete_another_users_passkey(app, user_client):
    _enrol(app, user_client)
    with app.app_context():
        passkey_id = PasskeyCredential.query.first().id

    other = app.test_client()
    other.post(
        "/register",
        data={"name": "Grace", "email": "grace@example.com", "password": "correct-horse", "confirm_password": "correct-horse"},
    )
    assert other.delete(f"/api/account/passkeys/{passkey_id}").status_code == 404
    assert user_client.delete(f"/api/account/passkeys/{passkey_id}").status_code == 200
    assert user_client.get("/api/account/passkeys").get_json() == []


def test_passkey_options_are_not_offered_when_already_logged_in(user_client):
    assert user_client.post("/auth/passkey/options").status_code == 400


def test_login_page_shows_passkey_button_and_settings_card(user_client, client):
    assert b'id="passkey-login-btn"' in client.get("/login").data
    assert b'id="passkey-card"' in user_client.get("/settings").data
