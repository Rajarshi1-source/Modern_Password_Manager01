"""
URL configuration for Shared Services API
Includes Performance Monitoring and Cryptography
"""

from django.urls import path
from shared import performance_views
from shared.views import crypto_views

app_name = 'shared'

urlpatterns = [
    # Performance summary and reports
    path('summary/', performance_views.performance_summary, name='summary'),
    path('system-health/', performance_views.system_health, name='system-health'),
    path('endpoints/', performance_views.endpoint_performance, name='endpoints'),
    path('database/', performance_views.database_performance, name='database'),
    
    # Error tracking
    path('errors/', performance_views.error_summary, name='errors'),
    
    # Performance alerts
    path('alerts/', performance_views.performance_alerts, name='alerts'),
    path('alerts/<int:alert_id>/acknowledge/', performance_views.acknowledge_alert, name='acknowledge-alert'),
    path('alerts/<int:alert_id>/resolve/', performance_views.resolve_alert, name='resolve-alert'),
    
    # Dependency management
    path('dependencies/', performance_views.dependencies_status, name='dependencies'),
    
    # ML predictions and optimization
    path('ml-predictions/', performance_views.ml_predictions, name='ml-predictions'),
    path('optimize/', performance_views.optimize_performance, name='optimize'),
    
    # Frontend performance reporting
    path('frontend/', performance_views.frontend_performance_report, name='frontend'),
    
    # Cryptography API
    path('crypto/generate-key/', crypto_views.generate_encryption_key, name='generate-key'),
    path('crypto/derive-key/', crypto_views.derive_key, name='derive-key'),
    path('crypto/test/', crypto_views.test_encryption, name='test-encryption'),
    path('crypto/info/', crypto_views.get_crypto_info, name='crypto-info'),
]

