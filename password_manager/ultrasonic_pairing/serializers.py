"""DRF serializers for ultrasonic_pairing."""

from __future__ import annotations

import base64

from rest_framework import serializers

from .models import PairingEvent, PairingSession


def _b64(data):
    if not data:
        return None
    return base64.b64encode(bytes(data)).decode('ascii')


class PairingSessionSerializer(serializers.ModelSerializer):
    initiator_pub_key_b64 = serializers.SerializerMethodField()
    responder_pub_key_b64 = serializers.SerializerMethodField()
    sas_hmac_b64 = serializers.SerializerMethodField()
    payload_ciphertext_b64 = serializers.SerializerMethodField()
    payload_nonce_b64 = serializers.SerializerMethodField()

    class Meta:
        model = PairingSession
        fields = (
            'id', 'purpose', 'status',
            'initiator_pub_key_b64', 'responder_pub_key_b64',
            'sas_hmac_b64',
            'payload_ciphertext_b64', 'payload_nonce_b64',
            'payload_vault_item_id',
            'created_at', 'expires_at', 'completed_at',
        )
        read_only_fields = fields

    def get_initiator_pub_key_b64(self, obj):
        return _b64(obj.initiator_pub_key)

    def get_responder_pub_key_b64(self, obj):
        return _b64(obj.responder_pub_key)

    def get_sas_hmac_b64(self, obj):
        return _b64(obj.sas_hmac)

    def get_payload_ciphertext_b64(self, obj):
        # Only the responder ever needs to read the payload, and this
        # is enforced at the view layer (fetch_delivered_payload).
        return _b64(obj.payload_ciphertext)

    def get_payload_nonce_b64(self, obj):
        return _b64(obj.payload_nonce)


class PairingSessionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PairingSession
        fields = ('id', 'purpose', 'status', 'expires_at', 'created_at')
        read_only_fields = fields


class PairingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PairingEvent
        fields = ('id', 'session', 'kind', 'ip', 'user_agent', 'detail', 'created_at')
        read_only_fields = fields
