"""
URL Configuration for ML Dark Web Monitoring
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'ml_dark_web'

router = DefaultRouter()
router.register(r'', views.MLDarkWebViewSet, basename='ml-darkweb')
router.register(r'admin', views.MLDarkWebAdminViewSet, basename='ml-darkweb-admin')

urlpatterns = [
    path('', include(router.urls)),
    path('classify-text/', views.classify_text, name='classify-text'),
    path('mark-alert-read/<int:alert_id>/', views.mark_alert_read, name='mark-alert-read'),
    path('breach-alerts/', views.get_breach_alerts, name='breach-alerts'),
]

