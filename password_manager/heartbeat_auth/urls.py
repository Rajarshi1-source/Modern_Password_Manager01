"""URL router for heartbeat_auth.

Mounted at ``/api/heartbeat/`` by the project-level urls.py.
"""

from django.urls import path

from . import views

app_name = 'heartbeat_auth'

urlpatterns = [
    path('enroll/', views.enroll, name='enroll'),
    path('verify/', views.verify, name='verify'),
    path('profile/', views.profile, name='profile'),
    path('profile/reset/', views.reset_profile, name='reset'),
]
