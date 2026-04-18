"""URL routes for /api/personality/."""
from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path('profile/', views.ProfileView.as_view(), name='personality-profile'),
    path('opt-in/', views.OptInView.as_view(), name='personality-opt-in'),
    path('infer/', views.InferView.as_view(), name='personality-infer'),
    path(
        'questions/generate/',
        views.GenerateQuestionsView.as_view(),
        name='personality-generate-questions',
    ),
    path(
        'challenges/start/',
        views.StartChallengeView.as_view(),
        name='personality-challenge-start',
    ),
    path(
        'challenges/<uuid:challenge_id>/',
        views.ChallengeDetailView.as_view(),
        name='personality-challenge-detail',
    ),
    path(
        'challenges/<uuid:challenge_id>/submit/',
        views.SubmitAnswerView.as_view(),
        name='personality-challenge-submit',
    ),
    path(
        'challenges/<uuid:challenge_id>/abandon/',
        views.AbandonChallengeView.as_view(),
        name='personality-challenge-abandon',
    ),
    path('audit/', views.AuditLogView.as_view(), name='personality-audit'),
]
