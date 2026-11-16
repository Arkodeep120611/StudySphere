"""Cloudflare Turnstile verification for the login and register forms.

The browser sends `cf-turnstile-response` with the form. The server checks it with siteverify
before any password is checked. Turnstile is active only when both a site key and a secret key
are configured, so local development works without them.
"""

import logging
from urllib.parse import urlparse

import requests

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TOKEN_FIELD = "cf-turnstile-response"
_TIMEOUT_SECONDS = 10
_MAX_TOKEN_LENGTH = 2048

logger = logging.getLogger(__name__)


def is_enabled(config):
    return bool(config.get("TURNSTILE_SITE_KEY") and config.get("TURNSTILE_SECRET_KEY"))


def allowed_hostnames(config):
    explicit = {h.strip().lower() for h in config.get("TURNSTILE_HOSTNAMES", "").split(",") if h.strip()}
    if explicit:
        return explicit
    host = urlparse(config.get("SITE_URL") or "").hostname
    return {host.lower()} if host else set()


def verify(token, action, config, remote_ip=None):
    """Return True only if Cloudflare confirms the token for this action and an allowed hostname.

    Fails closed: a missing token, a network error or a malformed response all return False.
    """
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        return False
    hostnames = allowed_hostnames(config)
    if not hostnames:
        logger.error("Turnstile is enabled but no allowed hostnames are configured.")
        return False

    payload = {"secret": config["TURNSTILE_SECRET_KEY"], "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        response = requests.post(SITEVERIFY_URL, data=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        logger.warning("Turnstile siteverify request failed.", exc_info=True)
        return False

    if not isinstance(result, dict):
        logger.warning("Turnstile siteverify returned a non-object response.")
        return False
    passed = (
        result.get("success") is True
        and result.get("action") == action
        and str(result.get("hostname") or "").lower() in hostnames
    )
    if not passed:
        # Log the reason (never the secret or token) so failures can be diagnosed.
        logger.warning(
            "Turnstile check rejected: success=%s action=%s (expected %s) hostname=%s error-codes=%s",
            result.get("success"),
            result.get("action"),
            action,
            result.get("hostname"),
            result.get("error-codes"),
        )
    return passed
