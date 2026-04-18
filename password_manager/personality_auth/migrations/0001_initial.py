"""
Initial migration for the personality_auth app.
"""

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalityProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('trait_features', models.JSONField(blank=True, default=dict)),
                ('theme_weights', models.JSONField(blank=True, default=list)),
                ('embedding', models.JSONField(blank=True, default=list)),
                ('source_messages_analysed', models.IntegerField(default=0)),
                ('last_inferred_at', models.DateTimeField(blank=True, null=True)),
                ('inference_model', models.CharField(blank=True, default='', max_length=128)),
                ('opted_in', models.BooleanField(default=False)),
                ('opt_in_changed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personality_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Personality Profile',
                'verbose_name_plural': 'Personality Profiles',
                'db_table': 'personality_profile',
            },
        ),
        migrations.CreateModel(
            name='MoralFrameworkSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('coefficients', models.JSONField(default=dict)),
                ('value_tags', models.JSONField(default=list)),
                ('confidence', models.FloatField(default=0.0, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('sample_size', models.IntegerField(default=0)),
                ('inference_model', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='framework_snapshots', to='personality_auth.personalityprofile')),
            ],
            options={
                'verbose_name': 'Moral Framework Snapshot',
                'verbose_name_plural': 'Moral Framework Snapshots',
                'db_table': 'personality_moral_framework_snapshot',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PersonalityQuestion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('dimension', models.CharField(choices=[('values', 'Core Values'), ('beliefs', 'Beliefs'), ('preferences', 'Preferences'), ('style', 'Communication Style'), ('decisions', 'Decision Patterns'), ('memories', 'Shared Memories')], default='values', max_length=16)),
                ('difficulty', models.IntegerField(choices=[(1, 'Easy'), (2, 'Medium'), (3, 'Hard')], default=2)),
                ('prompt', models.TextField(help_text='Question text shown to the user')),
                ('choices', models.JSONField(blank=True, default=list, help_text='Optional ordered list of multiple-choice answers')),
                ('expected_signature', models.JSONField(blank=True, default=dict, help_text="Structured expected answer, e.g. {'top': 'a', 'avoid': ['c']}")),
                ('rationale', models.TextField(blank=True, default='', help_text='LLM rationale for why this question probes the target dimension')),
                ('single_use', models.BooleanField(default=True)),
                ('used_count', models.IntegerField(default=0)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('generator_model', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='personality_auth.personalityprofile')),
            ],
            options={
                'verbose_name': 'Personality Question',
                'verbose_name_plural': 'Personality Questions',
                'db_table': 'personality_question',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PersonalityChallenge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('passed', 'Passed'), ('failed', 'Failed'), ('abandoned', 'Abandoned'), ('expired', 'Expired')], default='pending', max_length=16)),
                ('required_score', models.FloatField(default=0.65, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('achieved_score', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('mood_context', models.CharField(choices=[('calm', 'Calm'), ('stressed', 'Stressed'), ('rushed', 'Rushed'), ('happy', 'Happy'), ('frustrated', 'Frustrated'), ('unknown', 'Unknown')], default='unknown', max_length=16)),
                ('mood_signals', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('presented_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
                ('intent', models.CharField(default='login', help_text='Why the challenge was issued: login|recovery|step_up', max_length=64)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='challenges', to='personality_auth.personalityprofile')),
                ('questions', models.ManyToManyField(blank=True, related_name='challenges', to='personality_auth.personalityquestion')),
            ],
            options={
                'verbose_name': 'Personality Challenge',
                'verbose_name_plural': 'Personality Challenges',
                'db_table': 'personality_challenge',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PersonalityResponse',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('answer_text', models.TextField(blank=True, default='')),
                ('answer_choice', models.CharField(blank=True, default='', max_length=128)),
                ('answer_metadata', models.JSONField(blank=True, default=dict)),
                ('consistency_score', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('latency_ms', models.IntegerField(blank=True, null=True)),
                ('rationale', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='personality_auth.personalitychallenge')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='personality_auth.personalityquestion')),
            ],
            options={
                'verbose_name': 'Personality Response',
                'verbose_name_plural': 'Personality Responses',
                'db_table': 'personality_response',
                'unique_together': {('challenge', 'question')},
            },
        ),
        migrations.CreateModel(
            name='PersonalityAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('profile_inferred', 'Profile Updated'), ('questions_generated', 'Questions Generated'), ('challenge_created', 'Challenge Created'), ('challenge_presented', 'Challenge Presented'), ('response_submitted', 'Response Submitted'), ('challenge_passed', 'Challenge Passed'), ('challenge_failed', 'Challenge Failed'), ('challenge_abandoned', 'Challenge Abandoned'), ('rate_limited', 'Rate Limited'), ('model_error', 'Model Error')], max_length=32)),
                ('event_payload', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('previous_hash', models.CharField(blank=True, default='', max_length=128)),
                ('entry_hash', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('challenge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_entries', to='personality_auth.personalitychallenge')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_log', to='personality_auth.personalityprofile')),
            ],
            options={
                'verbose_name': 'Personality Audit Log',
                'verbose_name_plural': 'Personality Audit Logs',
                'db_table': 'personality_audit_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='moralframeworksnapshot',
            index=models.Index(fields=['profile', '-created_at'], name='pa_mfs_profile_created_idx'),
        ),
        migrations.AddIndex(
            model_name='personalityquestion',
            index=models.Index(fields=['profile', 'dimension', '-created_at'], name='pa_q_profile_dim_idx'),
        ),
        migrations.AddIndex(
            model_name='personalityquestion',
            index=models.Index(fields=['expires_at'], name='pa_q_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='personalitychallenge',
            index=models.Index(fields=['profile', '-created_at'], name='pa_ch_profile_created_idx'),
        ),
        migrations.AddIndex(
            model_name='personalitychallenge',
            index=models.Index(fields=['status', 'expires_at'], name='pa_ch_status_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='personalityresponse',
            index=models.Index(fields=['challenge', '-submitted_at'], name='pa_resp_chal_sub_idx'),
        ),
        migrations.AddIndex(
            model_name='personalityauditlog',
            index=models.Index(fields=['profile', '-created_at'], name='pa_audit_profile_idx'),
        ),
        migrations.AddIndex(
            model_name='personalityauditlog',
            index=models.Index(fields=['event_type', '-created_at'], name='pa_audit_event_idx'),
        ),
    ]
