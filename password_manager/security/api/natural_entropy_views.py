"""
Natural Entropy API Views
=========================

API endpoints for unified natural entropy password generation.
Combines Ocean Wave, Lightning, Seismic, and Solar Wind sources.
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from security.models import (
    LightningEntropyBatch,
    SeismicEntropyBatch,
    SolarWindEntropyBatch,
    NaturalEntropyCertificate,
    UserEntropyPreferences,
    GlobalEntropyStatistics,
)
from security.services.natural_entropy_providers import (
    LightningEntropyProvider,
    SeismicEntropyProvider,
    SolarWindEntropyProvider,
    NaturalEntropyMixer,
    EntropyUnavailable,
)
from security.services.ocean_wave_entropy_service import OceanWaveEntropyProvider

logger = logging.getLogger(__name__)


# Character sets for password generation
CHARSETS = {
    'standard': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*',
    'alphanumeric': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    'letters': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'digits': '0123456789',
    'max_entropy': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>?',
}


def _get_entropy_from_sources(
    sources: List[str],
    num_bytes: int = 64
) -> Dict[str, Any]:
    """
    Collect entropy from specified sources.
    
    Returns:
        Dict with 'entropy_blocks', 'source_info', and 'quality_scores'
    """
    entropy_blocks = []
    source_info = {}
    quality_scores = {}
    errors = []
    
    # Ocean Wave
    if 'ocean' in sources:
        try:
            provider = OceanWaveEntropyProvider()
            entropy, source = provider.fetch_random_bytes(num_bytes)
            entropy_blocks.append(entropy)
            source_info['ocean'] = {
                'source': source,
                'bytes_fetched': len(entropy),
                'timestamp': datetime.utcnow().isoformat(),
            }
            quality_scores['ocean'] = 0.85  # Ocean has good entropy quality
        except Exception as e:
            logger.warning(f"Ocean entropy unavailable: {e}")
            errors.append(f"ocean: {str(e)}")
    
    # Lightning
    if 'lightning' in sources:
        try:
            provider = LightningEntropyProvider()
            entropy = provider.fetch_entropy(num_bytes)
            entropy_blocks.append(entropy)
            source_info['lightning'] = provider.get_last_source_info()
            quality_scores['lightning'] = source_info['lightning'].get('quality_score', 0.8)
        except EntropyUnavailable as e:
            logger.warning(f"Lightning entropy unavailable: {e}")
            errors.append(f"lightning: {str(e)}")
    
    # Seismic
    if 'seismic' in sources:
        try:
            provider = SeismicEntropyProvider()
            entropy = provider.fetch_entropy(num_bytes)
            entropy_blocks.append(entropy)
            source_info['seismic'] = provider.get_last_source_info()
            quality_scores['seismic'] = source_info['seismic'].get('quality_score', 0.75)
        except EntropyUnavailable as e:
            logger.warning(f"Seismic entropy unavailable: {e}")
            errors.append(f"seismic: {str(e)}")
    
    # Solar Wind
    if 'solar' in sources:
        try:
            provider = SolarWindEntropyProvider()
            entropy = provider.fetch_entropy(num_bytes)
            entropy_blocks.append(entropy)
            source_info['solar'] = provider.get_last_source_info()
            quality_scores['solar'] = source_info['solar'].get('quality_score', 0.7)
        except EntropyUnavailable as e:
            logger.warning(f"Solar entropy unavailable: {e}")
            errors.append(f"solar: {str(e)}")
    
    return {
        'entropy_blocks': entropy_blocks,
        'source_info': source_info,
        'quality_scores': quality_scores,
        'errors': errors,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_natural_password(request: Request) -> Response:
    """
    Generate a password from multiple natural entropy sources.
    
    Request Body:
        - sources: List of sources to use ['ocean', 'lightning', 'seismic', 'solar']
        - length: Password length (default: 24)
        - charset: Character set to use (default: 'standard')
        - service_name: Optional service name for certificate
    
    Returns:
        - password: Generated password
        - certificate: Entropy certificate details
        - sources_used: List of sources that contributed
    """
    start_time = time.time()
    
    try:
        # Parse request
        data = request.data
        sources = data.get('sources', ['ocean', 'lightning', 'seismic', 'solar'])
        length = int(data.get('length', 24))
        charset_name = data.get('charset', 'standard')
        service_name = data.get('service_name', '')
        
        # Validate inputs
        length = max(8, min(128, length))  # Clamp to reasonable range
        valid_sources = {'ocean', 'lightning', 'seismic', 'solar'}
        sources = [s for s in sources if s in valid_sources]
        
        charset = CHARSETS.get(charset_name, CHARSETS['standard'])
        
        if not sources:
            return Response({
                'error': 'No valid entropy sources specified',
                'valid_sources': list(valid_sources),
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Collect entropy from sources
        entropy_result = _get_entropy_from_sources(sources, num_bytes=64)
        
        if not entropy_result['entropy_blocks']:
            return Response({
                'error': 'No entropy sources available',
                'details': entropy_result['errors'],
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Mix entropy from all sources
        mixed_entropy = NaturalEntropyMixer.mix_entropy_blocks(
            entropy_result['entropy_blocks'],
            output_length=length * 8  # Extra bytes for rejection sampling
        )
        
        # Generate password
        password = NaturalEntropyMixer.generate_password_from_entropy(
            mixed_entropy,
            length,
            charset
        )
        
        # Calculate combined quality score (weighted average)
        quality_scores = entropy_result['quality_scores']
        if quality_scores:
            combined_quality = sum(quality_scores.values()) / len(quality_scores)
        else:
            combined_quality = 0.0
        
        # Compute password hash prefix for certificate
        password_hash = hashlib.sha256(password.encode()).hexdigest()[:16]
        
        # Create signature
        signature_data = f"{password_hash}:{','.join(sorted(quality_scores.keys()))}:{timezone.now().isoformat()}"
        signature = hashlib.sha256(signature_data.encode()).hexdigest()
        
        # Create certificate
        certificate = NaturalEntropyCertificate.objects.create(
            user=request.user,
            password_hash_prefix=password_hash,
            sources_used=list(quality_scores.keys()),
            ocean_details=entropy_result['source_info'].get('ocean', {}),
            lightning_details=entropy_result['source_info'].get('lightning', {}),
            seismic_details=entropy_result['source_info'].get('seismic', {}),
            solar_details=entropy_result['source_info'].get('solar', {}),
            mixing_algorithm='XOR + SHA3-512 + SHAKE256',
            total_entropy_bits=len(mixed_entropy) * 8,
            password_length=length,
            charset_used=charset_name,
            combined_quality_score=combined_quality,
            individual_quality_scores=quality_scores,
            signature=signature,
            service_name=service_name,
        )
        
        # Update user preferences stats
        try:
            prefs, _ = UserEntropyPreferences.objects.get_or_create(user=request.user)
            prefs.total_passwords_generated += 1
            prefs.save(update_fields=['total_passwords_generated'])
        except Exception:
            pass  # Non-critical
        
        generation_time_ms = (time.time() - start_time) * 1000
        
        return Response({
            'success': True,
            'password': password,
            'length': length,
            'charset': charset_name,
            'sources_used': list(quality_scores.keys()),
            'quality_score': round(combined_quality, 3),
            'generation_time_ms': round(generation_time_ms, 2),
            'certificate': certificate.to_dict(),
            'errors': entropy_result['errors'] if entropy_result['errors'] else None,
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.exception("Natural password generation failed")
        return Response({
            'error': 'Password generation failed',
            'details': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_global_entropy_status(request: Request) -> Response:
    """
    Get status of all natural entropy sources.
    
    Returns availability and current conditions for each source.
    """
    try:
        status_data = {
            'timestamp': timezone.now().isoformat(),
            'sources': {},
        }
        
        # Ocean status
        try:
            ocean_provider = OceanWaveEntropyProvider()
            ocean_status = ocean_provider.get_status()
            status_data['sources']['ocean'] = {
                'available': ocean_provider.is_available(),
                'status': ocean_status,
                'icon': '🌊',
                'name': 'Ocean Waves',
                'description': 'NOAA Pacific Ocean buoy network',
            }
        except Exception as e:
            status_data['sources']['ocean'] = {
                'available': False,
                'error': str(e),
                'icon': '🌊',
                'name': 'Ocean Waves',
            }
        
        # Lightning status
        try:
            lightning_provider = LightningEntropyProvider()
            lightning_activity = lightning_provider.client.get_global_activity()
            status_data['sources']['lightning'] = {
                'available': lightning_provider.is_available(),
                'activity': lightning_activity,
                'icon': '⚡',
                'name': 'Lightning',
                'description': 'NOAA GOES satellite lightning detection',
            }
        except Exception as e:
            status_data['sources']['lightning'] = {
                'available': False,
                'error': str(e),
                'icon': '⚡',
                'name': 'Lightning',
            }
        
        # Seismic status
        try:
            seismic_provider = SeismicEntropyProvider()
            seismic_activity = seismic_provider.client.get_global_activity()
            status_data['sources']['seismic'] = {
                'available': seismic_provider.is_available(),
                'activity': seismic_activity,
                'icon': '🌍',
                'name': 'Seismic',
                'description': 'USGS global earthquake network',
            }
        except Exception as e:
            status_data['sources']['seismic'] = {
                'available': False,
                'error': str(e),
                'icon': '🌍',
                'name': 'Seismic',
            }
        
        # Solar wind status
        try:
            solar_provider = SolarWindEntropyProvider()
            solar_status = solar_provider.client.get_space_weather_status()
            status_data['sources']['solar'] = {
                'available': solar_provider.is_available(),
                'weather': solar_status,
                'icon': '☀️',
                'name': 'Solar Wind',
                'description': 'NOAA DSCOVR spacecraft at L1 point',
            }
        except Exception as e:
            status_data['sources']['solar'] = {
                'available': False,
                'error': str(e),
                'icon': '☀️',
                'name': 'Solar Wind',
            }
        
        # Count available sources
        available_count = sum(1 for s in status_data['sources'].values() if s.get('available'))
        status_data['available_sources'] = available_count
        status_data['total_sources'] = len(status_data['sources'])
        
        return Response(status_data)
        
    except Exception as e:
        logger.exception("Failed to get global entropy status")
        return Response({
            'error': 'Failed to fetch status',
            'details': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_entropy_statistics(request: Request) -> Response:
    """
    Get global entropy statistics and activity.
    """
    try:
        # Get latest statistics or calculate on the fly
        try:
            latest_stats = GlobalEntropyStatistics.objects.latest()
            stats_age = (timezone.now() - latest_stats.recorded_at).total_seconds()
            
            # If stats are older than 1 hour, they might be stale
            if stats_age > 3600:
                should_refresh = True
            else:
                should_refresh = False
        except GlobalEntropyStatistics.DoesNotExist:
            latest_stats = None
            should_refresh = True
        
        # Calculate current statistics
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        response_data = {
            'timestamp': now.isoformat(),
            'period': '24h',
        }
        
        # Lightning batches in last 24h
        lightning_batches = LightningEntropyBatch.objects.filter(
            fetched_at__gte=last_24h
        )
        response_data['lightning'] = {
            'batches_24h': lightning_batches.count(),
            'total_strikes': sum(b.strikes_used for b in lightning_batches),
            'avg_quality': lightning_batches.aggregate(
                avg=models.Avg('quality_score')
            )['avg'] or 0.0,
        }
        
        # Seismic batches
        seismic_batches = SeismicEntropyBatch.objects.filter(
            fetched_at__gte=last_24h
        )
        response_data['seismic'] = {
            'batches_24h': seismic_batches.count(),
            'total_events': sum(b.events_used for b in seismic_batches),
            'largest_magnitude': max(
                (b.largest_magnitude for b in seismic_batches),
                default=0.0
            ),
        }
        
        # Solar wind batches
        solar_batches = SolarWindEntropyBatch.objects.filter(
            fetched_at__gte=last_24h
        )
        response_data['solar'] = {
            'batches_24h': solar_batches.count(),
            'avg_speed': solar_batches.aggregate(
                avg=models.Avg('average_speed_kmps')
            )['avg'] or 0.0,
            'current_storm_level': solar_batches.last().storm_level if solar_batches.exists() else 'unknown',
        }
        
        # Natural certificates
        certificates = NaturalEntropyCertificate.objects.filter(
            generation_timestamp__gte=last_24h
        )
        response_data['passwords'] = {
            'generated_24h': certificates.count(),
            'avg_quality': certificates.aggregate(
                avg=models.Avg('combined_quality_score')
            )['avg'] or 0.0,
            'most_used_sources': _calculate_source_usage(certificates),
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.exception("Failed to get entropy statistics")
        return Response({
            'error': 'Failed to fetch statistics',
            'details': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _calculate_source_usage(certificates) -> Dict[str, int]:
    """Calculate source usage counts."""
    usage = {'ocean': 0, 'lightning': 0, 'seismic': 0, 'solar': 0}
    for cert in certificates:
        for source in cert.sources_used:
            if source in usage:
                usage[source] += 1
    return usage


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_lightning_activity(request: Request) -> Response:
    """Get current lightning activity data."""
    try:
        provider = LightningEntropyProvider()
        strikes = provider.client.get_recent_strikes(minutes=30, limit=50)
        activity = provider.client.get_global_activity()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'global_activity': activity,
            'recent_strikes': [s.to_dict() for s in strikes[:20]],
            'strikes_count': len(strikes),
            'icon': '⚡',
        })
    except Exception as e:
        logger.error(f"Lightning activity fetch failed: {e}")
        return Response({
            'error': str(e),
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_seismic_activity(request: Request) -> Response:
    """Get current seismic activity data."""
    try:
        provider = SeismicEntropyProvider()
        earthquakes = provider.client.get_recent_earthquakes(hours=24, limit=50)
        activity = provider.client.get_global_activity()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'global_activity': activity,
            'recent_earthquakes': [eq.to_dict() for eq in earthquakes[:20]],
            'events_count': len(earthquakes),
            'icon': '🌍',
        })
    except Exception as e:
        logger.error(f"Seismic activity fetch failed: {e}")
        return Response({
            'error': str(e),
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_solar_wind_status(request: Request) -> Response:
    """Get current solar wind data."""
    try:
        provider = SolarWindEntropyProvider()
        readings = provider.client.get_latest_readings(limit=50)
        weather = provider.client.get_space_weather_status()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'space_weather': weather,
            'recent_readings': [r.to_dict() for r in readings[-20:]],
            'readings_count': len(readings),
            'icon': '☀️',
        })
    except Exception as e:
        logger.error(f"Solar wind fetch failed: {e}")
        return Response({
            'error': str(e),
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_entropy_preferences(request: Request) -> Response:
    """Get or update user's entropy source preferences."""
    try:
        prefs, created = UserEntropyPreferences.objects.get_or_create(
            user=request.user
        )
        
        if request.method == 'GET':
            return Response({
                'use_quantum': prefs.use_quantum,
                'use_ocean': prefs.use_ocean,
                'use_lightning': prefs.use_lightning,
                'use_seismic': prefs.use_seismic,
                'use_solar': prefs.use_solar,
                'use_genetic': prefs.use_genetic,
                'min_sources_required': prefs.min_sources_required,
                'notify_on_rare_events': prefs.notify_on_rare_events,
                'total_passwords_generated': prefs.total_passwords_generated,
            })
        
        elif request.method == 'PUT':
            data = request.data
            
            # Update boolean preferences
            for field in ['use_quantum', 'use_ocean', 'use_lightning', 
                          'use_seismic', 'use_solar', 'use_genetic',
                          'notify_on_rare_events']:
                if field in data:
                    setattr(prefs, field, bool(data[field]))
            
            # Update min sources
            if 'min_sources_required' in data:
                prefs.min_sources_required = max(1, min(5, int(data['min_sources_required'])))
            
            prefs.save()
            
            return Response({
                'success': True,
                'message': 'Preferences updated',
            })
        
    except Exception as e:
        logger.exception("Failed to handle entropy preferences")
        return Response({
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_certificates(request: Request) -> Response:
    """Get user's natural entropy certificates."""
    try:
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        certificates = NaturalEntropyCertificate.objects.filter(
            user=request.user
        )[offset:offset + limit]
        
        total = NaturalEntropyCertificate.objects.filter(user=request.user).count()
        
        return Response({
            'certificates': [cert.to_dict() for cert in certificates],
            'total': total,
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        logger.exception("Failed to fetch certificates")
        return Response({
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
