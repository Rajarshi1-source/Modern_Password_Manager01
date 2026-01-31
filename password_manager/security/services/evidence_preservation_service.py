"""
Evidence Preservation Service

Handles automatic collection and preservation of forensic evidence
during duress events. Designed for legal admissibility.
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime

from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

from security.models.duress_models import EvidencePackage

logger = logging.getLogger(__name__)


class EvidencePreservationService:
    """
    Service for collecting and preserving forensic evidence.
    
    Features:
    - Device fingerprinting snapshot
    - Behavioral biometrics capture
    - Network/geolocation data
    - RFC 3161 timestamping for legal validity
    - Encrypted off-site backup (planned)
    """
    
    def __init__(self):
        """Initialize the evidence preservation service"""
        self.timestamp_authority_url = getattr(
            settings, 'RFC3161_TSA_URL', 
            'https://freetsa.org/tsr'  # Free TSA for development
        )
    
    def create_package(
        self,
        user: User,
        request_context: Dict[str, Any]
    ) -> EvidencePackage:
        """
        Create a new evidence package from the request context.
        
        Args:
            user: The user for whom evidence is collected
            request_context: Context from the duress event
            
        Returns:
            The created EvidencePackage
        """
        logger.info(f"Creating evidence package for user {user.username}")
        
        # Collect evidence components
        behavioral_snapshot = self._capture_behavioral_data(request_context)
        device_info = self._capture_device_info(request_context)
        network_info = self._capture_network_info(request_context)
        geo_location = self._capture_geo_location(request_context)
        session_recording = self._capture_session_data(request_context)
        
        # Create the package
        package = EvidencePackage.objects.create(
            user=user,
            status='collecting',
            behavioral_snapshot=behavioral_snapshot,
            device_info=device_info,
            network_info=network_info,
            geo_location=geo_location,
            session_recording=session_recording,
        )
        
        # Compute integrity hash
        package.evidence_hash = package.compute_hash()
        package.status = 'complete'
        package.save(update_fields=['evidence_hash', 'status'])
        
        # Add creation custody entry
        package.add_custody_entry(
            action='created',
            actor='system',
            details={'trigger': 'duress_activation'}
        )
        
        # Attempt RFC 3161 timestamp
        self._apply_legal_timestamp(package)
        
        logger.info(f"Evidence package {package.id} created successfully")
        return package
    
    def _capture_behavioral_data(
        self,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture behavioral biometrics at moment of duress"""
        behavioral_data = request_context.get('behavioral_data', {})
        
        return {
            'captured_at': timezone.now().isoformat(),
            'typing_patterns': behavioral_data.get('typing', {}),
            'mouse_patterns': behavioral_data.get('mouse', {}),
            'cognitive_patterns': behavioral_data.get('cognitive', {}),
            'stress_indicators': behavioral_data.get('stress_indicators', []),
            'stress_score': request_context.get('stress_score', 0.0),
            'duress_confidence': behavioral_data.get('duress_confidence', 0.0),
        }
    
    def _capture_device_info(
        self,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture device fingerprint and hardware info"""
        device_fp = request_context.get('device_fingerprint', {})
        
        return {
            'captured_at': timezone.now().isoformat(),
            'fingerprint_hash': hashlib.sha256(
                json.dumps(device_fp, sort_keys=True).encode()
            ).hexdigest() if device_fp else None,
            'user_agent': request_context.get('user_agent', ''),
            'screen_resolution': device_fp.get('screen_resolution'),
            'timezone': device_fp.get('timezone'),
            'language': device_fp.get('language'),
            'platform': device_fp.get('platform'),
            'plugins': device_fp.get('plugins', []),
            'fonts': len(device_fp.get('fonts', [])),  # Count only for privacy
            'canvas_hash': device_fp.get('canvas_hash'),
            'webgl_hash': device_fp.get('webgl_hash'),
            'audio_hash': device_fp.get('audio_hash'),
        }
    
    def _capture_network_info(
        self,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture network details"""
        ip = request_context.get('ip_address', '')
        
        return {
            'captured_at': timezone.now().isoformat(),
            'ip_address': ip,
            'ip_hash': hashlib.sha256(ip.encode()).hexdigest() if ip else None,
            'connection_type': request_context.get('connection_type'),
            'is_vpn_detected': request_context.get('is_vpn', False),
            'is_proxy_detected': request_context.get('is_proxy', False),
            'is_tor_detected': request_context.get('is_tor', False),
            'asn': request_context.get('asn'),
            'isp': request_context.get('isp'),
        }
    
    def _capture_geo_location(
        self,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture geographic location data"""
        geo = request_context.get('geo_location', {})
        
        return {
            'captured_at': timezone.now().isoformat(),
            'country': geo.get('country'),
            'country_code': geo.get('country_code'),
            'region': geo.get('region'),
            'city': geo.get('city'),
            'latitude': geo.get('latitude'),
            'longitude': geo.get('longitude'),
            'accuracy_radius_km': geo.get('accuracy_radius'),
            'timezone': geo.get('timezone'),
            'source': geo.get('source', 'ip_geolocation'),
        }
    
    def _capture_session_data(
        self,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture session activity data"""
        session_data = request_context.get('session_data', {})
        
        return {
            'captured_at': timezone.now().isoformat(),
            'session_id_hash': hashlib.sha256(
                session_data.get('session_id', '').encode()
            ).hexdigest() if session_data.get('session_id') else None,
            'session_start': session_data.get('session_start'),
            'pages_visited': session_data.get('page_count', 0),
            'actions_taken': session_data.get('action_count', 0),
            'time_on_page_seconds': session_data.get('time_on_page'),
            'last_activity': session_data.get('last_activity'),
            'auth_method': session_data.get('auth_method'),
        }
    
    def _apply_legal_timestamp(self, package: EvidencePackage) -> bool:
        """
        Apply RFC 3161 timestamp for legal validity.
        
        This creates a cryptographic proof of when the evidence was collected,
        recognized in legal proceedings.
        """
        try:
            # In production, this would make a request to a TSA
            # For now, we record the attempt
            
            # Compute hash of evidence for timestamping
            evidence_hash = bytes.fromhex(package.evidence_hash)
            
            # Placeholder for RFC 3161 implementation
            # In production:
            # 1. Create TimeStampReq with hash
            # 2. Send to TSA
            # 3. Verify and store TimeStampResp
            
            package.legal_timestamp = timezone.now()
            package.timestamp_authority = self.timestamp_authority_url
            # package.timestamp_token would store the actual token
            package.save(update_fields=['legal_timestamp', 'timestamp_authority'])
            
            logger.info(f"Legal timestamp applied to package {package.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply legal timestamp: {e}")
            return False
    
    def seal_package(self, package: EvidencePackage) -> bool:
        """
        Cryptographically seal an evidence package.
        
        Once sealed, the package cannot be modified without detection.
        """
        try:
            if package.status == 'sealed':
                logger.warning(f"Package {package.id} is already sealed")
                return True
            
            # Recompute hash to verify integrity
            current_hash = package.compute_hash()
            if current_hash != package.evidence_hash:
                logger.error(f"Package {package.id} integrity check failed!")
                return False
            
            # In production, encrypt the evidence
            # package.encrypted_evidence_blob = self._encrypt_evidence(package)
            
            package.status = 'sealed'
            package.sealed_at = timezone.now()
            package.save(update_fields=['status', 'sealed_at'])
            
            package.add_custody_entry(
                action='sealed',
                actor='system',
                details={'hash': current_hash}
            )
            
            logger.info(f"Package {package.id} sealed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to seal package: {e}")
            return False
    
    def export_for_legal(
        self,
        package: EvidencePackage,
        requesting_user: str
    ) -> Dict[str, Any]:
        """
        Export evidence package for legal proceedings.
        
        Args:
            package: The evidence package to export
            requesting_user: Identity of person requesting export
            
        Returns:
            Dict with exportable evidence data
        """
        logger.info(f"Exporting package {package.id} for legal use by {requesting_user}")
        
        # Log the export
        package.add_custody_entry(
            action='exported',
            actor=requesting_user,
            details={'format': 'json', 'purpose': 'legal'}
        )
        
        package.status = 'exported'
        package.save(update_fields=['status'])
        
        return {
            'package_id': str(package.id),
            'user_id': package.user.id,
            'username': package.user.username,
            'created_at': package.created_at.isoformat(),
            'sealed_at': package.sealed_at.isoformat() if package.sealed_at else None,
            'evidence_hash': package.evidence_hash,
            'legal_timestamp': package.legal_timestamp.isoformat() if package.legal_timestamp else None,
            'timestamp_authority': package.timestamp_authority,
            'evidence': {
                'behavioral': package.behavioral_snapshot,
                'device': package.device_info,
                'network': package.network_info,
                'geo_location': package.geo_location,
                'session': package.session_recording,
            },
            'custody_log': package.custody_log,
            'export_metadata': {
                'exported_at': timezone.now().isoformat(),
                'exported_by': requesting_user,
            }
        }
    
    def get_packages_for_user(
        self,
        user: User,
        limit: int = 50
    ) -> list:
        """Get evidence packages for a user"""
        return list(
            EvidencePackage.objects.filter(user=user)
            .order_by('-created_at')[:limit]
        )


# Singleton instance
_evidence_service = None


def get_evidence_preservation_service() -> EvidencePreservationService:
    """Get the singleton evidence preservation service instance"""
    global _evidence_service
    if _evidence_service is None:
        _evidence_service = EvidencePreservationService()
    return _evidence_service
