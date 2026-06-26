"""
Predictive Expiration API Views
================================

REST API endpoints for predictive password expiration.
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from ..models import (
    PasswordPatternProfile,
    ThreatActorTTP,
    IndustryThreatLevel,
    PredictiveExpirationRule,
    PasswordRotationEvent,
    PredictiveExpirationSettings,
)
from ..serializers.predictive_expiration_serializers import (
    PasswordPatternProfileSerializer,
    ThreatActorTTPSerializer,
    ThreatActorSummarySerializer,
    IndustryThreatLevelSerializer,
    PredictiveExpirationRuleSerializer,
    CredentialRiskListSerializer,
    PasswordRotationEventSerializer,
    PredictiveExpirationSettingsSerializer,
    DashboardSerializer,
    ForceRotationSerializer,
    FingerprintIngestSerializer,
    ThreatSummarySerializer,
)
from ..services.predictive_expiration_service import (
    get_predictive_expiration_service
)
from ..services.threat_intelligence_service import (
    get_threat_intelligence_service
)

logger = logging.getLogger(__name__)


class PredictiveExpirationDashboardView(APIView):
    """
    Dashboard overview for predictive password expiration.
    
    GET: Returns overall risk summary, at-risk credentials, and active threats.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get user's expiration rules
        rules = PredictiveExpirationRule.objects.filter(
            user=user,
            is_active=True
        )
        
        # Calculate statistics
        total_credentials = rules.count()
        at_risk = rules.filter(risk_score__gte=0.4)
        critical_count = rules.filter(risk_level='critical').count()
        high_count = rules.filter(risk_level='high').count()
        medium_count = rules.filter(risk_level='medium').count()
        
        # Pending rotations
        pending = rules.filter(
            recommended_action__in=['rotate_immediately', 'rotate_soon'],
            user_acknowledged=False
        ).count()
        
        # Recent rotations (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_rotations = PasswordRotationEvent.objects.filter(
            user=user,
            initiated_at__gte=thirty_days_ago
        ).count()
        
        # Active threats
        threat_service = get_threat_intelligence_service()
        active_threats = ThreatActorTTP.objects.filter(
            is_currently_active=True,
            threat_level__in=['high', 'critical']
        )[:5]
        
        # Industry threat (if user has industry set)
        industry_threat = None
        try:
            settings = PredictiveExpirationSettings.objects.get(user=user)
            if settings.industry:
                industry_threat = IndustryThreatLevel.objects.filter(
                    industry_code=settings.industry
                ).first()
        except PredictiveExpirationSettings.DoesNotExist:
            pass
        
        # Calculate overall risk score
        if total_credentials > 0:
            avg_risk = sum(r.risk_score for r in rules) / total_credentials
        else:
            avg_risk = 0.0
        
        # Top at-risk credentials
        top_at_risk = rules.order_by('-risk_score')[:5]
        
        # Last scan time
        last_scan = rules.order_by('-last_evaluated_at').first()
        last_scan_at = last_scan.last_evaluated_at if last_scan else None
        
        data = {
            'overall_risk_score': avg_risk,
            'total_credentials': total_credentials,
            'at_risk_count': at_risk.count(),
            'critical_count': critical_count,
            'high_count': high_count,
            # Alias for clients / tests that expect `high_risk_count`.
            'high_risk_count': high_count,
            'medium_count': medium_count,
            'pending_rotations': pending,
            'recent_rotations': recent_rotations,
            'active_threats': ThreatActorSummarySerializer(
                active_threats, many=True
            ).data,
            'industry_threat': IndustryThreatLevelSerializer(
                industry_threat
            ).data if industry_threat else None,
            'credentials_at_risk': CredentialRiskListSerializer(
                top_at_risk, many=True
            ).data,
            'last_scan_at': last_scan_at,
        }
        
        serializer = DashboardSerializer(data)
        return Response(serializer.data)


class CredentialRiskListView(generics.ListAPIView):
    """
    List all credentials with their risk assessments.
    
    GET: Returns paginated list of credentials sorted by risk score.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CredentialRiskListSerializer
    
    def get_queryset(self):
        queryset = PredictiveExpirationRule.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-risk_score', '-updated_at')
        
        # Filter by risk level
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        # Filter by domain
        domain = self.request.query_params.get('domain')
        if domain:
            queryset = queryset.filter(
                credential_domain__icontains=domain
            )
        
        # Filter unacknowledged only
        unacknowledged = self.request.query_params.get('unacknowledged')
        if unacknowledged and unacknowledged.lower() == 'true':
            queryset = queryset.filter(user_acknowledged=False)
        
        return queryset


class CredentialRiskDetailView(generics.RetrieveAPIView):
    """
    Detailed risk analysis for a specific credential.
    
    GET: Returns comprehensive risk assessment for the credential.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PredictiveExpirationRuleSerializer
    lookup_field = 'credential_id'
    lookup_url_kwarg = 'id'
    
    def get_queryset(self):
        return PredictiveExpirationRule.objects.filter(
            user=self.request.user
        )


class ForceRotationView(APIView):
    """
    Force password rotation for a credential.
    
    POST: Initiates immediate password rotation for the specified credential.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, id):
        serializer = ForceRotationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        reason = serializer.validated_data.get('reason', 'Manual rotation request')
        
        # Get the expiration rule
        try:
            rule = PredictiveExpirationRule.objects.get(
                user=user,
                credential_id=id
            )
        except PredictiveExpirationRule.DoesNotExist:
            return Response(
                {'error': 'Credential not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create rotation event
        event = PasswordRotationEvent.objects.create(
            user=user,
            credential_id=rule.credential_id,
            credential_domain=rule.credential_domain,
            rotation_type='forced',
            outcome='pending',
            trigger_reason=reason,
            threat_factors_at_rotation=rule.threat_factors,
            risk_score_at_rotation=rule.risk_score,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        # Mark rule as acknowledged
        rule.user_acknowledged = True
        rule.user_acknowledged_at = timezone.now()
        rule.save()
        
        return Response({
            'event_id': str(event.event_id),
            'message': 'Rotation initiated',
            'credential_id': str(id),
        }, status=status.HTTP_202_ACCEPTED)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class AcknowledgeRiskView(APIView):
    """
    Acknowledge a risk warning for a credential.
    
    POST: Marks the user as having acknowledged the risk.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, id):
        try:
            rule = PredictiveExpirationRule.objects.get(
                user=request.user,
                credential_id=id
            )
        except PredictiveExpirationRule.DoesNotExist:
            return Response(
                {'error': 'Credential not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        rule.user_acknowledged = True
        rule.user_acknowledged_at = timezone.now()
        rule.save()
        
        return Response({
            'message': 'Risk acknowledged',
            'credential_id': str(id),
        })


class ActiveThreatsView(generics.ListAPIView):
    """
    List currently active threats.
    
    GET: Returns list of active threat actors and their TTPs.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ThreatActorTTPSerializer
    
    def get_queryset(self):
        queryset = ThreatActorTTP.objects.filter(
            is_currently_active=True
        ).order_by('-threat_level', '-last_active')
        
        # Filter by threat level
        level = self.request.query_params.get('threat_level')
        if level:
            queryset = queryset.filter(threat_level=level)
        
        # Filter by actor type
        actor_type = self.request.query_params.get('actor_type')
        if actor_type:
            queryset = queryset.filter(actor_type=actor_type)
        
        # Filter by industry
        industry = self.request.query_params.get('industry')
        if industry:
            queryset = queryset.filter(
                target_industries__contains=[industry]
            )
        
        return queryset


class ThreatSummaryView(APIView):
    """
    Get threat landscape summary.
    
    GET: Returns high-level summary of current threat landscape.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        threat_service = get_threat_intelligence_service()
        summary = threat_service.get_threat_summary()
        
        # Convert ISO string back to datetime for serializer
        summary['last_updated'] = timezone.now()
        
        serializer = ThreatSummarySerializer(summary)
        return Response(serializer.data)


class PredictiveExpirationSettingsView(generics.RetrieveUpdateAPIView):
    """
    User settings for predictive password expiration.
    
    GET: Returns current settings.
    PUT/PATCH: Updates settings.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PredictiveExpirationSettingsSerializer
    
    def get_object(self):
        obj, created = PredictiveExpirationSettings.objects.get_or_create(
            user=self.request.user
        )
        return obj


class RotationHistoryView(generics.ListAPIView):
    """
    Password rotation history.
    
    GET: Returns paginated list of past rotation events.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordRotationEventSerializer
    
    def get_queryset(self):
        queryset = PasswordRotationEvent.objects.filter(
            user=self.request.user
        ).order_by('-initiated_at')
        
        # Filter by rotation type
        rotation_type = self.request.query_params.get('type')
        if rotation_type:
            queryset = queryset.filter(rotation_type=rotation_type)
        
        # Filter by outcome
        outcome = self.request.query_params.get('outcome')
        if outcome:
            queryset = queryset.filter(outcome=outcome)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(initiated_at__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(initiated_at__lte=end_date)
        
        return queryset


class FingerprintIngestView(APIView):
    """
    Ingest zero-knowledge password fingerprints from the browser.

    POST: Accepts a batch of irreversible structural fingerprints (computed
    client-side over the decrypted vault) and upserts a
    ``PredictiveExpirationRule`` per credential. No plaintext password — and
    no exact domain — ever reaches this endpoint.

    This is the path that populates the dashboard under the zero-knowledge
    model; it replaces the removed plaintext ``analyze/`` endpoint.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'predictive_fingerprint'

    def post(self, request):
        serializer = FingerprintIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fingerprints = serializer.validated_data['fingerprints']
        service = get_predictive_expiration_service()

        processed = []
        for fp in fingerprints:
            domain_class = fp.get('domain_class', '') or ''
            rule = service.create_expiration_rule_from_fingerprint(
                user_id=request.user.id,
                credential_id=str(fp['credential_id']),
                # Store only the coarse class for display + threat matching;
                # the exact domain never leaves the device.
                credential_domain=domain_class,
                domain_class=domain_class,
                char_class_sequence=fp['char_class_sequence'],
                length=fp.get('length'),
                length_bucket=fp['length_bucket'],
                entropy_band=fp['entropy_band'],
                entropy_estimate=fp.get('entropy_estimate'),
                has_dictionary_base=fp.get('has_dictionary_base', False),
                has_keyboard_pattern=fp.get('has_keyboard_pattern', False),
                has_date_pattern=fp.get('has_date_pattern', False),
                has_leet=fp.get('has_leet', False),
                structure_hash=fp.get('structure_hash', '') or '',
                credential_age_days=fp.get('age_days', 0),
            )
            processed.append({
                'credential_id': rule.credential_id,
                'risk_level': rule.risk_level,
                'risk_score': rule.risk_score,
                'recommended_action': rule.recommended_action,
            })

        # Refresh the aggregate pattern profile from this batch (ZK).
        service.update_user_pattern_profile_from_fingerprints(
            request.user.id, list(fingerprints)
        )

        return Response(
            {'processed': len(processed), 'rules': processed},
            status=status.HTTP_200_OK,
        )


class AnalyzeCredentialView(APIView):
    """
    Removed (zero-knowledge): the legacy plaintext analysis endpoint.

    Sending a password to the server violated the zero-knowledge model, so
    this endpoint now returns 410 Gone. Use ``fingerprints/`` instead, which
    accepts only irreversible structural metadata computed in the browser.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                'error': 'gone',
                'detail': (
                    'The plaintext analyze endpoint has been removed to '
                    'preserve zero-knowledge. Submit structural fingerprints '
                    'to predictive-expiration/fingerprints/ instead.'
                ),
                'replacement': 'predictive-expiration/fingerprints/',
            },
            status=status.HTTP_410_GONE,
        )


class PatternProfileView(generics.RetrieveAPIView):
    """
    User's password pattern profile.
    
    GET: Returns the user's password pattern analysis profile.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordPatternProfileSerializer
    
    def get_object(self):
        obj, created = PasswordPatternProfile.objects.get_or_create(
            user=self.request.user
        )
        return obj


class IndustryThreatsView(generics.ListAPIView):
    """
    Industry threat levels.
    
    GET: Returns list of industries with their current threat levels.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = IndustryThreatLevelSerializer
    
    def get_queryset(self):
        return IndustryThreatLevel.objects.all().order_by('-threat_score')
