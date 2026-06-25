"""Bug Bounty self-pentest API routes (mounted at /api/bug-bounty/)."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FindingViewSet, SelfTestViewSet

router = DefaultRouter()
router.register(r'findings', FindingViewSet, basename='bug-bounty-finding')
router.register(r'self-test', SelfTestViewSet, basename='bug-bounty-self-test')

urlpatterns = [
    path('', include(router.urls)),
]
