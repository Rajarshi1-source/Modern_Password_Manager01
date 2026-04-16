"""URL routing for the zk_proofs app (mounted under /api/zk/)."""

from django.urls import path

from .views import (
    ZKCommitmentViewSet,
    ZKSessionViewSet,
    list_attempts,
    list_my_invites,
    resolve_invite,
    schemes,
    submit_session_proof,
    verify_equality,
)

_commitment_collection = ZKCommitmentViewSet.as_view({"get": "list", "post": "create"})
_commitment_detail = ZKCommitmentViewSet.as_view({"get": "retrieve", "delete": "destroy"})

_session_collection = ZKSessionViewSet.as_view({"get": "list", "post": "create"})
_session_detail = ZKSessionViewSet.as_view({"get": "retrieve", "delete": "destroy"})
_session_invite = ZKSessionViewSet.as_view({"post": "invite"})
_session_revoke_participant = ZKSessionViewSet.as_view({"post": "revoke_participant"})

urlpatterns = [
    path("commit/", _commitment_collection, name="zk-commit-list"),
    path("commit/<uuid:pk>/", _commitment_detail, name="zk-commit-detail"),
    path("verify-equality/", verify_equality, name="zk-verify-equality"),
    path("attempts/", list_attempts, name="zk-attempts-list"),
    path("schemes/", schemes, name="zk-schemes"),

    # Phase 1b: multi-party sessions
    path("sessions/", _session_collection, name="zk-session-list"),
    path("sessions/<uuid:pk>/", _session_detail, name="zk-session-detail"),
    path("sessions/<uuid:pk>/invite/", _session_invite, name="zk-session-invite"),
    path(
        "sessions/<uuid:pk>/participants/<uuid:participant_id>/revoke/",
        _session_revoke_participant,
        name="zk-session-revoke-participant",
    ),
    path("sessions/join/<str:token>/", resolve_invite, name="zk-session-resolve-invite"),
    path("sessions/submit-proof/", submit_session_proof, name="zk-session-submit-proof"),
    path("sessions/my-invites/", list_my_invites, name="zk-session-my-invites"),
]
