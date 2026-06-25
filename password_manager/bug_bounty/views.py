"""
DRF viewsets for the vault self-pentest and bounty program (Bug Bounty).

Phase 1 (self-test): every queryset is scoped to ``request.user`` — a self-test
only ever assesses and reveals the requesting user's own posture.

Phase 2 (bounty program): a program is managed by its owner; a researcher (any
authenticated user) may submit to an *active* program. Submissions and rewards
are visible to the researcher who filed them and the program owner; only the
owner may triage, reward, pay or void. Researchers test the app's attack
surface — they never gain access to any user's vault data.
"""

from __future__ import annotations

from django.db.models import Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import (
    BountyProgram,
    Finding,
    FindingStatus,
    ProgramStatus,
    Reward,
    RunTrigger,
    SelfTestRun,
    Submission,
)
from .serializers import (
    BountyProgramSerializer,
    FindingSerializer,
    IssueRewardSerializer,
    RewardSerializer,
    SelfTestRunSerializer,
    SubmissionSerializer,
    TransitionSerializer,
)
from .services import triage_service
from .services.self_test_service import run_self_test


class FindingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """List/retrieve findings and update their triage status."""

    permission_classes = [IsAuthenticated]
    serializer_class = FindingSerializer

    def get_queryset(self):
        return Finding.objects.filter(user=self.request.user)

    # resolved_at bookkeeping lives in Finding.save() so every write path stays
    # consistent — no perform_update override needed here.


class SelfTestViewSet(viewsets.GenericViewSet):
    """Latest self-test result and on-demand trigger."""

    permission_classes = [IsAuthenticated]
    serializer_class = SelfTestRunSerializer

    def get_throttles(self):
        # Only the (expensive) on-demand run is rate-limited; reads aren't.
        if getattr(self, 'action', None) == 'run':
            self.throttle_scope = 'bug_bounty_run'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def list(self, request):
        """Latest run plus the user's currently open/acknowledged findings."""
        latest = (
            SelfTestRun.objects.filter(user=request.user).order_by('-started_at').first()
        )
        open_findings = Finding.objects.filter(user=request.user).exclude(
            status__in=[FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE]
        )
        return Response({
            'latest_run': SelfTestRunSerializer(latest).data if latest else None,
            'findings': FindingSerializer(open_findings, many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='run')
    def run(self, request):
        """Run the harness now and return the completed run + findings.

        Runs synchronously: the checks are lightweight DB reads, so immediate
        results give the dashboard a better "Run self-test" experience. The
        scheduled, fleet-wide runs go through Celery (see tasks.py).
        """
        run_obj = run_self_test(request.user, trigger=RunTrigger.MANUAL)
        findings = Finding.objects.filter(user=request.user).exclude(
            status__in=[FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE]
        )
        return Response(
            {
                'latest_run': SelfTestRunSerializer(run_obj).data,
                'findings': FindingSerializer(findings, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


# --------------------------------------------------------------------------- #
# Phase 2 — bounty program / submissions / rewards
# --------------------------------------------------------------------------- #


class BountyProgramViewSet(viewsets.ModelViewSet):
    """CRUD for the requesting user's own bounty programs.

    The default queryset is owner-scoped (management view). Researchers discover
    programs to submit to via the ``available`` action, which lists every
    currently-active program across owners (programs are published, not secret).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BountyProgramSerializer

    def get_queryset(self):
        return (
            BountyProgram.objects.filter(owner=self.request.user)
            .annotate(submission_count=Count('submissions'))
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """Active programs any researcher may submit to (incl. the user's own)."""
        programs = (
            BountyProgram.objects.filter(status=ProgramStatus.ACTIVE)
            .annotate(submission_count=Count('submissions'))
        )
        return Response(BountyProgramSerializer(programs, many=True).data)


class SubmissionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Researcher submissions and owner triage.

    Visibility: the researcher who filed a submission and the program owner.
    Triage actions (transition / reward) are owner-only.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Submission.objects.filter(
                Q(researcher=user) | Q(program__owner=user)
            )
            .select_related('program', 'researcher', 'reward')
        )

    def get_throttles(self):
        # Filing a report is the spammable action; rate-limit only that.
        if getattr(self, 'action', None) == 'create':
            self.throttle_scope = 'bug_bounty_submit'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        # researcher is always the caller; the program (validated active in the
        # serializer) may belong to any owner — that's the external-researcher model.
        serializer.save(researcher=self.request.user)

    def _require_owner(self, submission):
        if submission.program.owner_id != self.request.user.id:
            raise PermissionDenied('Only the program owner can triage submissions.')

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        """Owner-only: advance a submission through the triage state machine."""
        submission = self.get_object()
        self._require_owner(submission)
        payload = TransitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            triage_service.apply_transition(
                submission,
                payload.validated_data['to_status'],
                severity_assigned=payload.validated_data.get('severity_assigned', ''),
                note=payload.validated_data.get('note', ''),
            )
        except triage_service.InvalidTransition as exc:
            raise ValidationError(str(exc))
        return Response(SubmissionSerializer(submission).data)

    @action(detail=True, methods=['post'], url_path='reward')
    def reward(self, request, pk=None):
        """Owner-only: record a reward obligation and move the submission to rewarded."""
        submission = self.get_object()
        self._require_owner(submission)
        payload = IssueRewardSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            reward = triage_service.issue_reward(
                submission,
                amount=payload.validated_data['amount'],
                currency=payload.validated_data['currency'],
                adapter=payload.validated_data['adapter'],
                note=payload.validated_data.get('note', ''),
            )
        except triage_service.InvalidTransition as exc:
            raise ValidationError(str(exc))
        return Response(
            RewardSerializer(reward).data, status=status.HTTP_201_CREATED,
        )


class RewardViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Reward ledger, visible to the researcher and the program owner.

    Disbursement (``pay``) and ``void`` are owner-only and go through the payout
    adapter — no money moves in-product.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RewardSerializer

    def get_queryset(self):
        user = self.request.user
        return Reward.objects.filter(
            Q(submission__researcher=user) | Q(submission__program__owner=user)
        ).select_related('submission', 'submission__program')

    def _require_owner(self, reward):
        if reward.submission.program.owner_id != self.request.user.id:
            raise PermissionDenied('Only the program owner can manage payouts.')

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        """Owner-only: settle an owed reward through its payout adapter."""
        reward = self.get_object()
        self._require_owner(reward)
        try:
            triage_service.pay_reward(reward)
        except triage_service.InvalidTransition as exc:
            raise ValidationError(str(exc))
        return Response(RewardSerializer(reward).data)

    @action(detail=True, methods=['post'], url_path='void')
    def void(self, request, pk=None):
        """Owner-only: void an obligation that will not be paid."""
        reward = self.get_object()
        self._require_owner(reward)
        try:
            triage_service.void_reward(reward)
        except triage_service.InvalidTransition as exc:
            raise ValidationError(str(exc))
        return Response(RewardSerializer(reward).data)
