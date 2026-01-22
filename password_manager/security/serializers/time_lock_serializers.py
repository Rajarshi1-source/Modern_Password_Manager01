"""
Time-Lock Encryption Serializers
=================================

Serializers for time-lock capsules, beneficiaries, wills, and escrows.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone


class TimeLockCapsuleSerializer(serializers.Serializer):
    """Serializer for time-lock capsules."""
    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    mode = serializers.CharField()
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    status = serializers.CharField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    capsule_type = serializers.CharField()
    capsule_type_display = serializers.CharField(source='get_capsule_type_display', read_only=True)
    
    unlock_at = serializers.DateTimeField()
    delay_seconds = serializers.IntegerField()
    time_remaining_seconds = serializers.IntegerField(read_only=True)
    is_ready_to_unlock = serializers.BooleanField(read_only=True)
    
    # Puzzle params (for client mode)
    puzzle_n = serializers.CharField(allow_blank=True)
    puzzle_a = serializers.CharField(allow_blank=True)
    puzzle_t = serializers.IntegerField(allow_null=True)
    
    created_at = serializers.DateTimeField(read_only=True)
    opened_at = serializers.DateTimeField(allow_null=True, read_only=True)
    
    beneficiary_count = serializers.SerializerMethodField()
    
    def get_beneficiary_count(self, obj):
        return obj.beneficiaries.count() if hasattr(obj, 'beneficiaries') else 0


class CapsuleCreateSerializer(serializers.Serializer):
    """Input serializer for creating capsules."""
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    secret_data = serializers.CharField(help_text="The secret to time-lock")
    delay_seconds = serializers.IntegerField(
        min_value=60,
        max_value=31536000,  # 1 year
        help_text="Delay before unlock in seconds"
    )
    mode = serializers.ChoiceField(
        choices=['server', 'client', 'hybrid'],
        default='server'
    )
    capsule_type = serializers.ChoiceField(
        choices=['general', 'will', 'escrow', 'time_capsule', 'emergency'],
        default='general'
    )
    beneficiaries = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )
    
    def validate_delay_seconds(self, value):
        """Validate delay is reasonable."""
        if value < 60:
            raise serializers.ValidationError("Delay must be at least 60 seconds")
        if value > 31536000:
            raise serializers.ValidationError("Delay cannot exceed 1 year")
        return value


class BeneficiarySerializer(serializers.Serializer):
    """Serializer for capsule beneficiaries."""
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField()
    name = serializers.CharField()
    relationship = serializers.CharField(allow_blank=True)
    access_level = serializers.ChoiceField(
        choices=['view', 'full', 'download'],
        default='view'
    )
    requires_verification = serializers.BooleanField(default=True)
    verified = serializers.BooleanField(read_only=True)
    notified_at = serializers.DateTimeField(allow_null=True, read_only=True)


class BeneficiaryCreateSerializer(serializers.Serializer):
    """Input serializer for adding beneficiaries."""
    capsule_id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField(max_length=255)
    relationship = serializers.CharField(max_length=100, required=False, allow_blank=True)
    access_level = serializers.ChoiceField(
        choices=['view', 'full', 'download'],
        default='view'
    )
    requires_verification = serializers.BooleanField(default=True)


class VDFProofSerializer(serializers.Serializer):
    """Serializer for VDF proofs."""
    id = serializers.UUIDField(read_only=True)
    capsule_id = serializers.UUIDField(source='capsule.id')
    challenge = serializers.CharField()
    output = serializers.CharField()
    proof = serializers.CharField()
    modulus = serializers.CharField()
    iterations = serializers.IntegerField()
    verified = serializers.BooleanField()
    verification_time_ms = serializers.IntegerField(allow_null=True)
    computation_time_seconds = serializers.FloatField()
    created_at = serializers.DateTimeField(read_only=True)


class VDFVerifySerializer(serializers.Serializer):
    """Input serializer for VDF verification."""
    capsule_id = serializers.UUIDField()
    challenge = serializers.CharField()
    output = serializers.CharField()
    proof = serializers.CharField()
    modulus = serializers.CharField()
    iterations = serializers.IntegerField()


class PasswordWillSerializer(serializers.Serializer):
    """Serializer for password wills."""
    id = serializers.UUIDField(read_only=True)
    capsule_id = serializers.UUIDField(source='capsule.id')
    capsule_title = serializers.CharField(source='capsule.title', read_only=True)
    
    trigger_type = serializers.CharField()
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    inactivity_days = serializers.IntegerField(allow_null=True)
    target_date = serializers.DateTimeField(allow_null=True)
    
    last_check_in = serializers.DateTimeField()
    check_in_reminder_days = serializers.IntegerField()
    days_until_trigger = serializers.IntegerField(read_only=True)
    
    is_active = serializers.BooleanField()
    is_triggered = serializers.BooleanField(read_only=True)
    triggered_at = serializers.DateTimeField(allow_null=True, read_only=True)
    
    reminder_sent = serializers.BooleanField(read_only=True)
    beneficiaries_notified = serializers.BooleanField(read_only=True)
    
    notes = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class PasswordWillCreateSerializer(serializers.Serializer):
    """Input serializer for creating password wills."""
    # Capsule info
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    secret_data = serializers.CharField(help_text="Passwords/secrets to pass on")
    
    # Trigger settings
    trigger_type = serializers.ChoiceField(
        choices=['inactivity', 'date', 'manual'],
        default='inactivity'
    )
    inactivity_days = serializers.IntegerField(
        min_value=7,
        max_value=365,
        required=False
    )
    target_date = serializers.DateTimeField(required=False)
    check_in_reminder_days = serializers.IntegerField(
        min_value=1,
        max_value=30,
        default=7
    )
    
    # Beneficiaries
    beneficiaries = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="At least one beneficiary required"
    )
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate trigger settings."""
        trigger_type = data.get('trigger_type')
        
        if trigger_type == 'inactivity' and not data.get('inactivity_days'):
            raise serializers.ValidationError(
                "inactivity_days required for inactivity trigger"
            )
        
        if trigger_type == 'date' and not data.get('target_date'):
            raise serializers.ValidationError(
                "target_date required for date trigger"
            )
        
        if trigger_type == 'date':
            if data['target_date'] <= timezone.now():
                raise serializers.ValidationError(
                    "target_date must be in the future"
                )
        
        return data


class EscrowAgreementSerializer(serializers.Serializer):
    """Serializer for escrow agreements."""
    id = serializers.UUIDField(read_only=True)
    capsule_id = serializers.UUIDField(source='capsule.id')
    capsule_title = serializers.CharField(source='capsule.title', read_only=True)
    
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    release_condition = serializers.CharField()
    release_condition_display = serializers.CharField(
        source='get_release_condition_display', read_only=True
    )
    
    parties = serializers.SerializerMethodField()
    approval_count = serializers.IntegerField(read_only=True)
    total_parties = serializers.IntegerField(read_only=True)
    approved_by = serializers.ListField(child=serializers.IntegerField())
    approval_deadline = serializers.DateTimeField(allow_null=True)
    can_release = serializers.BooleanField(read_only=True)
    
    is_released = serializers.BooleanField(read_only=True)
    released_at = serializers.DateTimeField(allow_null=True, read_only=True)
    is_disputed = serializers.BooleanField()
    
    created_at = serializers.DateTimeField(read_only=True)
    
    def get_parties(self, obj):
        return [
            {'id': user.id, 'username': user.username, 'email': user.email}
            for user in obj.parties.all()
        ]


class EscrowCreateSerializer(serializers.Serializer):
    """Input serializer for creating escrow agreements."""
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    secret_data = serializers.CharField(help_text="Secret to escrow")
    
    release_condition = serializers.ChoiceField(
        choices=['date', 'all_approve', 'any_approve', 'majority', 'date_or_approve'],
        default='date'
    )
    unlock_date = serializers.DateTimeField(required=False)
    approval_deadline = serializers.DateTimeField(required=False)
    
    party_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1
    )
    dispute_resolution_email = serializers.EmailField(required=False)
    
    def validate(self, data):
        """Validate release conditions."""
        condition = data.get('release_condition')
        
        if condition in ['date', 'date_or_approve'] and not data.get('unlock_date'):
            raise serializers.ValidationError(
                "unlock_date required for date-based release"
            )
        
        if data.get('unlock_date') and data['unlock_date'] <= timezone.now():
            raise serializers.ValidationError(
                "unlock_date must be in the future"
            )
        
        return data


class CapsuleStatusSerializer(serializers.Serializer):
    """Serializer for capsule status response."""
    capsule_id = serializers.UUIDField()
    status = serializers.CharField()
    time_remaining_seconds = serializers.IntegerField()
    time_remaining_display = serializers.SerializerMethodField()
    can_unlock = serializers.BooleanField()
    unlock_at = serializers.DateTimeField()
    
    def get_time_remaining_display(self, obj):
        seconds = obj.get('time_remaining_seconds', 0)
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes"
        elif seconds < 86400:
            return f"{seconds // 3600} hours"
        else:
            return f"{seconds // 86400} days"


class UnlockCapsuleSerializer(serializers.Serializer):
    """Input serializer for unlocking a capsule."""
    # For client-mode puzzles
    vdf_output = serializers.CharField(required=False)
    vdf_proof = serializers.CharField(required=False)
    
    # For beneficiary access
    verification_token = serializers.CharField(required=False)
