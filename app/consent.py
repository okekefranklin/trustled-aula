"""Policy consent gate — redirect users who have not accepted current policies."""

from flask import redirect, request, url_for
from flask_login import current_user

CONSENT_EXEMPT_ENDPOINTS = frozenset({
    "auth.login",
    "auth.logout",
    "auth.consent",
})


def require_policy_consent():
    """Before-request hook: block features until policies are accepted."""
    if not current_user.is_authenticated:
        return None

    endpoint = request.endpoint or ""
    if endpoint.startswith("static"):
        return None
    if endpoint in CONSENT_EXEMPT_ENDPOINTS:
        return None

    if current_user.has_accepted_current_policy():
        return None

    return redirect(url_for("auth.consent"))
