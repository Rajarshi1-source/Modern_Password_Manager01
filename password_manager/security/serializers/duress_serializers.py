"""
Duress code serializers.

Phase D / D9 (2026-05): explicit validation surface for TrustedAuthority
creation. The previous POST handler in ``duress_code_views.py`` accepted
raw user-supplied JSON into the ``contact_details`` and
``trigger_threat_levels`` ``JSONField``s with no constraints — meaning:

* ``trigger_threat_levels=[]`` would silently disable every alert (the
  authority is "configured" but never fires, defeating the entire
  point of a silent alarm).
* ``contact_details`` could carry attacker-controlled webhook URLs
  under arbitrary keys, exfiltrating duress alerts to a third party.

These serializers enforce a typed contract: each contact channel has
its own sub-serializer with a known field set, and ``trigger_threat_levels``
must be a non-empty list of valid threat-level strings.
"""

from __future__ import annotations

from rest_framework import serializers

from security.models.duress_models import TrustedAuthority


# The list of allowed threat-level strings. Sourced from the
# ``DuressCode.THREAT_LEVELS`` choices used elsewhere in the duress
# module; duplicated here so the serializer doesn't drag the model
# import into application bootstrap order.
_THREAT_LEVELS = ('low', 'medium', 'high', 'critical')


class ContactDetailsSerializer(serializers.Serializer):
    """
    Typed contract for the ``contact_details`` JSONField.

    Each contact channel has its own optional field. Unknown keys are
    rejected (DRF's default behaviour when ``allow_null=False`` and the
    field isn't declared) — the previous free-form dict made it
    impossible to audit what was actually stored.
    """
    email = serializers.EmailField(required=False, allow_blank=False)
    phone = serializers.CharField(required=False, allow_blank=False, max_length=32)
    webhook_url = serializers.URLField(required=False, allow_blank=False)
    signal_number = serializers.CharField(
        required=False, allow_blank=False, max_length=32,
        help_text="Phone number for Signal Messenger",
    )

    def validate(self, attrs):
        # Defence-in-depth: at least one channel must be populated.
        # An empty contact_details dict would otherwise mean "alert
        # configured but no destination" — same silent-failure mode
        # as trigger_threat_levels=[].
        if not any(attrs.get(k) for k in (
            'email', 'phone', 'webhook_url', 'signal_number',
        )):
            raise serializers.ValidationError(
                "At least one of {email, phone, webhook_url, signal_number} "
                "must be provided."
            )
        return attrs


class TrustedAuthorityCreateSerializer(serializers.Serializer):
    """Validates a ``POST /trusted-authorities`` payload."""

    name = serializers.CharField(max_length=200, allow_blank=False)
    authority_type = serializers.ChoiceField(
        choices=[c[0] for c in TrustedAuthority.AUTHORITY_TYPES],
    )
    contact_method = serializers.ChoiceField(
        choices=[c[0] for c in TrustedAuthority.CONTACT_METHODS],
        default='email',
    )
    contact_details = ContactDetailsSerializer()

    # Phase D / D9: ``min_length=1`` is the linchpin. An attacker
    # (or a confused frontend) previously could POST
    # ``trigger_threat_levels: []`` and end up with an authority
    # that fires on no level — completely silent. Reject that here.
    trigger_threat_levels = serializers.ListField(
        child=serializers.ChoiceField(choices=_THREAT_LEVELS),
        min_length=1,
        max_length=len(_THREAT_LEVELS),
        help_text=(
            "List of threat levels that trigger notification. "
            "Must contain at least one valid level."
        ),
    )

    delay_seconds = serializers.IntegerField(
        min_value=0, max_value=3600, default=0,
        help_text="Stealth delay (0 = immediate, up to 1 hour).",
    )
    include_location = serializers.BooleanField(default=True)
    include_evidence_link = serializers.BooleanField(default=False)
