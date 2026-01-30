"""
NOAA Buoy API Client
=====================

Client for fetching real-time oceanographic data from NOAA's
National Data Buoy Center (NDBC) for entropy harvesting.

Data sources:
- Standard Meteorological Data (stdmet)
- Wave spectral data
- Real-time text files

API Endpoints:
- https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt
- https://www.ndbc.noaa.gov/data/latest_obs/{station_id}.txt

@author Password Manager Team
@created 2026-01-23
"""

import os
import re
import asyncio
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from enum import Enum

# HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Storm Chase Mode - Storm Severity Detection
# =============================================================================

class StormSeverity(Enum):
    """Storm severity levels for entropy bonus calculation."""
    NONE = "none"
    STORM = "storm"           # Elevated conditions
    SEVERE = "severe"         # Severe storm
    EXTREME = "extreme"       # Hurricane/Typhoon conditions


@dataclass
class StormConditions:
    """
    Detected storm conditions from buoy readings.
    
    Used for "Storm Chase Mode" - during hurricanes and severe storms,
    buoys report maximum chaos, providing excellent entropy!
    
    Thresholds based on NOAA/NWS classifications:
    - Wave Height: ≥4m (storm), ≥6m (severe), ≥9m (extreme/hurricane)
    - Wind Speed: ≥17 m/s (storm), ≥24 m/s (severe), ≥32 m/s (extreme)
    - Pressure: ≤1000 hPa (low), ≤990 hPa (very low), ≤980 hPa (extreme)
    """
    severity: StormSeverity
    is_storm: bool
    wave_height_factor: float  # 0.0-1.0 contribution from waves
    wind_factor: float         # 0.0-1.0 contribution from wind
    pressure_factor: float     # 0.0-1.0 contribution from pressure drop
    entropy_bonus: float       # Bonus added to quality score
    
    # Storm detection thresholds
    WAVE_STORM_M = 4.0
    WAVE_SEVERE_M = 6.0
    WAVE_EXTREME_M = 9.0
    
    WIND_STORM_MPS = 17.0    # ~38 mph / ~61 km/h
    WIND_SEVERE_MPS = 24.0   # ~54 mph / ~86 km/h
    WIND_EXTREME_MPS = 32.0  # ~72 mph / ~115 km/h (hurricane)
    
    PRESSURE_LOW_HPA = 1000.0
    PRESSURE_VERY_LOW_HPA = 990.0
    PRESSURE_EXTREME_HPA = 980.0
    
    # Entropy bonuses per severity level
    BONUS_STORM = 0.15
    BONUS_SEVERE = 0.25
    BONUS_EXTREME = 0.35
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize storm conditions for API response."""
        return {
            'severity': self.severity.value,
            'is_storm': self.is_storm,
            'wave_height_factor': self.wave_height_factor,
            'wind_factor': self.wind_factor,
            'pressure_factor': self.pressure_factor,
            'entropy_bonus': self.entropy_bonus,
        }



# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BuoyLocation:
    """Geographic location of NOAA buoy."""
    buoy_id: str
    name: str
    latitude: float
    longitude: float
    region: str  # atlantic, pacific, gulf, caribbean
    buoy_type: str  # weather, wave, tsunami


@dataclass
class BuoyReading:
    """Single reading from a NOAA buoy."""
    buoy_id: str
    timestamp: datetime
    
    # Wave data (primary entropy sources)
    wave_height_m: Optional[float] = None  # WVHT - significant wave height
    wave_period_sec: Optional[float] = None  # DPD - dominant wave period
    wave_direction_deg: Optional[int] = None  # MWD - mean wave direction
    average_period_sec: Optional[float] = None  # APD - average wave period
    
    # Atmospheric data (secondary entropy)
    wind_speed_mps: Optional[float] = None  # WSPD - wind speed
    wind_direction_deg: Optional[int] = None  # WDIR - wind direction
    wind_gust_mps: Optional[float] = None  # GST - peak gust
    pressure_hpa: Optional[float] = None  # PRES - atmospheric pressure
    air_temp_c: Optional[float] = None  # ATMP - air temperature
    
    # Ocean data (tertiary entropy)
    sea_temp_c: Optional[float] = None  # WTMP - sea surface temperature
    dewpoint_c: Optional[float] = None  # DEWP - dewpoint temperature
    visibility_nm: Optional[float] = None  # VIS - visibility
    
    # Location data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Data quality
    is_valid: bool = True
    quality_flags: Dict[str, str] = field(default_factory=dict)
    
    @property
    def entropy_value_count(self) -> int:
        """Count of non-null values available for entropy extraction."""
        values = [
            self.wave_height_m, self.wave_period_sec, self.wave_direction_deg,
            self.wind_speed_mps, self.wind_gust_mps, self.pressure_hpa,
            self.air_temp_c, self.sea_temp_c
        ]
        return sum(1 for v in values if v is not None)
    
    @property
    def entropy_quality_score(self) -> float:
        """
        Calculate quality score based on data completeness, variability, and storm conditions.
        
        Returns: 0.0 to 1.0, where 1.0 is perfect quality
        
        Storm Chase Mode: During hurricanes/storms, entropy quality is MAXIMUM!
        """
        # Count available parameters
        params = [
            self.wave_height_m, self.wave_period_sec, self.wave_direction_deg,
            self.sea_temp_c, self.air_temp_c,
            self.wind_speed_mps, self.wind_direction_deg, self.wind_gust_mps,
            self.pressure_hpa
        ]
        completeness = sum(1 for p in params if p is not None) / len(params)
        
        # Bonus for high-entropy wave data (larger waves = more chaos)
        wave_bonus = 0.0
        if self.wave_height_m is not None and self.wave_height_m > 1.0:
            wave_bonus = min(self.wave_height_m / 10.0, 0.2)  # Up to 0.2 bonus
        
        # STORM CHASE MODE: Add storm bonus for maximum entropy!
        storm_conditions = self.detect_storm_conditions()
        storm_bonus = storm_conditions.entropy_bonus
        
        return min(completeness + wave_bonus + storm_bonus, 1.0)
    
    def detect_storm_conditions(self) -> 'StormConditions':
        """
        Detect storm/hurricane conditions from buoy readings.
        
        Storm Chase Mode: During hurricanes, buoys have MAXIMUM entropy!
        High waves, strong winds, and low pressure = chaos = entropy gold.
        
        Returns:
            StormConditions with severity level and entropy bonus
        """
        # Calculate individual factors (0.0 to 1.0)
        wave_factor = 0.0
        wind_factor = 0.0
        pressure_factor = 0.0
        
        # Wave height factor
        if self.wave_height_m is not None:
            if self.wave_height_m >= StormConditions.WAVE_EXTREME_M:
                wave_factor = 1.0
            elif self.wave_height_m >= StormConditions.WAVE_SEVERE_M:
                wave_factor = 0.7
            elif self.wave_height_m >= StormConditions.WAVE_STORM_M:
                wave_factor = 0.4
        
        # Wind speed factor (use gust if available, else sustained)
        wind_speed = self.wind_gust_mps or self.wind_speed_mps
        if wind_speed is not None:
            if wind_speed >= StormConditions.WIND_EXTREME_MPS:
                wind_factor = 1.0
            elif wind_speed >= StormConditions.WIND_SEVERE_MPS:
                wind_factor = 0.7
            elif wind_speed >= StormConditions.WIND_STORM_MPS:
                wind_factor = 0.4
        
        # Pressure factor (lower = more severe)
        if self.pressure_hpa is not None:
            if self.pressure_hpa <= StormConditions.PRESSURE_EXTREME_HPA:
                pressure_factor = 1.0
            elif self.pressure_hpa <= StormConditions.PRESSURE_VERY_LOW_HPA:
                pressure_factor = 0.7
            elif self.pressure_hpa <= StormConditions.PRESSURE_LOW_HPA:
                pressure_factor = 0.4
        
        # Determine overall severity (weighted: waves 40%, wind 40%, pressure 20%)
        combined_score = (wave_factor * 0.4) + (wind_factor * 0.4) + (pressure_factor * 0.2)
        
        # Determine severity level and bonus
        if combined_score >= 0.7:
            severity = StormSeverity.EXTREME
            entropy_bonus = StormConditions.BONUS_EXTREME
        elif combined_score >= 0.4:
            severity = StormSeverity.SEVERE
            entropy_bonus = StormConditions.BONUS_SEVERE
        elif combined_score >= 0.2:
            severity = StormSeverity.STORM
            entropy_bonus = StormConditions.BONUS_STORM
        else:
            severity = StormSeverity.NONE
            entropy_bonus = 0.0
        
        is_storm = severity != StormSeverity.NONE
        
        return StormConditions(
            severity=severity,
            is_storm=is_storm,
            wave_height_factor=wave_factor,
            wind_factor=wind_factor,
            pressure_factor=pressure_factor,
            entropy_bonus=entropy_bonus,
        )
    
    def to_entropy_bytes(self) -> bytes:
        """
        Convert all available readings to entropy bytes.
        
        Uses IEEE 754 representation of floats and integer encodings
        to preserve full precision and variability. Returns SHA3-512
        hash of all data for uniform distribution.
        """
        import struct
        import hashlib
        
        entropy_parts = []
        
        # Timestamp microseconds (high-resolution timing entropy)
        entropy_parts.append(struct.pack('Q', int(self.timestamp.timestamp() * 1e6)))
        
        # Wave parameters (most chaotic)
        if self.wave_height_m is not None:
            entropy_parts.append(struct.pack('d', self.wave_height_m))
        if self.wave_period_sec is not None:
            entropy_parts.append(struct.pack('d', self.wave_period_sec))
        if self.wave_direction_deg is not None:
            entropy_parts.append(struct.pack('H', self.wave_direction_deg))
        
        # Temperature variations (fine-grained entropy)
        if self.sea_temp_c is not None:
            entropy_parts.append(struct.pack('d', self.sea_temp_c))
        if self.air_temp_c is not None:
            entropy_parts.append(struct.pack('d', self.air_temp_c))
        
        # Wind (highly variable)
        if self.wind_speed_mps is not None:
            entropy_parts.append(struct.pack('d', self.wind_speed_mps))
        if self.wind_direction_deg is not None:
            entropy_parts.append(struct.pack('H', self.wind_direction_deg))
        if self.wind_gust_mps is not None:
            entropy_parts.append(struct.pack('d', self.wind_gust_mps))
        
        # Pressure (subtle variations)
        if self.pressure_hpa is not None:
            entropy_parts.append(struct.pack('d', self.pressure_hpa))
        
        # Location (for buoy-specific entropy)
        if self.latitude is not None:
            entropy_parts.append(struct.pack('d', self.latitude))
        if self.longitude is not None:
            entropy_parts.append(struct.pack('d', self.longitude))
        
        # Combine all parts
        raw_data = b''.join(entropy_parts)
        
        # Hash to ensure uniform distribution
        return hashlib.sha3_512(raw_data).digest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        storm_conditions = self.detect_storm_conditions()
        return {
            'buoy_id': self.buoy_id,
            'timestamp': self.timestamp.isoformat(),
            'wave_height_m': self.wave_height_m,
            'wave_period_sec': self.wave_period_sec,
            'wave_direction_deg': self.wave_direction_deg,
            'wind_speed_mps': self.wind_speed_mps,
            'wind_gust_mps': self.wind_gust_mps,
            'pressure_hpa': self.pressure_hpa,
            'air_temp_c': self.air_temp_c,
            'sea_temp_c': self.sea_temp_c,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'entropy_values': self.entropy_value_count,
            'quality_score': self.entropy_quality_score,
            'storm_conditions': storm_conditions.to_dict(),
        }


@dataclass
class BuoyStatus:
    """Health status of a buoy."""
    buoy_id: str
    is_online: bool
    last_reading_time: Optional[datetime] = None
    data_age_minutes: Optional[int] = None
    error_message: Optional[str] = None


# =============================================================================
# Buoy Registry
# =============================================================================

# Distributed buoys across different ocean regions for maximum entropy diversity
PRIORITY_BUOYS = {
    'atlantic': [
        BuoyLocation('44013', 'Boston 16 NM East', 42.346, -70.651, 'atlantic', 'weather'),
        BuoyLocation('44025', 'Long Island 33 NM South', 40.251, -73.164, 'atlantic', 'weather'),
        BuoyLocation('41010', 'Canaveral East 120 NM', 28.906, -78.471, 'atlantic', 'weather'),
        BuoyLocation('41049', 'South Hatteras 225 NM', 27.514, -63.001, 'atlantic', 'wave'),
    ],
    'pacific': [
        BuoyLocation('46050', 'Stonewall Bank 20 NM W', 44.641, -124.500, 'pacific', 'weather'),
        BuoyLocation('46011', 'Santa Maria 21 NM NW', 34.868, -120.857, 'pacific', 'weather'),
        BuoyLocation('46001', 'Western Gulf Alaska', 56.300, -148.021, 'pacific', 'weather'),
        BuoyLocation('46026', 'San Francisco 18 NM W', 37.754, -122.839, 'pacific', 'weather'),
    ],
    'gulf': [
        BuoyLocation('42001', 'Mid Gulf 170 NM S', 25.888, -89.658, 'gulf', 'weather'),
        BuoyLocation('42040', 'Luke Offshore Platform', 29.212, -88.207, 'gulf', 'weather'),
        BuoyLocation('42039', 'Pensacola 115 NM SE', 28.791, -86.008, 'gulf', 'weather'),
    ],
    'caribbean': [
        BuoyLocation('41040', 'Puerto Rico Trench', 14.560, -53.000, 'caribbean', 'wave'),
        BuoyLocation('42056', 'Yucatan Basin', 19.820, -84.945, 'caribbean', 'weather'),
        BuoyLocation('42058', 'Isla Mujeres 125 NM NE', 21.943, -85.043, 'caribbean', 'weather'),
    ],
}

# Flatten for easy lookup
ALL_BUOYS = {
    buoy.buoy_id: buoy
    for region_buoys in PRIORITY_BUOYS.values()
    for buoy in region_buoys
}


# =============================================================================
# NOAA API Client
# =============================================================================

class NOAABuoyClient:
    """
    Client for NOAA National Data Buoy Center API.
    
    Fetches real-time meteorological and oceanographic data from buoys.
    Implements caching and rate limiting to respect NOAA servers.
    
    Usage:
        client = NOAABuoyClient()
        reading = await client.fetch_latest_reading('44013')
    """
    
    # NDBC data endpoints
    REALTIME2_URL = "https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt"
    LATEST_OBS_URL = "https://www.ndbc.noaa.gov/data/latest_obs/{station_id}.txt"
    STATION_PAGE_URL = "https://www.ndbc.noaa.gov/station_page.php?station={station_id}"
    
    # Rate limiting (be respectful to NOAA servers)
    MIN_REQUEST_INTERVAL_SECONDS = int(os.environ.get('NOAA_REQUEST_INTERVAL_SECONDS', 60))
    MAX_REQUESTS_PER_HOUR = int(os.environ.get('NOAA_MAX_REQUESTS_PER_HOUR', 60))
    
    # Cache settings
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self):
        self._client: Optional['httpx.AsyncClient'] = None
        self._cache: Dict[str, Tuple[BuoyReading, datetime]] = {}
        self._last_request_time: Dict[str, datetime] = {}
        self._request_count: int = 0
        self._request_count_reset: datetime = datetime.utcnow()
    
    async def _get_client(self) -> 'httpx.AsyncClient':
        """Get or create HTTP client."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not installed. Run: pip install httpx")
        
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    'User-Agent': 'PasswordManager-EntropyHarvester/1.0 (Educational/Research)',
                    'Accept': 'text/plain',
                }
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _check_rate_limit(self, buoy_id: str) -> bool:
        """Check if we can make a request without exceeding rate limits."""
        now = datetime.utcnow()
        
        # Reset hourly counter
        if (now - self._request_count_reset).total_seconds() > 3600:
            self._request_count = 0
            self._request_count_reset = now
        
        # Check hourly limit
        if self._request_count >= self.MAX_REQUESTS_PER_HOUR:
            logger.warning("NOAA hourly rate limit reached")
            return False
        
        # Check per-buoy interval
        last_request = self._last_request_time.get(buoy_id)
        if last_request:
            elapsed = (now - last_request).total_seconds()
            if elapsed < self.MIN_REQUEST_INTERVAL_SECONDS:
                return False
        
        return True
    
    def _get_cached(self, buoy_id: str) -> Optional[BuoyReading]:
        """Get cached reading if still valid."""
        if buoy_id in self._cache:
            reading, cached_at = self._cache[buoy_id]
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                logger.debug(f"Cache hit for buoy {buoy_id} (age: {age:.0f}s)")
                return reading
        return None
    
    def _cache_reading(self, buoy_id: str, reading: BuoyReading):
        """Cache a buoy reading."""
        self._cache[buoy_id] = (reading, datetime.utcnow())
    
    async def fetch_latest_reading(
        self, 
        buoy_id: str,
        force_refresh: bool = False
    ) -> Optional[BuoyReading]:
        """
        Fetch the latest reading from a NOAA buoy.
        
        Args:
            buoy_id: NOAA station ID (e.g., '44013')
            force_refresh: Bypass cache and rate limiting
            
        Returns:
            BuoyReading or None if fetch failed
        """
        # Check cache first
        if not force_refresh:
            cached = self._get_cached(buoy_id)
            if cached:
                return cached
        
        # Check rate limit
        if not force_refresh and not self._check_rate_limit(buoy_id):
            logger.debug(f"Rate limited for buoy {buoy_id}, returning cached")
            return self._get_cached(buoy_id)
        
        try:
            client = await self._get_client()
            
            # Fetch realtime2 data (comprehensive)
            url = self.REALTIME2_URL.format(station_id=buoy_id)
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"Buoy {buoy_id} fetch failed: HTTP {response.status_code}")
                return None
            
            # Parse response
            text = response.text
            reading = self._parse_realtime2(buoy_id, text)
            
            # Update tracking
            self._last_request_time[buoy_id] = datetime.utcnow()
            self._request_count += 1
            
            if reading:
                self._cache_reading(buoy_id, reading)
                logger.info(f"Fetched buoy {buoy_id}: {reading.entropy_value_count} entropy values")
            
            return reading
            
        except Exception as e:
            logger.error(f"Failed to fetch buoy {buoy_id}: {e}")
            return None
    
    def _parse_realtime2(self, buoy_id: str, text: str) -> Optional[BuoyReading]:
        """
        Parse NDBC realtime2 standard meteorological data format.
        
        Format:
        #YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
        #yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
        2024 07 15 10 00 120 5.2  6.1  1.5   8.0   5.3 135 1015.2 22.3 24.1 20.5 10.0 +0.2  MM
        """
        lines = text.strip().split('\n')
        
        # Find data lines (skip headers starting with #)
        data_lines = [l for l in lines if not l.startswith('#') and l.strip()]
        
        if not data_lines:
            logger.warning(f"No data lines found for buoy {buoy_id}")
            return None
        
        # Get most recent reading (first data line)
        latest = data_lines[0].split()
        
        try:
            # Parse timestamp
            year = int(latest[0])
            month = int(latest[1])
            day = int(latest[2])
            hour = int(latest[3])
            minute = int(latest[4])
            
            # Handle 2-digit year
            if year < 100:
                year += 2000
            
            timestamp = datetime(year, month, day, hour, minute)
            
            # Parse values (MM = missing data)
            def parse_val(idx: int, val_type=float) -> Optional[float]:
                try:
                    val = latest[idx]
                    if val == 'MM' or val == 'N/A':
                        return None
                    return val_type(val)
                except (IndexError, ValueError):
                    return None
            
            reading = BuoyReading(
                buoy_id=buoy_id,
                timestamp=timestamp,
                wind_direction_deg=parse_val(5, int),
                wind_speed_mps=parse_val(6),
                wind_gust_mps=parse_val(7),
                wave_height_m=parse_val(8),
                wave_period_sec=parse_val(9),
                average_period_sec=parse_val(10),
                wave_direction_deg=parse_val(11, int),
                pressure_hpa=parse_val(12),
                air_temp_c=parse_val(13),
                sea_temp_c=parse_val(14),
                dewpoint_c=parse_val(15),
                visibility_nm=parse_val(16),
            )
            
            return reading
            
        except (IndexError, ValueError) as e:
            logger.error(f"Failed to parse buoy {buoy_id} data: {e}")
            return None
    
    async def fetch_multiple_buoys(
        self,
        buoy_ids: List[str],
        max_concurrent: int = 5
    ) -> Dict[str, BuoyReading]:
        """
        Fetch readings from multiple buoys concurrently.
        
        Args:
            buoy_ids: List of station IDs
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dict mapping buoy_id to BuoyReading (only successful fetches)
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_one(buoy_id: str):
            async with semaphore:
                reading = await self.fetch_latest_reading(buoy_id)
                if reading:
                    results[buoy_id] = reading
        
        await asyncio.gather(*[fetch_one(bid) for bid in buoy_ids])
        
        return results
    
    async def get_buoy_status(self, buoy_id: str) -> BuoyStatus:
        """Check health status of a buoy."""
        reading = await self.fetch_latest_reading(buoy_id)
        
        if reading is None:
            return BuoyStatus(
                buoy_id=buoy_id,
                is_online=False,
                error_message="Failed to fetch data"
            )
        
        age_minutes = int((datetime.utcnow() - reading.timestamp).total_seconds() / 60)
        threshold = int(os.environ.get('OCEAN_BUOY_OFFLINE_THRESHOLD_MINUTES', 30))
        
        return BuoyStatus(
            buoy_id=buoy_id,
            is_online=age_minutes < threshold,
            last_reading_time=reading.timestamp,
            data_age_minutes=age_minutes,
            error_message=None if age_minutes < threshold else f"Data is {age_minutes} minutes old"
        )
    
    async def get_healthy_buoys(self, region: Optional[str] = None) -> List[str]:
        """Get list of healthy (recently reporting) buoys."""
        buoys_to_check = []
        
        if region and region in PRIORITY_BUOYS:
            buoys_to_check = [b.buoy_id for b in PRIORITY_BUOYS[region]]
        else:
            buoys_to_check = list(ALL_BUOYS.keys())
        
        healthy = []
        for buoy_id in buoys_to_check:
            status = await self.get_buoy_status(buoy_id)
            if status.is_online:
                healthy.append(buoy_id)
        
        return healthy
    
    def get_buoy_info(self, buoy_id: str) -> Optional[BuoyLocation]:
        """Get static info about a buoy."""
        return ALL_BUOYS.get(buoy_id)
    
    def get_region_for_hour(self, hour: Optional[int] = None) -> str:
        """
        Get which region to use based on current hour.
        Rotates through regions to distribute load.
        """
        if hour is None:
            hour = datetime.utcnow().hour
        
        regions = list(PRIORITY_BUOYS.keys())
        return regions[hour % len(regions)]
    
    def get_all_buoy_ids(self) -> List[str]:
        """Get all known buoy IDs."""
        return list(ALL_BUOYS.keys())
    
    def get_region_buoy_ids(self, region: str) -> List[str]:
        """Get buoy IDs for a specific region."""
        if region not in PRIORITY_BUOYS:
            return []
        return [b.buoy_id for b in PRIORITY_BUOYS[region]]


# =============================================================================
# Entropy Extraction Utilities
# =============================================================================

def extract_entropy_bytes_from_reading(reading: BuoyReading) -> bytes:
    """
    Extract entropy bytes from a single buoy reading.
    
    Uses the least significant bits of floating-point mantissas
    which are highly unpredictable.
    
    Args:
        reading: BuoyReading with oceanographic data
        
    Returns:
        Raw entropy bytes (not yet debiased)
    """
    import struct
    
    entropy_values = []
    
    # Collect all available numerical values
    values = [
        reading.wave_height_m,
        reading.wave_period_sec,
        reading.wind_speed_mps,
        reading.wind_gust_mps,
        reading.pressure_hpa,
        reading.air_temp_c,
        reading.sea_temp_c,
    ]
    
    # Optional integer values (convert to float)
    if reading.wave_direction_deg is not None:
        values.append(float(reading.wave_direction_deg))
    if reading.wind_direction_deg is not None:
        values.append(float(reading.wind_direction_deg))
    
    raw_bytes = bytearray()
    
    for val in values:
        if val is not None:
            # Pack as 64-bit double
            packed = struct.pack('d', val)
            # Extract least significant bytes (high entropy)
            raw_bytes.extend(packed[-3:])  # Last 3 bytes of mantissa
    
    # Add timestamp entropy
    ts_bytes = struct.pack('d', reading.timestamp.timestamp())
    raw_bytes.extend(ts_bytes[-2:])
    
    return bytes(raw_bytes)


def combine_readings_entropy(readings: List[BuoyReading]) -> bytes:
    """
    Combine entropy from multiple buoy readings.
    
    XORs entropy from each reading, then hashes to ensure
    uniform distribution.
    """
    if not readings:
        raise ValueError("No readings to combine")
    
    # Extract entropy from each reading
    all_entropy = [extract_entropy_bytes_from_reading(r) for r in readings]
    
    # Find minimum length
    min_len = min(len(e) for e in all_entropy)
    
    # XOR all entropy sources together
    combined = bytearray(min_len)
    for e in all_entropy:
        for i in range(min_len):
            combined[i] ^= e[i]
    
    # Hash to ensure uniform distribution
    return hashlib.blake2b(bytes(combined), digest_size=64).digest()


# =============================================================================
# Singleton instance
# =============================================================================

_noaa_client: Optional[NOAABuoyClient] = None


def get_noaa_client() -> NOAABuoyClient:
    """Get or create the NOAA client singleton."""
    global _noaa_client
    if _noaa_client is None:
        _noaa_client = NOAABuoyClient()
    return _noaa_client
