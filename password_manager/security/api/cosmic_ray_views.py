"""
Cosmic Ray Entropy API Views
=============================

REST API endpoints for cosmic ray-based entropy and password generation.

Endpoints:
- GET /api/security/cosmic/status/ - Detector status
- POST /api/security/cosmic/generate-password/ - Generate password
- GET /api/security/cosmic/events/ - Recent detection events
- POST /api/security/cosmic/settings/ - Update collection settings

@author Password Manager Team
@created 2026-02-08
"""

import logging
import asyncio
from typing import Dict, Any

from django.conf import settings
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def get_cosmic_provider():
    """Get the cosmic ray entropy provider instance."""
    try:
        from security.services.cosmic_ray_entropy_service import get_cosmic_provider as _get_provider
        return _get_provider()
    except ImportError as e:
        logger.error(f"Cosmic ray service not available: {e}")
        return None


def run_async(coro):
    """Run async function from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context - create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop
        return asyncio.run(coro)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_detector_status(request):
    """
    Get cosmic ray detector status.
    
    Returns:
        - connected: bool - Hardware detector connected
        - mode: str - 'hardware', 'simulation', or 'disabled'
        - continuous_collection: bool - Continuous collection enabled
        - buffer_size: int - Current event buffer size
        - config: dict - Current configuration
    """
    provider = get_cosmic_provider()
    
    if not provider:
        return Response({
            'success': False,
            'error': 'Cosmic ray service not available',
            'mode': 'disabled'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        provider_status = provider.get_status()
        
        # Get configuration
        cosmic_config = getattr(settings, 'COSMIC_RAY_ENTROPY', {})
        
        return Response({
            'success': True,
            'status': {
                'mode': provider_status.get('mode', 'unknown'),
                'available': provider_status.get('available', False),
                'continuous_collection': provider_status.get('continuous_collection', False),
            },
            'hardware': provider_status.get('hardware', {}),
            'simulation': provider_status.get('simulation', {}),
            'config': {
                'enabled': cosmic_config.get('ENABLED', True),
                'simulation_fallback': cosmic_config.get('SIMULATION_FALLBACK', True),
                'continuous_enabled': cosmic_config.get('CONTINUOUS_COLLECTION', False),
                'buffer_size': cosmic_config.get('EVENT_BUFFER_SIZE', 100),
            },
            'last_source': provider_status.get('last_source', {}),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error getting detector status: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_cosmic_password(request):
    """
    Generate a password using cosmic ray entropy.
    
    Request body:
        - length: int (8-128, default: 16) - Password length
        - include_uppercase: bool (default: true) - Include uppercase letters
        - include_lowercase: bool (default: true) - Include lowercase letters
        - include_digits: bool (default: true) - Include numbers
        - include_symbols: bool (default: true) - Include symbols
        - custom_charset: str (optional) - Custom characters to use
    
    Returns:
        - password: str - Generated password
        - source: str - Entropy source identifier
        - entropy_bits: int - Entropy bits used
        - detector_mode: str - 'hardware' or 'simulation'
    """
    provider = get_cosmic_provider()
    
    if not provider:
        return Response({
            'success': False,
            'error': 'Cosmic ray service not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    if not provider.is_available():
        return Response({
            'success': False,
            'error': 'Cosmic ray entropy not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        data = request.data
        
        # Parse parameters
        length = min(128, max(8, data.get('length', 16)))
        
        # Build charset
        if 'custom_charset' in data and data['custom_charset']:
            charset = data['custom_charset']
        else:
            charset = ""
            if data.get('include_lowercase', True):
                charset += "abcdefghijklmnopqrstuvwxyz"
            if data.get('include_uppercase', True):
                charset += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if data.get('include_digits', True):
                charset += "0123456789"
            if data.get('include_symbols', True):
                charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        if not charset:
            charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        
        # Import and generate password
        from security.services.cosmic_ray_entropy_service import generate_cosmic_password as _generate
        
        password, info = run_async(_generate(length=length, charset=charset))
        
        # Log generation (without password)
        logger.info(
            f"Generated cosmic ray password for user {request.user.id}: "
            f"length={length}, source={info.get('source')}"
        )
        
        return Response({
            'success': True,
            'password': password,
            'length': len(password),
            'source': info.get('source', 'unknown'),
            'entropy_bits': info.get('entropy_bits', 0),
            'detector_mode': info.get('status', {}).get('mode', 'unknown'),
            'events_used': info.get('status', {}).get('events_used', 0),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error generating cosmic password: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_events(request):
    """
    Get recent cosmic ray detection events.
    
    Query params:
        - limit: int (default: 20) - Maximum events to return
    
    Returns:
        - events: list - Recent cosmic ray events
        - count: int - Total events returned
        - mode: str - Current detection mode
    """
    provider = get_cosmic_provider()
    
    if not provider:
        return Response({
            'success': False,
            'error': 'Cosmic ray service not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        limit = min(100, max(1, int(request.query_params.get('limit', 20))))
        
        # Get provider status (which includes buffered events info)
        provider_status = provider.get_status()
        
        # For simulation mode, generate some sample events
        if provider_status.get('mode') == 'simulation':
            from security.services.cosmic_ray_entropy_service import SimulatedCosmicDetector
            
            simulator = SimulatedCosmicDetector()
            events = run_async(simulator.collect_events(count=limit, realistic_timing=False))
            
            events_data = [event.to_dict() for event in events]
        else:
            # Hardware mode - get from buffer
            hardware_status = provider_status.get('hardware', {})
            events_data = []  # Hardware events would come from buffer
        
        return Response({
            'success': True,
            'events': events_data,
            'count': len(events_data),
            'mode': provider_status.get('mode', 'unknown'),
            'continuous_collection': provider_status.get('continuous_collection', False),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error getting cosmic events: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_collection_settings(request):
    """
    Update cosmic ray collection settings.
    
    Request body:
        - continuous_collection: bool - Enable/disable continuous collection
    
    Returns:
        - success: bool
        - continuous_collection: bool - New setting value
    """
    provider = get_cosmic_provider()
    
    if not provider:
        return Response({
            'success': False,
            'error': 'Cosmic ray service not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        data = request.data
        
        enable_continuous = data.get('continuous_collection', False)
        
        if enable_continuous:
            buffer_size = getattr(settings, 'COSMIC_RAY_ENTROPY', {}).get('EVENT_BUFFER_SIZE', 100)
            provider.enable_continuous_collection(buffer_size)
            logger.info(f"User {request.user.id} enabled continuous cosmic ray collection")
        else:
            provider.disable_continuous_collection()
            logger.info(f"User {request.user.id} disabled continuous cosmic ray collection")
        
        return Response({
            'success': True,
            'continuous_collection': enable_continuous,
            'message': f"Continuous collection {'enabled' if enable_continuous else 'disabled'}",
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error updating collection settings: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_entropy_batch(request):
    """
    Generate a batch of raw entropy bytes from cosmic ray detection.
    
    Request body:
        - count: int (1-1024, default: 32) - Number of bytes
    
    Returns:
        - entropy_hex: str - Hex-encoded entropy bytes
        - entropy_base64: str - Base64-encoded entropy bytes  
        - source: str - Entropy source identifier
        - events_used: int - Number of cosmic events used
    """
    provider = get_cosmic_provider()
    
    if not provider:
        return Response({
            'success': False,
            'error': 'Cosmic ray service not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    if not provider.is_available():
        return Response({
            'success': False,
            'error': 'Cosmic ray entropy not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        import base64
        
        count = min(1024, max(1, request.data.get('count', 32)))
        
        entropy_bytes, source_id = run_async(provider.fetch_random_bytes(count))
        source_info = provider.get_last_source_info()
        
        return Response({
            'success': True,
            'entropy_hex': entropy_bytes.hex(),
            'entropy_base64': base64.b64encode(entropy_bytes).decode('utf-8'),
            'bytes_generated': len(entropy_bytes),
            'source': source_id,
            'detector_mode': source_info.get('mode', 'unknown'),
            'events_used': source_info.get('events_used', 0),
            'min_entropy_per_byte': source_info.get('min_entropy_per_byte', 0),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error generating entropy batch: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
