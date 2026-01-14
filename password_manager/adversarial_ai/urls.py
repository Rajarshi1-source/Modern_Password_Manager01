"""
URL Configuration for Adversarial AI module.

API Endpoints:
- POST /api/adversarial/analyze/           - Run adversarial analysis on password features
- POST /api/adversarial/analyze-raw/       - ML-powered analysis (accepts raw password)
- GET  /api/adversarial/recommendations/   - Get personalized defense recommendations
- POST /api/adversarial/recommendations/{id}/status/ - Update recommendation status
- GET  /api/adversarial/history/           - Get user's battle history
- GET  /api/adversarial/trending-attacks/  - Get currently trending attack patterns
- GET  /api/adversarial/profile/           - Get user defense profile
"""

from django.urls import path
from . import views

app_name = 'adversarial_ai'

urlpatterns = [
    # Password Analysis
    path('analyze/', views.analyze_password, name='analyze-password'),
    # ML-powered analysis (uses PasswordStrengthPredictor for feature extraction)
    path('analyze-raw/', views.analyze_raw_password, name='analyze-raw-password'),
    
    # Recommendations
    path('recommendations/', views.get_recommendations, name='get-recommendations'),
    path(
        'recommendations/<int:recommendation_id>/status/',
        views.update_recommendation_status,
        name='update-recommendation-status'
    ),
    
    # Battle History
    path('history/', views.get_battle_history, name='battle-history'),
    
    # Trending Attacks
    path('trending-attacks/', views.get_trending_attacks, name='trending-attacks'),
    
    # User Profile
    path('profile/', views.get_defense_profile, name='defense-profile'),
]
