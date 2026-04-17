"""
GeofenceEvaluator — Haversine distance check.

We intentionally keep this dependency-free (no GeoDjango required at
runtime for the simple bounding check). Latitude/longitude can come
from a browser Geolocation header set by the frontend axios
interceptor, a mobile app, or a GeoIP2 fallback.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two lat/lng points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


class GeofenceEvaluator:
    """Evaluate whether a point is inside a circular geofence."""

    def __init__(self, center_lat: float, center_lng: float, radius_m: int) -> None:
        self.center_lat = center_lat
        self.center_lng = center_lng
        self.radius_m = max(0, int(radius_m))

    def contains(self, lat: Optional[float], lng: Optional[float]) -> bool:
        """Returns False if lat/lng missing (fail closed)."""
        if lat is None or lng is None:
            return False
        return haversine_m(self.center_lat, self.center_lng, lat, lng) <= self.radius_m


def extract_coords(request) -> Tuple[Optional[float], Optional[float]]:
    """
    Pull lat/lng from request. Order of precedence:
      1. X-Geo-Latitude / X-Geo-Longitude headers (set by the frontend
         geolocation.js axios interceptor).
      2. request.data['_geolocation'] if the client preferred to inline it.
    """
    if request is None:
        return None, None

    lat = request.META.get('HTTP_X_GEO_LATITUDE') if hasattr(request, 'META') else None
    lng = request.META.get('HTTP_X_GEO_LONGITUDE') if hasattr(request, 'META') else None
    try:
        lat = float(lat) if lat not in (None, '') else None
        lng = float(lng) if lng not in (None, '') else None
    except (TypeError, ValueError):
        lat, lng = None, None

    if lat is None or lng is None:
        payload = getattr(request, 'data', None) or {}
        geo = payload.get('_geolocation') if isinstance(payload, dict) else None
        if isinstance(geo, dict):
            try:
                lat = float(geo.get('lat')) if geo.get('lat') is not None else lat
                lng = float(geo.get('lng')) if geo.get('lng') is not None else lng
            except (TypeError, ValueError):
                pass

    return lat, lng
