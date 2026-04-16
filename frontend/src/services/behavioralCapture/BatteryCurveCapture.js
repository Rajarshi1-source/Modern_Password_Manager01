/**
 * Battery drain-curve capture.
 *
 * Polls `navigator.getBattery()` periodically and estimates the rolling
 * drain slope. Emits a coarse bucket only; never sends timestamps or
 * levels.
 */

const POLL_MS = 60_000;
const WINDOW_SIZE = 10;

function bucket(slopePerMin) {
  if (slopePerMin == null || Number.isNaN(slopePerMin)) return 'unknown';
  if (slopePerMin >= 0) return 'charging';
  const magnitude = Math.abs(slopePerMin);
  if (magnitude < 0.0005) return 'stable';
  if (magnitude < 0.002) return 'slow';
  if (magnitude < 0.006) return 'medium';
  return 'fast';
}

export class BatteryCurveCapture {
  constructor() {
    this.attached = false;
    this.samples = []; // {t, level}
    this.available = false;
    this._timer = null;
    this._battery = null;
  }

  attach() {
    if (this.attached || typeof navigator === 'undefined') return;
    this.attached = true;
    if (typeof navigator.getBattery !== 'function') {
      this.available = false;
      return;
    }
    navigator.getBattery()
      .then((b) => {
        this._battery = b;
        this.available = true;
        this._poll();
        this._timer = setInterval(() => this._poll(), POLL_MS);
      })
      .catch(() => {
        this.available = false;
      });
  }

  detach() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    this._battery = null;
    this.attached = false;
  }

  _poll() {
    if (!this._battery) return;
    const level = typeof this._battery.level === 'number' ? this._battery.level : null;
    const charging = Boolean(this._battery.charging);
    const t = Date.now();
    this.samples.push({ t, level, charging });
    if (this.samples.length > WINDOW_SIZE) this.samples.shift();
  }

  _slopePerMin() {
    if (this.samples.length < 2) return null;
    const first = this.samples[0];
    const last = this.samples[this.samples.length - 1];
    if (last.charging) return 1; // treat as charging
    if (first.level == null || last.level == null) return null;
    const dl = last.level - first.level;
    const dtMin = (last.t - first.t) / 60_000;
    if (dtMin <= 0) return null;
    return dl / dtMin;
  }

  async getFeatures() {
    const slope = this._slopePerMin();
    return {
      battery_drain_slope_bucket: bucket(slope),
      available: this.available && this.samples.length >= 2,
    };
  }

  reset() {
    this.samples = [];
  }
}
