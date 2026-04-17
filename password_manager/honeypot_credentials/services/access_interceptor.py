"""
HoneypotAccessInterceptor
==========================

The single piece of the app that plugs into the vault retrieve path.
Callers invoke ``check_and_record(...)`` BEFORE hitting the real vault
lookup; if the id belongs to a honeypot we record the access, enqueue
alerts, and return the decoy payload. Otherwise the caller continues
with its normal flow.

Keeping the interceptor thin and read-mostly (one SELECT + INSERT) keeps
the extra latency for real requests negligible.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction

from shared.utils import get_client_ip

from ..models import HoneypotAccessEvent, HoneypotAccessType, HoneypotCredential
from .alerting import fire_alerts
from .honeypot_service import HoneypotService

logger = logging.getLogger(__name__)


class HoneypotAccessInterceptor:
    """Thin facade around HoneypotService + alerting pipeline."""

    def __init__(self) -> None:
        self.service = HoneypotService()

    @staticmethod
    def _enabled() -> bool:
        return bool(getattr(settings, 'HONEYPOT_CREDENTIALS_ENABLED', True))

    def _record(
        self,
        honeypot: HoneypotCredential,
        request,
        access_type: str,
    ) -> HoneypotAccessEvent:
        ip = get_client_ip(request) if request is not None else ''
        ua = ''
        session_key = ''
        if request is not None:
            ua = request.META.get('HTTP_USER_AGENT', '')[:512]
            try:
                session_key = (request.session.session_key or '')[:64]
            except Exception:
                session_key = ''

        geo_country = ''
        geo_city = ''
        # Best-effort GeoIP2 — we never let geo lookup block the response.
        try:
            from django.contrib.gis.geoip2 import GeoIP2
            g = GeoIP2().city(ip)
            geo_country = g.get('country_name', '') or ''
            geo_city = g.get('city', '') or ''
        except Exception:
            pass

        event = HoneypotAccessEvent.objects.create(
            honeypot=honeypot,
            access_type=access_type,
            ip=ip or None,
            user_agent=ua,
            geo_country=geo_country,
            geo_city=geo_city,
            session_key=session_key,
        )
        return event

    def check_and_record(
        self,
        candidate_id: Any,
        request,
        access_type: str = HoneypotAccessType.RETRIEVE,
    ) -> Optional[Dict[str, Any]]:
        """
        If ``candidate_id`` matches a honeypot: record the event, fire
        alerts, return the decoy payload. Otherwise return None so the
        caller continues its normal vault lookup.
        """
        if not self._enabled():
            return None

        honeypot = self.service.get_by_id(candidate_id)
        if honeypot is None or not honeypot.is_active:
            return None

        with transaction.atomic():
            event = self._record(honeypot, request, access_type)

        # Fire alerts OUTSIDE the transaction so DB work commits even if
        # email/webhook delivery is slow. Inline dispatch is fine here —
        # we do want the alert to be visible before the attacker can
        # clean up, and the channels themselves are fire-and-forget.
        try:
            fire_alerts(event)
        except Exception as exc:  # pragma: no cover
            logger.error("Honeypot alert fanout crashed: %s", exc)

        logger.warning(
            "Honeypot hit: hp=%s user=%s type=%s ip=%s",
            honeypot.id, honeypot.user_id, access_type, event.ip,
        )

        if access_type == HoneypotAccessType.LIST_VIEW:
            return self.service.masked_list_entry(honeypot)
        return self.service.reveal_decoy(honeypot)

    # Convenience wrappers used by the vault views.
    def intercept_retrieve(self, candidate_id, request):
        return self.check_and_record(candidate_id, request, HoneypotAccessType.RETRIEVE)

    def intercept_copy(self, candidate_id, request):
        return self.check_and_record(candidate_id, request, HoneypotAccessType.COPY)

    def intercept_autofill(self, candidate_id, request):
        return self.check_and_record(candidate_id, request, HoneypotAccessType.AUTOFILL)
