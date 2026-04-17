"""URL routes for circadian_totp (mounted at /api/circadian/)."""

from django.urls import path

from . import views

app_name = "circadian_totp"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path(
        "calibration/recompute/",
        views.recompute_calibration,
        name="recompute-calibration",
    ),
    path(
        "wearables/<str:provider>/connect/",
        views.wearable_connect,
        name="wearable-connect",
    ),
    path(
        "wearables/<str:provider>/callback/",
        views.wearable_callback,
        name="wearable-callback",
    ),
    path(
        "wearables/<str:provider>/ingest/",
        views.wearable_ingest,
        name="wearable-ingest",
    ),
    path(
        "wearables/<str:provider>/unlink/",
        views.wearable_unlink,
        name="wearable-unlink",
    ),
    path("device/setup/", views.device_setup, name="device-setup"),
    path("device/verify/", views.device_verify, name="device-verify"),
    path("device/list/", views.device_list, name="device-list"),
    path("device/<uuid:device_id>/", views.device_detail, name="device-detail"),
    path("verify/", views.mfa_verify, name="mfa-verify"),
]
