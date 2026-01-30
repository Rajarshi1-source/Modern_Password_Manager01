"""
Storm Chase API Views
======================

REST API endpoints for Storm Chase Mode.
Provides storm detection status, alerts, and enhanced entropy generation.

Endpoints:
- GET  /api/security/ocean/storms/          - List active storm alerts
- GET  /api/security/ocean/storms/status/   - Storm chase mode status
- GET  /api/security/ocean/storms/buoys/    - Buoys with active storms
- POST /api/security/ocean/generate-storm-entropy/ - Generate entropy from storm buoys

@author Password Manager Team
@created 2026-01-30
"""

import logging
from datetime import datetime
from typing import Dict, Any

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from security.services.storm_chase import (
    get_storm_chase_service,
    StormChaseService,
    StormSeverity,
)

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in sync context."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# =============================================================================
# Storm Chase API Views
# =============================================================================

class StormListView(APIView):
    """
    GET /api/security/ocean/storms/
    
    List all active storm alerts across all monitored buoys.
    
    Response:
    {
        "storms": [...],
        "count": 2,
        "most_severe": "extreme",
        "max_entropy_bonus": 0.35
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            service = get_storm_chase_service()
            alerts = run_async(service.get_active_storms())
            
            response_data = {
                'storms': [a.to_dict() for a in alerts],
                'count': len(alerts),
                'most_severe': max(a.severity.value for a in alerts) if alerts else None,
                'max_entropy_bonus': max(a.entropy_bonus for a in alerts) if alerts else 0.0,
                'timestamp': datetime.utcnow().isoformat(),
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Failed to list storms: {e}")
            return Response(
                {'error': 'Failed to fetch storm data', 'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class StormStatusView(APIView):
    """
    GET /api/security/ocean/storms/status/
    
    Get overall Storm Chase Mode status.
    
    Response:
    {
        "is_active": true,
        "active_storms_count": 2,
        "most_severe": "severe",
        "max_entropy_bonus": 0.25,
        "regions_affected": ["atlantic", "gulf"],
        "storm_alerts": [...],
        "message": "🌀 Storm Chase Mode ACTIVE! Maximum entropy available."
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            service = get_storm_chase_service()
            status_data = run_async(service.get_storm_chase_status())
            
            response = status_data.to_dict()
            
            # Add user-friendly message
            if status_data.is_active:
                severity_messages = {
                    StormSeverity.STORM: "⚠️ Storm detected! Enhanced entropy available.",
                    StormSeverity.SEVERE: "🌊 Severe storm! High entropy generation active.",
                    StormSeverity.EXTREME: "🌀 HURRICANE DETECTED! MAXIMUM entropy mode!",
                }
                response['message'] = severity_messages.get(
                    status_data.most_severe,
                    "Storm conditions detected."
                )
            else:
                response['message'] = "No active storms. Ocean entropy at normal levels."
            
            return Response(response)
            
        except Exception as e:
            logger.error(f"Failed to get storm status: {e}")
            return Response(
                {'error': 'Failed to fetch storm status', 'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class StormBuoysView(APIView):
    """
    GET /api/security/ocean/storms/buoys/
    
    Get buoys with active storm conditions.
    These buoys provide MAXIMUM entropy!
    
    Response:
    {
        "buoys": [...],
        "count": 2,
        "total_entropy_bonus": 0.50
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            service = get_storm_chase_service()
            alerts = run_async(service.get_active_storms())
            
            buoy_data = []
            for alert in alerts:
                if alert.reading:
                    buoy_info = alert.reading.to_dict()
                    buoy_info['storm_severity'] = alert.severity.value
                    buoy_info['storm_entropy_bonus'] = alert.entropy_bonus
                    buoy_data.append(buoy_info)
            
            return Response({
                'buoys': buoy_data,
                'count': len(buoy_data),
                'total_entropy_bonus': sum(a.entropy_bonus for a in alerts),
            })
            
        except Exception as e:
            logger.error(f"Failed to get storm buoys: {e}")
            return Response(
                {'error': 'Failed to fetch storm buoy data', 'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class GenerateStormEntropyView(APIView):
    """
    POST /api/security/ocean/generate-storm-entropy/
    
    Generate entropy prioritizing storm-affected buoys.
    
    "During hurricanes, buoys have MAXIMUM entropy!" 🌀
    
    Request:
    {
        "count": 32,        # bytes to generate (1-256)
        "format": "hex"     # "hex" or "base64"
    }
    
    Response:
    {
        "entropy": "a3b5c7d9...",
        "format": "hex",
        "bytes_count": 32,
        "source_buoys": ["44013", "41010"],
        "storm_mode": true,
        "entropy_bonus": 0.35,
        "message": "🌀 Generated from storm buoys!"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Parse request
            count = request.data.get('count', 32)
            output_format = request.data.get('format', 'hex')
            
            # Validate
            if not 1 <= count <= 256:
                return Response(
                    {'error': 'count must be between 1 and 256'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if output_format not in ('hex', 'base64'):
                return Response(
                    {'error': 'format must be "hex" or "base64"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate storm entropy
            service = get_storm_chase_service()
            entropy_bytes, source_id, storm_buoy_ids = run_async(
                service.generate_storm_entropy(count)
            )
            
            # Format output
            if output_format == 'hex':
                entropy_formatted = entropy_bytes.hex()
            else:
                import base64
                entropy_formatted = base64.b64encode(entropy_bytes).decode('ascii')
            
            # Get current status for bonus info
            status_data = run_async(service.get_storm_chase_status())
            
            response = {
                'entropy': entropy_formatted,
                'format': output_format,
                'bytes_count': len(entropy_bytes),
                'source_id': source_id,
                'source_buoys': storm_buoy_ids,
                'storm_mode': len(storm_buoy_ids) > 0,
                'entropy_bonus': status_data.max_entropy_bonus,
                'generated_at': datetime.utcnow().isoformat(),
            }
            
            if storm_buoy_ids:
                response['message'] = f"🌀 Generated from {len(storm_buoy_ids)} storm buoy(s)!"
            else:
                response['message'] = "No active storms. Using regular ocean entropy."
            
            return Response(response, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to generate storm entropy: {e}")
            return Response(
                {'error': 'Failed to generate storm entropy', 'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class ScanStormsView(APIView):
    """
    POST /api/security/ocean/storms/scan/
    
    Trigger a manual storm scan across all buoys.
    
    Response:
    {
        "scanned": true,
        "storms_found": 2,
        "alerts": [...]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            service = get_storm_chase_service()
            alerts = run_async(service.scan_for_storms())
            
            return Response({
                'scanned': True,
                'storms_found': len(alerts),
                'alerts': [a.to_dict() for a in alerts],
                'scanned_at': datetime.utcnow().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Failed to scan for storms: {e}")
            return Response(
                {'error': 'Storm scan failed', 'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
