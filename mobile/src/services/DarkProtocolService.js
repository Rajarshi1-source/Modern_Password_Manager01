/**
 * Dark Protocol Mobile Service
 * =============================
 * 
 * React Native service for Dark Protocol anonymous vault access.
 * Provides session management, traffic routing, and cover traffic.
 * 
 * @author Password Manager Team
 * @created 2026-02-06
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { Platform } from 'react-native';

// Configuration
const API_BASE_URL = process.env.API_URL || 'http://localhost:8000';
const WS_BASE_URL = process.env.WS_URL || 'ws://localhost:8001';
const STORAGE_KEY = '@dark_protocol_config';

/**
 * Dark Protocol Service for React Native
 */
class DarkProtocolService {
  constructor() {
    this.socket = null;
    this.sessionId = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.coverTrafficInterval = null;
    this.listeners = new Map();
  }

  // =========================================================================
  // Configuration
  // =========================================================================

  /**
   * Get stored configuration
   */
  async getStoredConfig() {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch (error) {
      console.error('Failed to get stored config:', error);
      return null;
    }
  }

  /**
   * Store configuration locally
   */
  async storeConfig(config) {
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch (error) {
      console.error('Failed to store config:', error);
    }
  }

  /**
   * Get user configuration from server
   */
  async getConfig(token) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/config/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      await this.storeConfig(data);
      return data;
    } catch (error) {
      console.error('Failed to get config:', error);
      // Return stored config as fallback
      return await this.getStoredConfig();
    }
  }

  /**
   * Update user configuration
   */
  async updateConfig(token, config) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/config/`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      await this.storeConfig(data);
      return data;
    } catch (error) {
      console.error('Failed to update config:', error);
      throw error;
    }
  }

  // =========================================================================
  // Session Management
  // =========================================================================

  /**
   * Establish a new dark protocol session
   */
  async establishSession(token, options = {}) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/session/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hop_count: options.hopCount,
          preferred_regions: options.preferredRegions,
        }),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || `HTTP ${response.status}`);
      }
      
      const data = await response.json();
      this.sessionId = data.session_id;
      
      // Connect WebSocket
      await this.connectWebSocket(token);
      
      return data;
    } catch (error) {
      console.error('Failed to establish session:', error);
      throw error;
    }
  }

  /**
   * Get current session status
   */
  async getSession(token) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/session/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to get session:', error);
      throw error;
    }
  }

  /**
   * Terminate current session
   */
  async terminateSession(token) {
    try {
      this.disconnectWebSocket();
      this.stopCoverTraffic();
      
      if (!this.sessionId) {
        return { success: true };
      }
      
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/session/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      this.sessionId = null;
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to terminate session:', error);
      throw error;
    }
  }

  // =========================================================================
  // WebSocket Connection
  // =========================================================================

  /**
   * Connect to dark protocol WebSocket
   */
  async connectWebSocket(token) {
    return new Promise((resolve, reject) => {
      if (!this.sessionId) {
        reject(new Error('No active session'));
        return;
      }
      
      // Check network connectivity
      NetInfo.fetch().then(state => {
        if (!state.isConnected) {
          reject(new Error('No network connection'));
          return;
        }
        
        const wsUrl = `${WS_BASE_URL}/ws/dark-protocol/${this.sessionId}/?token=${token}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
          console.log('Dark Protocol WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.notifyListeners('connected', { sessionId: this.sessionId });
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse message:', error);
          }
        };
        
        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.notifyListeners('error', { error });
        };
        
        this.socket.onclose = (event) => {
          console.log('WebSocket closed:', event.code);
          this.isConnected = false;
          this.notifyListeners('disconnected', { code: event.code });
          
          // Attempt reconnection
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            setTimeout(() => this.connectWebSocket(token), delay);
          }
        };
      });
    });
  }

  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket() {
    if (this.socket) {
      this.socket.close(1000);
      this.socket = null;
    }
    this.isConnected = false;
  }

  /**
   * Handle incoming WebSocket message
   */
  handleMessage(message) {
    switch (message.type) {
      case 'bundle_ack':
        this.notifyListeners('bundle_ack', message);
        break;
      case 'session_expired':
        this.sessionId = null;
        this.disconnectWebSocket();
        this.notifyListeners('session_expired', message);
        break;
      case 'path_rotated':
        this.notifyListeners('path_rotated', message);
        break;
      case 'cover_traffic_status':
        this.notifyListeners('cover_status', message);
        break;
      default:
        this.notifyListeners('message', message);
    }
  }

  // =========================================================================
  // Vault Operations
  // =========================================================================

  /**
   * Proxy a vault operation through dark protocol
   */
  async proxyVaultOperation(token, operation, payload) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/vault-proxy/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          operation,
          payload,
          session_id: this.sessionId,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to proxy vault operation:', error);
      throw error;
    }
  }

  // =========================================================================
  // Network Information
  // =========================================================================

  /**
   * Get network health status
   */
  async getNetworkHealth(token) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/health/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to get network health:', error);
      throw error;
    }
  }

  /**
   * Get available network nodes
   */
  async getNodes(token, nodeType = null) {
    try {
      let url = `${API_BASE_URL}/api/security/dark-protocol/nodes/`;
      if (nodeType) {
        url += `?type=${nodeType}`;
      }
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to get nodes:', error);
      throw error;
    }
  }

  /**
   * Get usage statistics
   */
  async getStats(token) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/dark-protocol/stats/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to get stats:', error);
      throw error;
    }
  }

  // =========================================================================
  // Cover Traffic
  // =========================================================================

  /**
   * Start generating cover traffic
   */
  startCoverTraffic(intensity = 0.5) {
    if (this.coverTrafficInterval) {
      return;
    }
    
    const baseInterval = 5000; // 5 seconds
    const interval = baseInterval / intensity;
    
    this.coverTrafficInterval = setInterval(() => {
      if (this.isConnected && this.socket) {
        this.generateCoverMessage();
      }
    }, interval);
  }

  /**
   * Stop generating cover traffic
   */
  stopCoverTraffic() {
    if (this.coverTrafficInterval) {
      clearInterval(this.coverTrafficInterval);
      this.coverTrafficInterval = null;
    }
  }

  /**
   * Generate a single cover traffic message
   */
  generateCoverMessage() {
    if (!this.socket || !this.isConnected) {
      return;
    }
    
    // Generate random cover message
    const operations = ['get_password', 'list_folders', 'get_note', 'search'];
    const operation = operations[Math.floor(Math.random() * operations.length)];
    
    // Generate random payload size (64-512 bytes)
    const size = 64 + Math.floor(Math.random() * 448);
    const noise = this.generateNoise(size);
    
    const message = {
      type: 'cover',
      operation,
      payload: noise,
      timestamp: Date.now(),
    };
    
    try {
      this.socket.send(JSON.stringify(message));
    } catch (error) {
      console.error('Failed to send cover message:', error);
    }
  }

  /**
   * Generate random noise for cover traffic
   */
  generateNoise(size) {
    const array = new Uint8Array(size);
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
      crypto.getRandomValues(array);
    } else {
      for (let i = 0; i < size; i++) {
        array[i] = Math.floor(Math.random() * 256);
      }
    }
    return Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================

  /**
   * Add event listener
   */
  addListener(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    
    return () => this.removeListener(event, callback);
  }

  /**
   * Remove event listener
   */
  removeListener(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Notify all listeners of an event
   */
  notifyListeners(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Listener error for ${event}:`, error);
        }
      });
    }
  }

  // =========================================================================
  // Utility Methods
  // =========================================================================

  /**
   * Check if dark protocol is enabled and connected
   */
  get isActive() {
    return this.isConnected && this.sessionId !== null;
  }

  /**
   * Get current connection state
   */
  getConnectionState() {
    return {
      isConnected: this.isConnected,
      sessionId: this.sessionId,
      hasSocket: this.socket !== null,
    };
  }

  /**
   * Clean up resources
   */
  cleanup() {
    this.disconnectWebSocket();
    this.stopCoverTraffic();
    this.listeners.clear();
    this.sessionId = null;
  }
}

// Export singleton instance
export default new DarkProtocolService();
