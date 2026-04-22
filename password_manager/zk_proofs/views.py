"""HTTP views for the zk_proofs app."""

from __future__ import annotations

import base64

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ZKCommitment,
    ZKSession,
    ZKSessionParticipant,
    ZKVerificationAttempt,
)
from .providers import available_schemes, get_provider
from .serializers import (
    ZKCommitmentCreateSerializer,
    ZKCommitmentSerializer,
    ZKEqualityProofSerializer,
    ZKSessionCreateSerializer,
    ZKSessionInviteSerializer,
    ZKSessionJoinInfoSerializer,
    ZKSessionParticipantOwnerSerializer,
    ZKSessionSerializer,
    ZKSessionSubmitProofSerializer,
    ZKVerificationAttemptSerializer,
)


class ZKCommitmentViewSet(viewsets.ViewSet):
    """CRUD-ish surface for user-owned commitments.

    ``create`` is idempotent per ``(scope_type, scope_id, scheme)`` — a second
    post with the same key updates the stored commitment. This matches the
    common password-rotation flow: a new commitment simply replaces the old
    one.
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        qs = ZKCommitment.objects.filter(user=request.user)
        scope_type = request.query_params.get("scope_type")
        if scope_type:
            qs = qs.filter(scope_type=scope_type)
        scope_id = request.query_params.get("scope_id")
        if scope_id:
            qs = qs.filter(scope_id=scope_id)
        qs = qs.order_by("-created_at")
        data = ZKCommitmentSerializer(qs, many=True).data
        return Response(data)

    def retrieve(self, request, pk=None):
        commitment = get_object_or_404(ZKCommitment, pk=pk, user=request.user)
        return Response(ZKCommitmentSerializer(commitment).data)

    def create(self, request):
        serializer = ZKCommitmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        provider = get_provider(payload["scheme"])
        if len(payload["commitment"]) != provider.commitment_size():
            return Response(
                {"detail": f"Commitment must be exactly {provider.commitment_size()} bytes for {payload['scheme']}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not provider.is_valid_commitment(payload["commitment"]):
            return Response(
                {"detail": "Commitment did not decode as a valid point for the declared scheme."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            commitment, created = ZKCommitment.objects.update_or_create(
                user=request.user,
                scope_type=payload["scope_type"],
                scope_id=payload["scope_id"],
                scheme=payload["scheme"],
                defaults={"commitment": payload["commitment"]},
            )
        except IntegrityError:
            # The ``(user, commitment_fingerprint)`` unique constraint fires
            # when the caller tries to store the same commitment bytes under
            # a different scope — a strong signal of either a misconfigured
            # client or an attempt to set up the D=0 equality-proof trick.
            return Response(
                {"detail": "Commitment bytes are already registered for this user."},
                status=status.HTTP_409_CONFLICT,
            )
        out = ZKCommitmentSerializer(commitment).data
        return Response(
            out,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, pk=None):
        commitment = get_object_or_404(ZKCommitment, pk=pk, user=request.user)
        commitment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_equality(request):
    """
    Verify that two of the caller's commitments hide the same secret.

    Returns ``{verified, scheme, attempt_id, verified_at}``. Every call is
    recorded in ``ZKVerificationAttempt`` regardless of outcome.
    """
    serializer = ZKEqualityProofSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    commitment_a = get_object_or_404(
        ZKCommitment, pk=payload["commitment_a_id"], user=request.user,
    )
    commitment_b = get_object_or_404(
        ZKCommitment, pk=payload["commitment_b_id"], user=request.user,
    )

    if commitment_a.id == commitment_b.id:
        return Response(
            {"detail": "commitment_a_id and commitment_b_id must refer to different commitments."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if commitment_a.scheme != commitment_b.scheme:
        return Response(
            {"detail": "Commitments use incompatible schemes."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    provider = get_provider(commitment_a.scheme)
    if (
        len(payload["proof_T"]) != provider.proof_T_size()
        or len(payload["proof_s"]) != provider.proof_s_size()
    ):
        attempt = ZKVerificationAttempt.objects.create(
            user=request.user,
            commitment_a=commitment_a,
            commitment_b=commitment_b,
            scheme=commitment_a.scheme,
            result=False,
            verifier_user=request.user,
            error_message="Malformed proof sizes",
        )
        return Response(
            {
                "verified": False,
                "attempt_id": str(attempt.id),
                "scheme": commitment_a.scheme,
                "detail": "Proof component sizes do not match the declared scheme.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    ok = provider.verify_equality(
        bytes(commitment_a.commitment),
        bytes(commitment_b.commitment),
        payload["proof_T"],
        payload["proof_s"],
    )

    attempt = ZKVerificationAttempt.objects.create(
        user=request.user,
        commitment_a=commitment_a,
        commitment_b=commitment_b,
        scheme=commitment_a.scheme,
        result=ok,
        verifier_user=request.user,
    )
    return Response(
        {
            "verified": ok,
            "attempt_id": str(attempt.id),
            "scheme": commitment_a.scheme,
            "verified_at": attempt.created_at.isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_attempts(request):
    """Return the caller's recent verification attempts (newest first)."""
    qs = ZKVerificationAttempt.objects.filter(user=request.user).order_by("-created_at")[:100]
    data = ZKVerificationAttemptSerializer(qs, many=True).data
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def schemes(request):
    return Response({"schemes": available_schemes()})


# ---------------------------------------------------------------------------
# Phase 1b: multi-party verification sessions
# ---------------------------------------------------------------------------


def _refresh_session_status(session: ZKSession) -> ZKSession:
    """Lazily move open→expired when the deadline has passed."""
    if session.status == ZKSession.STATUS_OPEN and session.is_expired():
        session.status = ZKSession.STATUS_EXPIRED
        session.save(update_fields=["status"])
    return session


class ZKSessionViewSet(viewsets.ViewSet):
    """Session lifecycle: create, list, retrieve, close, invite, revoke.

    Only the ``owner`` may mutate or inspect participant tokens. Invitees
    interact with sessions through the dedicated join/submit endpoints below
    using the one-time ``invite_token``.
    """

    permission_classes = [IsAuthenticated]

    def _get_owned(self, request, pk) -> ZKSession:
        session = get_object_or_404(ZKSession, pk=pk, owner=request.user)
        return _refresh_session_status(session)

    def list(self, request):
        qs = (
            ZKSession.objects.filter(owner=request.user)
            .prefetch_related("participants")
            .order_by("-created_at")[:100]
        )
        for session in qs:
            _refresh_session_status(session)
        return Response(ZKSessionSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        session = self._get_owned(request, pk)
        return Response(ZKSessionSerializer(session).data)

    def create(self, request):
        serializer = ZKSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        reference = get_object_or_404(
            ZKCommitment,
            pk=payload["reference_commitment_id"],
            user=request.user,
        )
        expires_at = timezone.now() + timezone.timedelta(hours=payload["expires_in_hours"])
        session = ZKSession.objects.create(
            owner=request.user,
            reference_commitment=reference,
            title=payload.get("title", ""),
            description=payload.get("description", ""),
            expires_at=expires_at,
        )
        return Response(
            ZKSessionSerializer(session).data, status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        """Destroy == close. The row is kept as an audit record."""
        session = self._get_owned(request, pk)
        if session.status == ZKSession.STATUS_OPEN:
            session.close()
        return Response(ZKSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="invite")
    def invite(self, request, pk=None):
        session = self._get_owned(request, pk)
        if session.status != ZKSession.STATUS_OPEN:
            return Response(
                {"detail": f"Session is {session.status}; cannot add invites."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ZKSessionInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        participant = ZKSessionParticipant.objects.create(
            session=session,
            invited_email=payload.get("invited_email", ""),
            invited_label=payload.get("invited_label", ""),
        )
        return Response(
            ZKSessionParticipantOwnerSerializer(participant).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path=r"participants/(?P<participant_id>[0-9a-f-]+)/revoke",
    )
    def revoke_participant(self, request, pk=None, participant_id=None):
        session = self._get_owned(request, pk)
        participant = get_object_or_404(
            ZKSessionParticipant,
            pk=participant_id,
            session=session,
        )
        if participant.status == ZKSessionParticipant.STATUS_VERIFIED:
            return Response(
                {"detail": "Cannot revoke an already-verified participant."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        participant.status = ZKSessionParticipant.STATUS_REVOKED
        participant.save(update_fields=["status"])
        return Response(ZKSessionParticipantOwnerSerializer(participant).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resolve_invite(request, token: str):
    """Resolve an invite token to join info (without leaking other participants).

    The caller must be authenticated — we record ``participant.user = request.user``
    on first touch so downstream proof submissions can be audited.
    """
    participant = get_object_or_404(ZKSessionParticipant, invite_token=token)
    session = _refresh_session_status(participant.session)

    if session.status != ZKSession.STATUS_OPEN:
        return Response(
            {"detail": f"Session is {session.status}."},
            status=status.HTTP_410_GONE,
        )
    if participant.status in {
        ZKSessionParticipant.STATUS_REVOKED,
    }:
        return Response(
            {"detail": f"Invite is {participant.status}."},
            status=status.HTTP_410_GONE,
        )

    # Bind the invitee to their login on first resolve. Later refusals handled
    # by the submit endpoint.
    if participant.user_id is None:
        participant.user = request.user
        if participant.status == ZKSessionParticipant.STATUS_PENDING:
            participant.status = ZKSessionParticipant.STATUS_JOINED
        participant.save(update_fields=["user", "status"])
    elif participant.user_id != request.user.id:
        return Response(
            {"detail": "This invite is bound to a different account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    ref = session.reference_commitment
    data = {
        "session_id": session.id,
        "participant_id": participant.id,
        "status": participant.status,
        "title": session.title,
        "description": session.description,
        "scheme": ref.scheme,
        "reference_commitment_id": ref.id,
        "reference_commitment_b64": base64.b64encode(bytes(ref.commitment)).decode("ascii"),
        "reference_scope_type": ref.scope_type,
        "reference_scope_id": ref.scope_id,
        "expires_at": session.expires_at,
    }
    return Response(ZKSessionJoinInfoSerializer(data).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_session_proof(request):
    """Accept a Schnorr equality proof from a session invitee.

    The proof binds the participant's own ``ZKCommitment`` to the session's
    reference commitment. The participant's commitment *must* be owned by
    ``request.user``; we never trust the invitee to claim commitments that
    belong to someone else.
    """
    serializer = ZKSessionSubmitProofSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    participant = get_object_or_404(ZKSessionParticipant, invite_token=payload["invite_token"])
    session = _refresh_session_status(participant.session)

    if session.status != ZKSession.STATUS_OPEN:
        return Response(
            {"detail": f"Session is {session.status}."},
            status=status.HTTP_410_GONE,
        )
    if participant.status == ZKSessionParticipant.STATUS_VERIFIED:
        return Response(
            {"detail": "This participant slot is already verified."},
            status=status.HTTP_409_CONFLICT,
        )
    if participant.status == ZKSessionParticipant.STATUS_REVOKED:
        return Response(
            {"detail": "This invite has been revoked."},
            status=status.HTTP_410_GONE,
        )

    # First-time submit: bind the invitee. Subsequent retries must come from
    # the same account.
    if participant.user_id is None:
        participant.user = request.user
        participant.status = ZKSessionParticipant.STATUS_JOINED
        participant.save(update_fields=["user", "status"])
    elif participant.user_id != request.user.id:
        return Response(
            {"detail": "This invite is bound to a different account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    participant_commitment = get_object_or_404(
        ZKCommitment,
        pk=payload["participant_commitment_id"],
        user=request.user,
    )
    reference = session.reference_commitment

    if participant_commitment.scheme != reference.scheme:
        return Response(
            {"detail": "Participant commitment uses a different scheme than the session reference."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if participant_commitment.id == reference.id:
        return Response(
            {"detail": "Participant commitment must differ from the reference."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    provider = get_provider(reference.scheme)
    if (
        len(payload["proof_T"]) != provider.proof_T_size()
        or len(payload["proof_s"]) != provider.proof_s_size()
    ):
        attempt = ZKVerificationAttempt.objects.create(
            user=reference.user,
            commitment_a=reference,
            commitment_b=participant_commitment,
            scheme=reference.scheme,
            result=False,
            verifier_user=request.user,
            error_message="Malformed proof sizes",
        )
        participant.mark_failed(attempt, "Proof component sizes do not match the declared scheme.")
        return Response(
            {
                "verified": False,
                "attempt_id": str(attempt.id),
                "detail": "Proof component sizes do not match the declared scheme.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    ok = provider.verify_equality(
        bytes(reference.commitment),
        bytes(participant_commitment.commitment),
        payload["proof_T"],
        payload["proof_s"],
    )

    with transaction.atomic():
        attempt = ZKVerificationAttempt.objects.create(
            user=reference.user,
            commitment_a=reference,
            commitment_b=participant_commitment,
            scheme=reference.scheme,
            result=ok,
            verifier_user=request.user,
            error_message="" if ok else "Schnorr verification failed.",
        )
        if ok:
            participant.mark_verified(attempt, participant_commitment)
        else:
            participant.mark_failed(attempt, "Schnorr verification failed.")

    return Response(
        {
            "verified": ok,
            "attempt_id": str(attempt.id),
            "participant_id": str(participant.id),
            "scheme": reference.scheme,
            "verified_at": attempt.created_at.isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_my_invites(request):
    """List sessions the caller has been invited to (bound to their user id)."""
    qs = (
        ZKSessionParticipant.objects.filter(user=request.user)
        .select_related("session", "session__reference_commitment")
        .order_by("-created_at")[:100]
    )
    out = []
    for p in qs:
        s = _refresh_session_status(p.session)
        out.append({
            "participant_id": str(p.id),
            "session_id": str(s.id),
            "session_title": s.title,
            "session_status": s.status,
            "participant_status": p.status,
            "invited_label": p.invited_label,
            "scheme": s.reference_commitment.scheme,
            "created_at": p.created_at.isoformat(),
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
        })
    return Response(out)
