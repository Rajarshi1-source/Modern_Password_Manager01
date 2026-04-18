"""DRF views for /api/personality/."""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import (
    PersonalityAuditLog,
    PersonalityChallenge,
    PersonalityProfile,
    PersonalityQuestion,
)
from .serializers import (
    InferRequestSerializer,
    OptInSerializer,
    PersonalityAuditLogSerializer,
    PersonalityChallengeSerializer,
    PersonalityProfileSerializer,
    StartChallengeSerializer,
    SubmitAnswerSerializer,
)
from .services import (
    ChallengeOrchestrator,
    LLMSchemaError,
    PersonalityInferenceService,
    QuestionGeneratorService,
    RateLimited,
    user_opted_in,
)

logger = logging.getLogger(__name__)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Throttles
# ---------------------------------------------------------------------------

class PersonalityChallengeThrottle(UserRateThrottle):
    scope = 'personality_challenge'


class PersonalityInferenceThrottle(UserRateThrottle):
    scope = 'personality_inference'


# ---------------------------------------------------------------------------
# Profile / opt-in
# ---------------------------------------------------------------------------

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = PersonalityProfile.objects.get(user=request.user)
        except PersonalityProfile.DoesNotExist:
            return Response(
                {
                    'opted_in': False,
                    'analytics_enabled': user_opted_in(request.user),
                },
                status=status.HTTP_200_OK,
            )
        data = PersonalityProfileSerializer(profile).data
        data['analytics_enabled'] = user_opted_in(request.user)
        return Response(data)


class OptInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OptInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wants_in = serializer.validated_data['opted_in']

        if wants_in and not user_opted_in(request.user):
            return Response(
                {
                    'error': (
                        'Enable privacy_analytics in user preferences before '
                        'opting in to personality auth.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = PersonalityProfile.objects.get_or_create(user=request.user)
        profile.mark_opted_in(wants_in)
        return Response(PersonalityProfileSerializer(profile).data)


# ---------------------------------------------------------------------------
# Inference & question pool
# ---------------------------------------------------------------------------

class InferView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PersonalityInferenceThrottle]

    def post(self, request):
        serializer = InferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = PersonalityInferenceService().infer(
                request.user,
                message_limit=serializer.validated_data.get('message_limit', 120),
            )
        except PermissionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LLMSchemaError as exc:
            return Response(
                {'error': 'inference_model_failed', 'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                'profile': PersonalityProfileSerializer(result.profile).data,
                'confidence': result.confidence,
                'sample_size': result.sample_size,
            }
        )


class GenerateQuestionsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PersonalityInferenceThrottle]

    def post(self, request):
        profile = get_object_or_404(PersonalityProfile, user=request.user)
        if not profile.opted_in:
            return Response(
                {'error': 'opt_in_required'}, status=status.HTTP_403_FORBIDDEN
            )
        generated = QuestionGeneratorService().generate(profile)
        return Response({'generated': len(generated)}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Challenge lifecycle
# ---------------------------------------------------------------------------

class StartChallengeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PersonalityChallengeThrottle]

    def post(self, request):
        serializer = StartChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        orchestrator = ChallengeOrchestrator()
        try:
            prepared = orchestrator.start_challenge(
                request.user,
                intent=data.get('intent', 'login'),
                ip_address=_client_ip(request),
                typing_signals=data.get('typing_signals'),
                required_score=data.get('required_score', 0.65),
                ttl_minutes=data.get('ttl_minutes', 10),
                question_count=data.get('question_count', 3),
            )
        except PermissionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except RateLimited as exc:
            return Response(
                {'error': 'rate_limited', 'detail': str(exc)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except RuntimeError as exc:
            return Response(
                {'error': 'no_questions', 'detail': str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            PersonalityChallengeSerializer(prepared.challenge).data,
            status=status.HTTP_201_CREATED,
        )


class ChallengeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, challenge_id):
        challenge = get_object_or_404(
            PersonalityChallenge, id=challenge_id, profile__user=request.user
        )
        return Response(PersonalityChallengeSerializer(challenge).data)


class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PersonalityChallengeThrottle]

    def post(self, request, challenge_id):
        challenge = get_object_or_404(
            PersonalityChallenge, id=challenge_id, profile__user=request.user
        )
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        question = get_object_or_404(PersonalityQuestion, id=data['question_id'])

        try:
            result = ChallengeOrchestrator().submit_response(
                challenge,
                question,
                answer_text=data.get('answer_text', ''),
                answer_choice=data.get('answer_choice', ''),
                latency_ms=data.get('latency_ms'),
                answer_metadata=data.get('answer_metadata'),
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'response_id': str(result.response.id),
                'score': result.score.score,
                'rationale': result.score.rationale,
                'finished': result.finished,
                'passed': result.passed,
                'challenge_status': result.challenge.status,
                'achieved_score': result.challenge.achieved_score,
            }
        )


class AbandonChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, challenge_id):
        challenge = get_object_or_404(
            PersonalityChallenge, id=challenge_id, profile__user=request.user
        )
        ChallengeOrchestrator().abandon(challenge)
        return Response({'status': challenge.status})


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = PersonalityProfile.objects.get(user=request.user)
        except PersonalityProfile.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        qs = (
            PersonalityAuditLog.objects.filter(profile=profile)
            .order_by('-created_at')[:200]
        )
        return Response(PersonalityAuditLogSerializer(qs, many=True).data)
