/**
 * Dark Protocol Service
 * =======================
 *
 * Frontend service for anonymous vault access.
 *
 * Where the anonymity comes from: the backend is published as a Tor v3 onion
 * service, and a client that reaches it over that .onion address gets a
 * circuit terminating inside Tor — no exit node, and the server never learns
 * the client IP. The server verifies that live against its Tor daemon and
 * reports it through `getCapabilities()`.
 *
 * The garlic bundling and cover traffic here are padding layered on top of
 * that circuit (traffic-analysis resistance); they run inside one deployment
 * and are NOT anonymity on their own. Nothing in this UI may present them as
 * such: when `capabilities.anonymity.available` is false, the feature shows
 * Unavailable rather than implying protection that is not there.
 *
 * Features:
 * - Capability reporting (gates the UI)
 * - Session management via REST API
 * - WebSocket connection for real-time communication
 * - Cover traffic generation (client-side)
 * - Connection state management
 *
 * @author Password Manager Team
 * @created 2026-02-02
 */
import { authHeader } from '../utils/authHeader';
import { getWsTicket } from './wsTicket';

// JSON + auth headers shared by every dark-protocol fetch call.
const authHeaders = () => ({
  'Content-Type': 'application/json',
  ...authHeader(),
});

// API base URL
const DARK_PROTOCOL_BASE = '/api/security/dark-protocol';

// WebSocket state
let wsConnection = null;
// Bumped by every connect/disconnect so an in-flight ticket fetch that has been
// superseded doesn't open a stale socket.
let wsConnectGeneration = 0;
let coverTrafficInterval = null;
let heartbeatInterval = null;
let connectionListeners = [];

/**
 * Configuration API
 */

export const getConfig = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/config/`, {
    method: 'GET',
    headers: authHeaders(),
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch dark protocol config');
  }
  
  return response.json();
};

export const updateConfig = async (config) => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/config/`, {
    method: 'PUT',
    headers: authHeaders(),
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
    headers: authHeaders(),
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch session');
  }
  
  return response.json();
};

export const establishSession = async (options = {}) => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/session/`, {
    method: 'POST',
    headers: authHeaders(),
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
  
  // Connect the WebSocket after creating the REST session. connectWebSocket
  // resolves to null when superseded, or rejects on ticket/socket failure. The
  // REST session already exists, so in every failure case terminate it before
  // propagating — otherwise it stays `active` until expiry and the next attempt
  // hits the server's one-active-session 409 (retry blocked for the whole TTL).
  if (session.session_id) {
    try {
      const ws = await connectWebSocket(session.session_id);
      if (!ws) {
        throw new Error('Dark Protocol connection was superseded before it opened');
      }
    } catch (err) {
      try {
        await terminateSession(session.session_id);
      } catch {
        /* best-effort cleanup; surface the original connect error below */
      }
      throw err;
    }
  }

  return session;
};

export const terminateSession = async (sessionId = null) => {
  // Disconnect WebSocket
  disconnectWebSocket();
  
  const response = await fetch(`${DARK_PROTOCOL_BASE}/session/`, {
    method: 'DELETE',
    headers: authHeaders(),
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
    headers: authHeaders(),
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch nodes');
  }
  
  return response.json();
};

export const getRoutes = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/route/`, {
    method: 'GET',
    headers: authHeaders(),
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch routes');
  }
  
  return response.json();
};

export const requestNewRoute = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/route/`, {
    method: 'POST',
    headers: authHeaders(),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create new route');
  }
  
  return response.json();
};

export const getNetworkHealth = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/health/`, {
    method: 'GET',
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch network health');
  }

  return response.json();
};

/**
 * Capability report — what Dark Protocol can genuinely do right now.
 *
 * The UI gates on this rather than on user configuration: `is_enabled` is a
 * preference, while `anonymity.available` is a fact the server verified
 * against a running Tor daemon. A failed fetch is deliberately treated as
 * "unavailable" by callers rather than defaulting to available, so a
 * capability endpoint that is down can never present the feature as active.
 */
export const getCapabilities = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/capabilities/`, {
    method: 'GET',
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch dark protocol capabilities');
  }

  return response.json();
};

export const getStats = async () => {
  const response = await fetch(`${DARK_PROTOCOL_BASE}/stats/`, {
    method: 'GET',
    headers: authHeaders(),
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
    headers: authHeaders(),
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
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    return wsConnection;
  }

  const generation = ++wsConnectGeneration;

  // Exchange the long-lived auth token for a short-lived, single-use ticket so
  // it never lands in the ws:// URL (access logs / browser history). The ticket
  // is consumed by the same TokenAuthMiddleware that authenticates the WS route,
  // so no consumer change is needed. Without it the socket connected as
  // AnonymousUser and the consumer immediately close(4003)'d. Demo enablement
  // only — connecting the socket does NOT make the anonymity / censorship-
  // resistance claims real (the transport is simulated on one server).
  let ticket;
  try {
    ticket = await getWsTicket();
  } catch (error) {
    // Superseded while the ticket was in flight — stay silent for a dead
    // attempt rather than propagating a rejection for an abandoned connect.
    if (generation !== wsConnectGeneration) return null;
    console.error('Error fetching dark-protocol WebSocket ticket:', error);
    throw error;
  }

  // Superseded by a disconnect()/newer connect() while the ticket was in
  // flight — abort rather than open a stale/duplicate socket.
  if (generation !== wsConnectGeneration) {
    return null;
  }

  const url = `${getWebSocketUrl(sessionId)}?ticket=${encodeURIComponent(ticket)}`;

  return new Promise((resolve, reject) => {
    // Bind handlers to THIS socket instance, not the module-level wsConnection,
    // and settle exactly once. A concurrent connect() can replace wsConnection
    // while this socket is still CONNECTING; without these guards a stale socket
    // could resolve an orphaned connection, tear down the newer one, or (on an
    // early close with no onerror) leave this promise — and establishSession —
    // hanging forever.
    const socket = new WebSocket(url);
    wsConnection = socket;
    let settled = false;
    const settle = (fn, value) => {
      if (settled) return;
      settled = true;
      fn(value);
    };

    socket.onopen = () => {
      // Superseded by a newer connect() while CONNECTING — close the orphan and
      // reject this attempt rather than overwrite the live connection.
      if (socket !== wsConnection) {
        try { socket.close(); } catch { /* already closing */ }
        settle(reject, new Error('Dark Protocol connect superseded'));
        return;
      }
      console.log('Dark Protocol WebSocket connected');
      startHeartbeat();
      notifyListeners({ type: 'connected', sessionId });
      settle(resolve, socket);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    socket.onclose = (event) => {
      console.log('Dark Protocol WebSocket closed:', event.code);
      // Closed before it ever opened — settle so awaiters don't hang when
      // onerror doesn't fire (a clean server-side close emits onclose only).
      // No-ops if the socket had already opened and resolved.
      settle(reject, new Error(`Dark Protocol WebSocket closed before open (code ${event.code})`));
      // Don't tear down a newer connection that already replaced this socket.
      if (socket !== wsConnection && wsConnection !== null) return;
      stopHeartbeat();
      stopCoverTraffic();
      notifyListeners({ type: 'disconnected', code: event.code });
      wsConnection = null;
    };

    socket.onerror = (event) => {
      console.error('Dark Protocol WebSocket error:', event);
      // The DOM error Event has no `.message`; reject with a real Error so
      // callers reading err.message don't see `undefined` (matches onclose).
      const err = new Error('Dark Protocol WebSocket connection error');
      // Superseded socket — settle its own promise, leave the newer one alone.
      if (socket !== wsConnection && wsConnection !== null) {
        settle(reject, err);
        return;
      }
      notifyListeners({ type: 'error', error: err });
      settle(reject, err);
    };
  });
};

export const disconnectWebSocket = () => {
  // Invalidate any connect() whose ticket request is still in flight.
  wsConnectGeneration++;
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
  
  // Capability
  getCapabilities,

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
