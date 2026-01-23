/**
 * Mesh Network Service - Mobile
 * ==============================
 * 
 * BLE mesh networking + Shamir secret sharing for React Native.
 * Handles dead drop creation, fragment distribution, and collection.
 */

import { Platform, PermissionsAndroid } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { BleManager } from 'react-native-ble-plx';
import Geolocation from '@react-native-community/geolocation';

const API_BASE = 'http://your-api-url/api/mesh';

// BLE Service UUID for mesh protocol
const MESH_SERVICE_UUID = '0000dead-0000-1000-8000-00805f9b34fb';
const FRAGMENT_CHAR_UUID = '0000f001-0000-1000-8000-00805f9b34fb';

class MeshService {
  constructor() {
    this.bleManager = null;
    this.isScanning = false;
    this.discoveredNodes = new Map();
    this.token = null;
  }

  // ===========================================================================
  // Initialization
  // ===========================================================================

  async initialize() {
    try {
      this.bleManager = new BleManager();
      this.token = await AsyncStorage.getItem('authToken');
      
      // Request permissions on Android
      if (Platform.OS === 'android') {
        await this.requestAndroidPermissions();
      }

      // Check BLE state
      const state = await this.bleManager.state();
      if (state !== 'PoweredOn') {
        console.warn('Bluetooth is not powered on');
      }

      return true;
    } catch (error) {
      console.error('Failed to initialize MeshService:', error);
      return false;
    }
  }

  async requestAndroidPermissions() {
    const permissions = [
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_ADVERTISE,
    ];

    for (const permission of permissions) {
      const granted = await PermissionsAndroid.request(permission);
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        console.warn(`Permission ${permission} not granted`);
      }
    }
  }

  // ===========================================================================
  // API Methods
  // ===========================================================================

  async getAuthHeaders() {
    if (!this.token) {
      this.token = await AsyncStorage.getItem('authToken');
    }
    return {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json',
    };
  }

  async getDeadDrops() {
    const response = await fetch(`${API_BASE}/deaddrops/`, {
      headers: await this.getAuthHeaders(),
    });
    return response.json();
  }

  async getDeadDropDetail(dropId) {
    const response = await fetch(`${API_BASE}/deaddrops/${dropId}/`, {
      headers: await this.getAuthHeaders(),
    });
    return response.json();
  }

  async createDeadDrop(data) {
    const response = await fetch(`${API_BASE}/deaddrops/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return response.json();
  }

  async cancelDeadDrop(dropId) {
    const response = await fetch(`${API_BASE}/deaddrops/${dropId}/cancel/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
    });
    return response.json();
  }

  async collectDeadDrop(dropId, locationData) {
    const response = await fetch(`${API_BASE}/deaddrops/${dropId}/collect/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify({ location: locationData }),
    });
    return response.json();
  }

  // ===========================================================================
  // Mesh Node Management
  // ===========================================================================

  async getMeshNodes() {
    const response = await fetch(`${API_BASE}/nodes/`, {
      headers: await this.getAuthHeaders(),
    });
    return response.json();
  }

  async registerAsNode(deviceInfo) {
    const response = await fetch(`${API_BASE}/nodes/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify(deviceInfo),
    });
    return response.json();
  }

  async pingNode(nodeId, location = null) {
    const body = location ? { latitude: location.lat, longitude: location.lng } : {};
    const response = await fetch(`${API_BASE}/nodes/${nodeId}/ping/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify(body),
    });
    return response.json();
  }

  async getNearbyNodes(lat, lng, radiusKm = 10) {
    const response = await fetch(
      `${API_BASE}/nodes/nearby/?lat=${lat}&lon=${lng}&radius=${radiusKm}`,
      { headers: await this.getAuthHeaders() }
    );
    return response.json();
  }

  // ===========================================================================
  // BLE Scanning
  // ===========================================================================

  async startScanningForNodes(onNodeDiscovered, durationMs = 10000) {
    if (this.isScanning) {
      console.warn('Already scanning');
      return;
    }

    this.isScanning = true;
    this.discoveredNodes.clear();

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.stopScanning();
        resolve(Array.from(this.discoveredNodes.values()));
      }, durationMs);

      this.bleManager.startDeviceScan(
        [MESH_SERVICE_UUID],
        { allowDuplicates: false },
        (error, device) => {
          if (error) {
            clearTimeout(timeoutId);
            this.isScanning = false;
            reject(error);
            return;
          }

          if (device && device.name?.includes('MeshNode')) {
            const nodeInfo = {
              id: device.id,
              name: device.name,
              rssi: device.rssi,
              discoveredAt: Date.now(),
            };

            this.discoveredNodes.set(device.id, nodeInfo);
            
            if (onNodeDiscovered) {
              onNodeDiscovered(nodeInfo);
            }
          }
        }
      );
    });
  }

  stopScanning() {
    if (this.bleManager && this.isScanning) {
      this.bleManager.stopDeviceScan();
      this.isScanning = false;
    }
  }

  getDiscoveredNodes() {
    return Array.from(this.discoveredNodes.values());
  }

  // ===========================================================================
  // Location Verification
  // ===========================================================================

  getCurrentLocation() {
    return new Promise((resolve, reject) => {
      Geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_meters: position.coords.accuracy,
            altitude: position.coords.altitude,
          });
        },
        (error) => reject(error),
        { 
          enableHighAccuracy: true, 
          timeout: 15000, 
          maximumAge: 10000 
        }
      );
    });
  }

  async buildLocationProof(dead_drop_id) {
    // Get current GPS location
    const location = await this.getCurrentLocation();

    // Scan for nearby BLE nodes
    const nodes = await this.startScanningForNodes(null, 5000);

    // Build location proof
    return {
      latitude: location.latitude.toFixed(6),
      longitude: location.longitude.toFixed(6),
      accuracy_meters: location.accuracy_meters,
      altitude: location.altitude,
      ble_nodes: nodes.map(n => ({
        id: n.id,
        rssi: n.rssi,
      })),
    };
  }

  // ===========================================================================
  // Dead Drop Collection Flow
  // ===========================================================================

  async attemptCollection(dropId, onProgress) {
    try {
      // Step 1: Get current location
      onProgress?.('Getting location...');
      const location = await this.getCurrentLocation();

      // Step 2: Scan for BLE nodes
      onProgress?.('Scanning for mesh nodes...');
      const nodes = await this.startScanningForNodes(
        (node) => onProgress?.(`Found node: ${node.name}`),
        8000
      );

      if (nodes.length === 0) {
        throw new Error('No mesh nodes found nearby');
      }

      // Step 3: Build location proof
      onProgress?.('Building location proof...');
      const locationProof = {
        latitude: location.latitude.toFixed(6),
        longitude: location.longitude.toFixed(6),
        accuracy_meters: location.accuracy_meters,
        ble_nodes: nodes.map(n => ({ id: n.id, rssi: n.rssi })),
      };

      // Step 4: Attempt collection
      onProgress?.('Collecting fragments...');
      const result = await this.collectDeadDrop(dropId, locationProof);

      return result;
    } catch (error) {
      console.error('Collection failed:', error);
      throw error;
    }
  }

  // ===========================================================================
  // Shamir Secret Sharing (Client-side)
  // ===========================================================================

  /**
   * Split a secret into shares using Shamir's Secret Sharing.
   * For client-side splitting before distribution.
   */
  splitSecret(secret, k, n) {
    // This is a simplified implementation
    // For production, use a proper library like 'secrets.js-grempe'
    
    const secretBytes = this.stringToBytes(secret);
    const shares = [];
    
    // Generate random polynomial coefficients
    const coefficients = [secretBytes];
    for (let i = 1; i < k; i++) {
      coefficients.push(this.generateRandomBytes(secretBytes.length));
    }
    
    // Evaluate polynomial at n points
    for (let x = 1; x <= n; x++) {
      const y = this.evaluatePolynomial(coefficients, x);
      shares.push({
        index: x,
        value: this.bytesToHex(y),
      });
    }
    
    return shares;
  }

  /**
   * Reconstruct secret from k or more shares.
   */
  reconstructSecret(shares) {
    if (shares.length < 2) {
      throw new Error('Need at least 2 shares');
    }

    // Convert shares to numerical format
    const points = shares.map(s => ({
      x: s.index,
      y: this.hexToBytes(s.value),
    }));

    // Lagrange interpolation at x=0
    const secret = this.lagrangeInterpolate(points, 0);
    
    return this.bytesToString(secret);
  }

  // ===========================================================================
  // Crypto Helpers
  // ===========================================================================

  stringToBytes(str) {
    return new TextEncoder().encode(str);
  }

  bytesToString(bytes) {
    return new TextDecoder().decode(bytes);
  }

  bytesToHex(bytes) {
    return Array.from(bytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  hexToBytes(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < bytes.length; i++) {
      bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
    }
    return bytes;
  }

  generateRandomBytes(length) {
    const bytes = new Uint8Array(length);
    for (let i = 0; i < length; i++) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
    return bytes;
  }

  evaluatePolynomial(coefficients, x) {
    // Horner's method
    const length = coefficients[0].length;
    const result = new Uint8Array(length);
    
    for (let i = coefficients.length - 1; i >= 0; i--) {
      for (let j = 0; j < length; j++) {
        result[j] = (result[j] * x + coefficients[i][j]) % 256;
      }
    }
    
    return result;
  }

  lagrangeInterpolate(points, x) {
    // Simplified Lagrange interpolation
    const n = points.length;
    const length = points[0].y.length;
    const result = new Uint8Array(length);
    
    for (let i = 0; i < n; i++) {
      let numerator = 1;
      let denominator = 1;
      
      for (let j = 0; j < n; j++) {
        if (i !== j) {
          numerator = numerator * (x - points[j].x);
          denominator = denominator * (points[i].x - points[j].x);
        }
      }
      
      const coefficient = numerator / denominator;
      
      for (let k = 0; k < length; k++) {
        result[k] = (result[k] + points[i].y[k] * coefficient) % 256;
        if (result[k] < 0) result[k] += 256;
      }
    }
    
    return result;
  }

  // ===========================================================================
  // NFC Verification
  // ===========================================================================

  async requestNFCChallenge(beaconId) {
    const response = await fetch(`${API_BASE}/nfc/challenge/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify({ beacon_id: beaconId }),
    });
    return response.json();
  }

  async verifyNFCResponse(beaconId, response) {
    const result = await fetch(`${API_BASE}/nfc/verify/`, {
      method: 'POST',
      headers: await this.getAuthHeaders(),
      body: JSON.stringify({ beacon_id: beaconId, response }),
    });
    return result.json();
  }

  // ===========================================================================
  // Cleanup
  // ===========================================================================

  destroy() {
    this.stopScanning();
    if (this.bleManager) {
      this.bleManager.destroy();
      this.bleManager = null;
    }
  }
}

// Export singleton instance
const meshService = new MeshService();
export default meshService;
