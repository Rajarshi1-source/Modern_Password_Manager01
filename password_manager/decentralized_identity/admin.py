from django.contrib import admin

from .models import (
    CredentialSchema,
    IssuerKey,
    RevocationList,
    SignInChallenge,
    UserDID,
    VCPresentation,
    VerifiableCredential,
)


@admin.register(IssuerKey)
class IssuerKeyAdmin(admin.ModelAdmin):
    list_display = ("kid", "algorithm", "did_web_identifier", "is_active", "created_at")
    list_filter = ("algorithm", "is_active")


@admin.register(UserDID)
class UserDIDAdmin(admin.ModelAdmin):
    list_display = ("did_string", "user", "algorithm", "is_primary", "created_at")
    search_fields = ("did_string", "user__username")


@admin.register(CredentialSchema)
class CredentialSchemaAdmin(admin.ModelAdmin):
    list_display = ("schema_id", "name", "version", "created_at")


@admin.register(VerifiableCredential)
class VerifiableCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "schema", "subject_did", "status", "issued_at", "expires_at")
    list_filter = ("status", "schema")
    search_fields = ("subject_did", "issuer_did")


@admin.register(VCPresentation)
class VCPresentationAdmin(admin.ModelAdmin):
    list_display = ("id", "holder_did", "verified", "presented_at")
    list_filter = ("verified",)


@admin.register(SignInChallenge)
class SignInChallengeAdmin(admin.ModelAdmin):
    list_display = ("did_string", "nonce", "expires_at", "consumed")
    list_filter = ("consumed",)


@admin.register(RevocationList)
class RevocationListAdmin(admin.ModelAdmin):
    list_display = ("list_id", "size", "updated_at")
