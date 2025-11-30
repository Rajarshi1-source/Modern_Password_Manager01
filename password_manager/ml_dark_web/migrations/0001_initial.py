# Generated migration file for ML Dark Web Monitoring

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BreachSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('url', models.URLField(max_length=500)),
                ('source_type', models.CharField(choices=[('forum', 'Dark Web Forum'), ('paste', 'Paste Site'), ('marketplace', 'Marketplace'), ('telegram', 'Telegram Channel'), ('irc', 'IRC Channel'), ('onion', 'Onion Site'), ('clearweb', 'Clear Web')], max_length=20)),
                ('last_scraped', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('reliability_score', models.FloatField(default=0.5, help_text='ML-computed reliability (0-1)')),
                ('scrape_frequency_hours', models.IntegerField(default=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'ml_breach_sources',
                'ordering': ['-reliability_score', '-last_scraped'],
            },
        ),
        migrations.CreateModel(
            name='MLBreachData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('breach_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('title', models.CharField(max_length=500)),
                ('description', models.TextField()),
                ('detected_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('breach_date', models.DateTimeField(blank=True, null=True)),
                ('severity', models.CharField(choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')], db_index=True, max_length=10)),
                ('confidence_score', models.FloatField(help_text='ML model confidence (0-1)')),
                ('ml_model_version', models.CharField(default='1.0', max_length=50)),
                ('affected_records', models.BigIntegerField(default=0)),
                ('exposed_data_types', models.JSONField(default=list, help_text="['email', 'password', 'phone', etc.]")),
                ('raw_content', models.TextField(help_text='Original scraped content')),
                ('processed_content', models.TextField(blank=True, help_text='Cleaned and processed content')),
                ('processing_status', models.CharField(choices=[('pending', 'Pending Analysis'), ('analyzing', 'Being Analyzed'), ('matched', 'Credentials Matched'), ('completed', 'Completed'), ('failed', 'Analysis Failed')], default='pending', max_length=20)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('extracted_emails', models.JSONField(default=list)),
                ('extracted_domains', models.JSONField(default=list)),
                ('extracted_credentials', models.JSONField(default=list, help_text='Hashed credential pairs')),
                ('content_embedding', models.BinaryField(blank=True, help_text='BERT embedding vector', null=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='breaches', to='ml_dark_web.breachsource')),
            ],
            options={
                'db_table': 'ml_breach_data',
                'ordering': ['-detected_at'],
            },
        ),
        migrations.CreateModel(
            name='UserCredentialMonitoring',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_hash', models.CharField(db_index=True, max_length=64)),
                ('username_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('email_embedding', models.BinaryField(blank=True, help_text='Siamese network embedding', null=True)),
                ('credential_type', models.CharField(default='email', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_checked', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='monitored_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ml_user_credential_monitoring',
                'unique_together': {('user', 'email_hash')},
            },
        ),
        migrations.CreateModel(
            name='MLBreachMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('similarity_score', models.FloatField(help_text='Siamese network similarity score (0-1)')),
                ('confidence_score', models.FloatField(help_text='Overall match confidence (0-1)')),
                ('match_type', models.CharField(default='credential', max_length=50)),
                ('matched_data', models.JSONField(default=dict, help_text='Details about the match')),
                ('alert_created', models.BooleanField(default=False)),
                ('alert_id', models.IntegerField(blank=True, help_text='Reference to BreachAlert', null=True)),
                ('detected_at', models.DateTimeField(auto_now_add=True)),
                ('resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('breach', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='ml_dark_web.mlbreachdata')),
                ('monitored_credential', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='ml_dark_web.usercredentialmonitoring')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ml_breach_matches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ml_breach_matches',
                'ordering': ['-detected_at'],
                'unique_together': {('user', 'breach', 'monitored_credential')},
            },
        ),
        migrations.CreateModel(
            name='MLModelMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_type', models.CharField(choices=[('breach_classifier', 'BERT Breach Classifier'), ('credential_matcher', 'Siamese Credential Matcher'), ('pattern_detector', 'LSTM Pattern Detector'), ('entity_extractor', 'NER Entity Extractor')], max_length=50)),
                ('version', models.CharField(max_length=50)),
                ('file_path', models.CharField(help_text='Path to model file', max_length=500)),
                ('accuracy', models.FloatField(blank=True, null=True)),
                ('precision', models.FloatField(blank=True, null=True)),
                ('recall', models.FloatField(blank=True, null=True)),
                ('f1_score', models.FloatField(blank=True, null=True)),
                ('training_samples', models.IntegerField(default=0)),
                ('training_date', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('hyperparameters', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'db_table': 'ml_model_metadata',
                'ordering': ['-training_date'],
                'unique_together': {('model_type', 'version')},
            },
        ),
        migrations.CreateModel(
            name='DarkWebScrapeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('items_found', models.IntegerField(default=0)),
                ('breaches_detected', models.IntegerField(default=0)),
                ('processing_time_seconds', models.FloatField(default=0)),
                ('status', models.CharField(choices=[('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('partial', 'Partial Success')], default='running', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scrape_logs', to='ml_dark_web.breachsource')),
            ],
            options={
                'db_table': 'ml_darkweb_scrape_logs',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='BreachPatternAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern_id', models.CharField(max_length=100, unique=True)),
                ('pattern_type', models.CharField(choices=[('temporal', 'Temporal Pattern'), ('geographical', 'Geographical Pattern'), ('threat_actor', 'Threat Actor Pattern'), ('credential_reuse', 'Credential Reuse Pattern')], max_length=50)),
                ('description', models.TextField()),
                ('confidence_score', models.FloatField()),
                ('first_seen', models.DateTimeField()),
                ('last_seen', models.DateTimeField()),
                ('frequency', models.IntegerField(default=1)),
                ('risk_level', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], max_length=20)),
                ('detected_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('affected_breaches', models.ManyToManyField(related_name='patterns', to='ml_dark_web.mlbreachdata')),
            ],
            options={
                'db_table': 'ml_breach_patterns',
                'ordering': ['-last_seen'],
            },
        ),
        # Indexes
        migrations.AddIndex(
            model_name='breachsource',
            index=models.Index(fields=['is_active', 'last_scraped'], name='ml_breach_s_is_acti_idx'),
        ),
        migrations.AddIndex(
            model_name='breachsource',
            index=models.Index(fields=['source_type', 'reliability_score'], name='ml_breach_s_source__idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachdata',
            index=models.Index(fields=['breach_date', 'severity'], name='ml_breach_d_breach__idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachdata',
            index=models.Index(fields=['confidence_score', 'severity'], name='ml_breach_d_confid_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachdata',
            index=models.Index(fields=['processing_status', 'detected_at'], name='ml_breach_d_process_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachdata',
            index=models.Index(fields=['source', 'detected_at'], name='ml_breach_d_source__idx2'),
        ),
        migrations.AddIndex(
            model_name='usercredentialmonitoring',
            index=models.Index(fields=['email_hash', 'is_active'], name='ml_user_cr_email_h_idx'),
        ),
        migrations.AddIndex(
            model_name='usercredentialmonitoring',
            index=models.Index(fields=['domain', 'is_active'], name='ml_user_cr_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='usercredentialmonitoring',
            index=models.Index(fields=['user', 'is_active', 'last_checked'], name='ml_user_cr_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachmatch',
            index=models.Index(fields=['user', 'resolved', 'detected_at'], name='ml_breach_m_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachmatch',
            index=models.Index(fields=['similarity_score', 'confidence_score'], name='ml_breach_m_similar_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbreachmatch',
            index=models.Index(fields=['alert_created', 'detected_at'], name='ml_breach_m_alert_c_idx'),
        ),
        migrations.AddIndex(
            model_name='darkwebscrapelog',
            index=models.Index(fields=['source', 'started_at'], name='ml_darkweb_source__idx'),
        ),
        migrations.AddIndex(
            model_name='darkwebscrapelog',
            index=models.Index(fields=['status', 'started_at'], name='ml_darkweb_status_idx'),
        ),
    ]

