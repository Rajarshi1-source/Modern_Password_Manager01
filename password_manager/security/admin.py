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
    # Chemical Storage Models
    ChemicalStorageSubscription,
    DNAEncodedPassword,
    TimeLockCapsule,
    ChemicalStorageCertificate,
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


# =============================================================================
# Chemical Password Storage Models Admin
# =============================================================================

@admin.register(ChemicalStorageSubscription)
class ChemicalStorageSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tier', 'status', 'passwords_stored', 'max_passwords', 'lab_provider')
    list_filter = ('tier', 'status', 'lab_provider')
    search_fields = ('user__username',)
    readonly_fields = ('id', 'started_at', 'created_at', 'updated_at')


@admin.register(DNAEncodedPassword)
class DNAEncodedPasswordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'service_name', 'status', 'sequence_length_bp', 'synthesis_cost_usd', 'synthesis_provider')
    list_filter = ('status', 'synthesis_provider', 'has_error_correction', 'time_lock_enabled')
    search_fields = ('user__username', 'service_name', 'synthesis_order_id', 'physical_sample_id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'sequence_hash', 'password_hash_prefix')



@admin.register(TimeLockCapsule)
class TimeLockCapsuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'mode', 'status', 'unlock_at', 'capsule_type')
    list_filter = ('mode', 'status', 'capsule_type')
    search_fields = ('owner__username',)
    readonly_fields = ('id', 'created_at', 'encrypted_data', 'encryption_key_encrypted')
    
    def time_remaining(self, obj):
        remaining = obj.time_remaining()
        if remaining == 0:
            return "Unlockable"
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return f"{hours}h {minutes}m"
    time_remaining.short_description = 'Time Remaining'



@admin.register(ChemicalStorageCertificate)
class ChemicalStorageCertificateAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'encoding_method', 'synthesis_provider', 'time_lock_enabled', 'created_at')
    list_filter = ('encoding_method', 'synthesis_provider', 'time_lock_enabled')
    search_fields = ('user__username', 'sequence_hash')
    readonly_fields = ('id', 'created_at', 'signature', 'sequence_hash')


# =============================================================================
# 🔮 Predictive Password Expiration Admin
# =============================================================================

from .models import (
    PasswordPatternProfile,
    ThreatActorTTP,
    IndustryThreatLevel,
    PredictiveExpirationRule,
    PasswordRotationEvent,
    ThreatIntelFeed,
    PredictiveExpirationSettings,
)


@admin.register(PasswordPatternProfile)
class PasswordPatternProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'total_passwords_analyzed',
        'weak_patterns_detected',
        'overall_pattern_risk_score',
        'last_analysis_at',
    )
    list_filter = (
        'uses_common_base_words',
        'uses_keyboard_patterns',
        'uses_leet_substitutions',
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'structure_fingerprint',
        'created_at',
        'updated_at',
        'last_analysis_at',
    )
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Pattern Statistics', {
            'fields': (
                'char_class_distribution',
                'avg_password_length',
                'length_variance',
                'min_length_used',
                'max_length_used',
            )
        }),
        ('Pattern Detection', {
            'fields': (
                'uses_common_base_words',
                'uses_keyboard_patterns',
                'uses_date_patterns',
                'uses_leet_substitutions',
                'common_mutations_used',
            )
        }),
        ('Risk Score', {
            'fields': (
                'total_passwords_analyzed',
                'weak_patterns_detected',
                'overall_pattern_risk_score',
            )
        }),
        ('Timestamps', {
            'fields': ('last_analysis_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ThreatActorTTP)
class ThreatActorTTPAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'actor_type',
        'threat_level',
        'is_currently_active',
        'first_observed',
        'last_active',
    )
    list_filter = (
        'actor_type',
        'threat_level',
        'is_currently_active',
    )
    search_fields = ('name', 'aliases', 'description')
    readonly_fields = ('actor_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Identity', {
            'fields': ('actor_id', 'name', 'aliases', 'description')
        }),
        ('Classification', {
            'fields': ('actor_type', 'threat_level', 'is_currently_active')
        }),
        ('Targeting', {
            'fields': ('target_industries', 'target_regions')
        }),
        ('TTPs', {
            'fields': ('password_patterns_exploited', 'attack_techniques')
        }),
        ('Timeline', {
            'fields': ('first_observed', 'last_active', 'source')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(IndustryThreatLevel)
class IndustryThreatLevelAdmin(admin.ModelAdmin):
    list_display = (
        'industry_name',
        'industry_code',
        'current_threat_level',
        'threat_score',
        'active_campaigns_count',
        'threat_trend',
    )
    list_filter = ('current_threat_level', 'threat_trend')
    search_fields = ('industry_name', 'industry_code')
    readonly_fields = ('created_at', 'last_assessment_at')


@admin.register(PredictiveExpirationRule)
class PredictiveExpirationRuleAdmin(admin.ModelAdmin):
    list_display = (
        'credential_domain',
        'user',
        'risk_level',
        'risk_score_display',
        'recommended_action',
        'user_acknowledged',
        'last_evaluated_at',
    )
    list_filter = (
        'risk_level',
        'recommended_action',
        'is_active',
        'user_acknowledged',
    )
    search_fields = (
        'user__username',
        'credential_domain',
    )
    readonly_fields = (
        'rule_id',
        'credential_id',
        'created_at',
        'updated_at',
        'last_evaluated_at',
    )
    
    fieldsets = (
        ('Credential', {
            'fields': ('rule_id', 'user', 'credential_id', 'credential_domain')
        }),
        ('Risk Assessment', {
            'fields': (
                'risk_level',
                'risk_score',
                'prediction_confidence',
                'threat_factors',
            )
        }),
        ('Prediction', {
            'fields': (
                'predicted_compromise_date',
                'pattern_similarity_score',
                'industry_threat_correlation',
            )
        }),
        ('Action', {
            'fields': (
                'recommended_action',
                'recommended_rotation_date',
                'is_active',
            )
        }),
        ('User Response', {
            'fields': (
                'user_acknowledged',
                'user_acknowledged_at',
                'last_notification_sent',
                'notification_count',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_evaluated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def risk_score_display(self, obj):
        score = obj.risk_score
        color = 'green' if score < 0.4 else 'orange' if score < 0.7 else 'red'
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, score
        )
    risk_score_display.short_description = 'Risk Score'


@admin.register(PasswordRotationEvent)
class PasswordRotationEventAdmin(admin.ModelAdmin):
    list_display = (
        'event_id_short',
        'user',
        'credential_domain',
        'rotation_type',
        'outcome',
        'initiated_at',
    )
    list_filter = ('rotation_type', 'outcome')
    search_fields = ('user__username', 'credential_domain')
    readonly_fields = (
        'event_id',
        'initiated_at',
        'completed_at',
    )
    
    def event_id_short(self, obj):
        return f"ROT-{str(obj.event_id)[:8]}"
    event_id_short.short_description = 'Event ID'


@admin.register(ThreatIntelFeed)
class ThreatIntelFeedAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'feed_type',
        'is_active',
        'is_healthy',
        'reliability_score',
        'last_sync_at',
    )
    list_filter = ('feed_type', 'is_active', 'is_healthy')
    search_fields = ('name', 'description')
    readonly_fields = (
        'feed_id',
        'last_sync_at',
        'last_sync_items_count',
        'total_items_ingested',
        'created_at',
        'updated_at',
    )


@admin.register(PredictiveExpirationSettings)
class PredictiveExpirationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'is_enabled',
        'auto_rotation_enabled',
        'force_rotation_threshold',
        'industry',
    )
    list_filter = (
        'is_enabled',
        'auto_rotation_enabled',
        'industry',
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Feature Toggles', {
            'fields': ('is_enabled', 'auto_rotation_enabled')
        }),
        ('Thresholds', {
            'fields': ('force_rotation_threshold', 'warning_threshold')
        }),
        ('Context', {
            'fields': ('industry', 'organization_size')
        }),
        ('Notifications', {
            'fields': (
                'notify_on_high_risk',
                'notify_on_medium_risk',
                'notification_frequency_hours',
            )
        }),
        ('Filtering', {
            'fields': ('include_all_credentials', 'exclude_domains')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

