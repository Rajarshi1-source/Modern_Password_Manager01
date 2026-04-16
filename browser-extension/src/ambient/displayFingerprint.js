/**
 * Display topology fingerprint.
 *
 * `chrome.system.display.getInfo` returns one entry per physical display.
 * We hash the sorted set of (width x height @ scale) tuples. No raw
 * resolution ships — only the salted digest goes over the wire via the
 * ambient engine.
 */

async function hashString(text) {
  const enc = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest('SHA-256', enc);
  const arr = new Uint8Array(buf);
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function getDisplayDigest() {
  const api = globalThis.chrome?.system?.display;
  if (!api || typeof api.getInfo !== 'function') return '';
  try {
    const displays = await new Promise((resolve) => {
      try { api.getInfo((x) => resolve(x || [])); } catch { resolve([]); }
    });
    const tuples = (displays || [])
      .map((d) => {
        const w = d?.bounds?.width ?? 0;
        const h = d?.bounds?.height ?? 0;
        const s = d?.displayZoomFactor ?? 1;
        return `${w}x${h}@${s}`;
      })
      .sort();
    if (tuples.length === 0) return '';
    return await hashString(tuples.join('|'));
  } catch {
    return '';
  }
}

export function getDisplayCountBucket(digest) {
  // Coarse bucket that's safe to ship in plain coarse features.
  if (!digest) return 'unknown';
  return 'present';
}
