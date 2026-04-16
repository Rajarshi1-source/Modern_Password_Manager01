/**
 * Pointer-pressure capture.
 *
 * Listens to `pointermove`/`pointerdown` events and tracks the rolling
 * mean of `PointerEvent.pressure`. Most mice report pressure == 0.5;
 * stylus and trackpads emit richer distributions. Only a bucket is
 * emitted.
 */

const SAMPLES_MAX = 256;

function bucket(mean) {
  if (mean == null || Number.isNaN(mean)) return 'unknown';
  if (mean < 0.1) return 'very_light';
  if (mean < 0.35) return 'light';
  if (mean < 0.6) return 'medium';
  if (mean < 0.85) return 'firm';
  return 'hard';
}

export class PointerPressureCapture {
  constructor() {
    this.attached = false;
    this.samples = [];
    this.available = false;
    this._onDown = this._record.bind(this);
    this._onMove = this._record.bind(this);
  }

  attach() {
    if (this.attached || typeof window === 'undefined') return;
    this.attached = true;
    try {
      window.addEventListener('pointerdown', this._onDown, { passive: true, capture: true });
      window.addEventListener('pointermove', this._onMove, { passive: true, capture: true });
      this.available = true;
    } catch {
      this.available = false;
    }
  }

  detach() {
    if (!this.attached) return;
    try {
      window.removeEventListener('pointerdown', this._onDown, { capture: true });
      window.removeEventListener('pointermove', this._onMove, { capture: true });
    } catch { /* ignore */ }
    this.attached = false;
  }

  _record(evt) {
    if (!evt) return;
    const p = typeof evt.pressure === 'number' ? evt.pressure : null;
    if (p == null || p === 0) return; // ignore synthetic zeros
    this.samples.push(p);
    if (this.samples.length > SAMPLES_MAX) this.samples.shift();
  }

  async getFeatures() {
    const n = this.samples.length;
    if (n === 0) {
      return { pointer_pressure_mean_bucket: 'unknown', available: false };
    }
    const mean = this.samples.reduce((a, b) => a + b, 0) / n;
    return {
      pointer_pressure_mean_bucket: bucket(mean),
      available: true,
    };
  }

  reset() {
    this.samples = [];
  }
}
