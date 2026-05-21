"""Sign-in with DID: challenge + VP verification to mint JWT tokens."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.utils import timezone as djtz

from ..models import SignInChallenge, UserDID
from .vc_verifier_service import verify_presentation

User = get_user_model()

CHALLENGE_TTL_SECONDS = 300

# Cookie name we hand back to the browser at challenge issuance. The
# verify endpoint reads the same key off `request.COOKIES`.
SIGNIN_BINDING_COOKIE = "did_signin_binding"


def create_challenge(did_string: str) -> Tuple[SignInChallenge, str]:
    """
    Create a single-use nonce bound to a DID and a fresh binding token.

    Returns ``(challenge, binding_token)``. The caller (view) is
    responsible for setting ``binding_token`` on an HttpOnly + Secure +
    SameSite=Strict cookie that the holder's browser will echo back on
    the verify request. Without that cookie the verify will fail even
    if the nonce + VP are otherwise valid (audit fix C9).
    """
    nonce = secrets.token_urlsafe(32)
    binding_token = secrets.token_urlsafe(24)
    expires_at = djtz.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS)
    challenge = SignInChallenge.objects.create(
        did_string=did_string,
        nonce=nonce,
        expires_at=expires_at,
        binding_token=binding_token,
    )
    return challenge, binding_token


def verify_sign_in_presentation(
    did_string: str,
    vp_jwt: str,
    expected_nonce: str,
    expected_audience: Optional[str] = None,
    client_binding: Optional[str] = None,
) -> Tuple[bool, Optional[User], list]:
    """
    Validate a holder's VP and return the linked user on success.

    ``client_binding`` is the value of the ``did_signin_binding`` cookie
    presented by the browser. It MUST equal the value stored on the
    challenge row. Pre-C9 challenges (created before the binding column
    was added) carry an empty `binding_token` and are accepted without a
    cookie — this is a one-release backward compat window; the next
    minor version should make `client_binding` mandatory.
    """
    ok, payload, errors = verify_presentation(
        vp_jwt=vp_jwt,
        expected_nonce=expected_nonce,
        expected_audience=expected_audience,
    )
    if not ok:
        return False, None, errors
    if payload.get("iss") != did_string:
        return False, None, ["Holder DID does not match payload iss"]

    # Atomically consume the nonce — and, if a binding_token was issued
    # alongside it, require the same cookie value on the verify call.
    # Two concurrent verifies cannot both see ``consumed=False`` because
    # the UPDATE returns the row count it touched.
    filter_kwargs = dict(
        did_string=did_string,
        nonce=expected_nonce,
        consumed=False,
        expires_at__gt=djtz.now(),
    )

    # Find the matching live challenge row (without consuming) so we can
    # branch on whether it has a binding token. We then re-check the
    # binding inside the atomic UPDATE so the consume + check happen
    # together — otherwise the nonce could be consumed without the
    # cookie check ever firing on a concurrent legit request.
    candidate = SignInChallenge.objects.filter(**filter_kwargs).only(
        "binding_token"
    ).first()
    if candidate is None:
        return False, None, ["Challenge not found, expired, or already consumed"]

    if candidate.binding_token:
        if not client_binding:
            return False, None, ["Missing sign-in binding cookie"]
        if not secrets.compare_digest(candidate.binding_token, client_binding):
            return False, None, ["Sign-in binding mismatch"]
        filter_kwargs["binding_token"] = candidate.binding_token

    updated = SignInChallenge.objects.filter(**filter_kwargs).update(consumed=True)
    if not updated:
        # Race with another consumer; treat as already consumed.
        return False, None, ["Challenge not found, expired, or already consumed"]

    user_did = UserDID.objects.filter(did_string=did_string).first()
    if user_did is None:
        return False, None, ["DID is not registered"]
    return True, user_did.user, []
