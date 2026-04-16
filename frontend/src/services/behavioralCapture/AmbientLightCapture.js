/**
 * Ambient light capture.
 *
 * Preferred: the `AmbientLightSensor` API (Android Chrome only).
 * Fallback: `matchMedia('(prefers-color-scheme: dark)')` as a coarse proxy
 * plus a guess-from-time-of-day bucket.
 *
 * Only a bucketed value is emitted. Never raw lux.
 */

const LIGHT_BUCKETS = ['dark', 'dim', 'normal', 'bright'];

function bucketFromLux(lux) {
  if (lux == null || Number.isNaN(lux)) return null;
  if (lux < 10) return 'dark';
  if (lux < 80) return 'dim';
  if (lux < 400) return 'normal';
  return 'bright';
}

function fallbackBucket() {
  try {
    if (typeof window === 'undefined') return null;
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dim';
    }
    const hour = new Date().getHours();
    if (hour < 6 || hour >= 22) return 'dark';
    if (hour < 8 || hour >= 20) return 'dim';
    return 'normal';
  } catch {
    return null;
  }
}

export class AmbientLightCapture {
  constructor() {
    this.sensor = null;
    this.lastBucket = null;
    this.available = false;
    this.attached = false;
  }

  attach() {
    if (this.attached || typeof window === 'undefined') return;
    this.attached = true;
    try {
      const Ctor = window.AmbientLightSensor;
      if (typeof Ctor === 'function') {
        this.sensor = new Ctor({ frequency: 1 });
        this.sensor.addEventListener('reading', () => {
          const b = bucketFromLux(this.sensor.illuminance);
          if (b) {
            this.lastBucket = b;
            this.available = true;
          }
        });
        this.sensor.addEventListener('error', () => {
          this.available = false;
          this.sensor = null;
        });
        this.sensor.start();
        this.available = true;
      }
    } catch {
      this.sensor = null;
      this.available = false;
    }
  }

  detach() {
    try {
      if (this.sensor && typeof this.sensor.stop === 'function') this.sensor.stop();
    } catch { /* ignore */ }
    this.sensor = null;
    this.attached = false;
  }

  async getFeatures() {
    const bucket = this.lastBucket || fallbackBucket();
    return {
      light_bucket: bucket,
      available: this.available || Boolean(bucket),
    };
  }

  reset() {
    this.lastBucket = null;
  }
}
