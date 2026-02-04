/**
 * Dark Protocol Service
 * =======================
 * 
 * Frontend service for the Dark Protocol anonymous vault access network.
 * 
 * Features:
 * - Session management via REST API
 * - WebSocket connection for real-time communication
 * - Cover traffic generation (client-side)
 * - Connection state management
 * 
 * @author Password Manager Team
 * @created 2026-02-02
 */

// API base URL
const DARK_PROTOCOL_BASE = '/api/security/dark-protocol';

// WebSocket state
let wsConnection = null;
let coverTrafficInterval = null;
let heartbeatInterval = null;
let connectionListeners = [];

/**
 * Configuration API
 */

export const getConfig = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/config/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch dark protocol config');
  }
  
  return response.json();
};

export const updateConfig = async (config) => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/config/`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify(config),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update dark protocol config');
  }
  
  return response.json();
};

/**
 * Session Management
 */

export const getSession = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/session/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch session');
  }
  
  return response.json();
};

export const establishSession = async (options = {}) => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/session/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({
      hop_count: options.hopCount,
      preferred_regions: options.preferredRegions,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to establish session');
  }
  
  const session = await response.json();
  
  // Connect WebSocket after establishing session
  if (session.session_id) {
    await connectWebSocket(session.session_id);
  }
  
  return session;
};

export const terminateSession = async (sessionId = null) => {
  // Disconnect WebSocket
  disconnectWebSocket();
  
  const response = await fetch(`${DARK_PROTOCOL_BASE}/session/`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({ session_id: sessionId }),
  });
  
  if (!response.ok) {
    throw new Error('Failed to terminate session');
  }
  
  return response.json();
};

/**
 * Network Information
 */

export const getNodes = async (nodeType = null) => {
  const params = nodeType ? `?type=${nodeType}` : '';
  
  const response = await fetch(`${DARK_PROTOCOL_BASE}/nodes/${params}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch nodes');
  }
  
  return response.json();
};

export const getRoutes = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/route/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch routes');
  }
  
  return response.json();
};

export const requestNewRoute = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/route/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to create new route');
  }
  
  return response.json();
};

export const getNetworkHealth = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/health/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch network health');
  }
  
  return response.json();
};

export const getStats = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/stats/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch stats');
  }
  
  return response.json();
};

/**
 * Vault Proxy
 */

export const proxyVaultOperation = async (operation, payload = {}, sessionId = null) => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/vault-proxy/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({
      operation,
      payload,
      session_id: sessionId,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Vault operation failed');
  }
  
  return response.json();
};

/**
 * WebSocket Connection
 */

const getWebSocketUrl = (sessionId) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/dark-protocol/${sessionId}/`;
};

export const connectWebSocket = async (sessionId) => {
  return new Promise((resolve, reject) => {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      resolve(wsConnection);
      return;
    }
    
    const url = getWebSocketUrl(sessionId);
    wsConnection = new WebSocket(url);
    
    wsConnection.onopen = () => {
      console.log('Dark Protocol WebSocket connected');
      startHeartbeat();
      notifyListeners({ type: 'connected', sessionId });
      resolve(wsConnection);
    };
    
    wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    wsConnection.onclose = (event) => {
      console.log('Dark Protocol WebSocket closed:', event.code);
      stopHeartbeat();
      stopCoverTraffic();
      notifyListeners({ type: 'disconnected', code: event.code });
      wsConnection = null;
    };
    
    wsConnection.onerror = (error) => {
      console.error('Dark Protocol WebSocket error:', error);
      notifyListeners({ type: 'error', error });
      reject(error);
    };
  });
};

export const disconnectWebSocket = () => {
  stopHeartbeat();
  stopCoverTraffic();
  
  if (wsConnection) {
    wsConnection.close();
    wsConnection = null;
  }
};

const handleWebSocketMessage = (data) => {
  switch (data.type) {
    case 'connected':
      console.log('Session connected:', data.session_id);
      break;
      
    case 'cover':
      // Cover traffic received - no action needed
      break;
      
    case 'bundle_ack':
      notifyListeners({ type: 'bundle_ack', bundleId: data.bundle_id });
      break;
      
    case 'bundle_response':
      notifyListeners({ type: 'response', bundleId: data.bundle_id, data: data.data });
      break;
      
    case 'session_expired':
      notifyListeners({ type: 'session_expired' });
      disconnectWebSocket();
      break;
      
    case 'heartbeat_ack':
      // Heartbeat acknowledged
      break;
      
    default:
      console.log('Unknown message type:', data.type);
  }
  
  notifyListeners(data);
};

export const sendBundle = (bundleId, data) => {
  if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
    throw new Error('WebSocket not connected');
  }
  
  wsConnection.send(JSON.stringify({
    type: 'bundle',
    bundle_id: bundleId,
    data,
  }));
};

/**
 * Heartbeat
 */

const startHeartbeat = () => {
  stopHeartbeat();
  
  heartbeatInterval = setInterval(() => {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      wsConnection.send(JSON.stringify({ type: 'heartbeat' }));
    }
  }, 30000); // Every 30 seconds
};

const stopHeartbeat = () => {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
};

/**
 * Cover Traffic (Client-side)
 */

export const startCoverTraffic = (intensity = 0.5) => {
  stopCoverTraffic();
  
  // Calculate interval based on intensity (2-10 seconds)
  const interval = Math.floor(10000 - (intensity * 8000));
  
  coverTrafficInterval = setInterval(() => {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      wsConnection.send(JSON.stringify({
        type: 'request_cover',
        count: 1,
      }));
    }
  }, interval);
};

export const stopCoverTraffic = () => {
  if (coverTrafficInterval) {
    clearInterval(coverTrafficInterval);
    coverTrafficInterval = null;
  }
};

/**
 * Event Listeners
 */

export const addConnectionListener = (callback) => {
  connectionListeners.push(callback);
  return () => {
    connectionListeners = connectionListeners.filter(cb => cb !== callback);
  };
};

const notifyListeners = (event) => {
  connectionListeners.forEach(callback => {
    try {
      callback(event);
    } catch (e) {
      console.error('Error in connection listener:', e);
    }
  });
};

/**
 * Connection State
 */

export const isConnected = () => {
  return wsConnection && wsConnection.readyState === WebSocket.OPEN;
};

export const getConnectionState = () => {
  if (!wsConnection) return 'disconnected';
  
  switch (wsConnection.readyState) {
    case WebSocket.CONNECTING:
      return 'connecting';
    case WebSocket.OPEN:
      return 'connected';
    case WebSocket.CLOSING:
      return 'closing';
    case WebSocket.CLOSED:
      return 'disconnected';
    default:
      return 'unknown';
  }
};

/**
 * Utility: Generate Noise
 */

export const generateClientNoise = (size = 256) => {
  const array = new Uint8Array(size);
  crypto.getRandomValues(array);
  return Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('');
};

/**
 * Default Export
 */

export default {
  // Config
  getConfig,
  updateConfig,
  
  // Session
  getSession,
  establishSession,
  terminateSession,
  
  // Network
  getNodes,
  getRoutes,
  requestNewRoute,
  getNetworkHealth,
  getStats,
  
  // Vault
  proxyVaultOperation,
  
  // WebSocket
  connectWebSocket,
  disconnectWebSocket,
  sendBundle,
  isConnected,
  getConnectionState,
  addConnectionListener,
  
  // Cover Traffic
  startCoverTraffic,
  stopCoverTraffic,
  
  // Utility
  generateClientNoise,
};
