"""
Password Archaeology API Views
================================

REST API endpoints for the Password Archaeology & Time Travel feature.
"""

from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .services.archaeology_service import PasswordArchaeologyService
from .serializers import (
    PasswordHistoryEntrySerializer,
    SecurityEventSerializer,
    StrengthSnapshotSerializer,
    AchievementSerializer,
    WhatIfScenarioSerializer,
    WhatIfRequestSerializer,
    TimelineEventSerializer,
)
from .models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    AchievementRecord,
    WhatIfScenario,
)

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# Timeline
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def timeline_view(request):
    """
    GET /api/archaeology/timeline/

    Returns a merged, chronological timeline of password changes
    and security events.

    Query params:
        - date_from: ISO datetime (default: 1 year ago)
        - date_to: ISO datetime (default: now)
        - vault_item_id: UUID (optional filter)
        - limit: int (default: 100)
    """
    try:
        date_from = parse_datetime(request.query_params.get('date_from', ''))
        date_to = parse_datetime(request.query_params.get('date_to', ''))
        vault_item_id = request.query_params.get('vault_item_id')
        limit = int(request.query_params.get('limit', 100))

        timeline = PasswordArchaeologyService.get_timeline_data(
            user=request.user,
            date_from=date_from,
            date_to=date_to,
            vault_item_id=vault_item_id,
            limit=min(limit, 500),
        )

        serializer = TimelineEventSerializer(timeline, many=True)
        return Response({
            'timeline': serializer.data,
            'count': len(serializer.data),
        })
    except Exception as e:
        logger.error(f"Timeline error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Strength Evolution
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def strength_evolution_view(request, vault_item_id=None):
    """
    GET /api/archaeology/strength-evolution/<vault_item_id>/
    GET /api/archaeology/strength-evolution/overall/

    Returns strength evolution data for charting.
    """
    try:
        date_from = parse_datetime(request.query_params.get('date_from', ''))
        date_to = parse_datetime(request.query_params.get('date_to', ''))
        credential_domain = request.query_params.get('credential_domain')

        data = PasswordArchaeologyService.get_strength_evolution(
            user=request.user,
            vault_item_id=vault_item_id,
            credential_domain=credential_domain,
            date_from=date_from,
            date_to=date_to,
        )

        return Response({
            'data_points': data,
            'count': len(data),
        })
    except Exception as e:
        logger.error(f"Strength evolution error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Security Events
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_events_view(request):
    """
    GET /api/archaeology/security-events/

    List security events with optional filters.
    """
    try:
        events = SecurityEvent.objects.filter(user=request.user)

        event_type = request.query_params.get('event_type')
        if event_type:
            events = events.filter(event_type=event_type)

        severity = request.query_params.get('severity')
        if severity:
            events = events.filter(severity=severity)

        resolved = request.query_params.get('resolved')
        if resolved is not None:
            events = events.filter(resolved=resolved.lower() == 'true')

        limit = int(request.query_params.get('limit', 50))
        events = events[:min(limit, 200)]

        serializer = SecurityEventSerializer(events, many=True)
        return Response({
            'events': serializer.data,
            'count': len(serializer.data),
        })
    except Exception as e:
        logger.error(f"Security events error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# What-If Scenarios
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def what_if_run_view(request):
    """
    POST /api/archaeology/what-if/

    Run a "what if" simulation.

    Body:
        {
            "scenario_type": "earlier_change",
            "credential_domain": "google.com",
            "params": {"days_earlier": 30}
        }
    """
    try:
        serializer = WhatIfRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vault_item = None
        vault_item_id = serializer.validated_data.get('vault_item_id')
        if vault_item_id:
            from vault.models import EncryptedVaultItem
            vault_item = EncryptedVaultItem.objects.filter(
                id=vault_item_id, user=request.user,
            ).first()

        scenario = PasswordArchaeologyService.run_what_if_scenario(
            user=request.user,
            scenario_type=serializer.validated_data['scenario_type'],
            vault_item=vault_item,
            credential_domain=serializer.validated_data.get('credential_domain', ''),
            params=serializer.validated_data.get('params', {}),
        )

        result = WhatIfScenarioSerializer(scenario)
        return Response(result.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"What-if error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def what_if_history_view(request):
    """
    GET /api/archaeology/what-if/history/

    Get past what-if simulations.
    """
    try:
        scenarios = WhatIfScenario.objects.filter(
            user=request.user,
        )[:50]

        serializer = WhatIfScenarioSerializer(scenarios, many=True)
        return Response({
            'scenarios': serializer.data,
            'count': len(serializer.data),
        })
    except Exception as e:
        logger.error(f"What-if history error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Time Machine
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def time_machine_view(request, timestamp):
    """
    GET /api/archaeology/time-machine/<timestamp>/

    Reconstruct account state at a specific point in time.
    """
    try:
        point_in_time = parse_datetime(timestamp)
        if not point_in_time:
            return Response(
                {'error': 'Invalid timestamp format. Use ISO 8601.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshot = PasswordArchaeologyService.get_time_machine_snapshot(
            user=request.user,
            point_in_time=point_in_time,
        )

        return Response(snapshot)
    except Exception as e:
        logger.error(f"Time machine error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Achievements
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def achievements_view(request):
    """
    GET /api/archaeology/achievements/

    Get user's achievement records.
    """
    try:
        achievements = AchievementRecord.objects.filter(user=request.user)
        serializer = AchievementSerializer(achievements, many=True)
        total_points = sum(a.score_points for a in achievements)

        return Response({
            'achievements': serializer.data,
            'total_points': total_points,
            'count': len(serializer.data),
        })
    except Exception as e:
        logger.error(f"Achievements error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def acknowledge_achievement_view(request, achievement_id):
    """
    PATCH /api/archaeology/achievements/<achievement_id>/acknowledge/

    Mark an achievement as acknowledged.
    """
    try:
        achievement = AchievementRecord.objects.get(
            id=achievement_id, user=request.user,
        )
        achievement.acknowledged = True
        achievement.save(update_fields=['acknowledged'])
        return Response({'acknowledged': True})
    except AchievementRecord.DoesNotExist:
        return Response(
            {'error': 'Achievement not found'},
            status=status.HTTP_404_NOT_FOUND,
        )


# =============================================================================
# Security Score
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_score_view(request):
    """
    GET /api/archaeology/security-score/

    Get security score history for gamification charts.
    """
    try:
        date_from = parse_datetime(request.query_params.get('date_from', ''))
        date_to = parse_datetime(request.query_params.get('date_to', ''))

        data = PasswordArchaeologyService.calculate_security_score_over_time(
            user=request.user,
            date_from=date_from,
            date_to=date_to,
        )

        return Response(data)
    except Exception as e:
        logger.error(f"Security score error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Dashboard
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    """
    GET /api/archaeology/dashboard/

    Get aggregated dashboard summary.
    """
    try:
        summary = PasswordArchaeologyService.get_dashboard_summary(request.user)
        return Response(summary)
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
