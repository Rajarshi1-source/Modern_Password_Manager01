/**
 * usePredictiveExpirationAlerts
 * =============================
 *
 * Subscribes to the predictive-expiration WebSocket and forwards each parsed
 * server event to `onMessage`. Backs the Phase 3 real-time notifications:
 * risk_alert / rotation_required / risk_updated / bulk_scan_complete /
 * threat_update (see PredictiveExpirationConsumer).
 *
 * Mirrors the auth + URL convention of useBreachWebSocket (token in the query
 * string, :8000 in dev) but stays intentionally small: connect, parse, forward,
 * reconnect with capped exponential backoff, and clean up on unmount.
 */

import { useCallback, useEffect, useRef } from 'react';

const MAX_RECONNECT_ATTEMPTS = 6;
const BASE_RECONNECT_DELAY = 1000; // 1s
const MAX_RECONNECT_DELAY = 30000; // 30s

/**
 * @param {(message: Object) => void} onMessage - called with each parsed event
 * @param {Object} [opts]
 * @param {boolean} [opts.enabled=true] - when false, no socket is opened
 */
export function usePredictiveExpirationAlerts(onMessage, opts = {}) {
  const { enabled = true } = opts;

  const wsRef = useRef(null);
  const attemptsRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const intentionallyClosedRef = useRef(false);
  // Keep the latest callback without forcing a reconnect on every render.
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token) return; // can't authenticate the socket without a token

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port =
      process.env.NODE_ENV === 'development'
        ? ':8000'
        : window.location.port
          ? `:${window.location.port}`
          : '';
    const url =
      `${protocol}//${host}${port}/ws/security/predictive-expiration/` +
      `?token=${encodeURIComponent(token)}`;

    let ws;
    try {
      ws = new WebSocket(url);
    } catch {
      return; // environment without WebSocket (e.g. SSR/tests) — no-op
    }
    wsRef.current = ws;

    ws.onopen = () => {
      attemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data.type && onMessageRef.current) {
          onMessageRef.current(data);
        }
      } catch {
        // Ignore malformed frames rather than crash the handler.
      }
    };

    ws.onerror = () => {
      // Let onclose drive the reconnect; just ensure the socket tears down.
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };

    ws.onclose = (event) => {
      if (intentionallyClosedRef.current || event.code === 1000) return;
      if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) return;

      const delay = Math.min(
        BASE_RECONNECT_DELAY * 2 ** attemptsRef.current,
        MAX_RECONNECT_DELAY
      );
      attemptsRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;

    intentionallyClosedRef.current = false;
    attemptsRef.current = 0;
    connect();

    return () => {
      intentionallyClosedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.close(1000, 'component unmounted');
        } catch {
          /* noop */
        }
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);
}

export default usePredictiveExpirationAlerts;
