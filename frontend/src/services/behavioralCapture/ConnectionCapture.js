/**
 * Connection-class capture.
 *
 * Reads `navigator.connection` (Network Information API) and exposes
 * the connection class + effective-type bucket. Never the IP or SSID.
 */

function normalizeType(type) {
  if (!type) return 'unknown';
  const t = String(type).toLowerCase();
  if (t === 'wifi') return 'wifi';
  if (t === 'cellular') return 'cellular';
  if (t === 'ethernet') return 'ethernet';
  if (t === 'bluetooth') return 'bluetooth';
  if (t === 'none' || t === 'other') return 'unknown';
  return t;
}

function normalizeEffective(ef) {
  if (!ef) return 'unknown';
  const e = String(ef).toLowerCase();
  if (['slow-2g', '2g', '3g', '4g', '5g'].includes(e)) return e;
  return 'unknown';
}

export class ConnectionCapture {
  constructor() {
    this.attached = false;
    this.available = false;
    this._conn = null;
    this._handler = this._updateCache.bind(this);
    this._cache = { connection_class: 'unknown', effective_type: 'unknown' };
  }

  attach() {
    if (this.attached || typeof navigator === 'undefined') return;
    this.attached = true;
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!conn) {
      this.available = false;
      return;
    }
    this._conn = conn;
    this.available = true;
    try { conn.addEventListener('change', this._handler); } catch { /* ignore */ }
    this._updateCache();
  }

  detach() {
    if (!this.attached) return;
    try { if (this._conn) this._conn.removeEventListener('change', this._handler); } catch { /* ignore */ }
    this._conn = null;
    this.attached = false;
  }

  _updateCache() {
    if (!this._conn) return;
    this._cache = {
      connection_class: normalizeType(this._conn.type),
      effective_type: normalizeEffective(this._conn.effectiveType),
    };
  }

  async getFeatures() {
    return { ...this._cache, available: this.available };
  }

  reset() {
    this._cache = { connection_class: 'unknown', effective_type: 'unknown' };
  }
}
