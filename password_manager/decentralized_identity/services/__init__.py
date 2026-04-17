"""Service exports for decentralized_identity."""

from .did_service import (  # noqa: F401
    create_did_key_from_public_key,
    did_document_for_did_key,
    did_document_for_did_web,
    ensure_issuer_key,
    multibase_decode,
    multibase_encode_ed25519_pub,
    public_key_from_did_key,
    register_user_did,
    resolve_did,
    verify_signature,
)
from .vc_issuer_service import (  # noqa: F401
    ensure_schema,
    issue_credential,
)
from .vc_verifier_service import (  # noqa: F401
    verify_presentation,
    verify_vc_jwt,
)
from .sign_in_service import (  # noqa: F401
    create_challenge,
    verify_sign_in_presentation,
)
