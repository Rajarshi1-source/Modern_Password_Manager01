"""
Geofence & Impossible Travel API Views
=======================================

API endpoints for geofencing and travel verification.
"""

import logging
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ipware import get_client_ip

from ..models import (
    LocationHistory, ImpossibleTravelEvent,
    GeofenceZone, TravelItinerary, UserDevice
)
from ..serializers.geofence_serializers import (
    LocationHistorySerializer, LocationRecordInputSerializer,
    GeofenceZoneSerializer, GeofenceZoneCreateSerializer,
    ImpossibleTravelEventSerializer, TravelItinerarySerializer,
    TravelItineraryCreateSerializer, TravelVerificationSerializer,
    TravelAnalysisResultSerializer, GeofenceCheckResultSerializer,
    ResolveTravelEventSerializer
)
from ..services.impossible_travel_service import (
    impossible_travel_service, Coordinates
)

logger = logging.getLogger(__name__)


# =============================================================================
# Location Recording
# =============================================================================

class RecordLocationView(APIView):
    """Record current location and analyze for impossible travel."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Record GPS location.
        
        Returns travel analysis if suspicious travel detected.
        """
        serializer = LocationRecordInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        client_ip, _ = get_client_ip(request)
        
        # Get device if provided
        device = None
        if data.get('device_id'):
            device = UserDevice.objects.filter(
                user=request.user,
                device_id=data['device_id']
            ).first()
        
        # Create new location
        new_coords = Coordinates(
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            accuracy_meters=data.get('accuracy_meters', 0),
            altitude=data.get('altitude'),
            source=data.get('source', 'gps')
        )
        
        # Analyze travel before recording
        analysis = impossible_travel_service.analyze_travel(
            user=request.user,
            new_location=new_coords
        )
        
        # Record location
        location = impossible_travel_service.record_location(
            user=request.user,
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            ip_address=client_ip or '127.0.0.1',
            source=data.get('source', 'gps'),
            accuracy_meters=data.get('accuracy_meters', 0),
            altitude=data.get('altitude'),
            device=device
        )
        
        # Record event if suspicious
        travel_event = None
        if not analysis.is_plausible or analysis.risk_score > 50:
            previous_location = LocationHistory.objects.filter(
                user=request.user
            ).exclude(id=location.id).order_by('-timestamp').first()
            
            if previous_location:
                travel_event = impossible_travel_service.record_impossible_travel_event(
                    user=request.user,
                    source_location=previous_location,
                    destination_location=location,
                    analysis=analysis
                )
        
        # Prepare response
        response_data = {
            'location': LocationHistorySerializer(location).data,
            'analysis': {
                'is_plausible': analysis.is_plausible,
                'distance_km': round(analysis.distance_km, 2),
                'time_seconds': analysis.time_seconds,
                'required_speed_kmh': round(analysis.required_speed_kmh, 2),
                'inferred_mode': analysis.inferred_mode.value,
                'severity': analysis.severity.value,
                'action': analysis.action.value,
                'risk_score': analysis.risk_score,
                'is_cloned_session': analysis.is_cloned_session,
                'recommendations': analysis.recommendations
            }
        }
        
        if travel_event:
            response_data['travel_event_id'] = str(travel_event.id)
            response_data['action_required'] = analysis.action.value
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class LocationHistoryView(APIView):
    """View location history."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's location history."""
        days = int(request.query_params.get('days', 30))
        limit = min(int(request.query_params.get('limit', 100)), 500)
        
        since = timezone.now() - timedelta(days=days)
        
        locations = LocationHistory.objects.filter(
            user=request.user,
            timestamp__gte=since
        ).select_related('device').order_by('-timestamp')[:limit]
        
        serializer = LocationHistorySerializer(locations, many=True)
        
        return Response({
            'locations': serializer.data,
            'total_count': len(serializer.data),
            'days': days
        })


# =============================================================================
# Geofence Zones
# =============================================================================

class GeofenceZoneListView(APIView):
    """List and create geofence zones."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's geofence zones."""
        zones = GeofenceZone.objects.filter(user=request.user)
        serializer = GeofenceZoneSerializer(zones, many=True)
        
        return Response({
            'zones': serializer.data,
            'total_count': zones.count()
        })
    
    def post(self, request):
        """Create a new geofence zone."""
        serializer = GeofenceZoneCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        zone = GeofenceZone.objects.create(
            user=request.user,
            **data
        )
        
        return Response(
            GeofenceZoneSerializer(zone).data,
            status=status.HTTP_201_CREATED
        )


class GeofenceZoneDetailView(APIView):
    """Manage individual geofence zones."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, zone_id):
        """Get zone details."""
        zone = get_object_or_404(
            GeofenceZone,
            id=zone_id,
            user=request.user
        )
        return Response(GeofenceZoneSerializer(zone).data)
    
    def put(self, request, zone_id):
        """Update a geofence zone."""
        zone = get_object_or_404(
            GeofenceZone,
            id=zone_id,
            user=request.user
        )
        
        serializer = GeofenceZoneCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        for field, value in serializer.validated_data.items():
            setattr(zone, field, value)
        zone.save()
        
        return Response(GeofenceZoneSerializer(zone).data)
    
    def delete(self, request, zone_id):
        """Delete a geofence zone."""
        zone = get_object_or_404(
            GeofenceZone,
            id=zone_id,
            user=request.user
        )
        zone.delete()
        
        return Response({'success': True}, status=status.HTTP_200_OK)


class GeofenceCheckView(APIView):
    """Check if coordinates are within trusted zones."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Check coordinates against geofence zones."""
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response(
                {'error': 'latitude and longitude required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = impossible_travel_service.check_geofence_zones(
            user=request.user,
            latitude=float(latitude),
            longitude=float(longitude)
        )
        
        return Response({
            'is_in_trusted_zone': result.is_in_trusted_zone,
            'zone_name': result.zone_name,
            'zone_id': result.zone_id,
            'distance_to_nearest_zone': round(result.distance_to_nearest_zone, 2),
            'requires_mfa': result.requires_mfa
        })


# =============================================================================
# Impossible Travel Events
# =============================================================================

class ImpossibleTravelEventListView(APIView):
    """List impossible travel events."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's impossible travel events."""
        days = int(request.query_params.get('days', 30))
        resolved = request.query_params.get('resolved')
        severity = request.query_params.get('severity')
        
        since = timezone.now() - timedelta(days=days)
        
        events = ImpossibleTravelEvent.objects.filter(
            user=request.user,
            created_at__gte=since
        ).select_related(
            'source_location', 'destination_location'
        ).order_by('-created_at')
        
        if resolved is not None:
            events = events.filter(resolved=(resolved.lower() == 'true'))
        
        if severity:
            events = events.filter(severity=severity)
        
        serializer = ImpossibleTravelEventSerializer(events, many=True)
        
        unresolved = events.filter(resolved=False).count()
        critical = events.filter(severity='critical').count()
        
        return Response({
            'events': serializer.data,
            'total_count': len(serializer.data),
            'unresolved_count': unresolved,
            'critical_count': critical
        })


class ResolveTravelEventView(APIView):
    """Resolve an impossible travel event."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Mark a travel event as resolved."""
        serializer = ResolveTravelEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        event = get_object_or_404(
            ImpossibleTravelEvent,
            id=data['event_id'],
            user=request.user
        )
        
        if event.resolved:
            return Response(
                {'error': 'Event already resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        event.resolve(
            user=request.user,
            legitimate=data.get('is_legitimate', True),
            notes=data.get('resolution_notes', '')
        )
        
        return Response({
            'success': True,
            'event_id': str(event.id),
            'resolved': True,
            'is_legitimate': event.is_legitimate
        })


# =============================================================================
# Travel Itineraries
# =============================================================================

class TravelItineraryListView(APIView):
    """List and create travel itineraries."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's travel itineraries."""
        include_past = request.query_params.get('include_past', 'false')
        
        itineraries = TravelItinerary.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-departure_time')
        
        if include_past.lower() != 'true':
            itineraries = itineraries.filter(
                arrival_time__gte=timezone.now() - timedelta(hours=24)
            )
        
        serializer = TravelItinerarySerializer(itineraries, many=True)
        
        return Response({
            'itineraries': serializer.data,
            'total_count': len(serializer.data)
        })
    
    def post(self, request):
        """Create a new travel itinerary."""
        serializer = TravelItineraryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Try to get airport coordinates
        from ..services.airline_api_service import airline_api_service
        
        dep_airport = airline_api_service.get_airport(
            data.get('departure_airport_code', '')
        )
        arr_airport = airline_api_service.get_airport(
            data.get('arrival_airport_code', '')
        )
        
        itinerary = TravelItinerary.objects.create(
            user=request.user,
            departure_latitude=dep_airport.latitude if dep_airport else None,
            departure_longitude=dep_airport.longitude if dep_airport else None,
            arrival_latitude=arr_airport.latitude if arr_airport else None,
            arrival_longitude=arr_airport.longitude if arr_airport else None,
            **data
        )
        
        return Response(
            TravelItinerarySerializer(itinerary).data,
            status=status.HTTP_201_CREATED
        )


class TravelItineraryDetailView(APIView):
    """Manage individual travel itineraries."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, itinerary_id):
        """Get itinerary details."""
        itinerary = get_object_or_404(
            TravelItinerary,
            id=itinerary_id,
            user=request.user
        )
        return Response(TravelItinerarySerializer(itinerary).data)
    
    def delete(self, request, itinerary_id):
        """Delete a travel itinerary."""
        itinerary = get_object_or_404(
            TravelItinerary,
            id=itinerary_id,
            user=request.user
        )
        itinerary.is_active = False
        itinerary.save()
        
        return Response({'success': True}, status=status.HTTP_200_OK)


class VerifyTravelView(APIView):
    """Verify travel via airline booking reference."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Verify a booking reference with airline API."""
        serializer = TravelVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        from ..services.airline_api_service import airline_api_service
        
        # Verify with airline API
        verification = airline_api_service.verify_booking(
            booking_reference=data['booking_reference'],
            last_name=data['last_name']
        )
        
        # Update itinerary if provided
        if data.get('itinerary_id') and verification.is_valid:
            try:
                itinerary = TravelItinerary.objects.get(
                    id=data['itinerary_id'],
                    user=request.user
                )
                itinerary.verification_status = 'verified'
                itinerary.verification_provider = 'amadeus'
                itinerary.verification_data = verification.raw_data
                itinerary.verified_at = timezone.now()
                itinerary.save()
            except TravelItinerary.DoesNotExist:
                pass
        
        return Response({
            'is_valid': verification.is_valid,
            'booking_reference': verification.booking_reference,
            'passenger_name': verification.passenger_name,
            'error_message': verification.error_message
        })


# =============================================================================
# Travel Analysis
# =============================================================================

class AnalyzeTravelView(APIView):
    """Analyze travel plausibility."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Analyze if travel between two points is plausible.
        
        Used for pre-flight checks before blocking access.
        """
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response(
                {'error': 'latitude and longitude required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_coords = Coordinates(
            latitude=float(latitude),
            longitude=float(longitude),
            source='manual'
        )
        
        analysis = impossible_travel_service.analyze_travel(
            user=request.user,
            new_location=new_coords
        )
        
        return Response({
            'is_plausible': analysis.is_plausible,
            'distance_km': round(analysis.distance_km, 2),
            'time_seconds': analysis.time_seconds,
            'required_speed_kmh': round(analysis.required_speed_kmh, 2),
            'max_allowed_speed_kmh': analysis.max_allowed_speed_kmh,
            'inferred_mode': analysis.inferred_mode.value,
            'severity': analysis.severity.value,
            'action': analysis.action.value,
            'risk_score': analysis.risk_score,
            'is_cloned_session': analysis.is_cloned_session,
            'has_matching_itinerary': analysis.matching_itinerary is not None,
            'recommendations': analysis.recommendations
        })
