"""
Vault Serializers
==================
"""

from rest_framework import serializers
from smart_contracts.models.vault import SmartContractVault, VaultCondition, ConditionType


class VaultConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaultCondition
        fields = [
            'id', 'condition_type', 'operator', 'parameters',
            'is_met', 'evaluated_at', 'order',
        ]
        read_only_fields = ['id', 'is_met', 'evaluated_at']


class VaultConditionResultSerializer(serializers.Serializer):
    met = serializers.BooleanField()
    reason = serializers.CharField()
    details = serializers.DictField()
    onchain_verified = serializers.BooleanField(required=False, allow_null=True)


class SmartContractVaultSerializer(serializers.ModelSerializer):
    """List-level vault serializer."""
    condition_type_display = serializers.CharField(source='get_condition_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    arbiscan_url = serializers.CharField(read_only=True)

    class Meta:
        model = SmartContractVault
        fields = [
            'id', 'title', 'description', 'condition_type', 'condition_type_display',
            'status', 'status_display', 'network', 'tx_hash', 'arbiscan_url',
            'vault_id_onchain', 'unlock_at', 'check_in_interval_days',
            'last_check_in', 'grace_period_days', 'price_threshold', 'price_above',
            'beneficiary_email', 'created_at', 'updated_at', 'unlocked_at',
        ]
        read_only_fields = [
            'id', 'status', 'tx_hash', 'vault_id_onchain',
            'contract_address', 'network', 'created_at', 'updated_at', 'unlocked_at',
        ]


class SmartContractVaultDetailSerializer(SmartContractVaultSerializer):
    """Detailed vault serializer with nested conditions."""
    conditions = VaultConditionSerializer(many=True, read_only=True)
    dead_mans_switch_deadline = serializers.DateTimeField(read_only=True)

    class Meta(SmartContractVaultSerializer.Meta):
        fields = SmartContractVaultSerializer.Meta.fields + [
            'conditions', 'contract_address', 'password_hash',
            'dead_mans_switch_deadline',
        ]


class SmartContractVaultCreateSerializer(serializers.Serializer):
    """Vault creation serializer — validates input for all condition types."""
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default='')
    password_encrypted = serializers.CharField()
    condition_type = serializers.ChoiceField(choices=ConditionType.choices)

    # Time-lock
    unlock_at = serializers.DateTimeField(required=False)

    # Dead man's switch
    check_in_interval_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    grace_period_days = serializers.IntegerField(required=False, min_value=1, max_value=90)
    beneficiary_email = serializers.EmailField(required=False)
    beneficiary_user_id = serializers.IntegerField(required=False)

    # Multi-sig
    signer_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    required_approvals = serializers.IntegerField(required=False, min_value=1, max_value=10)

    # DAO voting
    voter_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    voting_period_days = serializers.IntegerField(required=False, min_value=1, max_value=30)
    quorum_threshold = serializers.IntegerField(required=False, min_value=100, max_value=10000)
    proposal_title = serializers.CharField(required=False, max_length=255)
    proposal_description = serializers.CharField(required=False)

    # Price oracle
    price_threshold = serializers.DecimalField(required=False, max_digits=20, decimal_places=8)
    price_above = serializers.BooleanField(required=False, default=True)
    oracle_address = serializers.CharField(required=False, max_length=42)

    # Escrow
    arbitrator_id = serializers.IntegerField(required=False)
    arbitrator_wallet = serializers.CharField(required=False, max_length=42)
    release_conditions = serializers.CharField(required=False)

    def validate(self, data):
        ct = data['condition_type']

        if ct == ConditionType.TIME_LOCK:
            if not data.get('unlock_at'):
                raise serializers.ValidationError({'unlock_at': 'Required for time-lock vaults.'})

        elif ct == ConditionType.DEAD_MANS_SWITCH:
            if not data.get('check_in_interval_days'):
                raise serializers.ValidationError({'check_in_interval_days': 'Required for dead man\'s switch.'})
            if not data.get('beneficiary_email') and not data.get('beneficiary_user_id'):
                raise serializers.ValidationError('Beneficiary email or user ID required.')

        elif ct == ConditionType.MULTI_SIG:
            signers = data.get('signer_ids', [])
            if len(signers) < 2:
                raise serializers.ValidationError({'signer_ids': 'Need at least 2 signers.'})
            required = data.get('required_approvals', 2)
            if required > len(signers):
                raise serializers.ValidationError({'required_approvals': 'Cannot exceed number of signers.'})

        elif ct == ConditionType.DAO_VOTE:
            voters = data.get('voter_ids', [])
            if len(voters) < 1:
                raise serializers.ValidationError({'voter_ids': 'Need at least 1 voter.'})

        elif ct == ConditionType.PRICE_ORACLE:
            if not data.get('price_threshold'):
                raise serializers.ValidationError({'price_threshold': 'Required for price oracle.'})

        elif ct == ConditionType.ESCROW:
            if not data.get('beneficiary_user_id'):
                raise serializers.ValidationError({'beneficiary_user_id': 'Required for escrow.'})
            if not data.get('arbitrator_id'):
                raise serializers.ValidationError({'arbitrator_id': 'Required for escrow.'})

        return data
