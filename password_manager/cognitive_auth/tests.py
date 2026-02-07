"""
Cognitive Auth Tests
=====================

Unit tests for cognitive password testing services.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model


User = get_user_model()


class CognitiveAuthImportTests(TestCase):
    """Test that all cognitive auth modules can be imported."""
    
    def test_models_import(self):
        """Test models can be imported."""
        from cognitive_auth import models
        self.assertTrue(hasattr(models, 'CognitiveProfile'))
        self.assertTrue(hasattr(models, 'CognitiveChallenge'))
        self.assertTrue(hasattr(models, 'VerificationSession'))
    
    def test_services_import(self):
        """Test services can be imported."""
        from cognitive_auth.services import (
            ChallengeGenerator, ReactionTimeAnalyzer, ImplicitMemoryDetector,
            CognitiveProfileService, StroopEffectService, PrimingTestService
        )
        self.assertIsNotNone(ChallengeGenerator)
        self.assertIsNotNone(ReactionTimeAnalyzer)
        self.assertIsNotNone(ImplicitMemoryDetector)
    
    def test_views_import(self):
        """Test views can be imported."""
        from cognitive_auth import views
        self.assertTrue(hasattr(views, 'start_verification_session'))
        self.assertTrue(hasattr(views, 'submit_response'))


class ChallengeGeneratorTests(TestCase):
    """Tests for challenge generation service."""
    
    def setUp(self):
        from cognitive_auth.services import ChallengeGenerator
        self.generator = ChallengeGenerator()
        self.test_password = "TestP@ss123"
    
    def test_generate_scrambled_challenge(self):
        """Test scrambled password challenge generation."""
        challenge = self.generator.generate_scrambled_challenge(
            self.test_password, 
            difficulty='medium'
        )
        
        self.assertIn('scrambled_text', challenge)
        self.assertIn('options', challenge)
        self.assertIn('correct_answer', challenge)
    
    def test_generate_partial_challenge(self):
        """Test partial reveal challenge generation."""
        challenge = self.generator.generate_partial_challenge(
            self.test_password,
            difficulty='medium'
        )
        
        self.assertIn('masked_password', challenge)
        self.assertIn('hidden_positions', challenge)


class ReactionTimeAnalyzerTests(TestCase):
    """Tests for reaction time analysis service."""
    
    def setUp(self):
        from cognitive_auth.services import ReactionTimeAnalyzer
        self.analyzer = ReactionTimeAnalyzer()
    
    def test_analyze_response_times_basic(self):
        """Test basic response time analysis."""
        times = [450, 480, 520, 490, 510]
        
        analysis = self.analyzer.analyze_response_times(times)
        
        self.assertIn('mean', analysis)
        self.assertIn('median', analysis)
        self.assertIn('std_dev', analysis)


class CognitiveSessionModelTests(TestCase):
    """Tests for cognitive session model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='sessionuser',
            email='session@example.com',
            password='testpass123'
        )
    
    def test_session_creation(self):
        """Test cognitive session creation."""
        from cognitive_auth.models import CognitiveSession
        from django.utils import timezone
        from datetime import timedelta
        
        session = CognitiveSession.objects.create(
            user=self.user,
            total_challenges=5,
            verification_context='login',
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        
        self.assertEqual(session.status, 'pending')
        self.assertEqual(session.challenges_completed, 0)
        self.assertIsNotNone(session.id)
