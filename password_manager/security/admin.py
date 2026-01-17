from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserDevice, 
    SocialMediaAccount,
    QuantumEntropyBatch,
    QuantumPasswordCertificate,
    QuantumPoolStatus,
    GeneticSubscription,
    DNAConnection,
    GeneticPasswordCertificate,
    GeneticEvolutionLog,
    DNAConsentRecord,
)


# =============================================================================
# Security Models Admin
# =============================================================================

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'user', 'device_type', 'is_trusted', 'last_seen')
    list_filter = ('device_type', 'is_trusted')
    search_fields = ('device_name', 'user__username', 'browser', 'os')
    readonly_fields = ('device_id', 'fingerprint', 'created_at', 'last_seen')


@admin.register(SocialMediaAccount)
class SocialMediaAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'platform', 'user', 'status', 'auto_lock_enabled')
    list_filter = ('platform', 'status', 'auto_lock_enabled')
    search_fields = ('username', 'user__username')


# =============================================================================
# Quantum RNG Models Admin
# =============================================================================

@admin.register(QuantumEntropyBatch)
class QuantumEntropyBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'bytes_fetched', 'fetched_at')
    list_filter = ('provider', 'fetched_at')
    readonly_fields = ('id', 'fetched_at')


@admin.register(QuantumPasswordCertificate)
class QuantumPasswordCertificateAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'quantum_source', 'generation_timestamp')
    list_filter = ('provider', 'quantum_source')
    search_fields = ('user__username',)
    readonly_fields = ('id', 'generation_timestamp', 'signature')


@admin.register(QuantumPoolStatus)
class QuantumPoolStatusAdmin(admin.ModelAdmin):
    list_display = ('health', 'total_bytes_available', 'batch_count', 'recorded_at')
    list_filter = ('health',)
    readonly_fields = ('recorded_at',)


# =============================================================================
# Genetic Password Evolution Admin
# =============================================================================

@admin.register(GeneticSubscription)
class GeneticSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 
        'tier', 
        'status', 
        'epigenetic_evolution_enabled',
        'passwords_generated',
        'trial_status',
    )
    list_filter = ('tier', 'status', 'epigenetic_evolution_enabled')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'trial_started_at')
    
    fieldsets = (
        ('User Info', {
            'fields': ('id', 'user', 'tier', 'status')
        }),
        ('Trial Period', {
            'fields': ('trial_started_at', 'trial_expires_at')
        }),
        ('Subscription Period', {
            'fields': ('subscription_started_at', 'subscription_expires_at')
        }),
        ('Features', {
            'fields': ('epigenetic_evolution_enabled', 'quantum_combination_enabled')
        }),
        ('Usage', {
            'fields': ('passwords_generated', 'evolutions_triggered')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def trial_status(self, obj):
        if obj.is_trial_active():
            return format_html('<span style="color: green;">✓ Active</span>')
        elif obj.tier == 'trial':
            return format_html('<span style="color: red;">✗ Expired</span>')
        return '—'
    trial_status.short_description = 'Trial Status'


@admin.register(DNAConnection)
class DNAConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'provider',
        'status',
        'snp_count',
        'evolution_generation',
        'connected_at',
        'gdpr_consent',
    )
    list_filter = ('provider', 'status', 'gdpr_consent', 'combine_with_quantum')
    search_fields = ('user__username', 'user__email', 'genetic_hash_prefix')
    readonly_fields = (
        'id', 
        'genetic_hash_prefix', 
        'connected_at', 
        'last_sync',
        'consent_given_at',
    )
    
    fieldsets = (
        ('Connection', {
            'fields': ('id', 'user', 'provider', 'status')
        }),
        ('Genetic Data (Read-only)', {
            'fields': ('genetic_hash_prefix', 'snp_count'),
            'description': 'Raw DNA data is never stored - only hash prefixes.'
        }),
        ('Evolution', {
            'fields': ('evolution_generation', 'last_biological_age', 'last_epigenetic_update')
        }),
        ('Preferences', {
            'fields': ('combine_with_quantum',)
        }),
        ('Consent & Compliance', {
            'fields': ('consent_given_at', 'consent_version', 'gdpr_consent')
        }),
        ('Timestamps', {
            'fields': ('connected_at', 'last_sync', 'is_active'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GeneticPasswordCertificate)
class GeneticPasswordCertificateAdmin(admin.ModelAdmin):
    list_display = (
        'certificate_id_short',
        'user',
        'provider',
        'snp_markers_used',
        'evolution_generation',
        'combined_with_quantum',
        'generation_timestamp',
    )
    list_filter = ('provider', 'combined_with_quantum', 'generation_timestamp')
    search_fields = ('user__username', 'password_hash_prefix', 'genetic_hash_prefix')
    readonly_fields = ('id', 'generation_timestamp', 'signature')
    
    def certificate_id_short(self, obj):
        return f"GC-{str(obj.id)[:8]}"
    certificate_id_short.short_description = 'Certificate'


@admin.register(GeneticEvolutionLog)
class GeneticEvolutionLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'trigger_type',
        'evolution_change',
        'passwords_evolved',
        'success',
        'triggered_at',
    )
    list_filter = ('trigger_type', 'success', 'triggered_at')
    search_fields = ('user__username',)
    readonly_fields = ('triggered_at', 'completed_at')
    
    def evolution_change(self, obj):
        return f"Gen {obj.old_evolution_gen} → {obj.new_evolution_gen}"
    evolution_change.short_description = 'Evolution'


@admin.register(DNAConsentRecord)
class DNAConsentRecordAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'consent_type',
        'consent_version',
        'consented',
        'consented_at',
        'withdrawn_at',
    )
    list_filter = ('consent_type', 'consented', 'consent_version')
    search_fields = ('user__username', 'consent_type')
    readonly_fields = ('id', 'consented_at', 'withdrawn_at', 'consent_text_hash')

