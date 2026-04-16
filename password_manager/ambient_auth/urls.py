"""URL routes for ambient_auth (mounted at /api/ambient/)."""

from django.urls import path

from . import views

urlpatterns = [
    path("ingest/", views.ingest, name="ambient-ingest"),
    path("contexts/", views.list_contexts, name="ambient-list-contexts"),
    path("contexts/promote/", views.promote_context, name="ambient-promote-context"),
    path("contexts/<uuid:context_id>/", views.context_detail, name="ambient-context-detail"),
    path("observations/", views.list_observations, name="ambient-list-observations"),
    path("profile/", views.get_profile, name="ambient-get-profile"),
    path("settings/", views.signal_config, name="ambient-signal-config"),
    path("baseline/reset/", views.reset_baseline, name="ambient-reset-baseline"),
    path("config/", views.config, name="ambient-config"),
]
