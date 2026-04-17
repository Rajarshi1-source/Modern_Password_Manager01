"""URL routes for decentralized_identity (mounted at /api/did/)."""

from django.urls import path

from . import views

app_name = "decentralized_identity"

urlpatterns = [
    # DID lifecycle
    path("register/", views.register_did, name="register"),
    path("mine/", views.list_user_dids, name="list-mine"),
    path("resolve/<path:did>/", views.resolve, name="resolve"),
    # Credentials
    path("credentials/issue/", views.issue, name="issue"),
    path("credentials/mine/", views.list_my_credentials, name="list-my-credentials"),
    path(
        "credentials/<uuid:vc_id>/revoke/",
        views.revoke_credential,
        name="revoke",
    ),
    # Presentations
    path("presentations/verify/", views.verify_vp, name="verify-vp"),
    # Sign-in with DID
    path("auth/challenge/", views.sign_in_challenge, name="sign-in-challenge"),
    path("auth/verify/", views.sign_in_verify, name="sign-in-verify"),
    # Revocation status list
    path(
        "revocation/status-list/<str:list_id>/",
        views.status_list,
        name="status-list",
    ),
    # did:web discovery
    path(".well-known/did.json", views.well_known_did_json, name="well-known-did"),
]
