"""
Password Archaeology URL Configuration
=========================================
"""

from django.urls import path
from . import views

app_name = 'password_archaeology'

urlpatterns = [
    # Dashboard
    path(
        'dashboard/',
        views.dashboard_view,
        name='dashboard',
    ),

    # Timeline
    path(
        'timeline/',
        views.timeline_view,
        name='timeline',
    ),

    # Strength Evolution
    path(
        'strength-evolution/overall/',
        views.strength_evolution_view,
        name='strength-evolution-overall',
    ),
    path(
        'strength-evolution/<uuid:vault_item_id>/',
        views.strength_evolution_view,
        name='strength-evolution-item',
    ),

    # Security Events
    path(
        'security-events/',
        views.security_events_view,
        name='security-events',
    ),

    # What-If Scenarios
    path(
        'what-if/',
        views.what_if_run_view,
        name='what-if-run',
    ),
    path(
        'what-if/history/',
        views.what_if_history_view,
        name='what-if-history',
    ),

    # Time Machine
    path(
        'time-machine/<str:timestamp>/',
        views.time_machine_view,
        name='time-machine',
    ),

    # Achievements
    path(
        'achievements/',
        views.achievements_view,
        name='achievements',
    ),
    path(
        'achievements/<uuid:achievement_id>/acknowledge/',
        views.acknowledge_achievement_view,
        name='acknowledge-achievement',
    ),

    # Security Score
    path(
        'security-score/',
        views.security_score_view,
        name='security-score',
    ),
]
