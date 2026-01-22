/**
 * GeolocationService - Mobile
 * 
 * Service for handling GPS location capture and travel verification
 * on mobile devices. Used for impossible travel detection.
 */

import { Platform, PermissionsAndroid } from 'react-native';
import Geolocation from '@react-native-community/geolocation';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = 'http://localhost:8000/api/security';

class GeolocationService {
  constructor() {
    this.watchId = null;
    this.lastLocation = null;
    this.isTracking = false;
  }

  /**
   * Request location permissions
   */
  async requestPermissions() {
    if (Platform.OS === 'android') {
      try {
        const granted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
          {
            title: 'Location Permission',
            message: 'This app needs access to your location for security verification.',
            buttonPositive: 'Allow',
            buttonNegative: 'Deny',
          }
        );
        return granted === PermissionsAndroid.RESULTS.GRANTED;
      } catch (err) {
        console.error('Permission error:', err);
        return false;
      }
    }
    // iOS handles permissions automatically
    return true;
  }

  /**
   * Check if permission is granted
   */
  async checkPermissions() {
    if (Platform.OS === 'android') {
      const granted = await PermissionsAndroid.check(
        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
      );
      return granted;
    }
    return true;
  }

  /**
   * Get current position (one-time)
   * @param {Object} options - Geolocation options
   * @returns {Promise<Object>} Position data
   */
  getCurrentPosition(options = {}) {
    return new Promise((resolve, reject) => {
      const defaultOptions = {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 30000,
        ...options
      };

      Geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_meters: position.coords.accuracy,
            altitude: position.coords.altitude,
            timestamp: position.timestamp,
            source: 'gps'
          };
          this.lastLocation = coords;
          resolve(coords);
        },
        (error) => {
          console.error('Geolocation error:', error);
          reject(error);
        },
        defaultOptions
      );
    });
  }

  /**
   * Start watching position (continuous)
   * @param {Function} onUpdate - Callback for position updates
   * @param {Function} onError - Callback for errors
   * @param {Object} options - Geolocation options
   */
  watchPosition(onUpdate, onError, options = {}) {
    if (this.watchId !== null) {
      this.stopWatching();
    }

    const defaultOptions = {
      enableHighAccuracy: true,
      distanceFilter: 100, // Update every 100 meters
      interval: 60000, // Update every minute
      fastestInterval: 30000,
      ...options
    };

    this.watchId = Geolocation.watchPosition(
      (position) => {
        const coords = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_meters: position.coords.accuracy,
          altitude: position.coords.altitude,
          timestamp: position.timestamp,
          source: 'gps'
        };
        this.lastLocation = coords;
        this.isTracking = true;
        onUpdate?.(coords);
      },
      (error) => {
        console.error('Watch position error:', error);
        onError?.(error);
      },
      defaultOptions
    );

    return this.watchId;
  }

  /**
   * Stop watching position
   */
  stopWatching() {
    if (this.watchId !== null) {
      Geolocation.clearWatch(this.watchId);
      this.watchId = null;
      this.isTracking = false;
    }
  }

  /**
   * Send location to server for analysis
   * @param {Object} coords - Coordinates to send
   * @returns {Promise<Object>} Analysis result
   */
  async sendLocationToServer(coords) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) {
        throw new Error('No auth token');
      }

      const response = await fetch(`${API_BASE}/geofence/location/record/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(coords)
      });

      if (!response.ok) {
        throw new Error('Failed to record location');
      }

      const data = await response.json();
      
      // Store last analysis
      await AsyncStorage.setItem('lastTravelAnalysis', JSON.stringify({
        timestamp: Date.now(),
        analysis: data.analysis
      }));

      return data;
    } catch (error) {
      console.error('Send location error:', error);
      throw error;
    }
  }

  /**
   * Get location and send to server
   * Convenience method combining getCurrentPosition and sendLocationToServer
   */
  async captureAndAnalyze() {
    const coords = await this.getCurrentPosition();
    return this.sendLocationToServer(coords);
  }

  /**
   * Get geofence zones
   */
  async getGeofenceZones() {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/zones/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to fetch zones');
      
      const data = await response.json();
      return data.zones || [];
    } catch (error) {
      console.error('Get zones error:', error);
      throw error;
    }
  }

  /**
   * Create a trusted zone
   * @param {Object} zoneData - Zone data
   */
  async createZone(zoneData) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/zones/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(zoneData)
      });

      if (!response.ok) throw new Error('Failed to create zone');
      
      return response.json();
    } catch (error) {
      console.error('Create zone error:', error);
      throw error;
    }
  }

  /**
   * Delete a trusted zone
   * @param {string} zoneId - Zone ID to delete
   */
  async deleteZone(zoneId) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/zones/${zoneId}/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete zone');
      
      return { success: true };
    } catch (error) {
      console.error('Delete zone error:', error);
      throw error;
    }
  }

  /**
   * Check if current location is in a trusted zone
   */
  async checkGeofence(latitude, longitude) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/check/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ latitude, longitude })
      });

      if (!response.ok) throw new Error('Failed to check geofence');
      
      return response.json();
    } catch (error) {
      console.error('Check geofence error:', error);
      throw error;
    }
  }

  /**
   * Get impossible travel events
   * @param {Object} options - Filter options
   */
  async getTravelEvents(options = {}) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const params = new URLSearchParams(options).toString();
      const url = `${API_BASE}/geofence/travel/events/${params ? '?' + params : ''}`;

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to fetch travel events');
      
      return response.json();
    } catch (error) {
      console.error('Get travel events error:', error);
      throw error;
    }
  }

  /**
   * Resolve a travel event
   * @param {string} eventId - Event ID
   * @param {boolean} isLegitimate - Whether travel was legitimate
   * @param {string} notes - Resolution notes
   */
  async resolveTravelEvent(eventId, isLegitimate, notes = '') {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/travel/resolve/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          event_id: eventId,
          is_legitimate: isLegitimate,
          resolution_notes: notes
        })
      });

      if (!response.ok) throw new Error('Failed to resolve event');
      
      return response.json();
    } catch (error) {
      console.error('Resolve event error:', error);
      throw error;
    }
  }

  /**
   * Get travel itineraries
   * @param {boolean} includePast - Include past itineraries
   */
  async getItineraries(includePast = false) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const url = `${API_BASE}/geofence/itinerary/?include_past=${includePast}`;

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to fetch itineraries');
      
      return response.json();
    } catch (error) {
      console.error('Get itineraries error:', error);
      throw error;
    }
  }

  /**
   * Add a travel itinerary
   * @param {Object} itinerary - Itinerary data
   */
  async addItinerary(itinerary) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/itinerary/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(itinerary)
      });

      if (!response.ok) throw new Error('Failed to add itinerary');
      
      return response.json();
    } catch (error) {
      console.error('Add itinerary error:', error);
      throw error;
    }
  }

  /**
   * Verify travel with booking reference
   * @param {string} bookingRef - PNR / Booking reference
   * @param {string} lastName - Passenger last name
   */
  async verifyBooking(bookingRef, lastName) {
    try {
      const token = await AsyncStorage.getItem('authToken');
      if (!token) throw new Error('No auth token');

      const response = await fetch(`${API_BASE}/geofence/travel/verify/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          booking_reference: bookingRef,
          last_name: lastName
        })
      });

      if (!response.ok) throw new Error('Failed to verify booking');
      
      return response.json();
    } catch (error) {
      console.error('Verify booking error:', error);
      throw error;
    }
  }

  /**
   * Get last stored location
   */
  getLastLocation() {
    return this.lastLocation;
  }

  /**
   * Calculate distance between two points (Haversine)
   */
  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = this._toRad(lat2 - lat1);
    const dLon = this._toRad(lon2 - lon1);
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(this._toRad(lat1)) * Math.cos(this._toRad(lat2)) * 
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  _toRad(deg) {
    return deg * (Math.PI / 180);
  }
}

// Export singleton instance
const geolocationService = new GeolocationService();
export default geolocationService;
