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


def create_challenge(did_string: str) -> SignInChallenge:
    """Create a single-use nonce bound to a DID."""
    nonce = secrets.token_urlsafe(32)
    expires_at = djtz.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS)
    return SignInChallenge.objects.create(
        did_string=did_string, nonce=nonce, expires_at=expires_at
    )


def verify_sign_in_presentation(
    did_string: str,
    vp_jwt: str,
    expected_nonce: str,
    expected_audience: Optional[str] = None,
) -> Tuple[bool, Optional[User], list]:
    """Validate a holder's VP and return the linked user on success."""
    ok, payload, errors = verify_presentation(
        vp_jwt=vp_jwt,
        expected_nonce=expected_nonce,
        expected_audience=expected_audience,
    )
    if not ok:
        return False, None, errors
    if payload.get("iss") != did_string:
        return False, None, ["Holder DID does not match payload iss"]

    # Consume the nonce atomically.
    challenge = SignInChallenge.objects.filter(
        did_string=did_string, nonce=expected_nonce, consumed=False
    ).first()
    if challenge is None:
        return False, None, ["Challenge not found or already consumed"]
    if djtz.now() >= challenge.expires_at:
        return False, None, ["Challenge expired"]
    challenge.consumed = True
    challenge.save(update_fields=["consumed"])

    user_did = UserDID.objects.filter(did_string=did_string).first()
    if user_did is None:
        return False, None, ["DID is not registered"]
    return True, user_did.user, []
