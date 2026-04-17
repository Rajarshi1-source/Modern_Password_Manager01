from django.contrib import admin

from .models import PairingEvent, PairingSession


@admin.register(PairingSession)
class PairingSessionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'initiator', 'responder', 'purpose', 'status',
        'created_at', 'expires_at', 'completed_at',
    )
    list_filter = ('status', 'purpose')
    search_fields = ('id', 'initiator__email', 'responder__email', 'nonce_key')
    readonly_fields = (
        'id', 'initiator_pub_key', 'responder_pub_key', 'nonce',
        'nonce_key', 'sas_hmac', 'payload_ciphertext', 'payload_nonce',
        'created_at', 'expires_at', 'completed_at',
    )


@admin.register(PairingEvent)
class PairingEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'kind', 'actor', 'ip', 'created_at')
    list_filter = ('kind',)
    search_fields = ('session__id', 'actor__email', 'ip')
    readonly_fields = ('created_at',)
