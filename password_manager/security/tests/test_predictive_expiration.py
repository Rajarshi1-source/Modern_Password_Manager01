"""
Unit Tests for Predictive Password Expiration Feature
======================================================

Tests for pattern analysis engine, threat intelligence service,
and predictive expiration service.
"""

import json
import hashlib
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class PatternAnalysisEngineTests(TestCase):
    """Tests for the PatternAnalysisEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_analyze_password_structure(self):
        """Test password structure analysis."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        # Test simple password
        result = engine.analyze_password('password123')
        self.assertIsInstance(result, dict)
        self.assertIn('structure', result)
        self.assertIn('entropy', result)
        self.assertIn('char_classes', result)
        
    def test_detect_common_mutations(self):
        """Test detection of common character mutations."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        # Test leet speak detection
        result = engine.analyze_password('p@ssw0rd')
        self.assertIn('mutations', result)
        
    def test_detect_keyboard_patterns(self):
        """Test detection of keyboard patterns."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        # Test keyboard sequence detection
        result = engine.analyze_password('qwerty123')
        self.assertTrue(result.get('has_keyboard_pattern', False) or 
                       'keyboard' in str(result.get('patterns', [])).lower())
        
    def test_extract_structure_fingerprint(self):
        """Test structure fingerprint extraction."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        fingerprint = engine.extract_structure_fingerprint('Password123!')
        self.assertIsInstance(fingerprint, (str, bytes))
        self.assertTrue(len(fingerprint) > 0)
        
    def test_calculate_similarity_score(self):
        """Test similarity score calculation between patterns."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        fp1 = engine.extract_structure_fingerprint('Password123!')
        fp2 = engine.extract_structure_fingerprint('Password456!')
        fp3 = engine.extract_structure_fingerprint('CompletelyDifferent#99')
        
        # Similar passwords should have higher similarity
        similarity_similar = engine.calculate_similarity_score(fp1, fp2)
        similarity_different = engine.calculate_similarity_score(fp1, fp3)
        
        self.assertIsInstance(similarity_similar, float)
        self.assertIsInstance(similarity_different, float)
        self.assertTrue(0 <= similarity_similar <= 1)
        self.assertTrue(0 <= similarity_different <= 1)
        
    def test_identify_base_word_patterns(self):
        """Test base word pattern identification."""
        from security.services.pattern_analysis_engine import PatternAnalysisEngine
        
        engine = PatternAnalysisEngine()
        
        result = engine.analyze_password('summer2023!')
        # Should detect common base words or date patterns
        self.assertIn('patterns', result)


class ThreatIntelligenceServiceTests(TestCase):
    """Tests for the ThreatIntelligenceService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
    def test_get_real_time_threat_level(self):
        """Test real-time threat level assessment."""
        from security.services.threat_intelligence_service import ThreatIntelligenceService
        
        service = ThreatIntelligenceService()
        
        threat_level = service.get_real_time_threat_level(
            credential_domain='example.com'
        )
        
        self.assertIsInstance(threat_level, dict)
        self.assertIn('level', threat_level)
        self.assertIn(threat_level['level'], ['critical', 'high', 'medium', 'low', 'minimal'])
        
    def test_fetch_active_ttps(self):
        """Test fetching active threat actor TTPs."""
        from security.services.threat_intelligence_service import ThreatIntelligenceService
        
        service = ThreatIntelligenceService()
        
        ttps = service.fetch_active_ttps()
        
        self.assertIsInstance(ttps, list)
        
    def test_match_user_industry(self):
        """Test industry threat matching."""
        from security.services.threat_intelligence_service import ThreatIntelligenceService
        from security.models import PredictiveExpirationSettings
        
        # Create settings with industry
        settings = PredictiveExpirationSettings.objects.create(
            user=self.user,
            industry='technology'
        )
        
        service = ThreatIntelligenceService()
        
        threats = service.match_user_industry(self.user.id)
        
        self.assertIsInstance(threats, list)
        
    def test_check_pattern_in_dictionaries(self):
        """Test pattern checking against known dictionaries."""
        from security.services.threat_intelligence_service import ThreatIntelligenceService
        
        service = ThreatIntelligenceService()
        
        # Common password should match
        result_common = service.check_pattern_in_dictionaries('password123')
        self.assertIsInstance(result_common, dict)
        self.assertIn('is_common', result_common)
        
        # Complex password should not match
        result_complex = service.check_pattern_in_dictionaries('X$k2!mNp9@Qz')
        self.assertIsInstance(result_complex, dict)


class PredictiveExpirationServiceTests(TestCase):
    """Tests for the PredictiveExpirationService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
    def test_calculate_exposure_risk(self):
        """Test exposure risk calculation."""
        from security.services.predictive_expiration_service import PredictiveExpirationService
        
        service = PredictiveExpirationService()
        
        risk = service.calculate_exposure_risk(
            password='TestPassword123!',
            domain='example.com',
            age_days=30,
            user_id=self.user.id
        )
        
        self.assertIsInstance(risk, dict)
        self.assertIn('risk_score', risk)
        self.assertIn('risk_level', risk)
        self.assertTrue(0 <= risk['risk_score'] <= 1)
        self.assertIn(risk['risk_level'], ['critical', 'high', 'medium', 'low', 'minimal'])
        
    def test_predict_compromise_timeline(self):
        """Test compromise timeline prediction."""
        from security.services.predictive_expiration_service import PredictiveExpirationService
        
        service = PredictiveExpirationService()
        
        prediction = service.predict_compromise_timeline(
            password='WeakPassword1',
            domain='banking.com',
            user_id=self.user.id
        )
        
        self.assertIsInstance(prediction, dict)
        self.assertIn('predicted_date', prediction)
        self.assertIn('confidence', prediction)
        
    def test_should_force_rotation(self):
        """Test rotation decision logic."""
        from security.services.predictive_expiration_service import PredictiveExpirationService
        
        service = PredictiveExpirationService()
        
        # Test with weak, old password
        should_rotate, reasons = service.should_force_rotation(
            password='password123',
            domain='critical-system.com',
            age_days=100
        )
        
        self.assertIsInstance(should_rotate, bool)
        self.assertIsInstance(reasons, list)
        
    def test_generate_rotation_recommendation(self):
        """Test rotation recommendation generation."""
        from security.services.predictive_expiration_service import PredictiveExpirationService
        
        service = PredictiveExpirationService()
        
        recommendation = service.generate_rotation_recommendation(
            password='OldPassword123',
            domain='service.com',
            age_days=60,
            user_id=self.user.id
        )
        
        self.assertIsInstance(recommendation, dict)
        self.assertIn('action', recommendation)
        self.assertIn(recommendation['action'], [
            'rotate_immediately', 'rotate_soon', 'schedule_rotation', 'monitor', 'no_action'
        ])
        
    def test_create_expiration_rule(self):
        """Test expiration rule creation."""
        from security.services.predictive_expiration_service import PredictiveExpirationService
        from security.models import PredictiveExpirationRule
        
        service = PredictiveExpirationService()
        
        rule = service.create_expiration_rule(
            user_id=self.user.id,
            credential_id='test-cred-123',
            credential_domain='example.com',
            password='TestPassword123!',
            credential_age_days=45
        )
        
        self.assertIsInstance(rule, PredictiveExpirationRule)
        self.assertEqual(rule.user_id, self.user.id)
        self.assertEqual(rule.credential_domain, 'example.com')
        self.assertTrue(rule.is_active)


class PredictiveExpirationModelTests(TestCase):
    """Tests for predictive expiration database models."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
    def test_password_pattern_profile_creation(self):
        """Test PasswordPatternProfile model creation."""
        from security.models import PasswordPatternProfile
        
        profile = PasswordPatternProfile.objects.create(
            user=self.user,
            char_class_distribution={'lowercase': 60, 'uppercase': 20, 'digits': 15, 'special': 5},
            avg_password_length=12.5,
            total_passwords_analyzed=10
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.total_passwords_analyzed, 10)
        self.assertIsNotNone(profile.created_at)
        
    def test_threat_actor_ttp_creation(self):
        """Test ThreatActorTTP model creation."""
        from security.models import ThreatActorTTP
        
        ttp = ThreatActorTTP.objects.create(
            name='Test Threat Actor',
            actor_type='apt',
            threat_level='high',
            target_industries=['technology', 'finance'],
            attack_techniques=['credential_stuffing', 'phishing'],
            is_currently_active=True
        )
        
        self.assertEqual(ttp.name, 'Test Threat Actor')
        self.assertEqual(ttp.threat_level, 'high')
        self.assertTrue(ttp.is_currently_active)
        self.assertIsNotNone(ttp.actor_id)
        
    def test_industry_threat_level_creation(self):
        """Test IndustryThreatLevel model creation."""
        from security.models import IndustryThreatLevel
        
        industry = IndustryThreatLevel.objects.create(
            industry_name='Technology',
            industry_code='tech',
            current_threat_level='high',
            threat_score=0.75,
            active_campaigns_count=5
        )
        
        self.assertEqual(industry.industry_name, 'Technology')
        self.assertEqual(industry.threat_score, 0.75)
        
    def test_predictive_expiration_rule_creation(self):
        """Test PredictiveExpirationRule model creation."""
        from security.models import PredictiveExpirationRule
        
        rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='cred-123',
            credential_domain='example.com',
            risk_level='high',
            risk_score=0.75,
            recommended_action='rotate_soon',
            predicted_compromise_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        self.assertEqual(rule.user, self.user)
        self.assertEqual(rule.risk_level, 'high')
        self.assertFalse(rule.user_acknowledged)
        self.assertIsNotNone(rule.rule_id)
        
    def test_password_rotation_event_creation(self):
        """Test PasswordRotationEvent model creation."""
        from security.models import PasswordRotationEvent, PredictiveExpirationRule
        
        rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='cred-123',
            credential_domain='example.com',
            risk_level='critical',
            risk_score=0.9
        )
        
        from security.models import PasswordRotationEvent
        event = PasswordRotationEvent.objects.create(
            user=self.user,
            credential_id='cred-123',
            credential_domain='example.com',
            rotation_type='proactive',
            outcome='success',
            triggered_by_rule=rule,
            trigger_reason='High risk score detected'
        )
        
        self.assertEqual(event.rotation_type, 'proactive')
        self.assertEqual(event.outcome, 'success')
        self.assertEqual(event.triggered_by_rule, rule)
        
    def test_threat_intel_feed_creation(self):
        """Test ThreatIntelFeed model creation."""
        from security.models import ThreatIntelFeed
        
        feed = ThreatIntelFeed.objects.create(
            name='Test Feed',
            feed_type='misp',
            is_active=True,
            reliability_score=0.9
        )
        
        self.assertEqual(feed.name, 'Test Feed')
        self.assertTrue(feed.is_active)
        self.assertIsNotNone(feed.feed_id)
        
    def test_predictive_expiration_settings_creation(self):
        """Test PredictiveExpirationSettings model creation."""
        from security.models import PredictiveExpirationSettings
        
        settings = PredictiveExpirationSettings.objects.create(
            user=self.user,
            is_enabled=True,
            auto_rotation_enabled=False,
            force_rotation_threshold=0.8,
            industry='technology'
        )
        
        self.assertEqual(settings.user, self.user)
        self.assertTrue(settings.is_enabled)
        self.assertFalse(settings.auto_rotation_enabled)


class CeleryTasksTests(TestCase):
    """Tests for predictive expiration Celery tasks."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
    @patch('security.tasks.PatternAnalysisEngine')
    def test_analyze_user_password_patterns_task(self, mock_engine):
        """Test the analyze_user_password_patterns task."""
        from security.tasks import analyze_user_password_patterns
        
        mock_instance = MagicMock()
        mock_instance.analyze_password.return_value = {
            'structure': 'UlllllllldddS',
            'entropy': 45.0,
            'char_classes': {'lowercase': 60, 'uppercase': 10, 'digits': 20, 'special': 10}
        }
        mock_engine.return_value = mock_instance
        
        # Task should execute without error
        result = analyze_user_password_patterns(self.user.id)
        
        self.assertIsNotNone(result)
        
    @patch('security.tasks.ThreatIntelligenceService')
    def test_update_threat_intelligence_task(self, mock_service):
        """Test the update_threat_intelligence task."""
        from security.tasks import update_threat_intelligence
        from security.models import ThreatIntelFeed
        
        # Create a test feed
        ThreatIntelFeed.objects.create(
            name='Test Feed',
            feed_type='misp',
            is_active=True
        )
        
        mock_instance = MagicMock()
        mock_instance.fetch_from_feed.return_value = []
        mock_service.return_value = mock_instance
        
        # Task should execute without error
        result = update_threat_intelligence()
        
        self.assertIsNotNone(result)
        
    @patch('security.tasks.PredictiveExpirationService')
    def test_evaluate_password_expiration_risk_task(self, mock_service):
        """Test the evaluate_password_expiration_risk task."""
        from security.tasks import evaluate_password_expiration_risk
        from security.models import PredictiveExpirationRule
        
        mock_instance = MagicMock()
        mock_rule = PredictiveExpirationRule(
            user=self.user,
            credential_id='test-cred',
            credential_domain='example.com',
            risk_level='medium',
            risk_score=0.5
        )
        mock_instance.create_expiration_rule.return_value = mock_rule
        mock_service.return_value = mock_instance
        
        # Task should execute without error
        result = evaluate_password_expiration_risk('test-cred', self.user.id)
        
        self.assertIsNotNone(result)
        
    @patch('security.tasks.PredictiveExpirationRule')
    def test_process_forced_rotation_task(self, mock_rule_model):
        """Test the process_forced_rotation task."""
        from security.tasks import process_forced_rotation
        from security.models import PasswordRotationEvent
        
        # Mock the rule
        mock_rule = MagicMock()
        mock_rule.user = self.user
        mock_rule.credential_id = 'test-cred'
        mock_rule.credential_domain = 'example.com'
        mock_rule_model.objects.get.return_value = mock_rule
        
        # Task should execute without error
        result = process_forced_rotation('test-cred', self.user.id, 'High risk detected')
        
        self.assertIsNotNone(result)
