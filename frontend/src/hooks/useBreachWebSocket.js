/**
 * Enhanced WebSocket Hook for Real-time Breach Alerts
 * 
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Network quality estimation and monitoring
 * - Offline queue for missed alerts
 * - Ping/pong health monitoring
 * - Connection quality indicators
 * - HTTP polling fallback when WebSocket is unavailable (WSGI mode)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import NetworkQualityEstimator from '../utils/NetworkQualityEstimator';
import OfflineQueueManager from '../utils/OfflineQueueManager';

export const useBreachWebSocket = (userId, onAlert, onUpdate, onConnectionChange) => {
  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [connectionQuality, setConnectionQuality] = useState('good');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  
  // Network metrics
  const [networkQuality, setNetworkQuality] = useState({ 
    level: 'unknown', 
    text: 'Unknown', 
    color: 'gray' 
  });
  const [networkMetrics, setNetworkMetrics] = useState({
    averageLatency: 0,
    jitter: 0,
    minLatency: 0,
    maxLatency: 0,
    sampleCount: 0
  });
  
  // Offline queue
  const [offlineQueueSize, setOfflineQueueSize] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  
  // Refs
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const lastPongRef = useRef(Date.now());
  const reconnectAttemptsRef = useRef(0);
  const pingTimestampRef = useRef(null);
  const networkEstimatorRef = useRef(new NetworkQualityEstimator());
  const offlineQueueRef = useRef(new OfflineQueueManager());
  
  // HTTP polling fallback state
  const [usingPolling, setUsingPolling] = useState(false);
  const pollingIntervalRef = useRef(null);
  
  // Constants
  const MAX_RECONNECT_ATTEMPTS = 10;
  const INITIAL_RECONNECT_DELAY = 1000; // 1 second
  const MAX_RECONNECT_DELAY = 30000; // 30 seconds
  const PING_INTERVAL = 30000; // 30 seconds
  const PONG_TIMEOUT = 10000; // 10 seconds
  const POLLING_INTERVAL = 30000; // 30 seconds for HTTP fallback

  /**
   * Calculate reconnection delay with exponential backoff
   */
  const getReconnectDelay = useCallback(() => {
    const exponentialDelay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
      MAX_RECONNECT_DELAY
    );
    // Add random jitter (±10%)
    const jitter = exponentialDelay * 0.1 * (Math.random() * 2 - 1);
    return exponentialDelay + jitter;
  }, []);

  /**
   * Process all queued alerts when coming back online
   */
  const processOfflineQueue = useCallback(() => {
    const queuedAlerts = offlineQueueRef.current.dequeueAll();
    
    if (queuedAlerts.length === 0) return;
    
    console.log(`[OfflineQueue] 📥 Processing ${queuedAlerts.length} queued alerts`);
    
    queuedAlerts.forEach(alert => {
      if (onAlert) {
        onAlert(alert);
      }
    });
    
    setOfflineQueueSize(0);
  }, [onAlert]);

  /**
   * Start ping/pong health monitoring
   */
  const startHealthMonitoring = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    
    pingIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const timeSinceLastPong = Date.now() - lastPongRef.current;
        
        // Check for pong timeout
        if (timeSinceLastPong > PONG_TIMEOUT) {
          console.warn('[WebSocket] ⚠️ Connection unhealthy, no pong received');
          setConnectionQuality('poor');
        }

        // Send ping with timestamp for latency calculation
        pingTimestampRef.current = Date.now();
        wsRef.current.send(JSON.stringify({
          type: 'ping',
          timestamp: pingTimestampRef.current
        }));
      }
    }, PING_INTERVAL);
  }, []);

  /**
   * Stop ping/pong health monitoring
   */
  const stopHealthMonitoring = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  /**
   * Start HTTP polling as fallback when WebSocket is unavailable
   */
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    
    console.log('[Polling] 📡 Starting HTTP polling fallback');
    setUsingPolling(true);
    
    // Initial fetch
    const fetchAlerts = async () => {
      try {
        const response = await axios.get('/api/security/breach-alerts/');
        const alerts = response.data?.results || response.data || [];
        
        // Process new alerts
        if (alerts.length > 0) {
          alerts.forEach(alert => {
            if (onAlert && !alert.read) {
              onAlert(alert);
            }
          });
        }
        
        setIsConnected(true);
        setConnectionQuality('polling');
        setConnectionError(null);
        
        if (onConnectionChange) {
          onConnectionChange(true);
        }
      } catch (error) {
        console.error('[Polling] Error fetching alerts:', error);
        setConnectionError(error.message);
      }
    };
    
    // Initial fetch
    fetchAlerts();
    
    // Set up polling interval
    pollingIntervalRef.current = setInterval(fetchAlerts, POLLING_INTERVAL);
  }, [onAlert, onConnectionChange]);

  /**
   * Stop HTTP polling
   */
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setUsingPolling(false);
  }, []);

  /**
   * Establish WebSocket connection
   */
  const connect = useCallback(() => {
    if (!userId) {
      console.warn('[WebSocket] No userId provided');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname;
      const port = process.env.NODE_ENV === 'development' ? ':8000' : '';
      
      const wsUrl = `${protocol}//${host}${port}/ws/breach-alerts/${userId}/?token=${token}`;
      
      console.log(`[WebSocket] 🔌 Connecting... (attempt ${reconnectAttemptsRef.current + 1})`);
      
      const websocket = new WebSocket(wsUrl);
      wsRef.current = websocket;

      websocket.onopen = () => {
        console.log('[WebSocket] ✓ Connected successfully');
        setIsConnected(true);
        setConnectionQuality('good');
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        lastPongRef.current = Date.now();
        
        if (onConnectionChange) {
          onConnectionChange(true);
        }

        // Process any queued alerts
        processOfflineQueue();
        
        // Start health monitoring
        startHealthMonitoring();
        
        // Request unread count
        websocket.send(JSON.stringify({ type: 'get_unread_count' }));
      };

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle pong with latency calculation
          if (data.type === 'pong') {
            const latency = Date.now() - (pingTimestampRef.current || Date.now());
            lastPongRef.current = Date.now();
            
            // Update network quality estimation
            networkEstimatorRef.current.addLatency(latency);
            const quality = networkEstimatorRef.current.getQuality();
            const metrics = networkEstimatorRef.current.getMetrics();
            
            setNetworkQuality(quality);
            setNetworkMetrics(metrics);
            
            // Update connection quality based on latency
            if (latency < 300) {
              setConnectionQuality('good');
            } else if (latency < 1000) {
              setConnectionQuality('poor');
            }
            
            return;
          }
          
          // Handle breach alerts
          if (data.type === 'breach_alert') {
            console.log('[WebSocket] 🚨 New breach alert received');
            if (onAlert) {
              onAlert(data.message);
            }
            setUnreadCount(prev => prev + 1);
          }
          
          // Handle alert updates
          if (data.type === 'alert_update') {
            console.log('[WebSocket] 🔄 Alert update received');
            if (onUpdate) {
              onUpdate(data.message);
            }
            if (data.message.update_type === 'marked_read') {
              setUnreadCount(prev => Math.max(0, prev - 1));
            }
          }
          
          // Handle unread count
          if (data.type === 'unread_count') {
            setUnreadCount(data.count);
          }
          
          // Handle connection confirmation
          if (data.type === 'connection_established') {
            console.log('[WebSocket] ✓ Connection established:', data.message);
          }
        } catch (error) {
          console.error('[WebSocket] ❌ Error parsing message:', error);
        }
      };

      websocket.onerror = (error) => {
        console.error('[WebSocket] ❌ Error:', error);
        setConnectionQuality('poor');
      };

      websocket.onclose = (event) => {
        console.log('[WebSocket] 🔌 Disconnected:', event.code, event.reason);
        setIsConnected(false);
        setConnectionQuality('disconnected');
        
        if (onConnectionChange) {
          onConnectionChange(false);
        }
        
        stopHealthMonitoring();

        // Attempt reconnection with exponential backoff
        if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = getReconnectDelay();
          console.log(`[WebSocket] 🔄 Reconnecting in ${delay.toFixed(0)}ms...`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            setReconnectAttempts(reconnectAttemptsRef.current);
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.warn('[WebSocket] ⚠️ Max reconnection attempts reached, falling back to HTTP polling');
          // Fall back to HTTP polling when WebSocket is not available
          startPolling();
        }
      };
    } catch (error) {
      console.error('[WebSocket] ❌ Connection error:', error);
      setConnectionError(error.message);
      
      // If WebSocket fails to create, use polling fallback
      if (error.message?.includes('WebSocket') || error.message?.includes('ECONNREFUSED')) {
        console.log('[WebSocket] Falling back to HTTP polling');
        startPolling();
      }
    }
  }, [userId, onAlert, onUpdate, onConnectionChange, startHealthMonitoring, getReconnectDelay, processOfflineQueue, startPolling]);

  /**
   * Handle alerts when offline (add to queue)
   */
  const handleOfflineAlert = useCallback((alert) => {
    console.log('[OfflineQueue] 📥 Queueing alert for later delivery');
    const queued = offlineQueueRef.current.enqueue(alert);
    setOfflineQueueSize(offlineQueueRef.current.getQueueSize());
    return queued;
  }, []);

  /**
   * Manually disconnect
   */
  const disconnect = useCallback(() => {
    console.log('[WebSocket] 🔌 Manual disconnect');
    stopHealthMonitoring();
    stopPolling();
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect');
    }
  }, [stopHealthMonitoring, stopPolling]);

  /**
   * Manually reconnect
   */
  const reconnect = useCallback(() => {
    console.log('[WebSocket] 🔄 Manual reconnect triggered');
    disconnect();
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
    networkEstimatorRef.current.reset();
    setTimeout(connect, 500);
  }, [connect, disconnect]);

  /**
   * Send message through WebSocket
   */
  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] ⚠️ Not connected, cannot send message');
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();
    
    // Check initial queue size
    setOfflineQueueSize(offlineQueueRef.current.getQueueSize());
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Listen for online/offline events
  useEffect(() => {
    const handleOnline = () => {
      console.log('[Network] 🌐 Browser is online');
      if (!isConnected) {
        reconnect();
      }
    };

    const handleOffline = () => {
      console.log('[Network] 📡 Browser is offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [isConnected, reconnect]);

  return { 
    // Connection state
    isConnected, 
    connectionError, 
    connectionQuality,
    reconnectAttempts,
    usingPolling,
    
    // Network metrics
    networkQuality,
    networkMetrics,
    
    // Offline queue
    offlineQueueSize,
    unreadCount,
    
    // Methods
    reconnect,
    disconnect,
    send,
    handleOfflineAlert,
    
    // WebSocket ref (for advanced usage)
    ws: wsRef.current
  };
};

export default useBreachWebSocket;
