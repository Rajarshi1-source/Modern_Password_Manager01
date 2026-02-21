"""
Tests for Password Archaeology API
=====================================
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from password_archaeology.models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    AchievementRecord,
)
from password_archaeology.services.archaeology_service import PasswordArchaeologyService

User = get_user_model()


class PasswordArchaeologyAPITests(TestCase):
    """API integration tests for Password Archaeology endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            password='TestPassword123!',
            email='api@example.com',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Seed some data
        for i, domain in enumerate(['google.com', 'github.com', 'amazon.com']):
            PasswordArchaeologyService.record_password_change(
                user=self.user,
                credential_domain=domain,
                strength_before=30 + i * 10,
                strength_after=60 + i * 10,
                trigger='user_initiated',
            )
            PasswordArchaeologyService.record_security_event(
                user=self.user,
                event_type='suspicious_login',
                severity='medium',
                title=f'Suspicious login on {domain}',
            )

    def test_dashboard_endpoint(self):
        response = self.client.get('/api/archaeology/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('overall_score', data)
        self.assertIn('total_changes', data)
        self.assertEqual(data['total_changes'], 3)

    def test_timeline_endpoint(self):
        response = self.client.get('/api/archaeology/timeline/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('timeline', data)
        # 3 password changes + 3 security events
        self.assertEqual(data['count'], 6)

    def test_timeline_with_date_filter(self):
        now = timezone.now()
        date_from = (now - timedelta(days=7)).isoformat()
        response = self.client.get(f'/api/archaeology/timeline/?date_from={date_from}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_strength_evolution_overall(self):
        response = self.client.get('/api/archaeology/strength-evolution/overall/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('data_points', data)

    def test_security_events_endpoint(self):
        response = self.client.get('/api/archaeology/security-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 3)

    def test_security_events_filter_by_type(self):
        response = self.client.get(
            '/api/archaeology/security-events/?event_type=suspicious_login'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 3)

    def test_what_if_run(self):
        response = self.client.post('/api/archaeology/what-if/', {
            'scenario_type': 'earlier_change',
            'credential_domain': 'google.com',
            'params': {'days_earlier': 30},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn('insight_text', data)

    def test_what_if_history(self):
        # Run a scenario first
        self.client.post('/api/archaeology/what-if/', {
            'scenario_type': 'no_reuse',
        }, format='json')

        response = self.client.get('/api/archaeology/what-if/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreaterEqual(data['count'], 1)

    def test_time_machine(self):
        timestamp = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.client.get(f'/api/archaeology/time-machine/{timestamp}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('credentials', data)

    def test_achievements_endpoint(self):
        response = self.client.get('/api/archaeology/achievements/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('achievements', data)

    def test_security_score_endpoint(self):
        response = self.client.get('/api/archaeology/security-score/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('scores', data)

    def test_unauthenticated_access_denied(self):
        client = APIClient()
        response = client.get('/api/archaeology/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
