"""
Threat Intelligence Feed Adapters
=================================

Pluggable fetchers that turn a configured :class:`ThreatIntelFeed` into real
threat-intelligence updates (industry posture + threat actors). Each adapter is
graceful: when a feed is unconfigured or unreachable it returns a health flag
instead of raising, so ``update_threat_intelligence`` never hard-fails.

Phase 2 wires two real adapters:

* ``hibp`` — pulls the free public Have I Been Pwned breaches list and derives
  recent-breach pressure per industry from breach domains. No API key needed.
* ``internal_darkweb`` — reads the local ``ml_dark_web`` corpus (recent
  high-severity breaches + LSTM threat-actor patterns) with no external call.

``misp`` / ``alienvault_otx`` / ``custom_api`` / ``rss`` are pluggable stubs
that no-op with a clear "not configured / not implemented" health message until
credentials and a parser are supplied (mirrors the bug_bounty payout-adapter
pattern).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

# HIBP's breach list is free and unauthenticated.
HIBP_BREACHES_URL = "https://haveibeenpwned.com/api/v3/breaches"

# Coarse breach-domain -> industry-code keyword map (server-side; mirrors the
# client domain_class vocabulary). Used to attribute breaches to industries.
DOMAIN_INDUSTRY_KEYWORDS = {
    'finance': ['bank', 'paypal', 'finance', 'crypto', 'coinbase', 'capitalone',
                'visa', 'mastercard', 'chase', 'wellsfargo', 'amex'],
    'healthcare': ['health', 'clinic', 'hospital', 'medical', 'pharma'],
    'government': ['gov', 'irs', 'dmv', 'usps'],
    'education': ['edu', 'university', 'college', 'school', 'coursera', 'udemy'],
    'technology': ['github', 'gitlab', 'aws', 'cloud', 'adobe', 'dropbox', 'linkedin'],
    'retail': ['shop', 'store', 'amazon', 'ebay', 'walmart', 'target'],
    'social': ['facebook', 'instagram', 'twitter', 'tiktok', 'reddit', 'myspace'],
}

# Recency window for "recent" breach pressure.
RECENT_WINDOW_DAYS = 30


def classify_domain_industry(domain: str) -> str:
    """Map a breach domain to a coarse industry code, or '' if unknown."""
    if not domain:
        return ''
    host = domain.lower()
    for industry, keywords in DOMAIN_INDUSTRY_KEYWORDS.items():
        if any(kw in host for kw in keywords):
            return industry
    return ''


@dataclass
class FeedSyncResult:
    """Outcome of syncing a single feed."""
    items_count: int = 0
    ok: bool = True
    message: str = ''
    # industry_code -> number of recent breaches attributable to this feed.
    industry_signals: Dict[str, int] = field(default_factory=dict)


class ThreatFeedAdapter:
    """Base adapter. Subclasses implement :meth:`fetch`."""

    def fetch(self, feed) -> FeedSyncResult:  # pragma: no cover - abstract
        raise NotImplementedError


class HIBPFeedAdapter(ThreatFeedAdapter):
    """Ingest the free public HIBP breaches list into industry posture."""

    def _fetch_breaches(self):
        """Return the raw HIBP breaches list (isolated for testability)."""
        resp = requests.get(
            HIBP_BREACHES_URL,
            headers={"User-Agent": "PasswordManager-ThreatIntel"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self, feed) -> FeedSyncResult:
        try:
            breaches = self._fetch_breaches()
        except Exception as e:
            logger.warning(f"HIBP feed fetch failed: {e}")
            return FeedSyncResult(ok=False, message=f"fetch failed: {e}")

        cutoff = timezone.now().date() - timezone.timedelta(days=RECENT_WINDOW_DAYS)
        signals: Dict[str, int] = {}
        recent = 0

        for b in breaches:
            added = (b.get('AddedDate') or b.get('BreachDate') or '')[:10]
            try:
                added_date = timezone.datetime.strptime(added, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
            if added_date < cutoff:
                continue
            recent += 1
            industry = classify_domain_industry(b.get('Domain', ''))
            if industry:
                signals[industry] = signals.get(industry, 0) + 1

        return FeedSyncResult(
            items_count=recent,
            ok=True,
            message=f"{recent} recent breaches",
            industry_signals=signals,
        )


class InternalDarkWebFeedAdapter(ThreatFeedAdapter):
    """Derive threat intel from the local ml_dark_web corpus (no network)."""

    def fetch(self, feed) -> FeedSyncResult:
        try:
            from ml_dark_web.models import MLBreachData, BreachPatternAnalysis
        except Exception as e:
            return FeedSyncResult(ok=False, message=f"ml_dark_web unavailable: {e}")

        cutoff = timezone.now() - timezone.timedelta(days=RECENT_WINDOW_DAYS)
        signals: Dict[str, int] = {}
        count = 0

        recent_breaches = MLBreachData.objects.filter(
            detected_at__gte=cutoff,
            severity__in=['HIGH', 'CRITICAL'],
        )
        for breach in recent_breaches.iterator():
            count += 1
            for domain in (breach.extracted_domains or []):
                industry = classify_domain_industry(domain)
                if industry:
                    signals[industry] = signals.get(industry, 0) + 1

        # Promote active LSTM threat-actor patterns into ThreatActorTTP rows.
        actors_synced = self._sync_threat_actors(BreachPatternAnalysis)

        return FeedSyncResult(
            items_count=count + actors_synced,
            ok=True,
            message=f"{count} breaches, {actors_synced} actor patterns",
            industry_signals=signals,
        )

    def _sync_threat_actors(self, BreachPatternAnalysis) -> int:
        """Upsert ThreatActorTTP rows from active threat-actor patterns."""
        from ..models import ThreatActorTTP

        synced = 0
        patterns = BreachPatternAnalysis.objects.filter(
            pattern_type='threat_actor', is_active=True,
        )
        for p in patterns.iterator():
            ThreatActorTTP.objects.update_or_create(
                name=f"darkweb:{p.pattern_id}",
                defaults={
                    'actor_type': 'unknown',
                    'threat_level': p.risk_level or 'medium',
                    'is_currently_active': True,
                    'last_active': p.last_seen,
                    'source': 'internal_darkweb',
                },
            )
            synced += 1
        return synced


class UnconfiguredFeedAdapter(ThreatFeedAdapter):
    """Graceful no-op for feeds without a real fetcher yet (MISP/OTX/...)."""

    def __init__(self, feed_type: str):
        self.feed_type = feed_type

    def fetch(self, feed) -> FeedSyncResult:
        has_creds = bool(feed.api_endpoint) and bool(feed.api_key_encrypted)
        if not has_creds:
            return FeedSyncResult(
                ok=True, message=f"{self.feed_type} not configured (no endpoint/key)"
            )
        return FeedSyncResult(
            ok=True, message=f"{self.feed_type} adapter not implemented yet"
        )


_REAL_ADAPTERS = {
    'hibp': HIBPFeedAdapter,
    'internal_darkweb': InternalDarkWebFeedAdapter,
}


def get_feed_adapter(feed_type: str) -> ThreatFeedAdapter:
    """Return the adapter for a feed type (graceful no-op when unimplemented)."""
    adapter_cls = _REAL_ADAPTERS.get(feed_type)
    if adapter_cls:
        return adapter_cls()
    return UnconfiguredFeedAdapter(feed_type)
