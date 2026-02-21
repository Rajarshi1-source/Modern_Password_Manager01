"""
Seed demo data for Password Archaeology & Time Travel.

Usage:
    python manage.py seed_archaeology_data [--user <username>]

Creates realistic demo password history, security events, strength
snapshots, and achievements for visual testing.
"""

import random
import hashlib
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from password_archaeology.models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    AchievementRecord,
    PasswordTimeline,
)
from password_archaeology.services.archaeology_service import PasswordArchaeologyService

User = get_user_model()

# Realistic domains for demo
DOMAINS = [
    'google.com', 'github.com', 'amazon.com', 'netflix.com',
    'facebook.com', 'twitter.com', 'linkedin.com', 'dropbox.com',
    'slack.com', 'spotify.com', 'paypal.com', 'reddit.com',
    'stackoverflow.com', 'microsoft.com', 'apple.com',
]

TRIGGERS = [
    'user_initiated', 'breach_response', 'policy_expiration',
    'predictive_alert', 'scheduled_rotation', 'proactive',
]

EVENT_DATA = [
    ('breach_detected', 'critical', 'Data breach detected at {domain}',
     'Your credentials for {domain} were found in a data breach. Immediate action required.'),
    ('suspicious_login', 'high', 'Suspicious login attempt on {domain}',
     'An unusual login attempt was detected from an unrecognized device in {location}.'),
    ('account_locked', 'medium', '{domain} account temporarily locked',
     'Multiple failed login attempts triggered an account lock.'),
    ('mfa_enabled', 'info', 'MFA enabled for {domain}',
     'Two-factor authentication was successfully enabled.'),
    ('device_added', 'low', 'New device registered for {domain}',
     'A new device was added to your trusted devices list.'),
    ('impossible_travel', 'high', 'Impossible travel detected',
     'Login from {location} detected 2 hours after login from another continent.'),
    ('password_reuse', 'medium', 'Password reuse detected across services',
     'The same password is being used on {domain} and 2 other services.'),
    ('weak_password', 'medium', 'Weak password detected on {domain}',
     'Your password for {domain} scores below the recommended strength threshold.'),
]

LOCATIONS = [
    'New York, US', 'London, UK', 'Tokyo, Japan', 'Mumbai, India',
    'Berlin, Germany', 'São Paulo, Brazil', 'Sydney, Australia',
]


class Command(BaseCommand):
    help = 'Seed demo data for Password Archaeology & Time Travel feature'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to seed data for (default: first superuser or first user)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing archaeology data before seeding',
        )

    def handle(self, *args, **options):
        # Find target user
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(f"User '{username}' not found.")
                return
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()
            if not user:
                self.stderr.write("No users found. Create a user first.")
                return

        self.stdout.write(f"Seeding archaeology data for: {user.username}")

        if options.get('clear'):
            self.stdout.write("Clearing existing data...")
            PasswordHistoryEntry.objects.filter(user=user).delete()
            SecurityEvent.objects.filter(user=user).delete()
            StrengthSnapshot.objects.filter(user=user).delete()
            AchievementRecord.objects.filter(user=user).delete()
            WhatIfScenario = __import__(
                'password_archaeology.models', fromlist=['WhatIfScenario']
            ).WhatIfScenario
            WhatIfScenario.objects.filter(user=user).delete()
            PasswordTimeline.objects.filter(user=user).delete()

        now = timezone.now()
        created_count = {'history': 0, 'events': 0, 'snapshots': 0, 'achievements': 0}

        # ----- Password History Entries -----
        self.stdout.write("Creating password history entries...")
        for domain in DOMAINS:
            # Generate 3-8 changes per domain over the past year
            num_changes = random.randint(3, 8)
            base_strength = random.randint(20, 50)

            for i in range(num_changes):
                days_ago = random.randint(
                    int(365 * (num_changes - i) / num_changes),
                    int(365 * (num_changes - i + 0.5) / num_changes),
                )
                change_time = now - timedelta(days=days_ago, hours=random.randint(0, 23))

                # Strength generally improves over time
                strength_before = min(100, base_strength + i * random.randint(5, 12))
                strength_after = min(100, strength_before + random.randint(5, 20))
                base_strength = strength_after - random.randint(0, 5)

                trigger = random.choice(TRIGGERS)
                fake_hash = hashlib.sha256(
                    f"{domain}:{i}:{random.random()}".encode()
                ).hexdigest()

                PasswordHistoryEntry.objects.create(
                    user=user,
                    credential_domain=domain,
                    credential_label=f"{user.username}@{domain}",
                    old_password_hash=fake_hash[:32],
                    new_password_hash=fake_hash[32:],
                    strength_before=strength_before,
                    strength_after=strength_after,
                    entropy_before=strength_before * 0.8 + random.uniform(0, 10),
                    entropy_after=strength_after * 0.8 + random.uniform(0, 10),
                    trigger=trigger,
                    change_notes=f"{'Routine rotation' if trigger == 'scheduled_rotation' else 'Password updated'}",
                    commitment_hash=hashlib.sha256(fake_hash.encode()).hexdigest(),
                    changed_at=change_time,
                )
                created_count['history'] += 1

                # Corresponding strength snapshot
                StrengthSnapshot.objects.create(
                    user=user,
                    credential_domain=domain,
                    strength_score=strength_after,
                    entropy_bits=strength_after * 0.8 + random.uniform(0, 10),
                    character_class_coverage=min(1.0, 0.4 + i * 0.1 + random.uniform(0, 0.15)),
                    length=random.randint(8, 24),
                    breach_exposure_count=max(0, random.randint(-2, 2)),
                    is_reused=random.random() < 0.15,
                    snapshot_at=change_time,
                )
                created_count['snapshots'] += 1

        # ----- Security Events -----
        self.stdout.write("Creating security events...")
        for _ in range(25):
            evt_data = random.choice(EVENT_DATA)
            domain = random.choice(DOMAINS)
            location = random.choice(LOCATIONS)
            days_ago = random.randint(1, 365)
            event_time = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            resolved = random.random() < 0.7
            resolved_at = (
                event_time + timedelta(hours=random.randint(1, 72))
                if resolved else None
            )

            SecurityEvent.objects.create(
                user=user,
                event_type=evt_data[0],
                severity=evt_data[1],
                title=evt_data[2].format(domain=domain, location=location),
                description=evt_data[3].format(domain=domain, location=location),
                metadata={
                    'domain': domain,
                    'location': location,
                    'source': 'demo_seed',
                },
                risk_score_impact=random.randint(-20, 5),
                resolved=resolved,
                resolved_at=resolved_at,
                occurred_at=event_time,
            )
            created_count['events'] += 1

        # ----- Additional Strength Snapshots (weekly overall) -----
        self.stdout.write("Creating weekly strength snapshots...")
        for week in range(52):
            snapshot_time = now - timedelta(weeks=week)
            overall_score = min(100, 45 + week * 1.0 + random.randint(-5, 5))

            for domain in random.sample(DOMAINS, min(8, len(DOMAINS))):
                StrengthSnapshot.objects.create(
                    user=user,
                    credential_domain=domain,
                    strength_score=int(overall_score + random.randint(-15, 15)),
                    entropy_bits=overall_score * 0.7 + random.uniform(0, 20),
                    character_class_coverage=min(1.0, 0.5 + random.uniform(0, 0.3)),
                    length=random.randint(10, 20),
                    breach_exposure_count=max(0, random.randint(-3, 1)),
                    is_reused=random.random() < 0.1,
                    snapshot_at=snapshot_time,
                )
                created_count['snapshots'] += 1

        # ----- Achievements -----
        self.stdout.write("Creating achievements...")
        demo_achievements = [
            ('first_password_change', 'First Password Change',
             'You recorded your first password change!',
             'key-round', 'bronze', 10, 300),
            ('ten_passwords_changed', '10 Passwords Changed',
             'You have changed 10 passwords — keep it up!',
             'rotate-cw', 'silver', 25, 200),
            ('zero_breaches_30', 'Zero Breaches (30 Days)',
             '30 consecutive days without a breach!',
             'shield-off', 'bronze', 15, 150),
            ('security_score_80', 'Security Score 80+',
             'Your overall security score reached 80!',
             'shield-check', 'silver', 30, 60),
            ('proactive_changer', 'Proactive Changer',
             'Changed a password before it was compromised!',
             'zap', 'gold', 50, 90),
            ('what_if_explorer', 'What-If Explorer',
             'Used the What-If simulator for the first time!',
             'git-branch', 'bronze', 10, 30),
        ]

        for ach in demo_achievements:
            AchievementRecord.objects.get_or_create(
                user=user,
                achievement_type=ach[0],
                defaults={
                    'title': ach[1],
                    'description': ach[2],
                    'icon_name': ach[3],
                    'badge_tier': ach[4],
                    'score_points': ach[5],
                    'earned_at': now - timedelta(days=ach[6]),
                    'acknowledged': random.random() < 0.5,
                },
            )
            created_count['achievements'] += 1

        # ----- Refresh Timeline Cache -----
        self.stdout.write("Refreshing timeline cache...")
        PasswordArchaeologyService._refresh_timeline_cache(user)

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Seeded archaeology data for {user.username}:\n"
            f"   • {created_count['history']} password history entries\n"
            f"   • {created_count['events']} security events\n"
            f"   • {created_count['snapshots']} strength snapshots\n"
            f"   • {created_count['achievements']} achievements\n"
        ))
