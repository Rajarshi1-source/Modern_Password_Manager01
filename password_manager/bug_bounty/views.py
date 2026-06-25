"""
DRF viewsets for the vault self-pentest (Bug Bounty Phase 1).

All querysets are scoped to ``request.user`` — a self-test only ever assesses
and reveals the requesting user's own posture.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Finding, FindingStatus, RunTrigger, SelfTestRun
from .serializers import FindingSerializer, SelfTestRunSerializer
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

    def perform_update(self, serializer):
        new_status = serializer.validated_data.get('status')
        resolved_at = None
        if new_status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE):
            resolved_at = timezone.now()
        serializer.save(resolved_at=resolved_at)


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
