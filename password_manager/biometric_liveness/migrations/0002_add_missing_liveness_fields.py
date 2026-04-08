"""
Migration: Add 14 missing fields across biometric_liveness models

Models affected:
- LivenessProfile: baseline_expression_timing
- LivenessSession: verdict, verdict_reason
- LivenessChallenge: challenge_status, instruction
- ChallengeResponse: response_type, gaze_accuracy, expression_score, is_valid, score
- ThermalReading: is_valid
- GazeTrackingData: session (FK), accuracy, head_pose
- MicroExpressionEvent: is_genuine
"""

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('biometric_liveness', '0001_initial'),
    ]

    operations = [
        # ── LivenessProfile ──────────────────────────────────────────────
        migrations.AddField(
            model_name='livenessprofile',
            name='baseline_expression_timing',
            field=models.JSONField(
                default=dict,
                help_text='Per-user baseline: mean/std of onset duration, apex duration, offset duration, inter-expression interval in ms',
            ),
        ),

        # ── LivenessSession ──────────────────────────────────────────────
        migrations.AddField(
            model_name='livenesssession',
            name='verdict',
            field=models.CharField(
                blank=True,
                choices=[
                    ('HIGH_CONFIDENCE_LIVE', 'High confidence live'),
                    ('VERIFIED_LIVE', 'Verified live'),
                    ('LOW_CONFIDENCE', 'Low confidence'),
                    ('SUSPECTED_FAKE', 'Suspected fake'),
                    ('INCONCLUSIVE', 'Inconclusive'),
                ],
                help_text='Final human-readable verdict from complete_session()',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='livenesssession',
            name='verdict_reason',
            field=models.TextField(
                blank=True,
                help_text='Explanation of verdict: which signals drove the decision',
            ),
        ),

        # ── LivenessChallenge ────────────────────────────────────────────
        migrations.AddField(
            model_name='livenesschallenge',
            name='challenge_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                    ('expired', 'Expired'),
                    ('skipped', 'Skipped'),
                ],
                default='pending',
                help_text='Current lifecycle status of this challenge',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='livenesschallenge',
            name='instruction',
            field=models.CharField(
                blank=True,
                help_text='Human-readable challenge prompt',
                max_length=512,
            ),
        ),

        # ── ChallengeResponse ────────────────────────────────────────────
        migrations.AddField(
            model_name='challengeresponse',
            name='response_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('gaze', 'Gaze'),
                    ('expression', 'Expression'),
                    ('pulse', 'Pulse'),
                    ('blink', 'Blink'),
                    ('cognitive', 'Cognitive'),
                ],
                help_text='Type of challenge this response answers',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='challengeresponse',
            name='gaze_accuracy',
            field=models.FloatField(
                blank=True,
                help_text='Fraction of gaze targets hit within threshold',
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.AddField(
            model_name='challengeresponse',
            name='expression_score',
            field=models.FloatField(
                blank=True,
                help_text='Naturalness score for expression response',
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.AddField(
            model_name='challengeresponse',
            name='is_valid',
            field=models.BooleanField(
                help_text='Whether this response passed validation',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='challengeresponse',
            name='score',
            field=models.FloatField(
                default=0.0,
                help_text='Overall response score aggregated from sub-scores',
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),

        # ── ThermalReading ───────────────────────────────────────────────
        migrations.AddField(
            model_name='thermalreading',
            name='is_valid',
            field=models.BooleanField(
                default=True,
                help_text='Whether this thermal reading meets quality thresholds for use in scoring',
            ),
        ),

        # ── GazeTrackingData ─────────────────────────────────────────────
        migrations.AddField(
            model_name='gazetrackingdata',
            name='session',
            field=models.ForeignKey(
                blank=True,
                help_text='Direct session reference for session-level analytics',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='gaze_data',
                to='biometric_liveness.livenesssession',
            ),
        ),
        migrations.AddField(
            model_name='gazetrackingdata',
            name='accuracy',
            field=models.FloatField(
                blank=True,
                help_text='Distance from gaze point to nearest target, normalised',
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.AddField(
            model_name='gazetrackingdata',
            name='head_pose',
            field=models.JSONField(
                default=dict,
                help_text='Estimated head pose at this gaze point: {yaw, pitch, roll}',
            ),
        ),

        # ── MicroExpressionEvent ─────────────────────────────────────────
        migrations.AddField(
            model_name='microexpressionevent',
            name='is_genuine',
            field=models.BooleanField(
                help_text='Whether this expression is classified as genuine (involuntary) vs performed',
                null=True,
            ),
        ),
    ]
