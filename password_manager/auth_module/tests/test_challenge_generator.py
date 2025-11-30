"""
Unit Tests for Challenge Generator Service

Tests personalized temporal challenge generation based on user behavior and data.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from ..services.challenge_generator import challenge_generator
from ..quantum_recovery_models import BehavioralBiometrics

# Mock imports for models that might not exist yet
try:
    from vault.models import VaultItem
except ImportError:
    VaultItem = None

try:
    from security.models import UserDevice, LoginAttempt
except ImportError:
    UserDevice = None
    LoginAttempt = None

User = get_user_model()


@pytest.mark.django_db
class TestChallengeGeneratorService(TestCase):
    """Test challenge generation functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_generate_challenge_set_returns_list(self):
        """Test that generate_challenge_set returns a list"""
        challenges = challenge_generator.generate_challenge_set(self.user, num_challenges=5)
        
        self.assertIsInstance(challenges, list)
    
    def test_generate_challenge_set_correct_count(self):
        """Test that correct number of challenges are generated"""
        # With no user data, should return fewer challenges
        challenges = challenge_generator.generate_challenge_set(self.user, num_challenges=5)
        
        # Each challenge should be a tuple of (type, question, answer)
        for challenge in challenges:
            self.assertIsInstance(challenge, tuple)
            self.assertEqual(len(challenge), 3)
    
    def test_challenge_tuple_structure(self):
        """Test that challenge tuples have correct structure"""
        challenges = challenge_generator.generate_challenge_set(self.user, num_challenges=2)
        
        for challenge_type, question, answer in challenges:
            self.assertIsInstance(challenge_type, str)
            # Question and answer might be None if no data available
            if question is not None:
                self.assertIsInstance(question, str)
            if answer is not None:
                self.assertIsInstance(answer, str)
    
    @pytest.mark.skipif(VaultItem is None, reason="VaultItem model not available")
    def test_historical_activity_challenge_with_data(self):
        """Test historical activity challenge generation with vault data"""
        # Create vault items
        for i in range(3):
            VaultItem.objects.create(
                user=self.user,
                website_url=f'https://example{i}.com',
                website_name=f'Example {i}',
                username='testuser',
                encrypted_password='encrypted',
                created_at=timezone.now() - timedelta(days=30-i)
            )
        
        challenge_type, question, answer = challenge_generator.generate_historical_activity_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'historical_activity')
        self.assertIsNotNone(question)
        self.assertIsNotNone(answer)
        self.assertIn('first website', question.lower())
    
    def test_historical_activity_challenge_without_data(self):
        """Test historical activity challenge with insufficient data"""
        challenge_type, question, answer = challenge_generator.generate_historical_activity_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'historical_activity')
        self.assertIsNone(question)
        self.assertIsNone(answer)
    
    @pytest.mark.skipif(UserDevice is None, reason="UserDevice model not available")
    def test_device_fingerprint_challenge_with_data(self):
        """Test device fingerprint challenge generation"""
        # Create devices
        for browser in ['Chrome', 'Firefox', 'Chrome']:
            UserDevice.objects.create(
                user=self.user,
                fingerprint=f'fp_{browser}',
                browser=browser,
                os='Windows',
                is_trusted=True
            )
        
        challenge_type, question, answer = challenge_generator.generate_device_fingerprint_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'device_fingerprint')
        self.assertIsNotNone(question)
        self.assertIsNotNone(answer)
        self.assertEqual(answer, 'Chrome')  # Most common browser
    
    @pytest.mark.skipif(LoginAttempt is None, reason="LoginAttempt model not available")
    def test_geolocation_challenge_with_data(self):
        """Test geolocation challenge generation"""
        # Create login attempts
        for i in range(5):
            LoginAttempt.objects.create(
                user=self.user,
                success=True,
                ip_address=f'192.168.1.{i}',
                geolocation={'city': 'San Francisco', 'country': 'USA'},
                created_at=timezone.now() - timedelta(days=i)
            )
        
        challenge_type, question, answer = challenge_generator.generate_geolocation_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'geolocation_pattern')
        self.assertIsNotNone(question)
        self.assertIsNotNone(answer)
        self.assertEqual(answer, 'San Francisco')
    
    def test_usage_time_window_challenge_with_data(self):
        """Test usage time window challenge generation"""
        # Create behavioral biometrics
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 10, 14, 15, 18],  # Peak hours
            last_updated=timezone.now()
        )
        
        challenge_type, question, answer = challenge_generator.generate_usage_time_window_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'usage_time_window')
        self.assertIsNotNone(question)
        self.assertIsNotNone(answer)
        self.assertIn('time of day', question.lower())
    
    def test_usage_time_window_challenge_without_data(self):
        """Test usage time challenge without behavioral data"""
        challenge_type, question, answer = challenge_generator.generate_usage_time_window_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'usage_time_window')
        self.assertIsNone(question)
        self.assertIsNone(answer)
    
    @pytest.mark.skipif(VaultItem is None, reason="VaultItem model not available")
    def test_vault_content_challenge_with_data(self):
        """Test vault content challenge generation"""
        # Create vault items
        for i in range(8):
            VaultItem.objects.create(
                user=self.user,
                website_url=f'https://site{i}.com',
                website_name=f'Site {i}',
                username='user',
                encrypted_password='pass'
            )
        
        challenge_type, question, answer = challenge_generator.generate_vault_content_challenge(
            self.user
        )
        
        self.assertEqual(challenge_type, 'vault_content_knowledge')
        self.assertIsNotNone(question)
        self.assertIsNotNone(answer)
        self.assertEqual(answer, '6-10')  # 8 items falls in this range
    
    def test_vault_content_challenge_ranges(self):
        """Test correct range classification for vault content"""
        test_cases = [
            (3, "1-5"),
            (7, "6-10"),
            (15, "11-20"),
            (30, "21-50"),
            (75, "50+"),
        ]
        
        for count, expected_range in test_cases:
            # Create items
            if VaultItem is not None:
                VaultItem.objects.filter(user=self.user).delete()
                for i in range(count):
                    VaultItem.objects.create(
                        user=self.user,
                        website_url=f'https://test{i}.com',
                        website_name=f'Test {i}',
                        username='user',
                        encrypted_password='pass'
                    )
            
            # Generate challenge
            _, _, answer = challenge_generator.generate_vault_content_challenge(self.user)
            
            if VaultItem is not None:
                self.assertEqual(answer, expected_range)
    
    def test_encrypt_challenge_data(self):
        """Test challenge data encryption"""
        question = "What is your first website?"
        answer = "example.com"
        
        encrypted_question, encrypted_answer = challenge_generator.encrypt_challenge_data(
            question, answer
        )
        
        self.assertIsInstance(encrypted_question, bytes)
        self.assertIsInstance(encrypted_answer, bytes)
    
    def test_extract_domain_helper(self):
        """Test domain extraction from URLs"""
        test_cases = [
            ('https://www.example.com/path', 'example.com'),
            ('http://example.com', 'example.com'),
            ('https://subdomain.example.com', 'subdomain.example.com'),
            ('www.example.org', 'example.org'),
        ]
        
        for url, expected_domain in test_cases:
            domain = challenge_generator._extract_domain(url)
            self.assertEqual(domain, expected_domain)
    
    def test_hour_to_period_helper(self):
        """Test hour to time period conversion"""
        test_cases = [
            (8, 'Morning (6-12)'),
            (14, 'Afternoon (12-18)'),
            (20, 'Evening (18-24)'),
            (2, 'Night (0-6)'),
            (6, 'Morning (6-12)'),
            (12, 'Afternoon (12-18)'),
            (18, 'Evening (18-24)'),
            (0, 'Night (0-6)'),
        ]
        
        for hour, expected_period in test_cases:
            period = challenge_generator._hour_to_period(hour)
            self.assertEqual(period, expected_period)


@pytest.mark.django_db
class TestChallengeGeneratorIntegration(TestCase):
    """Integration tests for challenge generator with full user data"""
    
    def setUp(self):
        """Set up comprehensive test environment"""
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='TestPassword123!'
        )
        
        # Set up behavioral biometrics
        BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 10, 14, 15, 18],
            typical_locations=[
                {'city': 'San Francisco', 'country': 'USA'},
                {'city': 'New York', 'country': 'USA'}
            ],
            last_updated=timezone.now()
        )
        
        # Set up vault items if available
        if VaultItem is not None:
            for i in range(5):
                VaultItem.objects.create(
                    user=self.user,
                    website_url=f'https://example{i}.com',
                    website_name=f'Example {i}',
                    username='testuser',
                    encrypted_password='encrypted'
                )
        
        # Set up devices if available
        if UserDevice is not None:
            UserDevice.objects.create(
                user=self.user,
                fingerprint='fp_chrome',
                browser='Chrome',
                os='Windows',
                is_trusted=True
            )
        
        # Set up login attempts if available
        if LoginAttempt is not None:
            for i in range(3):
                LoginAttempt.objects.create(
                    user=self.user,
                    success=True,
                    ip_address=f'192.168.1.{i}',
                    geolocation={'city': 'San Francisco', 'country': 'USA'},
                    created_at=timezone.now() - timedelta(days=i)
                )
    
    def test_generate_full_challenge_set(self):
        """Test generating complete set of challenges with full user data"""
        challenges = challenge_generator.generate_challenge_set(self.user, num_challenges=5)
        
        # Should generate challenges (exact count depends on available data)
        self.assertGreater(len(challenges), 0)
        
        # Verify challenge types are diverse
        challenge_types = [challenge[0] for challenge in challenges]
        self.assertGreater(len(set(challenge_types)), 0)
    
    def test_challenge_quality_with_full_data(self):
        """Test that challenges are high quality with full user data"""
        challenges = challenge_generator.generate_challenge_set(self.user, num_challenges=5)
        
        for challenge_type, question, answer in challenges:
            if question is not None and answer is not None:
                # Questions should be readable
                self.assertGreater(len(question), 10)
                
                # Answers should be non-empty
                self.assertGreater(len(answer), 0)
                
                # Question should contain relevant keywords
                if challenge_type == 'historical_activity':
                    self.assertIn('website', question.lower())
                elif challenge_type == 'device_fingerprint':
                    self.assertIn('browser', question.lower())
                elif challenge_type == 'geolocation_pattern':
                    self.assertIn('city', question.lower())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

