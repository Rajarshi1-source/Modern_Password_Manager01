from django.urls import path

from stegano_vault import views

app_name = "stegano_vault"

urlpatterns = [
    path("embed/", views.stego_embed, name="embed"),
    path("extract/", views.stego_extract, name="extract"),
    path("store/", views.stego_store, name="store"),
    path("events/", views.stego_events, name="events"),
    path("config/", views.stego_config, name="config"),
    path("", views.stego_vault_collection, name="collection"),
    path("<uuid:vault_id>/", views.stego_vault_detail, name="detail"),
]
