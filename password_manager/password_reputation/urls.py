"""URL routing for password_reputation (mounted at /api/reputation/)."""

from django.urls import path

from .views import (
    config,
    leaderboard,
    me,
    my_events,
    my_proofs,
    recent_batches,
    submit_proof,
)

urlpatterns = [
    path("submit-proof/", submit_proof, name="reputation-submit-proof"),
    path("me/", me, name="reputation-me"),
    path("events/", my_events, name="reputation-my-events"),
    path("proofs/", my_proofs, name="reputation-my-proofs"),
    path("leaderboard/", leaderboard, name="reputation-leaderboard"),
    path("batches/", recent_batches, name="reputation-batches"),
    path("config/", config, name="reputation-config"),
]
