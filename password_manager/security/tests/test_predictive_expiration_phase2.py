"""
Phase 2 tests — Predictive Password Expiration (zero-knowledge)
===============================================================

Covers the Phase 2 additions:
- dark-web structural prevalence (model, seed command, lookup, risk wiring)
- pluggable threat-intel feed adapters (HIBP, internal dark-web, no-op)
- update_threat_intelligence ingestion task
- WebSocket risk-alert fan-out
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

User = get_user_model()


class StructuralPrevalenceTests(TestCase):
    """Dark-web structural prevalence signal."""

    def _svc(self):
        from security.services.threat_intelligence_service import (
            ThreatIntelligenceService,
        )
        return ThreatIntelligenceService()

    def test_structure_signature_collapses_runs(self):
        svc = self._svc()
        self.assertEqual(svc._structure_signature('ULLLLLDDDD'), 'ULD')
        self.assertEqual(svc._structure_signature('LLLLLLLL'), 'L')
        self.assertEqual(svc._structure_signature('LLLLDDDD'), 'LD')
        self.assertEqual(svc._structure_signature(''), '')

    def test_prevalence_lookup_after_seed(self):
        from security.models import PasswordStructurePrevalence
        PasswordStructurePrevalence.objects.create(
            char_class_pattern='ULD', length_bucket='medium', prevalence=0.09
        )
        svc = self._svc()
        # 'ULLLLLDDDD' -> 10 chars (medium) -> signature ULD
        self.assertAlmostEqual(svc.get_structural_prevalence('ULLLLLDDDD'), 0.09)
        # Unknown shape -> 0
        self.assertEqual(svc.get_structural_prevalence('SSSS'), 0.0)
        # Empty -> 0
        self.assertEqual(svc.get_structural_prevalence(''), 0.0)

    def test_any_length_fallback(self):
        from security.models import PasswordStructurePrevalence
        PasswordStructurePrevalence.objects.create(
            char_class_pattern='LD', length_bucket='', prevalence=0.12
        )
        svc = self._svc()
        # No medium-specific row, but the any-length row applies.
        self.assertAlmostEqual(svc.get_structural_prevalence('LLLLLLLDDD'), 0.12)

    def test_check_pattern_prevalence_then_fallback(self):
        from security.models import PasswordStructurePrevalence
        svc = self._svc()
        # With nothing seeded, the heuristic fallback still returns a list.
        res = svc.check_pattern_in_dictionaries('password123')
        self.assertIsInstance(res, list)
        # Seeded -> a real breach_corpus structural match.
        PasswordStructurePrevalence.objects.create(
            char_class_pattern='LD', length_bucket='medium', prevalence=0.18
        )
        res2 = svc.check_pattern_in_dictionaries(
            '', char_class_sequence='LLLLLLLDDD'
        )
        self.assertTrue(any(m.dictionary_name == 'breach_corpus' for m in res2))

    def test_threat_level_includes_prevalence_factor(self):
        from security.models import PasswordStructurePrevalence
        PasswordStructurePrevalence.objects.create(
            char_class_pattern='LD', length_bucket='medium', prevalence=0.5
        )
        svc = self._svc()
        tl = svc.get_real_time_threat_level(char_class_sequence='LLLLLLLDDD')
        self.assertTrue(any('breach corpora' in f for f in tl.factors))
        self.assertGreater(tl.score, 0)


class SeedStructurePrevalenceCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        from security.models import PasswordStructurePrevalence
        call_command('seed_structure_prevalence')
        count = PasswordStructurePrevalence.objects.count()
        self.assertGreater(count, 0)
        # Re-running must not create duplicates.
        call_command('seed_structure_prevalence')
        self.assertEqual(PasswordStructurePrevalence.objects.count(), count)


class FeedAdapterTests(TestCase):
    def test_classify_domain_industry(self):
        from security.services.threat_feed_adapters import classify_domain_industry
        self.assertEqual(classify_domain_industry('chase.com'), 'finance')
        self.assertEqual(classify_domain_industry('myhospital.org'), 'healthcare')
        self.assertEqual(classify_domain_industry('unknown.zzz'), '')
        self.assertEqual(classify_domain_industry(''), '')

    def test_hibp_adapter_parses_recent_breaches(self):
        from security.services.threat_feed_adapters import HIBPFeedAdapter
        today = timezone.now().date().strftime('%Y-%m-%d')
        adapter = HIBPFeedAdapter()
        with patch.object(adapter, '_fetch_breaches', return_value=[
            {'Name': 'X', 'Domain': 'chase.com', 'AddedDate': today},
            {'Name': 'Y', 'Domain': 'unknown.zzz', 'AddedDate': today},
            {'Name': 'Z', 'Domain': 'paypal.com', 'AddedDate': '2000-01-01'},
        ]):
            res = adapter.fetch(feed=MagicMock())
        self.assertTrue(res.ok)
        self.assertEqual(res.items_count, 2)  # two within the window
        self.assertEqual(res.industry_signals.get('finance'), 1)

    def test_hibp_adapter_graceful_on_failure(self):
        from security.services.threat_feed_adapters import HIBPFeedAdapter
        adapter = HIBPFeedAdapter()
        with patch.object(adapter, '_fetch_breaches', side_effect=Exception('boom')):
            res = adapter.fetch(feed=MagicMock())
        self.assertFalse(res.ok)
        self.assertIn('fetch failed', res.message)

    def test_unconfigured_adapter_is_graceful_noop(self):
        from security.services.threat_feed_adapters import get_feed_adapter
        adapter = get_feed_adapter('misp')
        feed = MagicMock(api_endpoint='', api_key_encrypted=None)
        res = adapter.fetch(feed)
        self.assertTrue(res.ok)
        self.assertIn('not configured', res.message)

    def test_internal_darkweb_adapter_reads_corpus(self):
        from ml_dark_web.models import BreachSource, MLBreachData
        from security.services.threat_feed_adapters import InternalDarkWebFeedAdapter
        src = BreachSource.objects.create(
            name='paste', url='http://example.onion', source_type='paste'
        )
        MLBreachData.objects.create(
            breach_id='b1', title='t', description='d', source=src,
            severity='HIGH', confidence_score=0.9,
            extracted_domains=['chase.com', 'paypal.com'],
        )
        res = InternalDarkWebFeedAdapter().fetch(feed=MagicMock())
        self.assertTrue(res.ok)
        # Both domains classify to finance -> count 2.
        self.assertEqual(res.industry_signals.get('finance'), 2)


class UpdateThreatIntelligenceTaskTests(TestCase):
    def test_internal_feed_updates_industry_posture(self):
        from security.models import ThreatIntelFeed, IndustryThreatLevel
        from ml_dark_web.models import BreachSource, MLBreachData
        from security.tasks import update_threat_intelligence

        src = BreachSource.objects.create(
            name='paste', url='http://example.onion', source_type='paste'
        )
        MLBreachData.objects.create(
            breach_id='b1', title='t', description='d', source=src,
            severity='CRITICAL', confidence_score=0.95,
            extracted_domains=['chase.com'],
        )
        feed = ThreatIntelFeed.objects.create(
            name='internal', feed_type='internal_darkweb', is_active=True
        )

        result = update_threat_intelligence()

        self.assertEqual(result['feeds_updated'], 1)
        self.assertEqual(result['feeds_failed'], 0)
        self.assertGreaterEqual(result['industries_updated'], 1)
        self.assertTrue(
            IndustryThreatLevel.objects.filter(industry_code='finance').exists()
        )
        feed.refresh_from_db()
        self.assertTrue(feed.last_sync_success)
        self.assertTrue(feed.is_healthy)
        self.assertEqual(feed.last_sync_items_count, 1)

    def test_unconfigured_feed_marked_healthy_noop(self):
        from security.models import ThreatIntelFeed
        from security.tasks import update_threat_intelligence

        feed = ThreatIntelFeed.objects.create(
            name='misp', feed_type='misp', is_active=True
        )
        result = update_threat_intelligence()

        self.assertEqual(result['feeds_updated'], 1)
        feed.refresh_from_db()
        self.assertTrue(feed.is_healthy)
        self.assertIn('not configured', feed.health_check_message)

    def test_stale_industry_pressure_is_reset(self):
        """An industry with no breaches in the current feed is cleared."""
        from security.models import ThreatIntelFeed, IndustryThreatLevel
        from security.tasks import update_threat_intelligence

        # Pre-existing elevated industry that the current feed won't mention.
        IndustryThreatLevel.objects.create(
            industry_code='finance', industry_name='Finance',
            recent_breaches_count=12, threat_score=0.6,
            current_threat_level='severe',
        )
        # Active feed that produces no industry signals (unconfigured no-op).
        ThreatIntelFeed.objects.create(
            name='misp', feed_type='misp', is_active=True
        )

        update_threat_intelligence()

        finance = IndustryThreatLevel.objects.get(industry_code='finance')
        self.assertEqual(finance.recent_breaches_count, 0)
        self.assertEqual(finance.threat_score, 0.0)
        self.assertEqual(finance.current_threat_level, 'low')


class WebSocketAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wsuser', email='ws@e.com')

    @patch('security.tasks.breach_tasks._send_ws_risk_alert')
    def test_notifications_fan_out_ws_alert(self, mock_ws):
        from security.models import PredictiveExpirationRule
        from security.tasks import send_expiration_notifications

        PredictiveExpirationRule.objects.create(
            user=self.user, credential_id='c1', credential_domain='finance',
            risk_level='critical', risk_score=0.95, user_acknowledged=False,
        )
        result = send_expiration_notifications()

        self.assertEqual(result['notifications_sent'], 1)
        mock_ws.assert_called_once()

    def test_send_ws_risk_alert_swallows_errors(self):
        """A broken/missing channel layer must never break the task."""
        from security.tasks.breach_tasks import _send_ws_risk_alert
        with patch(
            'security.consumers.predictive_expiration_consumer.send_risk_alert',
            side_effect=Exception('no channel layer'),
        ):
            # Must not raise.
            _send_ws_risk_alert(
                user_id=self.user.id, credential_id='c1',
                credential_domain='finance', risk_level='high', risk_score=0.7,
            )


class DailyScanFailureGatingTests(TestCase):
    """A partial scan failure must not dispatch the global notification pass."""

    def setUp(self):
        self.user = User.objects.create_user(username='scanu', email='s@e.com')

    @patch('security.tasks.breach_tasks.send_expiration_notifications')
    @patch('security.tasks.breach_tasks.update_threat_intelligence')
    def test_partial_failure_skips_notifications(self, _mock_refresh, mock_notify):
        from security.models import (
            PredictiveExpirationSettings, PredictiveExpirationRule,
        )
        from security.tasks.breach_tasks import daily_predictive_scan

        PredictiveExpirationSettings.objects.create(
            user=self.user, is_enabled=True
        )

        # Force the per-user rule query to fail.
        with patch.object(
            PredictiveExpirationRule.objects, 'filter',
            side_effect=Exception('db down'),
        ):
            result = daily_predictive_scan()

        self.assertGreaterEqual(result['scan_failures'], 1)
        self.assertFalse(result['notifications_dispatched'])
        mock_notify.delay.assert_not_called()
        mock_notify.si.assert_not_called()
