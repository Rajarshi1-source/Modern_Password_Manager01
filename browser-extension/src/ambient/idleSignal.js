/**
 * Idle-state signal for the extension ambient engine.
 *
 * `chrome.idle.queryState(threshold)` returns "active" | "idle" | "locked".
 * Folded into the coarse feature bucket so that a machine that is
 * normally active at a given time of day versus normally idle shows up
 * as two different contexts.
 */

export async function getIdleState(thresholdSecs = 60) {
  const api = globalThis.chrome?.idle;
  if (!api || typeof api.queryState !== 'function') return 'unknown';
  try {
    return await new Promise((resolve) => {
      try { api.queryState(thresholdSecs, (state) => resolve(state || 'unknown')); }
      catch { resolve('unknown'); }
    });
  } catch {
    return 'unknown';
  }
}
