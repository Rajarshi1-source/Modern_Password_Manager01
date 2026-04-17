"""Honeypot API routes."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    HoneypotAccessEventViewSet,
    HoneypotCredentialViewSet,
    HoneypotTemplateViewSet,
)

router = DefaultRouter()
router.register(r'credentials', HoneypotCredentialViewSet, basename='honeypot-credential')
router.register(r'events', HoneypotAccessEventViewSet, basename='honeypot-event')
router.register(r'templates', HoneypotTemplateViewSet, basename='honeypot-template')

urlpatterns = [
    path('', include(router.urls)),
]
