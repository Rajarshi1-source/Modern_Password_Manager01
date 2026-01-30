"""
Storm Chase Service
====================

Service for managing Storm Chase Mode - detecting hurricane/storm conditions
and maximizing entropy collection during severe weather events.

"During hurricanes, buoys have MAXIMUM entropy!" 🌀

Storm Chase Mode provides:
- Real-time storm detection from NOAA buoy data
- Active storm alert management with caching
- Priority buoy selection for storm-affected regions
- Enhanced entropy generation during severe weather

Thresholds (NOAA/NWS classifications):
- Wave Height: ≥4m (storm), ≥6m (severe), ≥9m (extreme/hurricane)
- Wind Speed: ≥17 m/s (storm), ≥24 m/s (severe), ≥32 m/s (extreme)
- Pressure: ≤1000 hPa (low), ≤990 hPa (very low), ≤980 hPa (extreme)

@author Password Manager Team
@created 2026-01-30
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from security.services.noaa_api_client import (
    NOAABuoyClient,
    BuoyReading,
    StormSeverity,
    StormConditions,
    PRIORITY_BUOYS,
    ALL_BUOYS,
    get_noaa_client,
)
from security.services.ocean_cache import OceanEntropyCache

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class StormAlert:
    """
    Active storm alert from a buoy.
    
    Represents a buoy that is currently detecting storm conditions,
    with details about severity and entropy bonus.
    """
    buoy_id: str
    buoy_name: str
    region: str
    latitude: float
    longitude: float
    severity: StormSeverity
    conditions: StormConditions
    detected_at: datetime
    reading: Optional[BuoyReading] = None
    
    @property
    def entropy_bonus(self) -> float:
        """Get entropy bonus from storm conditions."""
        return self.conditions.entropy_bonus
    
    @property
    def severity_label(self) -> str:
        """Human-readable severity label."""
        labels = {
            StormSeverity.NONE: "Normal",
            StormSeverity.STORM: "⚠️ Storm",
            StormSeverity.SEVERE: "🌊 Severe Storm",
            StormSeverity.EXTREME: "🌀 Hurricane/Extreme",
        }
        return labels.get(self.severity, "Unknown")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            'buoy_id': self.buoy_id,
            'buoy_name': self.buoy_name,
            'region': self.region,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'severity': self.severity.value,
            'severity_label': self.severity_label,
            'conditions': self.conditions.to_dict(),
            'entropy_bonus': self.entropy_bonus,
            'detected_at': self.detected_at.isoformat(),
            'wave_height_m': self.reading.wave_height_m if self.reading else None,
            'wind_speed_mps': self.reading.wind_speed_mps if self.reading else None,
            'pressure_hpa': self.reading.pressure_hpa if self.reading else None,
        }


@dataclass
class StormChaseStatus:
    """
    Overall Storm Chase Mode status.
    """
    is_active: bool
    active_storms_count: int
    most_severe: Optional[StormSeverity]
    max_entropy_bonus: float
    regions_affected: List[str]
    storm_alerts: List[StormAlert] = field(default_factory=list)
    last_scan: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'is_active': self.is_active,
            'active_storms_count': self.active_storms_count,
            'most_severe': self.most_severe.value if self.most_severe else None,
            'max_entropy_bonus': self.max_entropy_bonus,
            'regions_affected': self.regions_affected,
            'storm_alerts': [a.to_dict() for a in self.storm_alerts],
            'last_scan': self.last_scan.isoformat() if self.last_scan else None,
        }


# =============================================================================
# Storm Chase Service
# =============================================================================

class StormChaseService:
    """
    Manages storm detection and entropy maximization.
    
    "Storm Chase Mode: During hurricanes, buoys have MAXIMUM entropy!"
    
    Features:
    - Real-time storm detection from all monitored buoys
    - Active storm alert tracking with Redis caching
    - Priority entropy collection from storm-affected buoys
    - Storm chase mode toggle for user preferences
    """
    
    # Storm alert cache TTL (5 minutes)
    STORM_ALERT_TTL = 300
    
    # Scan interval for active storm detection
    SCAN_INTERVAL_SECONDS = 60
    
    def __init__(self):
        self._client = get_noaa_client()
        self._cache = OceanEntropyCache()
        self._last_scan: Optional[datetime] = None
        self._active_alerts: Dict[str, StormAlert] = {}
    
    async def scan_for_storms(self) -> List[StormAlert]:
        """
        Scan all monitored buoys for storm conditions.
        
        Returns list of StormAlert objects for buoys with active storms.
        """
        logger.info("🌀 Scanning for storm conditions...")
        
        alerts: List[StormAlert] = []
        
        # Scan all regions
        for region, buoys in PRIORITY_BUOYS.items():
            buoy_ids = [b.buoy_id for b in buoys]
            
            try:
                # Fetch readings from region
                readings = await self._client.fetch_multiple_buoys(buoy_ids)
                
                for buoy_id, reading in readings.items():
                    # Detect storm conditions
                    conditions = reading.detect_storm_conditions()
                    
                    if conditions.is_storm:
                        # Get buoy location info
                        buoy_info = ALL_BUOYS.get(buoy_id)
                        
                        alert = StormAlert(
                            buoy_id=buoy_id,
                            buoy_name=buoy_info.name if buoy_info else buoy_id,
                            region=region,
                            latitude=reading.latitude or (buoy_info.latitude if buoy_info else 0),
                            longitude=reading.longitude or (buoy_info.longitude if buoy_info else 0),
                            severity=conditions.severity,
                            conditions=conditions,
                            detected_at=datetime.utcnow(),
                            reading=reading,
                        )
                        
                        alerts.append(alert)
                        self._active_alerts[buoy_id] = alert
                        
                        # Cache storm alert
                        self._cache_storm_alert(alert)
                        
                        logger.info(
                            f"  🌊 Storm detected at {buoy_info.name if buoy_info else buoy_id}: "
                            f"{conditions.severity.value} (bonus: +{conditions.entropy_bonus:.2f})"
                        )
            
            except Exception as e:
                logger.warning(f"Failed to scan region {region}: {e}")
        
        self._last_scan = datetime.utcnow()
        
        logger.info(f"🌀 Storm scan complete: {len(alerts)} active storm(s) detected")
        
        return alerts
    
    def _cache_storm_alert(self, alert: StormAlert) -> None:
        """Cache a storm alert for quick access."""
        try:
            self._cache.set(
                f"storm_alert:{alert.buoy_id}",
                alert.to_dict(),
                ttl=self.STORM_ALERT_TTL
            )
        except Exception as e:
            logger.warning(f"Failed to cache storm alert: {e}")
    
    async def get_active_storms(self) -> List[StormAlert]:
        """
        Get list of active storm alerts.
        
        Will trigger a new scan if the last scan is stale.
        """
        # Check if we need to rescan
        if (self._last_scan is None or 
            datetime.utcnow() - self._last_scan > timedelta(seconds=self.SCAN_INTERVAL_SECONDS)):
            await self.scan_for_storms()
        
        return list(self._active_alerts.values())
    
    async def get_storm_buoys(self) -> List[BuoyReading]:
        """
        Get readings from buoys with active storm conditions.
        
        These buoys provide MAXIMUM entropy during storms!
        """
        alerts = await self.get_active_storms()
        return [a.reading for a in alerts if a.reading is not None]
    
    async def get_storm_chase_status(self) -> StormChaseStatus:
        """
        Get overall Storm Chase Mode status.
        """
        alerts = await self.get_active_storms()
        
        if not alerts:
            return StormChaseStatus(
                is_active=False,
                active_storms_count=0,
                most_severe=None,
                max_entropy_bonus=0.0,
                regions_affected=[],
                storm_alerts=[],
                last_scan=self._last_scan,
            )
        
        # Find most severe and max bonus
        most_severe = max(alerts, key=lambda a: a.conditions.entropy_bonus).severity
        max_bonus = max(a.entropy_bonus for a in alerts)
        regions = list(set(a.region for a in alerts))
        
        return StormChaseStatus(
            is_active=True,
            active_storms_count=len(alerts),
            most_severe=most_severe,
            max_entropy_bonus=max_bonus,
            regions_affected=regions,
            storm_alerts=alerts,
            last_scan=self._last_scan,
        )
    
    async def generate_storm_entropy(self, count: int) -> Tuple[bytes, str, List[str]]:
        """
        Generate entropy prioritizing storm-affected buoys.
        
        During storms, we get MAXIMUM entropy from the chaos!
        
        Args:
            count: Number of bytes to generate
            
        Returns:
            Tuple of (entropy_bytes, source_id, storm_buoy_ids)
        """
        from security.services.ocean_wave_entropy_service import EntropyExtractor
        
        # Get storm buoys first
        storm_readings = await self.get_storm_buoys()
        
        if not storm_readings:
            # No active storms, fall back to regular entropy
            logger.info("No active storms, using regular entropy generation")
            from security.services.ocean_wave_entropy_service import generate_ocean_entropy
            bytes_result, source_id = await generate_ocean_entropy(count)
            return bytes_result, source_id, []
        
        # Extract entropy from storm readings (maximum chaos!)
        entropy_bytes, min_entropy = EntropyExtractor.extract_entropy_from_readings(
            storm_readings,
            target_bytes=count,
            debias=True
        )
        
        storm_buoy_ids = [r.buoy_id for r in storm_readings]
        source_id = f"storm:{','.join(storm_buoy_ids[:3])}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        
        logger.info(
            f"🌀 Generated {len(entropy_bytes)} STORM entropy bytes from {len(storm_readings)} buoys "
            f"(min-entropy: {min_entropy:.2f} bits/byte)"
        )
        
        return entropy_bytes, source_id, storm_buoy_ids
    
    async def get_regional_storm_status(self, region: str) -> Dict[str, Any]:
        """
        Get storm status for a specific region.
        """
        alerts = await self.get_active_storms()
        regional_alerts = [a for a in alerts if a.region == region]
        
        return {
            'region': region,
            'has_storms': len(regional_alerts) > 0,
            'storm_count': len(regional_alerts),
            'alerts': [a.to_dict() for a in regional_alerts],
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_storm_chase_service: Optional[StormChaseService] = None


def get_storm_chase_service() -> StormChaseService:
    """Get or create the storm chase service singleton."""
    global _storm_chase_service
    if _storm_chase_service is None:
        _storm_chase_service = StormChaseService()
    return _storm_chase_service
