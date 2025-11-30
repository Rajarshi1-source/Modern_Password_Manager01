"""
Temporal Challenge Generator Service

Generates personalized identity verification challenges based on user's
historical activity, behavioral patterns, and vault usage.
"""

from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import random
import hashlib
from typing import Tuple, Optional

from vault.models import VaultItem
from security.models import UserDevice, LoginAttempt
from auth_module.quantum_recovery_models import BehavioralBiometrics


class ChallengeGeneratorService:
    """Generate personalized identity verification challenges"""
    
    def generate_challenge_set(self, user, num_challenges=5):
        """
        Generate a set of diverse challenges for recovery
        
        Returns:
            List of (challenge_type, question, expected_answer) tuples
        """
        challenge_generators = [
            self.generate_historical_activity_challenge,
            self.generate_device_fingerprint_challenge,
            self.generate_geolocation_challenge,
            self.generate_usage_time_window_challenge,
            self.generate_vault_content_challenge,
        ]
        
        challenges = []
        for generator in challenge_generators[:num_challenges]:
            challenge_type, question, answer = generator(user)
            if question and answer:
                challenges.append((challenge_type, question, answer))
        
        return challenges
    
    def generate_historical_activity_challenge(self, user) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Ask about first website saved to vault
        """
        vault_items = VaultItem.objects.filter(user=user).order_by('created_at')
        
        if vault_items.count() < 3:
            return 'historical_activity', None, None
        
        first_item = vault_items.first()
        
        # Extract domain from URL
        domain = self._extract_domain(first_item.website_url)
        
        question = f"What was the first website you saved to your vault? (e.g., example.com)"
        answer = domain
        
        return 'historical_activity', question, answer
    
    def generate_device_fingerprint_challenge(self, user) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Ask about most commonly used browser
        """
        devices = UserDevice.objects.filter(user=user)
        
        if not devices.exists():
            return 'device_fingerprint', None, None
        
        # Find most common browser
        browser_stats = devices.values('browser').annotate(
            count=Count('browser')
        ).order_by('-count')
        
        if not browser_stats:
            return 'device_fingerprint', None, None
        
        most_common_browser = browser_stats[0]['browser']
        
        # Create multiple choice
        options = ['Chrome', 'Firefox', 'Safari', 'Edge']
        if most_common_browser not in options:
            options[0] = most_common_browser
        
        question = f"Which browser do you typically use?\nOptions: {', '.join(options)}"
        answer = most_common_browser
        
        return 'device_fingerprint', question, answer
    
    def generate_geolocation_challenge(self, user) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Ask about typical login location
        """
        login_attempts = LoginAttempt.objects.filter(
            user=user,
            success=True,
            created_at__gte=timezone.now() - timedelta(days=90)
        )
        
        if not login_attempts.exists():
            return 'geolocation_pattern', None, None
        
        # Analyze most common city from IP geolocation
        location_counts = {}
        for attempt in login_attempts:
            if attempt.geolocation and 'city' in attempt.geolocation:
                city = attempt.geolocation['city']
                location_counts[city] = location_counts.get(city, 0) + 1
        
        if not location_counts:
            return 'geolocation_pattern', None, None
        
        most_common_city = max(location_counts, key=location_counts.get)
        
        question = f"Which city do you usually log in from?"
        answer = most_common_city
        
        return 'geolocation_pattern', question, answer
    
    def generate_usage_time_window_challenge(self, user) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Ask about typical usage time
        """
        behavioral = BehavioralBiometrics.objects.filter(user=user).first()
        
        if not behavioral or not behavioral.typical_login_times:
            return 'usage_time_window', None, None
        
        # Analyze typical login hours
        hour_counts = {}
        for hour in behavioral.typical_login_times:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        most_common_hour = max(hour_counts, key=hour_counts.get)
        
        # Convert to time period
        time_period = self._hour_to_period(most_common_hour)
        
        options = ['Morning (6-12)', 'Afternoon (12-18)', 'Evening (18-24)', 'Night (0-6)']
        
        question = f"What time of day do you usually access your vault?\nOptions: {', '.join(options)}"
        answer = time_period
        
        return 'usage_time_window', question, answer
    
    def generate_vault_content_challenge(self, user) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Ask about vault content statistics
        """
        vault_count = VaultItem.objects.filter(user=user).count()
        
        if vault_count == 0:
            return 'vault_content_knowledge', None, None
        
        # Create range buckets
        if vault_count < 5:
            answer_range = "1-5"
        elif vault_count < 10:
            answer_range = "6-10"
        elif vault_count < 20:
            answer_range = "11-20"
        elif vault_count < 50:
            answer_range = "21-50"
        else:
            answer_range = "50+"
        
        options = ["1-5", "6-10", "11-20", "21-50", "50+"]
        
        question = f"Approximately how many passwords do you have saved?\nOptions: {', '.join(options)}"
        answer = answer_range
        
        return 'vault_content_knowledge', question, answer
    
    def encrypt_challenge_data(self, question: str, answer: str):
        """
        Encrypt challenge question and expected answer
        """
        # Simple encryption for now (in production, use proper encryption)
        encrypted_question = question.encode('utf-8')
        encrypted_answer = answer.encode('utf-8')
        
        return encrypted_question, encrypted_answer
    
    # Helper methods
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    def _hour_to_period(self, hour: int) -> str:
        """Convert hour to time period"""
        if 6 <= hour < 12:
            return 'Morning (6-12)'
        elif 12 <= hour < 18:
            return 'Afternoon (12-18)'
        elif 18 <= hour < 24:
            return 'Evening (18-24)'
        else:
            return 'Night (0-6)'


# Global instance
challenge_generator = ChallengeGeneratorService()

