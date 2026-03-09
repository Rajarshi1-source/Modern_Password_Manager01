"""
AI Assistant URL Configuration

All endpoints are prefixed with /api/ai-assistant/ in the root URLs.
"""

from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    # Session management
    path('sessions/', views.session_list, name='session-list'),
    path('sessions/<uuid:session_id>/', views.session_detail, name='session-detail'),
    
    # Chat endpoint
    path('sessions/<uuid:session_id>/send/', views.send_message, name='send-message'),
    
    # Proactive suggestions
    path('suggestions/', views.suggestions, name='suggestions'),
    
    # Query audit log
    path('query-log/', views.query_log, name='query-log'),
]
