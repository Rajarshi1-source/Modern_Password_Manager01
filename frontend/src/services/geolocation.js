/**
 * geolocation.js
 *
 * Axios interceptor that attaches the current browser geolocation to
 * vault retrieve requests so the server can evaluate geofenced
 * self-destruct policies. We cache a recent fix for 60 seconds to
 * avoid hammering the browser geolocation API on every click.
 *
 * Usage:
 *   import { attachGeolocationInterceptor } from './geolocation';
 *   attachGeolocationInterceptor(apiInstance);
 */

const CACHE_TTL_MS = 60_000;
let cache = null; // { lat, lng, ts }
let pending = null;

function getPosition() {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    return Promise.resolve(null);
  }
  if (pending) return pending;

  pending = new Promise((resolve) => {
    const done = (value) => {
      pending = null;
      resolve(value);
    };
    try {
      navigator.geolocation.getCurrentPosition(
        (pos) => done({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          ts: Date.now(),
        }),
        () => done(null),
        { enableHighAccuracy: false, timeout: 3000, maximumAge: CACHE_TTL_MS },
      );
    } catch (_err) {
      done(null);
    }
  });
  return pending;
}

async function ensureFix() {
  const now = Date.now();
  if (cache && now - cache.ts < CACHE_TTL_MS) return cache;
  const pos = await getPosition();
  if (pos) cache = pos;
  return cache;
}

const GEO_ROUTES = [
  /\/api\/vault\/.+/,
  /\/api\/v1\/vault\/.+/,
];

function shouldAttach(url) {
  if (!url) return false;
  return GEO_ROUTES.some((re) => re.test(url));
}

export function attachGeolocationInterceptor(apiInstance) {
  if (!apiInstance || !apiInstance.interceptors) return;

  apiInstance.interceptors.request.use(async (config) => {
    try {
      if (!shouldAttach(config.url)) return config;
      const fix = await ensureFix();
      if (fix) {
        config.headers = config.headers || {};
        config.headers['X-Geo-Latitude'] = String(fix.lat);
        config.headers['X-Geo-Longitude'] = String(fix.lng);
      }
    } catch (_err) {
      // Never block a request because we couldn't get a fix.
    }
    return config;
  });
}

export default attachGeolocationInterceptor;
