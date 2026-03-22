"""
Governance Serializers — Multi-Sig & DAO
==========================================
"""

from rest_framework import serializers
from smart_contracts.models.governance import (
    MultiSigGroup, MultiSigApproval, DAOProposal, DAOVote
)


class MultiSigApprovalSerializer(serializers.ModelSerializer):
    signer_username = serializers.CharField(source='signer.username', read_only=True)

    class Meta:
        model = MultiSigApproval
        fields = ['id', 'signer', 'signer_username', 'approved', 'tx_hash', 'approved_at']
        read_only_fields = ['id', 'signer', 'approved', 'tx_hash', 'approved_at']


class MultiSigGroupSerializer(serializers.ModelSerializer):
    approvals = MultiSigApprovalSerializer(many=True, read_only=True)
    total_signers = serializers.IntegerField(read_only=True)
    approval_count = serializers.IntegerField(read_only=True)
    is_threshold_met = serializers.BooleanField(read_only=True)

    class Meta:
        model = MultiSigGroup
        fields = [
            'id', 'required_approvals', 'total_signers',
            'approval_count', 'is_threshold_met', 'approvals', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DAOVoteSerializer(serializers.ModelSerializer):
    voter_username = serializers.CharField(source='voter.username', read_only=True)

    class Meta:
        model = DAOVote
        fields = ['id', 'voter', 'voter_username', 'approve', 'tx_hash', 'voted_at']
        read_only_fields = ['id', 'voter', 'tx_hash', 'voted_at']


class DAOVoteCreateSerializer(serializers.Serializer):
    approve = serializers.BooleanField()


class DAOProposalSerializer(serializers.ModelSerializer):
    votes = DAOVoteSerializer(many=True, read_only=True)
    votes_for = serializers.IntegerField(read_only=True)
    votes_against = serializers.IntegerField(read_only=True)
    total_eligible = serializers.IntegerField(read_only=True)
    voting_ended = serializers.BooleanField(read_only=True)
    quorum_met = serializers.BooleanField(read_only=True)

    class Meta:
        model = DAOProposal
        fields = [
            'id', 'title', 'description', 'voting_deadline',
            'quorum_threshold', 'votes_for', 'votes_against',
            'total_eligible', 'voting_ended', 'quorum_met',
            'votes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
