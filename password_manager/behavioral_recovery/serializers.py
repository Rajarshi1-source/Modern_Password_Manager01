"""
Django REST Framework Serializers for Behavioral Recovery
"""

from rest_framework import serializers
from .models import (
    BehavioralCommitment,
    BehavioralRecoveryAttempt,
    BehavioralChallenge,
    BehavioralProfileSnapshot
)


class BehavioralCommitmentSerializer(serializers.ModelSerializer):
    """Serializer for behavioral commitments (limited fields for security)"""
    
    class Meta:
        model = BehavioralCommitment
        fields = [
            'commitment_id',
            'challenge_type',
            'is_active',
            'creation_timestamp',
            'samples_used'
        ]
        read_only_fields = ['commitment_id', 'creation_timestamp']


class BehavioralChallengeSerializer(serializers.ModelSerializer):
    """Serializer for behavioral challenges"""
    
    class Meta:
        model = BehavioralChallenge
        fields = [
            'challenge_id',
            'challenge_type',
            'challenge_data',
            'similarity_score',
            'passed',
            'created_at',
            'completed_at'
        ]
        read_only_fields = ['challenge_id', 'created_at', 'similarity_score', 'passed']


class BehavioralRecoveryAttemptSerializer(serializers.ModelSerializer):
    """Serializer for recovery attempts"""
    challenges = BehavioralChallengeSerializer(many=True, read_only=True)
    
    class Meta:
        model = BehavioralRecoveryAttempt
        fields = [
            'attempt_id',
            'current_stage',
            'status',
            'challenges_completed',
            'challenges_total',
            'similarity_scores',
            'overall_similarity',
            'started_at',
            'expected_completion_date',
            'challenges'
        ]
        read_only_fields = [
            'attempt_id',
            'started_at',
            'overall_similarity'
        ]


class RecoveryInitiateSerializer(serializers.Serializer):
    """Serializer for initiating recovery"""
    email = serializers.EmailField(required=True)


class ChallengeSubmitSerializer(serializers.Serializer):
    """Serializer for submitting challenge responses"""
    attempt_id = serializers.UUIDField(required=True)
    challenge_id = serializers.UUIDField(required=True)
    behavioral_data = serializers.JSONField(required=True)


class RecoveryCompleteSerializer(serializers.Serializer):
    """Serializer for completing recovery"""
    attempt_id = serializers.UUIDField(required=True)
    new_password = serializers.CharField(required=True, min_length=12)


class CommitmentSetupSerializer(serializers.Serializer):
    """Serializer for setting up behavioral commitments"""
    behavioral_profile = serializers.JSONField(required=True)

