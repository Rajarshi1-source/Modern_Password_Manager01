"""Self-destruct API routes."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SelfDestructEventViewSet, SelfDestructPolicyViewSet

router = DefaultRouter()
router.register(r'policies', SelfDestructPolicyViewSet, basename='self-destruct-policy')
router.register(r'events', SelfDestructEventViewSet, basename='self-destruct-event')

urlpatterns = [path('', include(router.urls))]
