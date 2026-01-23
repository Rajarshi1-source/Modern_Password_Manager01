"""
Ocean Entropy API Views
========================

REST API endpoints for ocean wave entropy harvesting.

Endpoints:
- GET /api/security/ocean/status/ - Provider status and buoy health
- GET /api/security/ocean/buoys/ - List of active buoys
- GET /api/security/ocean/readings/ - Latest buoy readings
- POST /api/security/ocean/generate/ - Generate entropy from ocean data
- GET /api/security/ocean/certificate/<id>/ - Get entropy certificate

@author Password Manager Team
@created 2026-01-23
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def run_async(coro):
    """Run an async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


# =============================================================================
# Ocean Entropy Status View
# =============================================================================

class OceanEntropyStatusView(APIView):
    """
    GET /api/security/ocean/status/
    
    Returns the status of the ocean wave entropy provider including
    buoy health, availability, and configuration.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from security.services.ocean_wave_entropy_service import (
                get_ocean_provider,
                OceanEntropyConfig,
            )
            from security.services.noaa_api_client import ALL_BUOYS
            
            provider = get_ocean_provider()
            
            # Get async status
            provider_status = run_async(provider.get_status())
            
            return Response({
                'status': 'available' if provider_status.get('available') else 'degraded',
                'provider': 'noaa_ocean_wave',
                'display_name': 'NOAA Ocean Wave Entropy',
                'description': 'Powered by the ocean\'s chaos',
                'source': 'Ocean wave patterns & temperature',
                'icon': '🌊',
                'color': '#0077B6',
                'enabled': OceanEntropyConfig.ENABLED,
                'buoys': {
                    'total': len(ALL_BUOYS),
                    'healthy': provider_status.get('healthy_count', 0),
                    'details': provider_status.get('buoys', {}),
                },
                'config': {
                    'min_buoys': OceanEntropyConfig.MIN_BUOYS,
                    'max_buoys': OceanEntropyConfig.MAX_BUOYS,
                    'min_entropy_bits': OceanEntropyConfig.MIN_ENTROPY_BITS,
                    'pool_contribution_percent': OceanEntropyConfig.POOL_CONTRIBUTION_PERCENT,
                },
            })
            
        except ImportError as e:
            return Response({
                'status': 'unavailable',
                'error': 'Ocean entropy service not installed',
                'details': str(e),
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Ocean entropy status error")
            return Response({
                'status': 'error',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Buoy List View
# =============================================================================

class OceanBuoyListView(APIView):
    """
    GET /api/security/ocean/buoys/
    
    Returns list of all known NOAA buoys with their locations
    and current status.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from security.services.noaa_api_client import (
                PRIORITY_BUOYS,
                ALL_BUOYS,
                get_noaa_client,
            )
            
            # Get region filter
            region = request.query_params.get('region')
            
            client = get_noaa_client()
            
            # Build buoy list
            buoys = []
            
            for buoy_id, buoy_info in ALL_BUOYS.items():
                if region and buoy_info.region != region:
                    continue
                
                buoys.append({
                    'id': buoy_id,
                    'name': buoy_info.name,
                    'latitude': buoy_info.latitude,
                    'longitude': buoy_info.longitude,
                    'region': buoy_info.region,
                    'type': buoy_info.buoy_type,
                })
            
            # Get regions summary
            regions = {}
            for region_name, region_buoys in PRIORITY_BUOYS.items():
                regions[region_name] = {
                    'count': len(region_buoys),
                    'buoy_ids': [b.buoy_id for b in region_buoys],
                }
            
            return Response({
                'buoys': buoys,
                'total': len(buoys),
                'regions': regions,
                'current_region': client.get_region_for_hour(),
            })
            
        except Exception as e:
            logger.exception("Buoy list error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Ocean Readings View
# =============================================================================

class OceanReadingsView(APIView):
    """
    GET /api/security/ocean/readings/
    
    Returns latest readings from buoys.
    Query params:
        buoy_id: Specific buoy to fetch (optional)
        limit: Number of buoys to return (default 5)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from security.services.noaa_api_client import get_noaa_client
            from security.services.ocean_wave_entropy_service import get_ocean_provider
            
            buoy_id = request.query_params.get('buoy_id')
            limit = min(int(request.query_params.get('limit', 5)), 10)
            
            client = get_noaa_client()
            
            if buoy_id:
                # Fetch specific buoy
                reading = run_async(client.fetch_latest_reading(buoy_id))
                
                if reading:
                    return Response({
                        'reading': reading.to_dict(),
                        'buoy_id': buoy_id,
                    })
                else:
                    return Response({
                        'error': f'No data available for buoy {buoy_id}',
                    }, status=status.HTTP_404_NOT_FOUND)
            
            else:
                # Fetch from multiple buoys
                provider = get_ocean_provider()
                buoys_to_fetch = provider._select_buoys()[:limit]
                
                readings = run_async(client.fetch_multiple_buoys(buoys_to_fetch))
                
                return Response({
                    'readings': [r.to_dict() for r in readings.values()],
                    'count': len(readings),
                    'buoys_requested': buoys_to_fetch,
                })
                
        except Exception as e:
            logger.exception("Ocean readings error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Ocean Entropy Generate View
# =============================================================================

class OceanEntropyGenerateView(APIView):
    """
    POST /api/security/ocean/generate/
    
    Generate entropy from ocean wave data.
    
    Request body:
        count: Number of bytes to generate (default 32, max 256)
        format: Output format - 'hex' or 'base64' (default 'hex')
    
    Returns:
        entropy: Generated random bytes
        source_buoys: List of buoys used
        min_entropy: Estimated min-entropy (bits/byte)
        certificate_id: ID of generated certificate
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from security.services.ocean_wave_entropy_service import generate_ocean_entropy
            import base64
            
            # Parse parameters
            count = min(max(int(request.data.get('count', 32)), 1), 256)
            output_format = request.data.get('format', 'hex')
            
            # Generate entropy
            entropy_bytes, source_id = run_async(generate_ocean_entropy(count))
            
            # Format output
            if output_format == 'base64':
                entropy_output = base64.b64encode(entropy_bytes).decode()
            else:
                entropy_output = entropy_bytes.hex()
            
            # Parse source buoys from source_id
            # Format: ocean:buoy1,buoy2,buoy3:timestamp
            parts = source_id.split(':')
            source_buoys = parts[1].split(',') if len(parts) > 1 else []
            
            return Response({
                'entropy': entropy_output,
                'format': output_format,
                'bytes_count': len(entropy_bytes),
                'source_buoys': source_buoys,
                'source_id': source_id,
                'provider': 'noaa_ocean_wave',
                'quantum_source': 'ocean_wave_patterns',
                'generated_at': timezone.now().isoformat(),
                'message': 'Powered by the ocean\'s chaos 🌊',
            })
            
        except Exception as e:
            logger.exception("Ocean entropy generation error")
            return Response({
                'error': str(e),
                'message': 'Failed to generate ocean entropy',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Ocean Pool Status View
# =============================================================================

class OceanPoolStatusView(APIView):
    """
    GET /api/security/ocean/pool/
    
    Returns the ocean entropy pool status and contribution
    to the overall quantum entropy pool.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from security.services.ocean_wave_entropy_service import (
                get_ocean_provider,
                OceanEntropyConfig,
            )
            from security.services.noaa_api_client import get_noaa_client
            
            provider = get_ocean_provider()
            client = get_noaa_client()
            
            # Get healthy buoys count
            healthy_buoys = run_async(client.get_healthy_buoys())
            
            return Response({
                'pool_contribution_percent': OceanEntropyConfig.POOL_CONTRIBUTION_PERCENT,
                'healthy_buoys': len(healthy_buoys),
                'current_region': client.get_region_for_hour(),
                'is_contributing': len(healthy_buoys) >= OceanEntropyConfig.MIN_BUOYS,
                'status': 'active' if len(healthy_buoys) >= OceanEntropyConfig.MIN_BUOYS else 'degraded',
            })
            
        except Exception as e:
            logger.exception("Ocean pool status error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Hybrid Password Generation View
# =============================================================================

class HybridPasswordGenerateView(APIView):
    """
    POST /api/security/ocean/generate-hybrid-password/
    
    Generate a password using hybrid entropy (quantum + ocean + optional genetic).
    
    Request Body:
    {
        "length": 16,
        "include_uppercase": true,
        "include_lowercase": true,
        "include_numbers": true,
        "include_symbols": true,
        "include_genetic": false,
        "service_name": "example.com"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        import hashlib
        import hmac
        import secrets
        import math
        
        try:
            from security.services.ocean_wave_entropy_service import (
                generate_hybrid_entropy,
                InsufficientEntropySources,
                EntropyUnavailable,
            )
            
            # Parse request
            length = request.data.get('length', 16)
            include_uppercase = request.data.get('include_uppercase', True)
            include_lowercase = request.data.get('include_lowercase', True)
            include_numbers = request.data.get('include_numbers', True)
            include_symbols = request.data.get('include_symbols', True)
            include_genetic = request.data.get('include_genetic', False)
            service_name = request.data.get('service_name', '')
            
            # Validate length
            if not 8 <= length <= 128:
                return Response(
                    {'error': 'Length must be between 8 and 128'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Build character set
            charset = ''
            if include_lowercase:
                charset += 'abcdefghijklmnopqrstuvwxyz'
            if include_uppercase:
                charset += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            if include_numbers:
                charset += '0123456789'
            if include_symbols:
                charset += '!@#$%^&*()-_=+[]{}|;:,.<>?'
            
            if not charset:
                return Response(
                    {'error': 'At least one character type must be selected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate hybrid entropy (generous estimate)
            bytes_needed = length * 2
            entropy_bytes, certificate = run_async(
                generate_hybrid_entropy(
                    count=bytes_needed,
                    include_quantum=True,
                    include_genetic=include_genetic,
                )
            )
            
            # Generate password from entropy
            password = self._generate_password_from_entropy(
                entropy_bytes=entropy_bytes,
                length=length,
                charset=charset
            )
            
            # Calculate entropy bits
            entropy_bits = length * math.log2(len(charset))
            
            # Generate signature
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            signature = hmac.new(
                key=secrets.token_bytes(32),
                msg=password_hash[:16].encode(),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Get ocean details from certificate
            ocean_source = next(
                (s for s in certificate.get('sources', []) if s['name'] == 'ocean'),
                None
            )
            
            response_data = {
                'password': password,
                'sources': [s['name'] for s in certificate.get('sources', [])],
                'entropy_bits': entropy_bits,
                'quality_assessment': certificate.get('quality_assessment', {}),
                'service_name': service_name,
                'mixing_algorithm': certificate.get('mixing_algorithm'),
                'total_sources': certificate.get('total_sources', 0),
                'signature': signature,
                'generated_at': timezone.now().isoformat(),
            }
            
            if ocean_source:
                response_data['ocean_details'] = ocean_source.get('metadata', {})
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except InsufficientEntropySources as e:
            return Response({
                'error': str(e),
                'message': 'At least 2 entropy sources required',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Hybrid password generation error")
            return Response({
                'error': str(e),
                'message': 'Failed to generate hybrid password',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_password_from_entropy(
        self, 
        entropy_bytes: bytes, 
        length: int, 
        charset: str
    ) -> str:
        """Generate password from entropy using unbiased selection."""
        from hashlib import shake_256
        
        password = []
        charset_size = len(charset)
        bytes_per_char = 8
        entropy_index = 0
        
        while len(password) < length:
            if entropy_index + bytes_per_char > len(entropy_bytes):
                entropy_bytes = shake_256(entropy_bytes).digest(len(entropy_bytes) * 2)
                entropy_index = 0
            
            chunk = entropy_bytes[entropy_index:entropy_index + bytes_per_char]
            value = int.from_bytes(chunk, 'big')
            
            # Rejection sampling for unbiased selection
            max_value = (2 ** 64) - ((2 ** 64) % charset_size)
            if value < max_value:
                char_index = value % charset_size
                password.append(charset[char_index])
            
            entropy_index += bytes_per_char
        
        return ''.join(password)


# =============================================================================
# Live Wave Data View
# =============================================================================

class LiveWaveDataView(APIView):
    """
    GET /api/security/ocean/buoy/<buoy_id>/live-data/
    
    Get live wave data from a specific buoy for visualization.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, buoy_id):
        try:
            from security.services.noaa_api_client import get_noaa_client, ALL_BUOYS
            
            client = get_noaa_client()
            reading = run_async(client.fetch_latest_reading(buoy_id))
            
            if reading is None:
                return Response({
                    'error': f'Buoy {buoy_id} is currently unavailable',
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get buoy info for location
            buoy_info = ALL_BUOYS.get(buoy_id)
            
            return Response({
                'buoy_id': buoy_id,
                'buoy_name': buoy_info.name if buoy_info else '',
                'timestamp': reading.timestamp.isoformat(),
                'wave_data': {
                    'height': reading.wave_height_m,
                    'period': reading.wave_period_sec,
                    'direction': reading.wave_direction_deg,
                },
                'weather_data': {
                    'water_temp': reading.sea_temp_c,
                    'air_temp': reading.air_temp_c,
                    'wind_speed': reading.wind_speed_mps,
                    'wind_direction': reading.wind_direction_deg,
                    'pressure': reading.pressure_hpa,
                },
                'location': [buoy_info.latitude, buoy_info.longitude] if buoy_info else None,
                'quality_score': reading.entropy_quality_score,
            })
            
        except Exception as e:
            logger.exception("Live wave data error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# User Ocean Stats View
# =============================================================================

class UserOceanStatsView(APIView):
    """
    GET /api/security/ocean/my-stats/
    
    Get user's ocean entropy usage statistics.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from security.models.ocean_entropy_models import OceanEntropyUsageStats
            
            try:
                stats = OceanEntropyUsageStats.objects.get(user=request.user)
                
                return Response({
                    'total_ocean_passwords': stats.total_ocean_passwords,
                    'total_hybrid_passwords': stats.total_hybrid_passwords,
                    'favorite_buoy': stats.favorite_buoy_id,
                    'average_quality': stats.average_quality_score,
                    'first_password': stats.first_ocean_password.isoformat() if stats.first_ocean_password else None,
                    'last_password': stats.last_ocean_password.isoformat() if stats.last_ocean_password else None,
                })
                
            except OceanEntropyUsageStats.DoesNotExist:
                return Response({
                    'total_ocean_passwords': 0,
                    'total_hybrid_passwords': 0,
                    'message': 'No ocean passwords generated yet'
                })
                
        except ImportError:
            # Models not yet migrated
            return Response({
                'total_ocean_passwords': 0,
                'total_hybrid_passwords': 0,
                'message': 'Ocean entropy tracking not yet enabled'
            })
        except Exception as e:
            logger.exception("User ocean stats error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Certificate View
# =============================================================================

class HybridCertificateView(APIView):
    """
    GET /api/security/ocean/certificate/<uuid>/
    
    Retrieve a hybrid password certificate.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, certificate_id):
        try:
            from security.models.ocean_entropy_models import HybridPasswordCertificate
            
            certificate = HybridPasswordCertificate.objects.get(
                id=certificate_id,
                user=request.user
            )
            
            return Response(certificate.to_dict())
            
        except HybridPasswordCertificate.DoesNotExist:
            return Response({
                'error': 'Certificate not found',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Certificate retrieval error")
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

