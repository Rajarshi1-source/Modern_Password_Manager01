"""
Geofence & Impossible Travel Serializers
==========================================

Serializers for geofencing and travel verification API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from decimal import Decimal


class CoordinatesSerializer(serializers.Serializer):
    """Serializer for GPS coordinates."""
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7,
        min_value=Decimal('-90'), max_value=Decimal('90')
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7,
        min_value=Decimal('-180'), max_value=Decimal('180')
    )
    accuracy_meters = serializers.FloatField(required=False, default=0)
    altitude = serializers.FloatField(required=False, allow_null=True)
    source = serializers.ChoiceField(
        choices=['gps', 'network', 'ip_fallback', 'manual'],
        default='gps'
    )


class LocationHistorySerializer(serializers.Serializer):
    """Serializer for location history records."""
    id = serializers.UUIDField(read_only=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    accuracy_meters = serializers.FloatField()
    altitude = serializers.FloatField(allow_null=True)
    ip_address = serializers.IPAddressField()
    ip_location_city = serializers.CharField()
    ip_location_country = serializers.CharField()
    source = serializers.CharField()
    timestamp = serializers.DateTimeField()
    is_ntp_verified = serializers.BooleanField()
    device_id = serializers.UUIDField(source='device.device_id', allow_null=True)
    device_name = serializers.CharField(source='device.device_name', allow_null=True)


class LocationRecordInputSerializer(serializers.Serializer):
    """Input serializer for recording location."""
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    accuracy_meters = serializers.FloatField(required=False, default=0)
    altitude = serializers.FloatField(required=False, allow_null=True)
    source = serializers.ChoiceField(
        choices=['gps', 'network', 'ip_fallback'],
        default='gps'
    )
    device_id = serializers.UUIDField(required=False, allow_null=True)


class GeofenceZoneSerializer(serializers.Serializer):
    """Serializer for geofence zones."""
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=100)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = serializers.IntegerField(min_value=50, max_value=50000)
    is_always_trusted = serializers.BooleanField(default=True)
    require_mfa_outside = serializers.BooleanField(default=True)
    notify_on_entry = serializers.BooleanField(default=False)
    notify_on_exit = serializers.BooleanField(default=False)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class GeofenceZoneCreateSerializer(serializers.Serializer):
    """Input serializer for creating geofence zones."""
    name = serializers.CharField(max_length=100)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = serializers.IntegerField(min_value=50, max_value=50000, default=500)
    is_always_trusted = serializers.BooleanField(default=True)
    require_mfa_outside = serializers.BooleanField(default=True)
    notify_on_entry = serializers.BooleanField(default=False)
    notify_on_exit = serializers.BooleanField(default=False)


class ImpossibleTravelEventSerializer(serializers.Serializer):
    """Serializer for impossible travel events."""
    id = serializers.UUIDField(read_only=True)
    
    # Locations
    source_location_id = serializers.UUIDField()
    source_latitude = serializers.DecimalField(
        source='source_location.latitude',
        max_digits=10, decimal_places=7
    )
    source_longitude = serializers.DecimalField(
        source='source_location.longitude',
        max_digits=10, decimal_places=7
    )
    source_city = serializers.CharField(source='source_location.ip_location_city')
    source_timestamp = serializers.DateTimeField(source='source_location.timestamp')
    
    destination_location_id = serializers.UUIDField()
    destination_latitude = serializers.DecimalField(
        source='destination_location.latitude',
        max_digits=10, decimal_places=7
    )
    destination_longitude = serializers.DecimalField(
        source='destination_location.longitude',
        max_digits=10, decimal_places=7
    )
    destination_city = serializers.CharField(source='destination_location.ip_location_city')
    destination_timestamp = serializers.DateTimeField(source='destination_location.timestamp')
    
    # Physics data
    distance_km = serializers.FloatField()
    time_difference_seconds = serializers.IntegerField()
    time_difference_display = serializers.SerializerMethodField()
    required_speed_kmh = serializers.FloatField()
    max_allowed_speed_kmh = serializers.FloatField()
    inferred_travel_mode = serializers.CharField()
    inferred_travel_mode_display = serializers.CharField(
        source='get_inferred_travel_mode_display'
    )
    
    # Risk assessment
    severity = serializers.CharField()
    severity_display = serializers.CharField(source='get_severity_display')
    risk_score = serializers.IntegerField()
    action_taken = serializers.CharField()
    action_taken_display = serializers.CharField(source='get_action_taken_display')
    
    # Status
    is_legitimate = serializers.BooleanField()
    airline_verified = serializers.BooleanField()
    is_cloned_session = serializers.BooleanField()
    resolved = serializers.BooleanField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    resolution_notes = serializers.CharField()
    
    created_at = serializers.DateTimeField()
    
    def get_time_difference_display(self, obj):
        """Format time difference for display."""
        seconds = obj.time_difference_seconds
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"


class TravelItinerarySerializer(serializers.Serializer):
    """Serializer for travel itineraries."""
    id = serializers.UUIDField(read_only=True)
    
    # Departure
    departure_city = serializers.CharField()
    departure_country = serializers.CharField()
    departure_airport_code = serializers.CharField()
    departure_latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, allow_null=True
    )
    departure_longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, allow_null=True
    )
    departure_time = serializers.DateTimeField()
    
    # Arrival
    arrival_city = serializers.CharField()
    arrival_country = serializers.CharField()
    arrival_airport_code = serializers.CharField()
    arrival_latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, allow_null=True
    )
    arrival_longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, allow_null=True
    )
    arrival_time = serializers.DateTimeField()
    
    # Flight details
    airline_code = serializers.CharField()
    airline_name = serializers.CharField()
    flight_number = serializers.CharField()
    booking_reference = serializers.CharField()
    
    # Verification
    verification_status = serializers.CharField()
    verification_status_display = serializers.CharField(
        source='get_verification_status_display'
    )
    verification_provider = serializers.CharField()
    verified_at = serializers.DateTimeField(allow_null=True)
    
    # Computed
    duration_hours = serializers.FloatField()
    
    created_at = serializers.DateTimeField(read_only=True)


class TravelItineraryCreateSerializer(serializers.Serializer):
    """Input serializer for creating travel itineraries."""
    departure_city = serializers.CharField(max_length=255)
    departure_country = serializers.CharField(max_length=100, required=False)
    departure_airport_code = serializers.CharField(max_length=10, required=False)
    departure_time = serializers.DateTimeField()
    
    arrival_city = serializers.CharField(max_length=255)
    arrival_country = serializers.CharField(max_length=100, required=False)
    arrival_airport_code = serializers.CharField(max_length=10, required=False)
    arrival_time = serializers.DateTimeField()
    
    airline_code = serializers.CharField(max_length=10, required=False)
    airline_name = serializers.CharField(max_length=100, required=False)
    flight_number = serializers.CharField(max_length=20, required=False)
    booking_reference = serializers.CharField(max_length=50, required=False)
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate arrival is after departure."""
        if data['arrival_time'] <= data['departure_time']:
            raise serializers.ValidationError(
                "Arrival time must be after departure time"
            )
        return data


class TravelVerificationSerializer(serializers.Serializer):
    """Input serializer for verifying travel via booking reference."""
    booking_reference = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=100)
    itinerary_id = serializers.UUIDField(required=False, allow_null=True)


class TravelAnalysisResultSerializer(serializers.Serializer):
    """Serializer for travel analysis results."""
    is_plausible = serializers.BooleanField()
    distance_km = serializers.FloatField()
    time_seconds = serializers.IntegerField()
    required_speed_kmh = serializers.FloatField()
    max_allowed_speed_kmh = serializers.FloatField()
    inferred_mode = serializers.CharField()
    severity = serializers.CharField()
    action = serializers.CharField()
    risk_score = serializers.IntegerField()
    is_cloned_session = serializers.BooleanField()
    has_matching_itinerary = serializers.BooleanField()
    recommendations = serializers.ListField(child=serializers.CharField())


class GeofenceCheckResultSerializer(serializers.Serializer):
    """Serializer for geofence check results."""
    is_in_trusted_zone = serializers.BooleanField()
    zone_name = serializers.CharField(allow_null=True)
    zone_id = serializers.CharField(allow_null=True)
    distance_to_nearest_zone = serializers.FloatField()
    requires_mfa = serializers.BooleanField()


class ResolveTravelEventSerializer(serializers.Serializer):
    """Input serializer for resolving travel events."""
    event_id = serializers.UUIDField()
    is_legitimate = serializers.BooleanField(default=True)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)
