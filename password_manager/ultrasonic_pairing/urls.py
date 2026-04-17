"""URL router for the ultrasonic_pairing app.

Mounted at ``/api/ultrasonic/`` by the project-level urls.py.
"""

from django.urls import path

from . import views

app_name = 'ultrasonic_pairing'

urlpatterns = [
    path('sessions/', views.initiate_session, name='initiate'),
    path('sessions/claim/', views.claim_session, name='claim'),
    path('sessions/<uuid:session_id>/', views.get_session, name='get'),
    path('sessions/<uuid:session_id>/confirm/', views.confirm_session, name='confirm'),
    path('sessions/<uuid:session_id>/share/', views.share_payload, name='share'),
    path(
        'sessions/<uuid:session_id>/delivered/',
        views.fetch_delivered_payload,
        name='delivered',
    ),
    path(
        'sessions/<uuid:session_id>/enroll-device/',
        views.enroll_device,
        name='enroll_device',
    ),
]
