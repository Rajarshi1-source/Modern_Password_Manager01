"""
Escrow & Inheritance Serializers
==================================
"""

from rest_framework import serializers
from smart_contracts.models.escrow import EscrowAgreement, InheritancePlan


class EscrowAgreementSerializer(serializers.ModelSerializer):
    depositor_username = serializers.CharField(source='depositor.username', read_only=True)
    beneficiary_username = serializers.CharField(source='beneficiary.username', read_only=True)
    arbitrator_username = serializers.CharField(source='arbitrator.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EscrowAgreement
        fields = [
            'id', 'depositor', 'depositor_username',
            'beneficiary', 'beneficiary_username',
            'arbitrator', 'arbitrator_username',
            'arbitrator_wallet', 'release_conditions',
            'status', 'status_display', 'released_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'released_at', 'created_at', 'updated_at']


class InheritancePlanSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    beneficiary_username = serializers.CharField(
        source='beneficiary_user.username', read_only=True, default=None
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    inactivity_deadline = serializers.DateTimeField(read_only=True)
    release_deadline = serializers.DateTimeField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = InheritancePlan
        fields = [
            'id', 'owner', 'owner_username',
            'beneficiary_email', 'beneficiary_user', 'beneficiary_username',
            'inactivity_period_days', 'grace_period_days',
            'last_check_in', 'grace_period_started_at',
            'notification_sent', 'beneficiary_notified',
            'status', 'status_display', 'triggered_at',
            'inactivity_deadline', 'release_deadline', 'is_overdue',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'owner', 'notification_sent', 'beneficiary_notified',
            'triggered_at', 'created_at', 'updated_at',
        ]
