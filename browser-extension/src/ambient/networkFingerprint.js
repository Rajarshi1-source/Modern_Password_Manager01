/**
 * Network fingerprint for the MV3 extension.
 *
 * Chromium-only: `chrome.system.network.getNetworkInterfaces()` gives us
 * non-loopback interface IPs. We hash the sorted set. Raw IPs never
 * leave the device — only the salted digest does.
 *
 * Firefox MV3 doesn't expose `system.network`, so we gracefully return
 * an empty digest list.
 */

async function hashBytes(bytes) {
  const buf = await crypto.subtle.digest('SHA-256', bytes);
  const arr = new Uint8Array(buf);
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function getNetworkDigests() {
  const api = globalThis.chrome?.system?.network;
  if (!api || typeof api.getNetworkInterfaces !== 'function') {
    return [];
  }
  try {
    const ifaces = await new Promise((resolve) => {
      try { api.getNetworkInterfaces((x) => resolve(x || [])); } catch { resolve([]); }
    });
    const addrs = (ifaces || [])
      .map((i) => i?.address)
      .filter((a) => typeof a === 'string')
      .filter((a) => !a.startsWith('127.') && a !== '::1')
      .sort();
    if (addrs.length === 0) return [];
    const enc = new TextEncoder().encode(addrs.join('|'));
    const digest = await hashBytes(enc);
    return [digest];
  } catch {
    return [];
  }
}

export function getConnectionClass() {
  const conn = globalThis.navigator?.connection;
  if (!conn) return { connection_class: 'unknown', effective_type: 'unknown' };
  const raw = String(conn.type || '').toLowerCase();
  const eff = String(conn.effectiveType || '').toLowerCase();
  return {
    connection_class: ['wifi', 'cellular', 'ethernet', 'bluetooth'].includes(raw) ? raw : 'unknown',
    effective_type: ['slow-2g', '2g', '3g', '4g', '5g'].includes(eff) ? eff : 'unknown',
  };
}
