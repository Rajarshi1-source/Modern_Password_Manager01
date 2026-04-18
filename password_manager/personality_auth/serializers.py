"""DRF serializers for personality-auth endpoints."""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    PersonalityAuditLog,
    PersonalityChallenge,
    PersonalityProfile,
    PersonalityQuestion,
    PersonalityResponse,
)


class PersonalityProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalityProfile
        fields = [
            'id',
            'opted_in',
            'opt_in_changed_at',
            'trait_features',
            'theme_weights',
            'source_messages_analysed',
            'last_inferred_at',
            'inference_model',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class PersonalityQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalityQuestion
        fields = [
            'id',
            'dimension',
            'difficulty',
            'prompt',
            'choices',
            'expires_at',
        ]
        read_only_fields = fields


class PersonalityChallengeSerializer(serializers.ModelSerializer):
    questions = PersonalityQuestionSerializer(many=True, read_only=True)
    mood_context = serializers.CharField(read_only=True)

    class Meta:
        model = PersonalityChallenge
        fields = [
            'id',
            'status',
            'required_score',
            'achieved_score',
            'mood_context',
            'mood_signals',
            'created_at',
            'presented_at',
            'completed_at',
            'expires_at',
            'intent',
            'questions',
        ]
        read_only_fields = fields


class StartChallengeSerializer(serializers.Serializer):
    intent = serializers.CharField(required=False, default='login', max_length=64)
    required_score = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
    question_count = serializers.IntegerField(required=False, min_value=1, max_value=6)
    ttl_minutes = serializers.IntegerField(required=False, min_value=1, max_value=60)
    typing_signals = serializers.DictField(required=False)


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    answer_text = serializers.CharField(required=False, allow_blank=True, default='')
    answer_choice = serializers.CharField(required=False, allow_blank=True, default='', max_length=128)
    latency_ms = serializers.IntegerField(required=False, min_value=0)
    answer_metadata = serializers.DictField(required=False)


class PersonalityResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalityResponse
        fields = [
            'id',
            'challenge',
            'question',
            'answer_choice',
            'consistency_score',
            'latency_ms',
            'submitted_at',
        ]
        read_only_fields = fields


class OptInSerializer(serializers.Serializer):
    opted_in = serializers.BooleanField()


class InferRequestSerializer(serializers.Serializer):
    message_limit = serializers.IntegerField(
        required=False, min_value=5, max_value=500, default=120
    )


class PersonalityAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalityAuditLog
        fields = [
            'id',
            'event_type',
            'event_payload',
            'challenge',
            'ip_address',
            'previous_hash',
            'entry_hash',
            'created_at',
        ]
        read_only_fields = fields
