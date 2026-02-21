"""
Tests for Password Archaeology Service
=========================================
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from password_archaeology.models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    PasswordTimeline,
    AchievementRecord,
    WhatIfScenario,
)
from password_archaeology.services.archaeology_service import PasswordArchaeologyService

User = get_user_model()


class PasswordArchaeologyServiceTests(TestCase):
    """Unit tests for PasswordArchaeologyService."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='TestPassword123!',
            email='test@example.com',
        )

    # ------------------------------------------------------------------ #
    #  record_password_change
    # ------------------------------------------------------------------ #

    def test_record_password_change_creates_entry(self):
        entry = PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='google.com',
            credential_label='test@google.com',
            strength_before=30,
            strength_after=85,
            trigger='user_initiated',
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.credential_domain, 'google.com')
        self.assertEqual(entry.strength_before, 30)
        self.assertEqual(entry.strength_after, 85)
        self.assertEqual(entry.trigger, 'user_initiated')

    def test_record_password_change_creates_snapshot(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='github.com',
            strength_before=40,
            strength_after=90,
        )
        snapshot = StrengthSnapshot.objects.filter(
            user=self.user,
            credential_domain='github.com',
        ).first()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.strength_score, 90)

    def test_record_password_change_refreshes_timeline(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='amazon.com',
            strength_after=75,
        )
        timeline = PasswordTimeline.objects.filter(user=self.user).first()
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline.total_password_changes, 1)

    def test_record_password_change_generates_commitment_hash(self):
        entry = PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='netflix.com',
            new_password_hash='abc123',
        )
        self.assertTrue(len(entry.commitment_hash) > 0)

    # ------------------------------------------------------------------ #
    #  record_security_event
    # ------------------------------------------------------------------ #

    def test_record_security_event(self):
        event = PasswordArchaeologyService.record_security_event(
            user=self.user,
            event_type='breach_detected',
            severity='critical',
            title='Test breach',
            description='A test breach was detected.',
        )
        self.assertEqual(event.event_type, 'breach_detected')
        self.assertEqual(event.severity, 'critical')

    # ------------------------------------------------------------------ #
    #  get_timeline_data
    # ------------------------------------------------------------------ #

    def test_get_timeline_data_returns_merged_sorted(self):
        # Create some history entries
        for i in range(3):
            PasswordArchaeologyService.record_password_change(
                user=self.user,
                credential_domain=f'site{i}.com',
                strength_after=50 + i * 10,
            )

        # Create some security events
        for i in range(2):
            PasswordArchaeologyService.record_security_event(
                user=self.user,
                event_type='suspicious_login',
                severity='medium',
            )

        timeline = PasswordArchaeologyService.get_timeline_data(self.user)
        self.assertEqual(len(timeline), 5)

        # Check sorted by timestamp (descending)
        timestamps = [e['timestamp'] for e in timeline]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_get_timeline_data_respects_date_range(self):
        now = timezone.now()
        old_entry = PasswordHistoryEntry.objects.create(
            user=self.user,
            credential_domain='old.com',
            changed_at=now - timedelta(days=400),
        )
        new_entry = PasswordHistoryEntry.objects.create(
            user=self.user,
            credential_domain='new.com',
            changed_at=now - timedelta(days=10),
        )

        timeline = PasswordArchaeologyService.get_timeline_data(
            self.user,
            date_from=now - timedelta(days=30),
            date_to=now,
        )

        domains = [e.get('credential_domain', '') for e in timeline]
        self.assertIn('new.com', domains)
        self.assertNotIn('old.com', domains)

    # ------------------------------------------------------------------ #
    #  get_strength_evolution
    # ------------------------------------------------------------------ #

    def test_get_strength_evolution(self):
        now = timezone.now()
        for i in range(5):
            StrengthSnapshot.objects.create(
                user=self.user,
                credential_domain='google.com',
                strength_score=40 + i * 10,
                snapshot_at=now - timedelta(days=30 * (5 - i)),
            )

        data = PasswordArchaeologyService.get_strength_evolution(
            self.user,
            credential_domain='google.com',
        )

        self.assertEqual(len(data), 5)
        # Should be ordered ascending by timestamp
        scores = [d['strength_score'] for d in data]
        self.assertEqual(scores, [40, 50, 60, 70, 80])

    # ------------------------------------------------------------------ #
    #  run_what_if_scenario
    # ------------------------------------------------------------------ #

    def test_run_what_if_earlier_change(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='example.com',
            strength_after=70,
        )

        scenario = PasswordArchaeologyService.run_what_if_scenario(
            user=self.user,
            scenario_type='earlier_change',
            credential_domain='example.com',
            params={'days_earlier': 30},
        )

        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.scenario_type, 'earlier_change')
        self.assertIn('example.com', scenario.insight_text)

    def test_run_what_if_no_reuse(self):
        scenario = PasswordArchaeologyService.run_what_if_scenario(
            user=self.user,
            scenario_type='no_reuse',
        )
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.scenario_type, 'no_reuse')

    # ------------------------------------------------------------------ #
    #  Time Machine
    # ------------------------------------------------------------------ #

    def test_time_machine_snapshot(self):
        now = timezone.now()
        # Create historical data
        PasswordHistoryEntry.objects.create(
            user=self.user,
            credential_domain='timetest.com',
            strength_after=60,
            changed_at=now - timedelta(days=90),
        )
        StrengthSnapshot.objects.create(
            user=self.user,
            credential_domain='timetest.com',
            strength_score=60,
            snapshot_at=now - timedelta(days=90),
        )

        snapshot = PasswordArchaeologyService.get_time_machine_snapshot(
            self.user,
            point_in_time=now - timedelta(days=45),
        )

        self.assertIn('credentials', snapshot)
        self.assertEqual(snapshot['total_credentials'], 1)
        self.assertEqual(snapshot['credentials'][0]['credential_domain'], 'timetest.com')

    # ------------------------------------------------------------------ #
    #  Achievements
    # ------------------------------------------------------------------ #

    def test_check_achievements_first_change(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='first.com',
        )

        achievements = PasswordArchaeologyService.check_achievements(self.user)
        types = [a.achievement_type for a in achievements]
        self.assertIn('first_password_change', types)

    def test_check_achievements_no_duplicates(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='dup.com',
        )
        first_run = PasswordArchaeologyService.check_achievements(self.user)
        second_run = PasswordArchaeologyService.check_achievements(self.user)

        # Second run should not award 'first_password_change' again
        first_types = [a.achievement_type for a in first_run]
        second_types = [a.achievement_type for a in second_run]
        if 'first_password_change' in first_types:
            self.assertNotIn('first_password_change', second_types)

    # ------------------------------------------------------------------ #
    #  Dashboard
    # ------------------------------------------------------------------ #

    def test_dashboard_summary(self):
        PasswordArchaeologyService.record_password_change(
            user=self.user,
            credential_domain='dash.com',
            strength_after=80,
        )
        summary = PasswordArchaeologyService.get_dashboard_summary(self.user)
        self.assertIn('overall_score', summary)
        self.assertIn('total_changes', summary)
        self.assertEqual(summary['total_changes'], 1)
