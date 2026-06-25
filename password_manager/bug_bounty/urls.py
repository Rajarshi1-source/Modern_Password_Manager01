"""Bug Bounty API routes (mounted at /api/bug-bounty/).

Phase 1: self-pentest (findings, self-test). Phase 2: bounty program
(programs, submissions, rewards).
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BountyProgramViewSet,
    FindingViewSet,
    RewardViewSet,
    SelfTestViewSet,
    SubmissionViewSet,
)

router = DefaultRouter()
router.register(r'findings', FindingViewSet, basename='bug-bounty-finding')
router.register(r'self-test', SelfTestViewSet, basename='bug-bounty-self-test')
router.register(r'programs', BountyProgramViewSet, basename='bug-bounty-program')
router.register(r'submissions', SubmissionViewSet, basename='bug-bounty-submission')
router.register(r'rewards', RewardViewSet, basename='bug-bounty-reward')

urlpatterns = [
    path('', include(router.urls)),
]
