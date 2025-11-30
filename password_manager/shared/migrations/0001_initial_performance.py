# Generated migration for performance monitoring models

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
            name='PerformanceMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=500)),
                ('method', models.CharField(max_length=10)),
                ('duration_ms', models.FloatField(help_text='Request duration in milliseconds')),
                ('status_code', models.IntegerField()),
                ('query_count', models.IntegerField(default=0)),
                ('query_time_ms', models.FloatField(default=0)),
                ('memory_mb', models.FloatField(default=0, help_text='Memory used in MB')),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('user', models.CharField(default='anonymous', max_length=150)),
            ],
            options={
                'db_table': 'performance_metrics',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='APIPerformanceMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(max_length=500)),
                ('method', models.CharField(max_length=10)),
                ('duration_ms', models.FloatField()),
                ('status', models.IntegerField()),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'api_performance_metrics',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='SystemMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cpu_percent', models.FloatField()),
                ('memory_percent', models.FloatField()),
                ('memory_available_mb', models.FloatField()),
                ('disk_percent', models.FloatField()),
                ('disk_free_gb', models.FloatField()),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'system_metrics',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='ErrorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(choices=[('DEBUG', 'Debug'), ('INFO', 'Info'), ('WARNING', 'Warning'), ('ERROR', 'Error'), ('CRITICAL', 'Critical')], max_length=10)),
                ('message', models.TextField()),
                ('exception_type', models.CharField(blank=True, max_length=200, null=True)),
                ('traceback', models.TextField(blank=True, null=True)),
                ('path', models.CharField(blank=True, max_length=500, null=True)),
                ('method', models.CharField(blank=True, max_length=10, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('request_data', models.JSONField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('count', models.IntegerField(default=1, help_text='Number of times this error occurred')),
                ('last_occurrence', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_errors', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'error_logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='PerformanceAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('SLOW_REQUEST', 'Slow Request'), ('EXCESSIVE_QUERIES', 'Excessive Queries'), ('HIGH_CPU', 'High CPU Usage'), ('HIGH_MEMORY', 'High Memory Usage'), ('HIGH_DISK', 'High Disk Usage'), ('ERROR_RATE', 'High Error Rate'), ('ANOMALY', 'Performance Anomaly')], max_length=50)),
                ('severity', models.CharField(choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')], max_length=10)),
                ('message', models.TextField()),
                ('details', models.JSONField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'performance_alerts',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='DependencyVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('current_version', models.CharField(max_length=50)),
                ('latest_version', models.CharField(blank=True, max_length=50, null=True)),
                ('update_available', models.BooleanField(default=False)),
                ('has_vulnerabilities', models.BooleanField(default=False)),
                ('vulnerability_count', models.IntegerField(default=0)),
                ('vulnerability_details', models.JSONField(blank=True, null=True)),
                ('last_checked', models.DateTimeField(default=django.utils.timezone.now)),
                ('ecosystem', models.CharField(default='python', max_length=50)),
            ],
            options={
                'db_table': 'dependency_versions',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='PerformancePrediction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(max_length=500)),
                ('predicted_duration_ms', models.FloatField()),
                ('actual_duration_ms', models.FloatField(blank=True, null=True)),
                ('prediction_accuracy', models.FloatField(blank=True, null=True)),
                ('confidence_score', models.FloatField()),
                ('features_used', models.JSONField()),
                ('model_version', models.CharField(max_length=50)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'performance_predictions',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['-timestamp', 'path'], name='performance_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['path', 'method'], name='performance_path_me_idx'),
        ),
        migrations.AddIndex(
            model_name='apiperformancemetric',
            index=models.Index(fields=['-timestamp', 'endpoint'], name='api_perfor_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='apiperformancemetric',
            index=models.Index(fields=['endpoint', 'method'], name='api_perfor_endpoin_idx'),
        ),
        migrations.AddIndex(
            model_name='errorlog',
            index=models.Index(fields=['-timestamp', 'level'], name='error_logs_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='errorlog',
            index=models.Index(fields=['resolved', '-timestamp'], name='error_logs_resolve_idx'),
        ),
        migrations.AddIndex(
            model_name='errorlog',
            index=models.Index(fields=['exception_type', '-timestamp'], name='error_logs_excepti_idx'),
        ),
        migrations.AddIndex(
            model_name='performancealert',
            index=models.Index(fields=['acknowledged', 'resolved', '-timestamp'], name='performanc_acknowl_idx'),
        ),
        migrations.AddIndex(
            model_name='performancealert',
            index=models.Index(fields=['severity', '-timestamp'], name='performanc_severit_idx'),
        ),
        migrations.AddIndex(
            model_name='performancealert',
            index=models.Index(fields=['alert_type', '-timestamp'], name='performanc_alert_t_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='dependencyversion',
            unique_together={('name', 'ecosystem')},
        ),
    ]

