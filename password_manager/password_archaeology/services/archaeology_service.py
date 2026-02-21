"""
Password Archaeology Service
==============================

Core business logic for password history tracking, timeline aggregation,
strength evolution, what-if simulations, and gamification achievements.
"""

import hashlib
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Min, Max, Q, F
from django.contrib.auth import get_user_model

from password_archaeology.models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    PasswordTimeline,
    AchievementRecord,
    WhatIfScenario,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class PasswordArchaeologyService:
    """
    Provides all business logic for Password Archaeology & Time Travel.
    """

    # ------------------------------------------------------------------ #
    #  Recording Events
    # ------------------------------------------------------------------ #

    @staticmethod
    def record_password_change(
        user,
        vault_item=None,
        credential_domain='',
        credential_label='',
        old_password_hash='',
        new_password_hash='',
        strength_before=0,
        strength_after=0,
        entropy_before=0.0,
        entropy_after=0.0,
        trigger='user_initiated',
        change_notes='',
        ip_address=None,
        user_agent='',
    ):
        """
        Record a password change event and optionally submit a
        blockchain commitment for tamper-proof timestamping.
        """
        entry = PasswordHistoryEntry.objects.create(
            user=user,
            vault_item=vault_item,
            credential_domain=credential_domain,
            credential_label=credential_label,
            old_password_hash=old_password_hash,
            new_password_hash=new_password_hash,
            strength_before=strength_before,
            strength_after=strength_after,
            entropy_before=entropy_before,
            entropy_after=entropy_after,
            trigger=trigger,
            change_notes=change_notes,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Attempt blockchain commitment
        try:
            commitment_hash = hashlib.sha256(
                f"{entry.id}:{user.id}:{entry.changed_at.isoformat()}:{new_password_hash}".encode()
            ).hexdigest()
            entry.commitment_hash = commitment_hash
            entry.save(update_fields=['commitment_hash'])

            # Try to create a PendingCommitment via blockchain app
            try:
                from blockchain.models import PendingCommitment
                commitment = PendingCommitment.objects.create(
                    user=user,
                    commitment_hash=commitment_hash,
                )
                entry.blockchain_commitment = commitment
                entry.save(update_fields=['blockchain_commitment'])
            except Exception as bc_err:
                logger.warning(f"Could not create blockchain commitment: {bc_err}")
        except Exception as e:
            logger.warning(f"Could not compute commitment hash: {e}")

        # Take a strength snapshot
        if vault_item or credential_domain:
            StrengthSnapshot.objects.create(
                user=user,
                vault_item=vault_item,
                credential_domain=credential_domain,
                strength_score=strength_after,
                entropy_bits=entropy_after,
                snapshot_at=entry.changed_at,
            )

        # Refresh the timeline cache
        PasswordArchaeologyService._refresh_timeline_cache(user)

        # Check for new achievements
        PasswordArchaeologyService.check_achievements(user)

        logger.info(f"Recorded password change for {user.username}: {credential_domain}")
        return entry

    @staticmethod
    def record_security_event(
        user,
        event_type,
        severity='medium',
        title='',
        description='',
        vault_item=None,
        metadata=None,
        risk_score_impact=0,
    ):
        """Record a security-relevant event on the user's timeline."""
        event = SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            severity=severity,
            title=title or dict(SecurityEvent.EVENT_TYPES).get(event_type, event_type),
            description=description,
            vault_item=vault_item,
            metadata=metadata or {},
            risk_score_impact=risk_score_impact,
        )

        PasswordArchaeologyService._refresh_timeline_cache(user)
        logger.info(f"Recorded security event for {user.username}: {event_type}")
        return event

    @staticmethod
    def take_strength_snapshot(user, vault_item=None, credential_domain='', **kwargs):
        """Take a point-in-time strength snapshot for a credential."""
        snapshot = StrengthSnapshot.objects.create(
            user=user,
            vault_item=vault_item,
            credential_domain=credential_domain,
            strength_score=kwargs.get('strength_score', 0),
            entropy_bits=kwargs.get('entropy_bits', 0.0),
            character_class_coverage=kwargs.get('character_class_coverage', 0.0),
            length=kwargs.get('length', 0),
            breach_exposure_count=kwargs.get('breach_exposure_count', 0),
            is_reused=kwargs.get('is_reused', False),
        )
        return snapshot

    # ------------------------------------------------------------------ #
    #  Timeline Data Retrieval
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_timeline_data(user, date_from=None, date_to=None, vault_item_id=None, limit=100):
        """
        Get a merged, chronological timeline of password changes
        and security events.
        """
        now = timezone.now()
        if date_from is None:
            date_from = now - timedelta(days=365)
        if date_to is None:
            date_to = now

        # Password history entries
        history_qs = PasswordHistoryEntry.objects.filter(
            user=user,
            changed_at__gte=date_from,
            changed_at__lte=date_to,
        )
        if vault_item_id:
            history_qs = history_qs.filter(vault_item_id=vault_item_id)

        history_events = [
            {
                'id': str(entry.id),
                'type': 'password_change',
                'timestamp': entry.changed_at.isoformat(),
                'credential_domain': entry.credential_domain,
                'credential_label': entry.credential_label,
                'trigger': entry.trigger,
                'trigger_display': entry.get_trigger_display(),
                'strength_before': entry.strength_before,
                'strength_after': entry.strength_after,
                'entropy_before': entry.entropy_before,
                'entropy_after': entry.entropy_after,
                'change_notes': entry.change_notes,
                'has_blockchain_proof': bool(entry.blockchain_commitment_id),
                'commitment_hash': entry.commitment_hash,
            }
            for entry in history_qs[:limit]
        ]

        # Security events
        security_qs = SecurityEvent.objects.filter(
            user=user,
            occurred_at__gte=date_from,
            occurred_at__lte=date_to,
        )
        if vault_item_id:
            security_qs = security_qs.filter(vault_item_id=vault_item_id)

        security_events = [
            {
                'id': str(event.id),
                'type': 'security_event',
                'event_type': event.event_type,
                'event_type_display': event.get_event_type_display(),
                'timestamp': event.occurred_at.isoformat(),
                'severity': event.severity,
                'title': event.title,
                'description': event.description,
                'risk_score_impact': event.risk_score_impact,
                'resolved': event.resolved,
                'resolved_at': event.resolved_at.isoformat() if event.resolved_at else None,
                'metadata': event.metadata,
            }
            for event in security_qs[:limit]
        ]

        # Merge and sort by timestamp
        timeline = history_events + security_events
        timeline.sort(key=lambda e: e['timestamp'], reverse=True)

        return timeline[:limit]

    # ------------------------------------------------------------------ #
    #  Strength Evolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_strength_evolution(user, vault_item_id=None, credential_domain=None,
                                date_from=None, date_to=None):
        """Return strength snapshots for charting."""
        now = timezone.now()
        if date_from is None:
            date_from = now - timedelta(days=365)
        if date_to is None:
            date_to = now

        qs = StrengthSnapshot.objects.filter(
            user=user,
            snapshot_at__gte=date_from,
            snapshot_at__lte=date_to,
        )

        if vault_item_id:
            qs = qs.filter(vault_item_id=vault_item_id)
        elif credential_domain:
            qs = qs.filter(credential_domain=credential_domain)

        return [
            {
                'timestamp': snap.snapshot_at.isoformat(),
                'strength_score': snap.strength_score,
                'entropy_bits': snap.entropy_bits,
                'character_class_coverage': snap.character_class_coverage,
                'length': snap.length,
                'breach_exposure_count': snap.breach_exposure_count,
                'is_reused': snap.is_reused,
                'credential_domain': snap.credential_domain,
            }
            for snap in qs.order_by('snapshot_at')
        ]

    # ------------------------------------------------------------------ #
    #  What-If Scenarios
    # ------------------------------------------------------------------ #

    @staticmethod
    def run_what_if_scenario(user, scenario_type, vault_item=None,
                              credential_domain='', params=None):
        """
        Simulate an alternative history and compute risk reduction.
        """
        params = params or {}
        actual_risk = 50  # baseline
        simulated_risk = 50
        exposure_days_saved = 0
        insight = ''

        if scenario_type == 'earlier_change':
            days_earlier = params.get('days_earlier', 30)
            # Look at actual password history
            last_change = PasswordHistoryEntry.objects.filter(
                user=user,
                credential_domain=credential_domain,
            ).order_by('-changed_at').first()

            if last_change:
                actual_risk = max(0, 100 - last_change.strength_after)
                exposure_days_saved = days_earlier
                simulated_risk = max(0, actual_risk - (days_earlier * 0.5))
                insight = (
                    f"If you had changed your {credential_domain} password "
                    f"{days_earlier} days earlier, you could have reduced your "
                    f"risk score from {actual_risk} to {int(simulated_risk)} and "
                    f"saved {exposure_days_saved} days of exposure."
                )
            else:
                insight = f"No password change history found for {credential_domain}."

        elif scenario_type == 'stronger_password':
            target_strength = params.get('target_strength', 90)
            last_snapshot = StrengthSnapshot.objects.filter(
                user=user,
                credential_domain=credential_domain,
            ).order_by('-snapshot_at').first()

            if last_snapshot:
                actual_risk = max(0, 100 - last_snapshot.strength_score)
                simulated_risk = max(0, 100 - target_strength)
                insight = (
                    f"Using a password with strength {target_strength}/100 instead "
                    f"of {last_snapshot.strength_score}/100 would reduce your risk "
                    f"from {actual_risk} to {simulated_risk}."
                )
            else:
                insight = f"No strength data found for {credential_domain}."

        elif scenario_type == 'no_reuse':
            reused_count = StrengthSnapshot.objects.filter(
                user=user,
                is_reused=True,
            ).values('credential_domain').distinct().count()
            actual_risk = min(100, reused_count * 15)
            simulated_risk = 0
            insight = (
                f"You have {reused_count} reused passwords. Eliminating reuse "
                f"would reduce your reuse-related risk from {actual_risk} to 0."
            )

        elif scenario_type == 'regular_rotation':
            rotation_days = params.get('rotation_days', 90)
            stale = PasswordHistoryEntry.objects.filter(
                user=user,
            ).values('credential_domain').annotate(
                last_change=Max('changed_at'),
            ).filter(
                last_change__lt=timezone.now() - timedelta(days=rotation_days),
            ).count()
            actual_risk = min(100, stale * 10)
            simulated_risk = 0
            exposure_days_saved = stale * rotation_days // 2
            insight = (
                f"{stale} credentials haven't been rotated in {rotation_days}+ days. "
                f"Regular rotation could save ~{exposure_days_saved} days of exposure."
            )

        else:
            insight = f"Scenario type '{scenario_type}' is not yet implemented."

        risk_reduction = max(0, actual_risk - int(simulated_risk))

        scenario = WhatIfScenario.objects.create(
            user=user,
            vault_item=vault_item,
            credential_domain=credential_domain,
            scenario_type=scenario_type,
            scenario_params=params,
            actual_risk_score=actual_risk,
            simulated_risk_score=int(simulated_risk),
            risk_reduction=risk_reduction,
            exposure_days_saved=exposure_days_saved,
            insight_text=insight,
        )

        return scenario

    # ------------------------------------------------------------------ #
    #  Time Machine
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_time_machine_snapshot(user, point_in_time):
        """
        Reconstruct account security state at a specific point in time.
        """
        # Get credentials that existed at that time
        credentials = PasswordHistoryEntry.objects.filter(
            user=user,
            changed_at__lte=point_in_time,
        ).values('credential_domain').annotate(
            last_change=Max('changed_at'),
            total_changes=Count('id'),
        ).order_by('credential_domain')

        # For each credential, get the strength at that point
        credential_states = []
        for cred in credentials:
            domain = cred['credential_domain']
            # Get the latest strength snapshot before point_in_time
            snapshot = StrengthSnapshot.objects.filter(
                user=user,
                credential_domain=domain,
                snapshot_at__lte=point_in_time,
            ).order_by('-snapshot_at').first()

            # Get the latest password history entry before point_in_time
            history = PasswordHistoryEntry.objects.filter(
                user=user,
                credential_domain=domain,
                changed_at__lte=point_in_time,
            ).order_by('-changed_at').first()

            credential_states.append({
                'credential_domain': domain,
                'strength_score': snapshot.strength_score if snapshot else 0,
                'entropy_bits': snapshot.entropy_bits if snapshot else 0,
                'last_changed': history.changed_at.isoformat() if history else None,
                'password_age_days': (
                    (point_in_time - history.changed_at).days if history else 0
                ),
                'total_changes': cred['total_changes'],
                'breach_exposure': snapshot.breach_exposure_count if snapshot else 0,
            })

        # Get security events that had occurred up to that point
        events_before = SecurityEvent.objects.filter(
            user=user,
            occurred_at__lte=point_in_time,
        )
        unresolved_events = events_before.filter(
            Q(resolved=False) | Q(resolved_at__gt=point_in_time)
        ).count()

        # Calculate overall score at that point
        scores = [c['strength_score'] for c in credential_states if c['strength_score'] > 0]
        avg_score = sum(scores) / len(scores) if scores else 50

        return {
            'point_in_time': point_in_time.isoformat(),
            'total_credentials': len(credential_states),
            'credentials': credential_states,
            'overall_score': int(avg_score),
            'total_security_events': events_before.count(),
            'unresolved_events': unresolved_events,
            'total_breaches': events_before.filter(
                event_type='breach_detected',
            ).count(),
        }

    # ------------------------------------------------------------------ #
    #  Security Score History
    # ------------------------------------------------------------------ #

    @staticmethod
    def calculate_security_score_over_time(user, date_from=None, date_to=None):
        """Return security score trajectory for gamification charts."""
        now = timezone.now()
        if date_from is None:
            date_from = now - timedelta(days=365)
        if date_to is None:
            date_to = now

        # Get daily average strength scores
        snapshots = StrengthSnapshot.objects.filter(
            user=user,
            snapshot_at__gte=date_from,
            snapshot_at__lte=date_to,
        ).values('snapshot_at__date').annotate(
            avg_score=Avg('strength_score'),
            min_score=Min('strength_score'),
            max_score=Max('strength_score'),
            count=Count('id'),
        ).order_by('snapshot_at__date')

        # Get security events for impact markers
        events = SecurityEvent.objects.filter(
            user=user,
            occurred_at__gte=date_from,
            occurred_at__lte=date_to,
        ).values('occurred_at__date', 'event_type', 'severity', 'risk_score_impact')

        event_map = {}
        for e in events:
            date_key = str(e['occurred_at__date'])
            if date_key not in event_map:
                event_map[date_key] = []
            event_map[date_key].append({
                'event_type': e['event_type'],
                'severity': e['severity'],
                'impact': e['risk_score_impact'],
            })

        return {
            'scores': [
                {
                    'date': str(s['snapshot_at__date']),
                    'avg_score': round(s['avg_score'], 1),
                    'min_score': s['min_score'],
                    'max_score': s['max_score'],
                    'credential_count': s['count'],
                }
                for s in snapshots
            ],
            'events': event_map,
        }

    # ------------------------------------------------------------------ #
    #  Gamification / Achievements
    # ------------------------------------------------------------------ #

    @staticmethod
    def check_achievements(user):
        """Evaluate and award achievements based on current state."""
        awarded = []
        existing = set(
            AchievementRecord.objects.filter(user=user)
            .values_list('achievement_type', flat=True)
        )

        # --- First Password Change ---
        if 'first_password_change' not in existing:
            if PasswordHistoryEntry.objects.filter(user=user).exists():
                awarded.append(
                    PasswordArchaeologyService._award_achievement(
                        user, 'first_password_change', 'First Password Change',
                        'You recorded your first password change!',
                        'key-round', 'bronze', 10,
                    )
                )

        # --- Password change milestones ---
        total_changes = PasswordHistoryEntry.objects.filter(user=user).count()
        if 'ten_passwords_changed' not in existing and total_changes >= 10:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'ten_passwords_changed', '10 Passwords Changed',
                    'You have changed 10 passwords — keep it up!',
                    'rotate-cw', 'silver', 25,
                )
            )
        if 'fifty_passwords_changed' not in existing and total_changes >= 50:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'fifty_passwords_changed', '50 Passwords Changed',
                    'Incredible! 50 password rotations completed.',
                    'trophy', 'gold', 100,
                )
            )

        # --- Security Score milestones ---
        timeline, _ = PasswordTimeline.objects.get_or_create(user=user)
        score = timeline.current_overall_score

        if 'security_score_80' not in existing and score >= 80:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'security_score_80', 'Security Score 80+',
                    'Your overall security score reached 80!',
                    'shield-check', 'silver', 30,
                )
            )
        if 'security_score_90' not in existing and score >= 90:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'security_score_90', 'Security Score 90+',
                    'Outstanding! Security score above 90.',
                    'shield', 'gold', 50,
                )
            )
        if 'security_score_100' not in existing and score >= 100:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'security_score_100', 'Perfect Score',
                    'You achieved a perfect security score!',
                    'crown', 'diamond', 200,
                )
            )

        # --- Zero breaches streak ---
        last_breach = SecurityEvent.objects.filter(
            user=user,
            event_type='breach_detected',
        ).order_by('-occurred_at').first()

        if last_breach:
            days_since = (timezone.now() - last_breach.occurred_at).days
        else:
            first_event = PasswordHistoryEntry.objects.filter(
                user=user
            ).order_by('changed_at').first()
            days_since = (
                (timezone.now() - first_event.changed_at).days
                if first_event else 0
            )

        if 'zero_breaches_30' not in existing and days_since >= 30:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'zero_breaches_30', 'Zero Breaches (30 Days)',
                    '30 consecutive days without a breach!',
                    'shield-off', 'bronze', 15,
                )
            )
        if 'zero_breaches_90' not in existing and days_since >= 90:
            awarded.append(
                PasswordArchaeologyService._award_achievement(
                    user, 'zero_breaches_90', 'Zero Breaches (90 Days)',
                    '90 days breach-free!',
                    'shield-off', 'silver', 40,
                )
            )

        return awarded

    @staticmethod
    def _award_achievement(user, achievement_type, title, description,
                            icon_name, badge_tier, score_points):
        """Create an achievement record."""
        achievement = AchievementRecord.objects.create(
            user=user,
            achievement_type=achievement_type,
            title=title,
            description=description,
            icon_name=icon_name,
            badge_tier=badge_tier,
            score_points=score_points,
        )
        logger.info(f"Achievement awarded to {user.username}: {title}")
        return achievement

    # ------------------------------------------------------------------ #
    #  Dashboard Summary
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_dashboard_summary(user):
        """Get aggregated dashboard data for the archaeology view."""
        timeline, _ = PasswordTimeline.objects.get_or_create(user=user)

        # Recent events (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_changes = PasswordHistoryEntry.objects.filter(
            user=user, changed_at__gte=week_ago,
        ).count()
        recent_events = SecurityEvent.objects.filter(
            user=user, occurred_at__gte=week_ago,
        ).count()

        # Achievements
        achievements = AchievementRecord.objects.filter(user=user)
        total_points = sum(a.score_points for a in achievements)

        return {
            'overall_score': timeline.current_overall_score,
            'total_credentials': timeline.total_credentials_tracked,
            'total_changes': timeline.total_password_changes,
            'total_events': timeline.total_security_events,
            'total_breaches': timeline.total_breaches_detected,
            'avg_password_age_days': round(timeline.average_password_age_days, 1),
            'avg_strength': round(timeline.average_strength_score, 1),
            'weakest': {
                'domain': timeline.weakest_credential_domain,
                'score': timeline.weakest_credential_score,
            },
            'strongest': {
                'domain': timeline.strongest_credential_domain,
                'score': timeline.strongest_credential_score,
            },
            'streaks': {
                'all_strong_days': timeline.current_all_strong_streak_days,
                'longest_strong_days': timeline.longest_all_strong_streak_days,
                'no_breach_days': timeline.current_no_breach_streak_days,
            },
            'recent': {
                'changes_7d': recent_changes,
                'events_7d': recent_events,
            },
            'achievements': {
                'total': achievements.count(),
                'total_points': total_points,
                'unacknowledged': achievements.filter(acknowledged=False).count(),
            },
            'last_change': (
                timeline.last_password_change_at.isoformat()
                if timeline.last_password_change_at else None
            ),
            'last_event': (
                timeline.last_security_event_at.isoformat()
                if timeline.last_security_event_at else None
            ),
        }

    # ------------------------------------------------------------------ #
    #  Internal Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _refresh_timeline_cache(user):
        """Recompute the PasswordTimeline aggregate cache for a user."""
        timeline, _ = PasswordTimeline.objects.get_or_create(user=user)

        # Total counts
        changes = PasswordHistoryEntry.objects.filter(user=user)
        events = SecurityEvent.objects.filter(user=user)

        timeline.total_password_changes = changes.count()
        timeline.total_security_events = events.count()
        timeline.total_breaches_detected = events.filter(
            event_type='breach_detected',
        ).count()

        # Unique credentials
        domains = changes.values_list(
            'credential_domain', flat=True
        ).distinct()
        timeline.total_credentials_tracked = domains.count()

        # Last events
        last_change = changes.order_by('-changed_at').first()
        last_event = events.order_by('-occurred_at').first()
        timeline.last_password_change_at = (
            last_change.changed_at if last_change else None
        )
        timeline.last_security_event_at = (
            last_event.occurred_at if last_event else None
        )

        # Strength stats from latest snapshots per domain
        latest_snapshots = []
        for domain in domains:
            snap = StrengthSnapshot.objects.filter(
                user=user,
                credential_domain=domain,
            ).order_by('-snapshot_at').first()
            if snap:
                latest_snapshots.append(snap)

        if latest_snapshots:
            scores = [s.strength_score for s in latest_snapshots]
            timeline.average_strength_score = sum(scores) / len(scores)
            timeline.current_overall_score = int(timeline.average_strength_score)

            weakest = min(latest_snapshots, key=lambda s: s.strength_score)
            timeline.weakest_credential_domain = weakest.credential_domain
            timeline.weakest_credential_score = weakest.strength_score

            strongest = max(latest_snapshots, key=lambda s: s.strength_score)
            timeline.strongest_credential_domain = strongest.credential_domain
            timeline.strongest_credential_score = strongest.strength_score

        # Average password age
        if last_change:
            now = timezone.now()
            ages = []
            for domain in domains:
                latest = changes.filter(
                    credential_domain=domain,
                ).order_by('-changed_at').first()
                if latest:
                    ages.append((now - latest.changed_at).days)
            if ages:
                timeline.average_password_age_days = sum(ages) / len(ages)

        timeline.save()
        return timeline
