"""WebAuthn passkeys: registration from Settings and passwordless login from the login page.

The relying party ID and origin come from SITE_URL, so a passkey only works on the configured
site. Each challenge is random, kept in the signed server-side session with its purpose and an
expiry, and consumed on first use so it cannot be replayed.
"""

import time
from urllib.parse import urlparse

from flask import session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,

    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..extensions import db
from ..models import PasskeyCredential, User, utcnow
from ..utils import ApiError

SESSION_KEY = "passkey_challenge"
CHALLENGE_TTL_SECONDS = 300
RP_NAME = "StudySphere"
MAX_PASSKEYS_PER_USER = 10


class PasskeyError(ApiError):
    pass


def _relying_party(config):
    parsed = urlparse(config["SITE_URL"])
    return parsed.hostname, f"{parsed.scheme}://{parsed.netloc}"


def _store_challenge(challenge, purpose, user_id=None):
    session[SESSION_KEY] = {
        "challenge": bytes_to_base64url(challenge),
        "purpose": purpose,
        "user_id": user_id,
        "expires": time.time() + CHALLENGE_TTL_SECONDS,
    }


def _take_challenge(purpose, user_id=None):
    """Return the stored challenge bytes for this purpose and remove it so it is single-use."""
    stored = session.pop(SESSION_KEY, None)
    if not isinstance(stored, dict) or stored.get("purpose") != purpose:
        raise PasskeyError("Your passkey request expired. Please try again.", 400)
    if stored.get("user_id") != user_id or time.time() > stored.get("expires", 0):
        raise PasskeyError("Your passkey request expired. Please try again.", 400)
    return base64url_to_bytes(stored["challenge"])


def begin_registration(user, config):
    rp_id, _ = _relying_party(config)
    existing = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(p.credential_id))
        for p in PasskeyCredential.query.filter_by(user_id=user.id).all()
    ]
    if len(existing) >= MAX_PASSKEYS_PER_USER:
        raise PasskeyError(f"You can register up to {MAX_PASSKEYS_PER_USER} passkeys.", 400)

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=existing,
    )
    _store_challenge(options.challenge, "register", user.id)
    return options_to_json_dict(options)


def finish_registration(user, credential, name, config):
    rp_id, origin = _relying_party(config)
    challenge = _take_challenge("register", user.id)
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        raise PasskeyError("The passkey could not be verified. Please try again.", 400) from exc

    passkey = PasskeyCredential(
        user_id=user.id,
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        name=name,
    )
    db.session.add(passkey)
    db.session.commit()
    return passkey


def begin_login(config):
    rp_id, _ = _relying_party(config)
    # No allow-list: the browser offers the passkeys saved for this site (discoverable credentials).
    options = generate_authentication_options(
        rp_id=rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _store_challenge(options.challenge, "login")
    return options_to_json_dict(options)


def finish_login(credential, config):
    """Verify a passkey sign-in and return the user it belongs to."""
    rp_id, origin = _relying_party(config)
    challenge = _take_challenge("login")
    if not isinstance(credential, dict) or not isinstance(credential.get("id"), str):
        raise PasskeyError("Passkey sign-in did not return a credential. Please try again.", 400)

    passkey = PasskeyCredential.query.filter_by(credential_id=credential["id"]).first()
    if passkey is None:
        raise PasskeyError("This passkey is not registered with StudySphere.", 401)

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        raise PasskeyError("The passkey could not be verified. Please try again.", 401) from exc

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = utcnow()
    db.session.commit()
    return db.session.get(User, passkey.user_id)
