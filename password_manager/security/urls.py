from django.urls import path, include
from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from .api.darkWebEndpoints import DarkWebViewSet
from .api.account_protection import AccountProtectionViewSet, SocialMediaAccountViewSet
from .api import quantum_rng_views
from .api import genetic_password_views
from .api import chemical_storage_views
from .api import adaptive_password_views
from .api import ocean_entropy_views  # 🌊 Ocean Wave Entropy


@api_view(['GET'])
def security_root(request, format=None):
    """Entry point for security endpoints"""
    return Response({
        'dashboard': reverse('security-dashboard', request=request, format=format),
        'score': reverse('security-score', request=request, format=format),
        'devices': reverse('security-devices', request=request, format=format),
        'social-accounts': reverse('security-social-accounts-list', request=request, format=format),
        'dark-web': reverse('security-dark-web-list', request=request, format=format),
        'health-check': reverse('security-health-check', request=request, format=format),
        'audit-log': reverse('security-audit-log', request=request, format=format),
        'quantum': reverse('quantum-generate-password', request=request, format=format),
        'genetic': reverse('genetic-generate-password', request=request, format=format),
        'chemical': reverse('chemical-encode', request=request, format=format),
        'adaptive': reverse('adaptive-config', request=request, format=format),
    })


# Create a router for viewsets
router = routers.DefaultRouter()
router.register(r'dark-web', DarkWebViewSet, basename='security-dark-web')
router.register(r'social-accounts', SocialMediaAccountViewSet, basename='security-social-accounts')

urlpatterns = [
    path('', security_root, name='security-root'),
    path('', include(router.urls)),
    
    # Security Dashboard endpoints
    path('dashboard/', views.security_dashboard, name='security-dashboard'),
    path('score/', views.security_score, name='security-score'),
    
    # Device Management endpoints
    path('devices/', views.devices_list, name='security-devices'),
    path('devices/<str:device_id>/', views.device_detail, name='security-device-detail'),
    path('devices/<str:device_id>/trust/', views.device_trust, name='security-device-trust'),
    path('devices/<str:device_id>/untrust/', views.device_untrust, name='security-device-untrust'),
    
    # Social Account Management endpoints (additional to the viewset)
    path('social-accounts/<int:account_id>/lock/', views.social_account_lock, name='security-social-account-lock'),
    path('social-accounts/<int:account_id>/unlock/', views.social_account_unlock, name='security-social-account-unlock'),
    
    # Quantum Random Number Generator endpoints
    path('quantum/generate-password/', quantum_rng_views.generate_quantum_password, name='quantum-generate-password'),
    path('quantum/random-bytes/', quantum_rng_views.get_random_bytes, name='quantum-random-bytes'),
    path('quantum/certificate/<uuid:certificate_id>/', quantum_rng_views.get_certificate, name='quantum-certificate'),
    path('quantum/certificates/', quantum_rng_views.list_certificates, name='quantum-certificates'),
    path('quantum/pool-status/', quantum_rng_views.get_pool_status, name='quantum-pool-status'),
    
    # ==========================================================================
    # 🌊 Ocean Wave Entropy endpoints
    # ==========================================================================
    path('ocean/status/', ocean_entropy_views.OceanEntropyStatusView.as_view(), name='ocean-status'),
    path('ocean/buoys/', ocean_entropy_views.OceanBuoyListView.as_view(), name='ocean-buoys'),
    path('ocean/readings/', ocean_entropy_views.OceanReadingsView.as_view(), name='ocean-readings'),
    path('ocean/generate/', ocean_entropy_views.OceanEntropyGenerateView.as_view(), name='ocean-generate'),
    path('ocean/pool/', ocean_entropy_views.OceanPoolStatusView.as_view(), name='ocean-pool'),
    path('ocean/generate-hybrid-password/', ocean_entropy_views.HybridPasswordGenerateView.as_view(), name='ocean-hybrid-password'),
    path('ocean/buoy/<str:buoy_id>/live-data/', ocean_entropy_views.LiveWaveDataView.as_view(), name='ocean-live-data'),
    path('ocean/my-stats/', ocean_entropy_views.UserOceanStatsView.as_view(), name='ocean-my-stats'),
    path('ocean/certificate/<uuid:certificate_id>/', ocean_entropy_views.HybridCertificateView.as_view(), name='ocean-certificate'),
    
    # ==========================================================================
    # Genetic Password Evolution endpoints
    # ==========================================================================
    
    # DNA Provider Connection
    path('genetic/connect/', genetic_password_views.initiate_connection, name='genetic-connect'),
    path('genetic/callback/', genetic_password_views.oauth_callback, name='genetic-callback'),
    path('genetic/upload/', genetic_password_views.upload_dna_file, name='genetic-upload'),
    path('genetic/disconnect/', genetic_password_views.disconnect_dna, name='genetic-disconnect'),
    path('genetic/connection-status/', genetic_password_views.get_connection_status, name='genetic-connection-status'),
    
    # Password Generation
    path('genetic/generate-password/', genetic_password_views.generate_genetic_password, name='genetic-generate-password'),
    
    # Certificates
    path('genetic/certificate/<uuid:certificate_id>/', genetic_password_views.get_certificate, name='genetic-certificate'),
    path('genetic/certificates/', genetic_password_views.list_certificates, name='genetic-certificates'),
    
    # Epigenetic Evolution (Premium)
    path('genetic/evolution-status/', genetic_password_views.get_evolution_status, name='genetic-evolution-status'),
    path('genetic/trigger-evolution/', genetic_password_views.trigger_evolution, name='genetic-trigger-evolution'),
    
    # Preferences
    path('genetic/preferences/', genetic_password_views.update_preferences, name='genetic-preferences'),
    
    # ==========================================================================
    # Chemical Password Storage endpoints
    # ==========================================================================
    
    # DNA Encoding
    path('chemical/encode/', chemical_storage_views.encode_password_to_dna, name='chemical-encode'),
    path('chemical/decode/', chemical_storage_views.decode_dna_to_password, name='chemical-decode'),
    
    # Time-Lock Capsules
    path('chemical/time-lock/', chemical_storage_views.create_time_lock, name='chemical-time-lock'),
    path('chemical/capsule-status/<uuid:capsule_id>/', chemical_storage_views.get_capsule_status, name='chemical-capsule-status'),
    path('chemical/unlock-capsule/<uuid:capsule_id>/', chemical_storage_views.unlock_capsule, name='chemical-unlock-capsule'),
    
    # Lab Synthesis
    path('chemical/synthesis-order/', chemical_storage_views.order_synthesis, name='chemical-synthesis-order'),
    path('chemical/synthesis-status/<str:order_id>/', chemical_storage_views.check_synthesis_status, name='chemical-synthesis-status'),
    path('chemical/sequencing-request/', chemical_storage_views.request_sequencing, name='chemical-sequencing-request'),
    
    # Certificates
    path('chemical/certificates/', chemical_storage_views.list_certificates, name='chemical-certificates'),
    path('chemical/certificate/<uuid:certificate_id>/', chemical_storage_views.get_certificate, name='chemical-certificate'),
    
    # Subscription
    path('chemical/subscription/', chemical_storage_views.get_subscription, name='chemical-subscription'),
    
    # Full Workflow
    path('chemical/store/', chemical_storage_views.store_password_chemically, name='chemical-store'),
    
    # Provider Info
    path('chemical/providers/', chemical_storage_views.list_lab_providers, name='chemical-providers'),
    
    # ==========================================================================
    # Adaptive Password Evolution endpoints
    # ==========================================================================
    
    # Configuration
    path('adaptive/config/', adaptive_password_views.get_adaptive_config, name='adaptive-config'),
    path('adaptive/enable/', adaptive_password_views.enable_adaptive_passwords, name='adaptive-enable'),
    path('adaptive/disable/', adaptive_password_views.disable_adaptive_passwords, name='adaptive-disable'),
    
    # Typing Session Recording
    path('adaptive/record-session/', adaptive_password_views.record_typing_session, name='adaptive-record-session'),
    
    # Adaptation Suggestions
    path('adaptive/suggest/', adaptive_password_views.suggest_adaptation, name='adaptive-suggest'),
    path('adaptive/apply/', adaptive_password_views.apply_adaptation, name='adaptive-apply'),
    path('adaptive/rollback/', adaptive_password_views.rollback_adaptation, name='adaptive-rollback'),
    
    # Profile and History
    path('adaptive/profile/', adaptive_password_views.get_typing_profile, name='adaptive-profile'),
    path('adaptive/history/', adaptive_password_views.get_adaptation_history, name='adaptive-history'),
    path('adaptive/stats/', adaptive_password_views.get_evolution_stats, name='adaptive-stats'),
    
    # Data Management (GDPR)
    path('adaptive/data/', adaptive_password_views.delete_adaptive_data, name='adaptive-delete-data'),
    path('adaptive/export/', adaptive_password_views.export_adaptive_data, name='adaptive-export-data'),
    
    # Feedback
    path('adaptive/feedback/', adaptive_password_views.submit_feedback, name='adaptive-submit-feedback'),
    path('adaptive/feedback/<uuid:adaptation_id>/', adaptive_password_views.get_feedback_for_adaptation, name='adaptive-get-feedback'),
    
    # ==========================================================================
    # Quantum Entanglement-Inspired Key Distribution endpoints
    # ==========================================================================
    
    # Device Pairing
    path('entanglement/initiate/', 
         __import__('security.api.entanglement_views', fromlist=['InitiatePairingView']).InitiatePairingView.as_view(), 
         name='entanglement-initiate'),
    path('entanglement/verify/', 
         __import__('security.api.entanglement_views', fromlist=['VerifyPairingView']).VerifyPairingView.as_view(), 
         name='entanglement-verify'),
    
    # Key Synchronization
    path('entanglement/sync/', 
         __import__('security.api.entanglement_views', fromlist=['SyncKeysView']).SyncKeysView.as_view(), 
         name='entanglement-sync'),
    path('entanglement/rotate/', 
         __import__('security.api.entanglement_views', fromlist=['RotateKeysView']).RotateKeysView.as_view(), 
         name='entanglement-rotate'),
    
    # Status and Analysis
    path('entanglement/status/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['PairStatusView']).PairStatusView.as_view(), 
         name='entanglement-status'),
    path('entanglement/entropy/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['EntropyAnalysisView']).EntropyAnalysisView.as_view(), 
         name='entanglement-entropy'),
    path('entanglement/detail/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['PairDetailView']).PairDetailView.as_view(), 
         name='entanglement-detail'),
    
    # Revocation and Deletion
    path('entanglement/revoke/', 
         __import__('security.api.entanglement_views', fromlist=['RevokeView']).RevokeView.as_view(), 
         name='entanglement-revoke'),
    path('entanglement/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['DeletePairView']).DeletePairView.as_view(), 
         name='entanglement-delete'),
    
    # User's Pairs
    path('entanglement/pairs/', 
         __import__('security.api.entanglement_views', fromlist=['UserPairsView']).UserPairsView.as_view(), 
         name='entanglement-pairs'),
    
    # Entropy History (NEW)
    path('entanglement/entropy-history/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['EntropyHistoryView']).EntropyHistoryView.as_view(), 
         name='entanglement-entropy-history'),
    
    # Anomaly Events (NEW)
    path('entanglement/anomalies/<uuid:pair_id>/', 
         __import__('security.api.entanglement_views', fromlist=['AnomalyListView']).AnomalyListView.as_view(), 
         name='entanglement-anomalies'),
    path('entanglement/resolve-anomaly/', 
         __import__('security.api.entanglement_views', fromlist=['ResolveAnomalyView']).ResolveAnomalyView.as_view(), 
         name='entanglement-resolve-anomaly'),
    
    # ==========================================================================
    # Geofencing & Impossible Travel Detection Endpoints
    # ==========================================================================
    
    # Location Recording
    path('geofence/location/record/', 
         __import__('security.api.geofence_views', fromlist=['RecordLocationView']).RecordLocationView.as_view(), 
         name='geofence-location-record'),
    path('geofence/location/history/', 
         __import__('security.api.geofence_views', fromlist=['LocationHistoryView']).LocationHistoryView.as_view(), 
         name='geofence-location-history'),
    
    # Geofence Zones
    path('geofence/zones/', 
         __import__('security.api.geofence_views', fromlist=['GeofenceZoneListView']).GeofenceZoneListView.as_view(), 
         name='geofence-zones'),
    path('geofence/zones/<uuid:zone_id>/', 
         __import__('security.api.geofence_views', fromlist=['GeofenceZoneDetailView']).GeofenceZoneDetailView.as_view(), 
         name='geofence-zone-detail'),
    path('geofence/check/', 
         __import__('security.api.geofence_views', fromlist=['GeofenceCheckView']).GeofenceCheckView.as_view(), 
         name='geofence-check'),
    
    # Impossible Travel Events
    path('geofence/travel/events/', 
         __import__('security.api.geofence_views', fromlist=['ImpossibleTravelEventListView']).ImpossibleTravelEventListView.as_view(), 
         name='geofence-travel-events'),
    path('geofence/travel/resolve/', 
         __import__('security.api.geofence_views', fromlist=['ResolveTravelEventView']).ResolveTravelEventView.as_view(), 
         name='geofence-travel-resolve'),
    path('geofence/travel/analyze/', 
         __import__('security.api.geofence_views', fromlist=['AnalyzeTravelView']).AnalyzeTravelView.as_view(), 
         name='geofence-travel-analyze'),
    
    # Travel Itineraries
    path('geofence/itinerary/', 
         __import__('security.api.geofence_views', fromlist=['TravelItineraryListView']).TravelItineraryListView.as_view(), 
         name='geofence-itinerary-list'),
    path('geofence/itinerary/<uuid:itinerary_id>/', 
         __import__('security.api.geofence_views', fromlist=['TravelItineraryDetailView']).TravelItineraryDetailView.as_view(), 
         name='geofence-itinerary-detail'),
    path('geofence/travel/verify/', 
         __import__('security.api.geofence_views', fromlist=['VerifyTravelView']).VerifyTravelView.as_view(), 
         name='geofence-travel-verify'),
    
    # ==========================================================================
    # Time-Lock Encryption Endpoints
    # ==========================================================================
    
    # Capsule CRUD
    path('timelock/capsules/', 
         __import__('security.api.time_lock_views', fromlist=['CapsuleListView']).CapsuleListView.as_view(), 
         name='timelock-capsules'),
    path('timelock/capsules/<uuid:capsule_id>/', 
         __import__('security.api.time_lock_views', fromlist=['CapsuleDetailView']).CapsuleDetailView.as_view(), 
         name='timelock-capsule-detail'),
    path('timelock/capsules/<uuid:capsule_id>/status/', 
         __import__('security.api.time_lock_views', fromlist=['CapsuleStatusView']).CapsuleStatusView.as_view(), 
         name='timelock-capsule-status'),
    path('timelock/capsules/<uuid:capsule_id>/unlock/', 
         __import__('security.api.time_lock_views', fromlist=['UnlockCapsuleView']).UnlockCapsuleView.as_view(), 
         name='timelock-capsule-unlock'),
    path('timelock/capsules/<uuid:capsule_id>/cancel/', 
         __import__('security.api.time_lock_views', fromlist=['CancelCapsuleView']).CancelCapsuleView.as_view(), 
         name='timelock-capsule-cancel'),
    
    # Beneficiaries
    path('timelock/beneficiaries/', 
         __import__('security.api.time_lock_views', fromlist=['BeneficiaryListView']).BeneficiaryListView.as_view(), 
         name='timelock-beneficiaries'),
    path('timelock/beneficiaries/<uuid:beneficiary_id>/', 
         __import__('security.api.time_lock_views', fromlist=['BeneficiaryDetailView']).BeneficiaryDetailView.as_view(), 
         name='timelock-beneficiary-detail'),
    
    # Password Wills
    path('timelock/wills/', 
         __import__('security.api.time_lock_views', fromlist=['PasswordWillListView']).PasswordWillListView.as_view(), 
         name='timelock-wills'),
    path('timelock/wills/<uuid:will_id>/checkin/', 
         __import__('security.api.time_lock_views', fromlist=['PasswordWillCheckInView']).PasswordWillCheckInView.as_view(), 
         name='timelock-will-checkin'),
    
    # Escrow Agreements
    path('timelock/escrows/', 
         __import__('security.api.time_lock_views', fromlist=['EscrowListView']).EscrowListView.as_view(), 
         name='timelock-escrows'),
    path('timelock/escrows/<uuid:escrow_id>/approve/', 
         __import__('security.api.time_lock_views', fromlist=['EscrowApproveView']).EscrowApproveView.as_view(), 
         name='timelock-escrow-approve'),
    
    # VDF Verification
    path('timelock/vdf/verify/', 
         __import__('security.api.time_lock_views', fromlist=['VDFVerifyView']).VDFVerifyView.as_view(), 
         name='timelock-vdf-verify'),
    
    # Other endpoints
    path('health-check/', views.health_check, name='security-health-check'),
    path('audit-log/', views.audit_log, name='security-audit-log'),
]


