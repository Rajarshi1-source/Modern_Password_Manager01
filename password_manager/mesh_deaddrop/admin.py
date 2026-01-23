"""
Mesh Dead Drop Admin Configuration
====================================

Django admin interface for managing mesh dead drops.

@author Password Manager Team
@created 2026-01-22
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess,
    FragmentTransfer,
    LocationVerificationCache,
)


@admin.register(DeadDrop)
class DeadDropAdmin(admin.ModelAdmin):
    """Admin for dead drops."""
    
    list_display = [
        'title',
        'owner',
        'status_badge',
        'threshold_display',
        'location_display',
        'expires_at',
        'created_at',
    ]
    list_filter = ['status', 'require_ble_verification', 'require_nfc_tap', 'is_active']
    search_fields = ['title', 'owner__username', 'location_hint']
    readonly_fields = ['id', 'secret_hash', 'created_at', 'collected_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'owner', 'title', 'description')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'radius_meters', 'location_hint')
        }),
        ('Threshold', {
            'fields': ('required_fragments', 'total_fragments')
        }),
        ('Security', {
            'fields': (
                'require_ble_verification',
                'require_nfc_tap',
                'min_ble_nodes_required',
                'max_attempts',
                'recipient_email',
            )
        }),
        ('Status', {
            'fields': ('status', 'is_active', 'expires_at', 'collected_at')
        }),
        ('Technical', {
            'fields': ('secret_hash', 'encryption_algorithm'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'distributed': '#17a2b8',
            'active': '#28a745',
            'collected': '#6c757d',
            'expired': '#dc3545',
            'cancelled': '#343a40',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def location_display(self, obj):
        return f"{float(obj.latitude):.4f}, {float(obj.longitude):.4f}"
    location_display.short_description = 'Location'


@admin.register(DeadDropFragment)
class DeadDropFragmentAdmin(admin.ModelAdmin):
    """Admin for fragments."""
    
    list_display = [
        'fragment_index',
        'dead_drop',
        'storage_type',
        'node',
        'is_distributed',
        'is_available',
        'is_collected',
    ]
    list_filter = ['storage_type', 'is_distributed', 'is_available', 'is_collected']
    search_fields = ['dead_drop__title']
    raw_id_fields = ['dead_drop', 'node', 'collected_by']


@admin.register(MeshNode)
class MeshNodeAdmin(admin.ModelAdmin):
    """Admin for mesh nodes."""
    
    list_display = [
        'device_name',
        'device_type',
        'owner',
        'online_badge',
        'trust_badge',
        'fragment_count',
        'last_seen',
    ]
    list_filter = ['device_type', 'is_online', 'is_available_for_storage']
    search_fields = ['device_name', 'owner__username', 'ble_address']
    readonly_fields = ['id', 'registered_at', 'successful_transfers', 'failed_transfers', 'trust_score']
    
    def online_badge(self, obj):
        if obj.is_online:
            return format_html(
                '<span style="color:green;">●</span> Online'
            )
        return format_html(
            '<span style="color:red;">●</span> Offline'
        )
    online_badge.short_description = 'Status'
    
    def trust_badge(self, obj):
        percent = int(obj.trust_score * 100)
        if percent >= 80:
            color = '#28a745'
        elif percent >= 50:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}%</span>',
            color, percent
        )
    trust_badge.short_description = 'Trust'
    
    def fragment_count(self, obj):
        return f"{obj.current_fragment_count}/{obj.max_fragments}"
    fragment_count.short_description = 'Fragments'


@admin.register(NFCBeacon)
class NFCBeaconAdmin(admin.ModelAdmin):
    """Admin for NFC beacons."""
    
    list_display = ['tag_id', 'dead_drop', 'is_active', 'tap_count', 'last_tapped']
    list_filter = ['is_active']
    search_fields = ['tag_id', 'dead_drop__title']
    raw_id_fields = ['dead_drop']


@admin.register(DeadDropAccess)
class DeadDropAccessAdmin(admin.ModelAdmin):
    """Admin for access logs."""
    
    list_display = [
        'dead_drop',
        'accessor',
        'result_badge',
        'verification_summary',
        'fragments_collected',
        'access_time',
    ]
    list_filter = ['result', 'gps_verified', 'ble_verified', 'nfc_verified']
    search_fields = ['dead_drop__title', 'accessor__username']
    raw_id_fields = ['dead_drop', 'accessor']
    readonly_fields = [
        'id', 'access_time', 'claimed_latitude', 'claimed_longitude',
        'ble_node_ids', 'access_ip', 'user_agent',
    ]
    
    def result_badge(self, obj):
        colors = {
            'success': '#28a745',
            'insufficient_fragments': '#ffc107',
            'location_failed': '#dc3545',
            'spoofing_detected': '#dc3545',
            'ble_failed': '#dc3545',
            'nfc_failed': '#dc3545',
            'access_code_wrong': '#dc3545',
            'expired': '#6c757d',
            'locked_out': '#343a40',
            'error': '#dc3545',
        }
        color = colors.get(obj.result, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 6px; '
            'border-radius:3px; font-size:10px;">{}</span>',
            color, obj.result.upper()
        )
    result_badge.short_description = 'Result'
    
    def verification_summary(self, obj):
        parts = []
        if obj.gps_verified:
            parts.append('GPS✓')
        if obj.ble_verified:
            parts.append('BLE✓')
        if obj.nfc_verified:
            parts.append('NFC✓')
        return ' '.join(parts) if parts else '-'
    verification_summary.short_description = 'Verified'


@admin.register(FragmentTransfer)
class FragmentTransferAdmin(admin.ModelAdmin):
    """Admin for fragment transfers."""
    
    list_display = [
        'fragment',
        'from_node',
        'to_node',
        'transfer_successful',
        'transfer_time',
    ]
    list_filter = ['transfer_successful']
    raw_id_fields = ['fragment', 'from_node', 'to_node']


@admin.register(LocationVerificationCache)
class LocationCacheAdmin(admin.ModelAdmin):
    """Admin for location cache."""
    
    list_display = ['user', 'source', 'is_verified', 'recorded_at']
    list_filter = ['source', 'is_verified']
    search_fields = ['user__username']
    raw_id_fields = ['user']
