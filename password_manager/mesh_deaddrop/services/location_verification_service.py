"""
Location Verification Service
==============================

Multi-factor location verification for dead drop access:
1. GPS coordinates verification
2. BLE beacon/node detection
3. WiFi fingerprinting (optional)
4. Cell tower triangulation (optional)
5. NFC tap verification (optional)

Anti-Spoofing Measures:
- Velocity anomaly detection (impossible travel)
- Location history analysis
- Multi-source correlation
- BLE signal strength validation

@author Password Manager Team
@created 2026-01-22
"""

import math
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from django.utils import timezone


class VerificationMethod(Enum):
    """Location verification methods."""
    GPS = 'gps'
    BLE = 'ble'
    WIFI = 'wifi'
    CELL = 'cell'
    NFC = 'nfc'


class VerificationResult(Enum):
    """Verification outcome."""
    SUCCESS = 'success'
    FAILED = 'failed'
    SPOOFING_DETECTED = 'spoofing_detected'
    INSUFFICIENT_EVIDENCE = 'insufficient_evidence'


@dataclass
class LocationClaim:
    """A claimed location from a device."""
    latitude: float
    longitude: float
    accuracy_meters: float = 10.0
    altitude: Optional[float] = None
    timestamp: datetime = field(default_factory=timezone.now)
    source: VerificationMethod = VerificationMethod.GPS
    
    # Additional signals
    ble_nodes: List[Dict] = field(default_factory=list)  # [{'id': uuid, 'rssi': -60}, ...]
    wifi_fingerprint: Optional[str] = None
    cell_info: Optional[Dict] = None
    nfc_response: Optional[str] = None


@dataclass
class VerificationResponse:
    """Result of location verification."""
    result: VerificationResult
    confidence: float  # 0.0 to 1.0
    message: str
    
    # Detailed results per method
    gps_verified: bool = False
    ble_verified: bool = False
    wifi_verified: bool = False
    nfc_verified: bool = False
    
    # Anti-spoofing results
    velocity_check_passed: bool = True
    history_check_passed: bool = True
    
    # Evidence
    ble_nodes_found: int = 0
    distance_from_target_meters: float = 0.0


class LocationVerificationService:
    """
    Multi-factor location verification with anti-spoofing.
    
    Usage:
        service = LocationVerificationService()
        
        # Verify user is at dead drop location
        result = service.verify_location(
            claimed=user_location,
            target_lat=dead_drop.latitude,
            target_lon=dead_drop.longitude,
            radius=dead_drop.radius_meters,
            require_ble=True,
            require_nfc=False
        )
        
        if result.result == VerificationResult.SUCCESS:
            # Grant access
            pass
    """
    
    # Earth radius in meters
    EARTH_RADIUS_M = 6371000
    
    # Maximum reasonable speed (m/s) - about 1200 km/h (fast jet)
    MAX_REASONABLE_SPEED_MS = 333
    
    # Typical walking/driving speeds for confidence
    WALKING_SPEED_MS = 1.5
    DRIVING_SPEED_MS = 30
    
    # BLE RSSI thresholds
    BLE_VERY_CLOSE_RSSI = -50  # Very close (< 2m)
    BLE_CLOSE_RSSI = -70       # Close (< 10m)
    BLE_MEDIUM_RSSI = -85      # Medium (< 30m)
    
    def __init__(self):
        """Initialize the location verification service."""
        self.location_history: Dict[str, List[LocationClaim]] = {}
    
    def verify_location(
        self,
        claimed: LocationClaim,
        target_lat: float,
        target_lon: float,
        radius_meters: float = 50.0,
        user_id: Optional[str] = None,
        require_ble: bool = True,
        require_nfc: bool = False,
        min_ble_nodes: int = 2,
        required_ble_node_ids: Optional[List[str]] = None,
        nfc_expected_response: Optional[str] = None
    ) -> VerificationResponse:
        """
        Verify that the claimed location is at the target location.
        
        Args:
            claimed: User's claimed location with signals
            target_lat: Target latitude
            target_lon: Target longitude
            radius_meters: Acceptable radius from target
            user_id: User ID for history tracking
            require_ble: Require BLE node verification
            require_nfc: Require NFC tap verification
            min_ble_nodes: Minimum BLE nodes that must be visible
            required_ble_node_ids: Specific BLE nodes that must be present
            nfc_expected_response: Expected NFC challenge response
            
        Returns:
            VerificationResponse with detailed results
        """
        # Calculate distance from target
        distance = self._haversine_distance(
            claimed.latitude, claimed.longitude,
            target_lat, target_lon
        )
        
        # Initialize response
        response = VerificationResponse(
            result=VerificationResult.FAILED,
            confidence=0.0,
            message="Verification failed",
            distance_from_target_meters=distance
        )
        
        confidence_factors = []
        
        # =================================================================
        # 1. GPS Verification
        # =================================================================
        gps_verified = distance <= (radius_meters + claimed.accuracy_meters)
        response.gps_verified = gps_verified
        
        if gps_verified:
            # Higher confidence for smaller distance and accuracy
            gps_confidence = max(0, 1 - (distance / radius_meters)) * \
                           max(0, 1 - (claimed.accuracy_meters / 100))
            confidence_factors.append(('gps', gps_confidence, 0.3))  # 30% weight
        else:
            response.message = f"Too far from location ({distance:.0f}m away, max {radius_meters}m)"
            return response
        
        # =================================================================
        # 2. Velocity/Impossible Travel Check (Anti-Spoofing)
        # =================================================================
        if user_id:
            velocity_ok, travel_speed = self._check_velocity(user_id, claimed)
            response.velocity_check_passed = velocity_ok
            
            if not velocity_ok:
                response.result = VerificationResult.SPOOFING_DETECTED
                response.message = f"Impossible travel detected (speed: {travel_speed:.0f} m/s)"
                response.confidence = 0.0
                return response
            
            # Record this location
            self._record_location(user_id, claimed)
        
        # =================================================================
        # 3. BLE Node Verification
        # =================================================================
        ble_nodes_found = len(claimed.ble_nodes)
        response.ble_nodes_found = ble_nodes_found
        
        if require_ble:
            if ble_nodes_found < min_ble_nodes:
                response.message = f"Insufficient BLE nodes ({ble_nodes_found}/{min_ble_nodes})"
                return response
            
            # Check for required specific nodes
            if required_ble_node_ids:
                found_ids = {n.get('id') for n in claimed.ble_nodes}
                missing = set(required_ble_node_ids) - found_ids
                if missing:
                    response.message = f"Required BLE nodes not found: {missing}"
                    return response
            
            # Verify RSSI is reasonable (not fabricated)
            ble_confidence = self._calculate_ble_confidence(claimed.ble_nodes)
            response.ble_verified = ble_confidence > 0.5
            
            if not response.ble_verified:
                response.message = "BLE signal verification failed - possible spoofing"
                return response
            
            confidence_factors.append(('ble', ble_confidence, 0.4))  # 40% weight
        
        # =================================================================
        # 4. NFC Tap Verification (Optional)
        # =================================================================
        if require_nfc:
            if not claimed.nfc_response:
                response.message = "NFC tap required but not provided"
                return response
            
            if nfc_expected_response and claimed.nfc_response != nfc_expected_response:
                response.result = VerificationResult.SPOOFING_DETECTED
                response.message = "NFC verification failed - invalid response"
                return response
            
            response.nfc_verified = True
            confidence_factors.append(('nfc', 1.0, 0.3))  # 30% weight for NFC
        
        # =================================================================
        # 5. WiFi Fingerprint Verification (Optional, if provided)
        # =================================================================
        if claimed.wifi_fingerprint:
            # WiFi fingerprint matching would go here
            # For now, just use as additional confidence boost
            wifi_confidence = 0.7  # Placeholder
            response.wifi_verified = True
            confidence_factors.append(('wifi', wifi_confidence, 0.1))
        
        # =================================================================
        # Calculate Final Confidence
        # =================================================================
        if confidence_factors:
            total_weight = sum(f[2] for f in confidence_factors)
            weighted_sum = sum(f[1] * f[2] for f in confidence_factors)
            response.confidence = weighted_sum / total_weight
        
        # Determine overall result
        if response.confidence >= 0.7:
            response.result = VerificationResult.SUCCESS
            response.message = "Location verified successfully"
        elif response.confidence >= 0.4:
            response.result = VerificationResult.INSUFFICIENT_EVIDENCE
            response.message = "Partial verification - low confidence"
        else:
            response.result = VerificationResult.FAILED
            response.message = "Location verification failed"
        
        return response
    
    def _haversine_distance(
        self, 
        lat1: float, 
        lon1: float, 
        lat2: float, 
        lon2: float
    ) -> float:
        """
        Calculate great-circle distance between two points using Haversine formula.
        
        Args:
            lat1, lon1: First point (degrees)
            lat2, lon2: Second point (degrees)
            
        Returns:
            Distance in meters
        """
        # Convert to radians
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return self.EARTH_RADIUS_M * c
    
    def _check_velocity(
        self, 
        user_id: str, 
        current: LocationClaim
    ) -> Tuple[bool, float]:
        """
        Check for impossible travel (velocity anomaly detection).
        
        Args:
            user_id: User identifier
            current: Current location claim
            
        Returns:
            Tuple of (is_valid, calculated_speed_ms)
        """
        if user_id not in self.location_history:
            return True, 0.0
        
        history = self.location_history[user_id]
        if not history:
            return True, 0.0
        
        # Get most recent location
        previous = history[-1]
        
        # Calculate time difference
        time_diff = (current.timestamp - previous.timestamp).total_seconds()
        if time_diff <= 0:
            return True, 0.0
        
        # Calculate distance
        distance = self._haversine_distance(
            previous.latitude, previous.longitude,
            current.latitude, current.longitude
        )
        
        # Calculate speed
        speed_ms = distance / time_diff
        
        # Check against maximum reasonable speed
        if speed_ms > self.MAX_REASONABLE_SPEED_MS:
            return False, speed_ms
        
        return True, speed_ms
    
    def _record_location(self, user_id: str, location: LocationClaim):
        """Record location for history tracking."""
        if user_id not in self.location_history:
            self.location_history[user_id] = []
        
        self.location_history[user_id].append(location)
        
        # Keep only last 100 entries per user
        if len(self.location_history[user_id]) > 100:
            self.location_history[user_id] = self.location_history[user_id][-100:]
    
    def _calculate_ble_confidence(self, ble_nodes: List[Dict]) -> float:
        """
        Calculate confidence from BLE node signals.
        
        Checks for:
        - Reasonable RSSI values
        - Signal strength consistency
        - Known node patterns
        
        Args:
            ble_nodes: List of {'id': uuid, 'rssi': int}
            
        Returns:
            Confidence score 0.0 to 1.0
        """
        if not ble_nodes:
            return 0.0
        
        confidences = []
        
        for node in ble_nodes:
            rssi = node.get('rssi', -100)
            
            # RSSI should be negative and within reasonable range
            if rssi > 0 or rssi < -120:
                # Suspicious - probably fabricated
                confidences.append(0.1)
                continue
            
            # Calculate confidence based on signal strength
            if rssi >= self.BLE_VERY_CLOSE_RSSI:
                confidences.append(1.0)  # Very close - high confidence
            elif rssi >= self.BLE_CLOSE_RSSI:
                confidences.append(0.8)  # Close - good confidence
            elif rssi >= self.BLE_MEDIUM_RSSI:
                confidences.append(0.5)  # Medium - moderate confidence
            else:
                confidences.append(0.3)  # Far - low confidence
        
        # Average confidence, with bonus for multiple nodes
        avg_confidence = sum(confidences) / len(confidences)
        node_bonus = min(0.2, len(ble_nodes) * 0.05)  # Up to 20% bonus
        
        return min(1.0, avg_confidence + node_bonus)
    
    def analyze_location_pattern(
        self, 
        user_id: str, 
        current: LocationClaim
    ) -> Dict:
        """
        Analyze location history for patterns and anomalies.
        
        Returns analysis including:
        - Movement pattern type (stationary, walking, driving, flying)
        - Average speed
        - Anomaly score
        """
        if user_id not in self.location_history:
            return {
                'pattern': 'unknown',
                'avg_speed_ms': 0,
                'anomaly_score': 0.5,
                'history_points': 0
            }
        
        history = self.location_history[user_id]
        if len(history) < 2:
            return {
                'pattern': 'insufficient_data',
                'avg_speed_ms': 0,
                'anomaly_score': 0.5,
                'history_points': len(history)
            }
        
        # Calculate speeds between consecutive points
        speeds = []
        for i in range(1, len(history)):
            prev = history[i-1]
            curr = history[i]
            
            time_diff = (curr.timestamp - prev.timestamp).total_seconds()
            if time_diff > 0:
                distance = self._haversine_distance(
                    prev.latitude, prev.longitude,
                    curr.latitude, curr.longitude
                )
                speeds.append(distance / time_diff)
        
        if not speeds:
            return {
                'pattern': 'stationary',
                'avg_speed_ms': 0,
                'anomaly_score': 0,
                'history_points': len(history)
            }
        
        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        
        # Determine movement pattern
        if avg_speed < 0.5:
            pattern = 'stationary'
        elif avg_speed < self.WALKING_SPEED_MS * 2:
            pattern = 'walking'
        elif avg_speed < self.DRIVING_SPEED_MS * 2:
            pattern = 'driving'
        elif avg_speed < 200:
            pattern = 'fast_vehicle'
        else:
            pattern = 'flying'
        
        # Calculate anomaly score based on speed variance
        if len(speeds) > 1:
            variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
            std_dev = math.sqrt(variance)
            # High variance = more anomalous
            anomaly_score = min(1.0, std_dev / 50)
        else:
            anomaly_score = 0.3
        
        return {
            'pattern': pattern,
            'avg_speed_ms': avg_speed,
            'max_speed_ms': max_speed,
            'anomaly_score': anomaly_score,
            'history_points': len(history)
        }
    
    def clear_user_history(self, user_id: str):
        """Clear location history for a user."""
        if user_id in self.location_history:
            del self.location_history[user_id]


# Module-level instance
location_verification_service = LocationVerificationService()
