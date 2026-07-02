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
import { getWsTicket } from '../services/wsTicket';

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

  const connect = useCallback(async () => {
    // Guard all browser-only access together: localStorage and window can throw
    // (restricted storage, SSR, tests). Fail closed rather than break the
    // dashboard before the socket is even created.
    let token;
    let location;
    let SocketCtor;
    try {
      if (typeof window === 'undefined') return;
      location = window.location;
      SocketCtor = window.WebSocket;
      token = window.localStorage?.getItem('token');
    } catch {
      return;
    }
    if (!token || !SocketCtor) return; // not authenticated / no WebSocket — no-op

    // Exchange the long-lived token for a short-lived, single-use ticket so it
    // never appears in the ws:// URL (access logs / history). Retry a ticket
    // failure with the same capped backoff the socket itself uses.
    let ticket;
    try {
      ticket = await getWsTicket();
    } catch {
      if (intentionallyClosedRef.current || attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) return;
      const retryDelay = Math.min(
        BASE_RECONNECT_DELAY * 2 ** attemptsRef.current,
        MAX_RECONNECT_DELAY
      );
      attemptsRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, retryDelay);
      return;
    }
    if (intentionallyClosedRef.current) return; // torn down while fetching the ticket

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = location.hostname;
    const port =
      process.env.NODE_ENV === 'development'
        ? ':8000'
        : location.port
          ? `:${location.port}`
          : '';
    const url =
      `${protocol}//${host}${port}/ws/security/predictive-expiration/` +
      `?ticket=${encodeURIComponent(ticket)}`;

    let ws;
    try {
      ws = new SocketCtor(url);
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

    ws.onclose = () => {
      // Reconnect on any unexpected close — including a clean (1000) server-side
      // idle timeout or restart, which would otherwise silently stop alerts.
      // Skip only when we closed it ourselves or this socket is already stale
      // (a newer connect() has replaced it).
      if (intentionallyClosedRef.current || wsRef.current !== ws) return;
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
        // Clear the ref BEFORE closing so the stale-socket guard in onclose
        // (wsRef.current !== ws) suppresses a reconnect for this teardown.
        const sock = wsRef.current;
        wsRef.current = null;
        try {
          sock.close(1000, 'component unmounted');
        } catch {
          /* noop */
        }
      }
    };
  }, [enabled, connect]);
}

export default usePredictiveExpirationAlerts;
