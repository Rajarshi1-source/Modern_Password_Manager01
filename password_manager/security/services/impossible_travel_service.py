"""
Impossible Travel Detection Service
====================================

Physics-based security service for detecting impossible travel patterns.
Uses GPS coordinates, time-distance calculations, and airline API integration.

Speed Thresholds (km/h):
- Walking: 6 km/h
- Driving: 200 km/h
- High-speed rail: 400 km/h
- Commercial flight: 920 km/h (Mach 0.85)
- Supersonic/Impossible: > 1200 km/h
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from math import radians, sin, cos, sqrt, atan2, asin
from typing import Optional, List, Tuple, Dict, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from ..models import LocationHistory, ImpossibleTravelEvent

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes and Enums
# =============================================================================

class TravelMode(Enum):
    """Inferred travel modes based on speed."""
    WALKING = "walking"
    DRIVING = "driving"
    TRAIN = "train"
    FLIGHT = "flight"
    SUPERSONIC = "supersonic"
    UNKNOWN = "unknown"


class TravelSeverity(Enum):
    """Severity levels for travel anomalies."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TravelAction(Enum):
    """Actions to take for travel anomalies."""
    ALLOW = "allowed"
    CHALLENGE = "challenged"
    BLOCK = "blocked"
    VERIFY = "travel_verified"


@dataclass
class Coordinates:
    """GPS coordinates."""
    latitude: float
    longitude: float
    accuracy_meters: float = 0.0
    altitude: Optional[float] = None
    source: str = "ip_fallback"
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)


@dataclass
class TravelAnalysis:
    """Result of travel plausibility analysis."""
    distance_km: float
    time_seconds: int
    required_speed_kmh: float
    max_allowed_speed_kmh: float = 920.0
    inferred_mode: TravelMode = TravelMode.UNKNOWN
    is_plausible: bool = True
    severity: TravelSeverity = TravelSeverity.NONE
    action: TravelAction = TravelAction.ALLOW
    risk_score: int = 0
    is_cloned_session: bool = False
    matching_itinerary: Optional[Any] = None
    recommendations: List[str] = field(default_factory=list)


@dataclass
class GeofenceCheck:
    """Result of geofence zone checking."""
    is_in_trusted_zone: bool = False
    zone_name: Optional[str] = None
    zone_id: Optional[str] = None
    distance_to_nearest_zone: float = 0.0
    requires_mfa: bool = True


# =============================================================================
# Speed Thresholds Configuration
# =============================================================================

class SpeedThresholds:
    """Speed thresholds for travel mode inference (km/h)."""
    
    WALKING_MAX = float(getattr(settings, 'TRAVEL_SPEED_WALKING', 6))
    CYCLING_MAX = float(getattr(settings, 'TRAVEL_SPEED_CYCLING', 40))
    DRIVING_MAX = float(getattr(settings, 'TRAVEL_SPEED_DRIVING', 200))
    HIGH_SPEED_RAIL_MAX = float(getattr(settings, 'TRAVEL_SPEED_RAIL', 400))
    COMMERCIAL_FLIGHT_MAX = float(getattr(settings, 'TRAVEL_SPEED_FLIGHT', 920))
    SUPERSONIC_THRESHOLD = float(getattr(settings, 'TRAVEL_SPEED_SUPERSONIC', 1200))
    
    @classmethod
    def infer_mode(cls, speed_kmh: float) -> TravelMode:
        """Infer travel mode from required speed."""
        if speed_kmh <= cls.WALKING_MAX:
            return TravelMode.WALKING
        elif speed_kmh <= cls.DRIVING_MAX:
            return TravelMode.DRIVING
        elif speed_kmh <= cls.HIGH_SPEED_RAIL_MAX:
            return TravelMode.TRAIN
        elif speed_kmh <= cls.COMMERCIAL_FLIGHT_MAX:
            return TravelMode.FLIGHT
        else:
            return TravelMode.SUPERSONIC
    
    @classmethod
    def get_severity(cls, speed_kmh: float) -> TravelSeverity:
        """Determine severity based on required speed."""
        if speed_kmh <= cls.DRIVING_MAX:
            return TravelSeverity.NONE
        elif speed_kmh <= cls.HIGH_SPEED_RAIL_MAX:
            return TravelSeverity.LOW
        elif speed_kmh <= cls.COMMERCIAL_FLIGHT_MAX:
            return TravelSeverity.MEDIUM
        elif speed_kmh <= cls.SUPERSONIC_THRESHOLD:
            return TravelSeverity.HIGH
        else:
            return TravelSeverity.CRITICAL
    
    @classmethod
    def get_action(cls, speed_kmh: float, has_itinerary: bool = False) -> TravelAction:
        """Determine action based on speed and context."""
        if speed_kmh <= cls.DRIVING_MAX:
            return TravelAction.ALLOW
        elif speed_kmh <= cls.COMMERCIAL_FLIGHT_MAX:
            return TravelAction.CHALLENGE if not has_itinerary else TravelAction.VERIFY
        else:
            return TravelAction.BLOCK


# =============================================================================
# Impossible Travel Service
# =============================================================================

class ImpossibleTravelService:
    """
    Physics-based impossible travel detection service.
    
    Analyzes login locations to detect:
    - Impossible travel (faster than commercial flight)
    - Cloned sessions (simultaneous logins from distant locations)
    - Suspicious travel patterns
    """
    
    EARTH_RADIUS_KM = 6371.0
    
    def __init__(self):
        """Initialize the service."""
        self.thresholds = SpeedThresholds()
        self._airline_service = None
    
    @property
    def airline_service(self):
        """Lazy-load airline API service."""
        if self._airline_service is None:
            try:
                from .airline_api_service import AirlineAPIService
                self._airline_service = AirlineAPIService()
            except Exception as e:
                logger.warning(f"Airline API service not available: {e}")
        return self._airline_service
    
    # =========================================================================
    # Distance Calculation (Haversine Formula)
    # =========================================================================
    
    def calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate great-circle distance using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates (decimal degrees)
            lat2, lon2: Second point coordinates (decimal degrees)
            
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_r, lon1_r = radians(lat1), radians(lon1)
        lat2_r, lon2_r = radians(lat2), radians(lon2)
        
        # Differences
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        
        # Haversine formula
        a = sin(dlat/2)**2 + cos(lat1_r) * cos(lat2_r) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return self.EARTH_RADIUS_KM * c
    
    def calculate_distance_from_coords(
        self,
        coords1: Coordinates,
        coords2: Coordinates
    ) -> float:
        """Calculate distance between two Coordinates objects."""
        return self.calculate_distance(
            coords1.latitude, coords1.longitude,
            coords2.latitude, coords2.longitude
        )
    
    # =========================================================================
    # Speed Calculation
    # =========================================================================
    
    def calculate_required_speed(
        self,
        distance_km: float,
        time_seconds: int
    ) -> float:
        """
        Calculate required speed to travel a distance in given time.
        
        Args:
            distance_km: Distance in kilometers
            time_seconds: Time in seconds
            
        Returns:
            Speed in km/h
        """
        if time_seconds <= 0:
            return float('inf')
        
        hours = time_seconds / 3600.0
        return distance_km / hours
    
    # =========================================================================
    # Travel Analysis
    # =========================================================================
    
    def analyze_travel(
        self,
        user: User,
        new_location: 'Coordinates',
        new_timestamp: Optional[datetime] = None
    ) -> TravelAnalysis:
        """
        Analyze travel from previous location to new location.
        
        Args:
            user: The user to analyze
            new_location: New login location
            new_timestamp: Timestamp of new location (defaults to now)
            
        Returns:
            TravelAnalysis with plausibility assessment
        """
        from ..models import LocationHistory, TravelItinerary
        
        new_timestamp = new_timestamp or timezone.now()
        
        # Get previous location
        previous = LocationHistory.objects.filter(
            user=user
        ).order_by('-timestamp').first()
        
        if not previous:
            # First location for user - no travel to analyze
            return TravelAnalysis(
                distance_km=0,
                time_seconds=0,
                required_speed_kmh=0,
                is_plausible=True,
                severity=TravelSeverity.NONE,
                action=TravelAction.ALLOW
            )
        
        # Calculate distance
        distance_km = self.calculate_distance(
            float(previous.latitude), float(previous.longitude),
            new_location.latitude, new_location.longitude
        )
        
        # Calculate time difference
        time_delta = new_timestamp - previous.timestamp
        time_seconds = int(time_delta.total_seconds())
        
        # Calculate required speed
        if time_seconds <= 0:
            required_speed = float('inf')
        else:
            required_speed = self.calculate_required_speed(distance_km, time_seconds)
        
        # Infer travel mode
        travel_mode = SpeedThresholds.infer_mode(required_speed)
        severity = SpeedThresholds.get_severity(required_speed)
        
        # Check for matching itinerary
        matching_itinerary = self._find_matching_itinerary(
            user, previous.timestamp, new_timestamp
        )
        has_itinerary = matching_itinerary is not None
        
        # Determine action
        action = SpeedThresholds.get_action(required_speed, has_itinerary)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(
            required_speed, distance_km, time_seconds, has_itinerary
        )
        
        # Check for cloned session
        is_cloned = self._detect_cloned_session(user, previous, new_location)
        if is_cloned:
            severity = TravelSeverity.CRITICAL
            action = TravelAction.BLOCK
            risk_score = min(100, risk_score + 50)
        
        # Build recommendations
        recommendations = self._build_recommendations(
            travel_mode, severity, action, has_itinerary
        )
        
        return TravelAnalysis(
            distance_km=distance_km,
            time_seconds=time_seconds,
            required_speed_kmh=required_speed,
            max_allowed_speed_kmh=SpeedThresholds.COMMERCIAL_FLIGHT_MAX,
            inferred_mode=travel_mode,
            is_plausible=(travel_mode != TravelMode.SUPERSONIC),
            severity=severity,
            action=action,
            risk_score=risk_score,
            is_cloned_session=is_cloned,
            matching_itinerary=matching_itinerary,
            recommendations=recommendations
        )
    
    def _find_matching_itinerary(
        self,
        user: User,
        departure_after: datetime,
        arrival_before: datetime
    ) -> Optional[Any]:
        """Find a matching travel itinerary for the timeframe."""
        from ..models import TravelItinerary
        
        try:
            return TravelItinerary.objects.filter(
                user=user,
                is_active=True,
                departure_time__lte=departure_after + timedelta(hours=3),
                arrival_time__gte=arrival_before - timedelta(hours=3)
            ).first()
        except Exception as e:
            logger.error(f"Error finding itinerary: {e}")
            return None
    
    def _calculate_risk_score(
        self,
        speed_kmh: float,
        distance_km: float,
        time_seconds: int,
        has_itinerary: bool
    ) -> int:
        """Calculate risk score (0-100)."""
        score = 0
        
        # Base score from speed
        if speed_kmh > SpeedThresholds.SUPERSONIC_THRESHOLD:
            score = 100  # Impossible
        elif speed_kmh > SpeedThresholds.COMMERCIAL_FLIGHT_MAX:
            score = 80  # Very suspicious
        elif speed_kmh > SpeedThresholds.HIGH_SPEED_RAIL_MAX:
            score = 50  # Likely flight
        elif speed_kmh > SpeedThresholds.DRIVING_MAX:
            score = 30  # Possible with fast transit
        else:
            score = 0  # Normal
        
        # Reduce if has matching itinerary
        if has_itinerary:
            score = max(0, score - 30)
        
        # Short time windows are more suspicious
        if time_seconds < 300 and distance_km > 10:  # 5 min, 10km
            score = min(100, score + 20)
        
        return score
    
    def _detect_cloned_session(
        self,
        user: User,
        previous_location: 'LocationHistory',
        new_location: Coordinates
    ) -> bool:
        """
        Detect if this might be a cloned session.
        
        Two logins within a very short time from impossible distances
        suggests session cloning.
        """
        from ..models import LocationHistory
        
        # Check for other recent locations within 5 minutes
        recent_window = timezone.now() - timedelta(minutes=5)
        
        recent_locations = LocationHistory.objects.filter(
            user=user,
            timestamp__gte=recent_window
        ).exclude(id=previous_location.id)
        
        for loc in recent_locations:
            distance = self.calculate_distance(
                float(loc.latitude), float(loc.longitude),
                new_location.latitude, new_location.longitude
            )
            
            time_diff = (timezone.now() - loc.timestamp).total_seconds()
            
            if distance > 100 and time_diff < 300:  # >100km in <5min
                logger.warning(
                    f"Potential cloned session for user {user.id}: "
                    f"{distance:.1f}km in {time_diff:.0f}s"
                )
                return True
        
        return False
    
    def _build_recommendations(
        self,
        mode: TravelMode,
        severity: TravelSeverity,
        action: TravelAction,
        has_itinerary: bool
    ) -> List[str]:
        """Build list of recommendations for the user."""
        recommendations = []
        
        if severity == TravelSeverity.CRITICAL:
            recommendations.append("This login appears impossible based on physics.")
            recommendations.append("If this was not you, change your password immediately.")
            
        elif severity == TravelSeverity.HIGH:
            recommendations.append("This travel speed exceeds commercial flight capability.")
            if not has_itinerary:
                recommendations.append("Consider registering your travel plans.")
                
        elif severity == TravelSeverity.MEDIUM:
            if not has_itinerary:
                recommendations.append("Consider adding your flight itinerary for faster verification.")
        
        if action == TravelAction.CHALLENGE:
            recommendations.append("Please complete MFA verification to continue.")
        elif action == TravelAction.BLOCK:
            recommendations.append("Access has been temporarily blocked for security.")
        
        return recommendations
    
    # =========================================================================
    # Location Recording
    # =========================================================================
    
    def record_location(
        self,
        user: User,
        latitude: float,
        longitude: float,
        ip_address: str,
        source: str = "ip_fallback",
        accuracy_meters: float = 0.0,
        altitude: Optional[float] = None,
        device=None,
        login_attempt=None
    ) -> 'LocationHistory':
        """
        Record a new location for a user.
        
        Args:
            user: The user
            latitude, longitude: GPS coordinates
            ip_address: Client IP address
            source: Location source ('gps', 'network', 'ip_fallback')
            accuracy_meters: GPS accuracy
            altitude: Altitude in meters
            device: Associated UserDevice
            login_attempt: Associated LoginAttempt
            
        Returns:
            Created LocationHistory object
        """
        from ..models import LocationHistory
        
        # Get IP-based location for fallback/verification
        ip_location = self._get_location_from_ip(ip_address)
        
        location = LocationHistory.objects.create(
            user=user,
            device=device,
            latitude=Decimal(str(latitude)),
            longitude=Decimal(str(longitude)),
            accuracy_meters=accuracy_meters,
            altitude=altitude,
            ip_address=ip_address,
            ip_location_city=ip_location.get('city', ''),
            ip_location_country=ip_location.get('country', ''),
            ip_location_country_code=ip_location.get('country_code', ''),
            source=source,
            login_attempt=login_attempt,
            is_ntp_verified=True  # Server timestamp is always verified
        )
        
        return location
    
    def _get_location_from_ip(self, ip_address: str) -> Dict[str, str]:
        """Get location from IP address using GeoIP."""
        if not ip_address or ip_address in ('127.0.0.1', '::1', 'localhost'):
            return {}
        
        geo_db_path = getattr(settings, 'GEOIP_DB_PATH', None)
        
        if geo_db_path:
            try:
                import geoip2.database
                with geoip2.database.Reader(f"{geo_db_path}/GeoLite2-City.mmdb") as reader:
                    response = reader.city(ip_address)
                    return {
                        'city': response.city.name or '',
                        'country': response.country.name or '',
                        'country_code': response.country.iso_code or '',
                        'latitude': response.location.latitude,
                        'longitude': response.location.longitude
                    }
            except Exception as e:
                logger.warning(f"GeoIP2 lookup failed: {e}")
        
        # Fallback to external service
        try:
            import requests
            response = requests.get(
                f"https://ipinfo.io/{ip_address}/json",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                loc = data.get('loc', '0,0').split(',')
                return {
                    'city': data.get('city', ''),
                    'country': data.get('country', ''),
                    'country_code': data.get('country', ''),
                    'latitude': float(loc[0]) if len(loc) > 0 else 0,
                    'longitude': float(loc[1]) if len(loc) > 1 else 0
                }
        except Exception as e:
            logger.error(f"IP geolocation failed: {e}")
        
        return {}
    
    # =========================================================================
    # Geofence Checking
    # =========================================================================
    
    def check_geofence_zones(
        self,
        user: User,
        latitude: float,
        longitude: float
    ) -> GeofenceCheck:
        """
        Check if coordinates are within any of user's trusted zones.
        
        Args:
            user: The user
            latitude, longitude: Current coordinates
            
        Returns:
            GeofenceCheck result
        """
        from ..models import GeofenceZone
        
        zones = GeofenceZone.objects.filter(user=user, is_active=True)
        
        if not zones.exists():
            return GeofenceCheck(requires_mfa=True)
        
        nearest_distance = float('inf')
        
        for zone in zones:
            if zone.contains_point(latitude, longitude):
                return GeofenceCheck(
                    is_in_trusted_zone=True,
                    zone_name=zone.name,
                    zone_id=str(zone.id),
                    distance_to_nearest_zone=0,
                    requires_mfa=not zone.is_always_trusted
                )
            else:
                # Calculate distance to zone center
                distance = self.calculate_distance(
                    float(zone.latitude), float(zone.longitude),
                    latitude, longitude
                ) * 1000  # Convert to meters
                distance_to_edge = distance - zone.radius_meters
                nearest_distance = min(nearest_distance, distance_to_edge)
        
        # Outside all zones
        any_require_mfa = zones.filter(require_mfa_outside=True).exists()
        
        return GeofenceCheck(
            is_in_trusted_zone=False,
            distance_to_nearest_zone=nearest_distance,
            requires_mfa=any_require_mfa
        )
    
    # =========================================================================
    # Event Recording
    # =========================================================================
    
    def record_impossible_travel_event(
        self,
        user: User,
        source_location: 'LocationHistory',
        destination_location: 'LocationHistory',
        analysis: TravelAnalysis
    ) -> 'ImpossibleTravelEvent':
        """Record an impossible travel event."""
        from ..models import ImpossibleTravelEvent
        
        event = ImpossibleTravelEvent.objects.create(
            user=user,
            source_location=source_location,
            destination_location=destination_location,
            distance_km=analysis.distance_km,
            time_difference_seconds=analysis.time_seconds,
            required_speed_kmh=analysis.required_speed_kmh,
            max_allowed_speed_kmh=analysis.max_allowed_speed_kmh,
            inferred_travel_mode=analysis.inferred_mode.value,
            severity=analysis.severity.value,
            risk_score=analysis.risk_score,
            action_taken=analysis.action.value,
            is_cloned_session=analysis.is_cloned_session
        )
        
        logger.warning(
            f"Impossible travel detected for user {user.id}: "
            f"{analysis.distance_km:.1f}km in {analysis.time_seconds}s "
            f"({analysis.required_speed_kmh:.1f} km/h)"
        )
        
        return event


# Create singleton instance
impossible_travel_service = ImpossibleTravelService()
