/**
 * Geofence Service
 * 
 * API client for geofencing and impossible travel detection endpoints.
 * Provides methods for location recording, zone management, and travel verification.
 */

const BASE_URL = '/api/security';

/**
 * Get authentication headers
 */
const getHeaders = (authToken) => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authToken}`
});

// =============================================================================
// Location Recording
// =============================================================================

/**
 * Record current GPS location and get travel analysis
 * @param {string} authToken - JWT authentication token
 * @param {Object} locationData - GPS coordinates and metadata
 * @returns {Promise<Object>} Location record and travel analysis
 */
export const recordLocation = async (authToken, locationData) => {
    const response = await fetch(`${BASE_URL}/geofence/location/record/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            latitude: locationData.latitude,
            longitude: locationData.longitude,
            accuracy_meters: locationData.accuracy || 0,
            altitude: locationData.altitude || null,
            source: locationData.source || 'gps',
            device_id: locationData.deviceId || null
        })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to record location');
    }
    
    return response.json();
};

/**
 * Get location history for the authenticated user
 * @param {string} authToken - JWT authentication token
 * @param {Object} options - Query options (days, limit)
 * @returns {Promise<Object>} Location history records
 */
export const getLocationHistory = async (authToken, options = {}) => {
    const params = new URLSearchParams();
    if (options.days) params.append('days', options.days);
    if (options.limit) params.append('limit', options.limit);
    
    const response = await fetch(
        `${BASE_URL}/geofence/location/history/?${params}`,
        { headers: getHeaders(authToken) }
    );
    
    if (!response.ok) {
        throw new Error('Failed to fetch location history');
    }
    
    return response.json();
};

// =============================================================================
// Geofence Zones
// =============================================================================

/**
 * Get all trusted zones for the user
 * @param {string} authToken - JWT authentication token
 * @returns {Promise<Object>} List of geofence zones
 */
export const getZones = async (authToken) => {
    const response = await fetch(`${BASE_URL}/geofence/zones/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch zones');
    }
    
    return response.json();
};

/**
 * Create a new trusted zone
 * @param {string} authToken - JWT authentication token
 * @param {Object} zoneData - Zone configuration
 * @returns {Promise<Object>} Created zone
 */
export const createZone = async (authToken, zoneData) => {
    const response = await fetch(`${BASE_URL}/geofence/zones/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify(zoneData)
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to create zone');
    }
    
    return response.json();
};

/**
 * Update an existing zone
 * @param {string} authToken - JWT authentication token
 * @param {string} zoneId - Zone UUID
 * @param {Object} zoneData - Updated zone data
 * @returns {Promise<Object>} Updated zone
 */
export const updateZone = async (authToken, zoneId, zoneData) => {
    const response = await fetch(`${BASE_URL}/geofence/zones/${zoneId}/`, {
        method: 'PUT',
        headers: getHeaders(authToken),
        body: JSON.stringify(zoneData)
    });
    
    if (!response.ok) {
        throw new Error('Failed to update zone');
    }
    
    return response.json();
};

/**
 * Delete a trusted zone
 * @param {string} authToken - JWT authentication token
 * @param {string} zoneId - Zone UUID
 * @returns {Promise<void>}
 */
export const deleteZone = async (authToken, zoneId) => {
    const response = await fetch(`${BASE_URL}/geofence/zones/${zoneId}/`, {
        method: 'DELETE',
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete zone');
    }
};

/**
 * Check if coordinates are in a trusted zone
 * @param {string} authToken - JWT authentication token
 * @param {number} latitude - Latitude
 * @param {number} longitude - Longitude
 * @returns {Promise<Object>} Geofence check result
 */
export const checkGeofence = async (authToken, latitude, longitude) => {
    const response = await fetch(`${BASE_URL}/geofence/check/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({ latitude, longitude })
    });
    
    if (!response.ok) {
        throw new Error('Failed to check geofence');
    }
    
    return response.json();
};

// =============================================================================
// Impossible Travel Events
// =============================================================================

/**
 * Get impossible travel events
 * @param {string} authToken - JWT authentication token
 * @param {Object} options - Query options (resolved, severity, limit)
 * @returns {Promise<Object>} Travel events
 */
export const getTravelEvents = async (authToken, options = {}) => {
    const params = new URLSearchParams();
    if (options.resolved !== undefined) params.append('resolved', options.resolved);
    if (options.severity) params.append('severity', options.severity);
    if (options.limit) params.append('limit', options.limit);
    
    const response = await fetch(
        `${BASE_URL}/geofence/travel/events/?${params}`,
        { headers: getHeaders(authToken) }
    );
    
    if (!response.ok) {
        throw new Error('Failed to fetch travel events');
    }
    
    return response.json();
};

/**
 * Resolve a travel event
 * @param {string} authToken - JWT authentication token
 * @param {string} eventId - Event UUID
 * @param {Object} resolution - Resolution data (is_legitimate, notes)
 * @returns {Promise<Object>} Resolved event
 */
export const resolveTravelEvent = async (authToken, eventId, resolution) => {
    const response = await fetch(`${BASE_URL}/geofence/travel/resolve/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            event_id: eventId,
            is_legitimate: resolution.isLegitimate,
            notes: resolution.notes || ''
        })
    });
    
    if (!response.ok) {
        throw new Error('Failed to resolve travel event');
    }
    
    return response.json();
};

/**
 * Analyze travel between two locations
 * @param {string} authToken - JWT authentication token
 * @param {Object} source - Source coordinates {latitude, longitude, timestamp}
 * @param {Object} destination - Destination coordinates
 * @returns {Promise<Object>} Travel analysis result
 */
export const analyzeTravel = async (authToken, source, destination) => {
    const response = await fetch(`${BASE_URL}/geofence/travel/analyze/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            source_latitude: source.latitude,
            source_longitude: source.longitude,
            source_timestamp: source.timestamp,
            destination_latitude: destination.latitude,
            destination_longitude: destination.longitude,
            destination_timestamp: destination.timestamp
        })
    });
    
    if (!response.ok) {
        throw new Error('Failed to analyze travel');
    }
    
    return response.json();
};

// =============================================================================
// Travel Itineraries
// =============================================================================

/**
 * Get travel itineraries
 * @param {string} authToken - JWT authentication token
 * @param {Object} options - Query options (upcoming, verified)
 * @returns {Promise<Object>} Itineraries
 */
export const getItineraries = async (authToken, options = {}) => {
    const params = new URLSearchParams();
    if (options.upcoming) params.append('upcoming', 'true');
    if (options.verified !== undefined) params.append('verified', options.verified);
    
    const response = await fetch(
        `${BASE_URL}/geofence/itinerary/?${params}`,
        { headers: getHeaders(authToken) }
    );
    
    if (!response.ok) {
        throw new Error('Failed to fetch itineraries');
    }
    
    return response.json();
};

/**
 * Add a travel itinerary
 * @param {string} authToken - JWT authentication token
 * @param {Object} itinerary - Itinerary data
 * @returns {Promise<Object>} Created itinerary
 */
export const addItinerary = async (authToken, itinerary) => {
    const response = await fetch(`${BASE_URL}/geofence/itinerary/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify(itinerary)
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to add itinerary');
    }
    
    return response.json();
};

/**
 * Delete a travel itinerary
 * @param {string} authToken - JWT authentication token
 * @param {string} itineraryId - Itinerary UUID
 * @returns {Promise<void>}
 */
export const deleteItinerary = async (authToken, itineraryId) => {
    const response = await fetch(`${BASE_URL}/geofence/itinerary/${itineraryId}/`, {
        method: 'DELETE',
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete itinerary');
    }
};

/**
 * Verify travel with airline booking
 * @param {string} authToken - JWT authentication token
 * @param {Object} booking - Booking details (reference, lastName, itineraryId)
 * @returns {Promise<Object>} Verification result
 */
export const verifyTravel = async (authToken, booking) => {
    const response = await fetch(`${BASE_URL}/geofence/travel/verify/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            booking_reference: booking.reference,
            last_name: booking.lastName,
            itinerary_id: booking.itineraryId || null
        })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to verify travel');
    }
    
    return response.json();
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get current GPS location from browser
 * @returns {Promise<Object>} Coordinates {latitude, longitude, accuracy}
 */
export const getCurrentLocation = () => {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation not supported'));
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    altitude: position.coords.altitude,
                    timestamp: new Date().toISOString()
                });
            },
            (error) => {
                reject(new Error(`Location error: ${error.message}`));
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 30000
            }
        );
    });
};

/**
 * Calculate distance between two points (km)
 * @param {number} lat1 - First point latitude
 * @param {number} lon1 - First point longitude
 * @param {number} lat2 - Second point latitude
 * @param {number} lon2 - Second point longitude
 * @returns {number} Distance in kilometers
 */
export const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
};

/**
 * Format travel mode for display
 * @param {string} mode - Travel mode key
 * @returns {Object} {icon, label}
 */
export const formatTravelMode = (mode) => {
    const modes = {
        walking: { icon: '🚶', label: 'Walking' },
        driving: { icon: '🚗', label: 'Driving' },
        train: { icon: '🚄', label: 'High-Speed Rail' },
        flight: { icon: '✈️', label: 'Commercial Flight' },
        supersonic: { icon: '🚀', label: 'Impossible (Supersonic)' },
        unknown: { icon: '❓', label: 'Unknown' }
    };
    return modes[mode] || modes.unknown;
};

/**
 * Format severity for display
 * @param {string} severity - Severity level
 * @returns {Object} {color, label}
 */
export const formatSeverity = (severity) => {
    const levels = {
        none: { color: '#22c55e', label: 'Normal' },
        low: { color: '#84cc16', label: 'Low' },
        medium: { color: '#eab308', label: 'Medium' },
        high: { color: '#f97316', label: 'High' },
        critical: { color: '#ef4444', label: 'Critical' }
    };
    return levels[severity] || levels.none;
};

export default {
    recordLocation,
    getLocationHistory,
    getZones,
    createZone,
    updateZone,
    deleteZone,
    checkGeofence,
    getTravelEvents,
    resolveTravelEvent,
    analyzeTravel,
    getItineraries,
    addItinerary,
    deleteItinerary,
    verifyTravel,
    getCurrentLocation,
    calculateDistance,
    formatTravelMode,
    formatSeverity
};
