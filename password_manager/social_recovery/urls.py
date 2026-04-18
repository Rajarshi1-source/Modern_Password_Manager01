"""URL routes for /api/social-recovery/."""
from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path("circles/", views.CircleListCreateView.as_view(), name="social-recovery-circles"),
    path("circles/<uuid:circle_id>/", views.CircleDetailView.as_view(), name="social-recovery-circle-detail"),
    path(
        "vouchers/<str:invitation_token>/accept/",
        views.AcceptInvitationView.as_view(),
        name="social-recovery-voucher-accept",
    ),
    path("requests/", views.InitiateRecoveryView.as_view(), name="social-recovery-request-create"),
    path("requests/<uuid:request_id>/", views.RequestDetailView.as_view(), name="social-recovery-request-detail"),
    path(
        "requests/<uuid:request_id>/attest/",
        views.AttestRequestView.as_view(),
        name="social-recovery-request-attest",
    ),
    path(
        "requests/<uuid:request_id>/complete/",
        views.CompleteRequestView.as_view(),
        name="social-recovery-request-complete",
    ),
    path(
        "requests/<uuid:request_id>/cancel/",
        views.CancelRequestView.as_view(),
        name="social-recovery-request-cancel",
    ),
    path("audit/", views.audit_log_view, name="social-recovery-audit"),
]
