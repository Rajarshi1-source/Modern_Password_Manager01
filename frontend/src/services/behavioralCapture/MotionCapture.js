/**
 * Motion capture via `DeviceMotionEvent` / `DeviceOrientationEvent`.
 *
 * Emits a coarse motion class (still / walking / vehicle / unknown) based
 * on recent acceleration magnitude. Raw accelerometer samples are
 * discarded after the classification update.
 *
 * On iOS, `DeviceMotionEvent.requestPermission()` must be invoked from a
 * user gesture — the ambient onboarding screen calls `requestPermission`
 * explicitly. Here we just attempt to attach and gracefully degrade when
 * permission is not granted.
 */

const STILL_THRESHOLD = 0.20;     // m/s^2 above gravity
const WALKING_THRESHOLD = 2.5;
const VEHICLE_THRESHOLD = 5.0;
const WINDOW_SIZE = 32;

export class MotionCapture {
  constructor() {
    this.attached = false;
    this.magnitudes = [];
    this.lastClass = 'unknown';
    this.available = false;
    this._handler = this._onMotion.bind(this);
  }

  async requestPermissionIfNeeded() {
    try {
      if (typeof DeviceMotionEvent !== 'undefined'
          && typeof DeviceMotionEvent.requestPermission === 'function') {
        const res = await DeviceMotionEvent.requestPermission();
        return res === 'granted';
      }
    } catch {
      return false;
    }
    return true;
  }

  attach() {
    if (this.attached || typeof window === 'undefined') return;
    this.attached = true;
    try {
      window.addEventListener('devicemotion', this._handler, { passive: true });
      this.available = true;
    } catch {
      this.available = false;
    }
  }

  detach() {
    if (!this.attached) return;
    try {
      window.removeEventListener('devicemotion', this._handler);
    } catch { /* ignore */ }
    this.attached = false;
  }

  _onMotion(evt) {
    const a = evt && evt.accelerationIncludingGravity;
    if (!a) return;
    const x = typeof a.x === 'number' ? a.x : 0;
    const y = typeof a.y === 'number' ? a.y : 0;
    const z = typeof a.z === 'number' ? a.z : 0;
    const mag = Math.sqrt(x * x + y * y + z * z);
    this.magnitudes.push(Math.abs(mag - 9.81));
    if (this.magnitudes.length > WINDOW_SIZE) this.magnitudes.shift();
  }

  _classify() {
    if (this.magnitudes.length === 0) return 'unknown';
    const mean = this.magnitudes.reduce((a, b) => a + b, 0) / this.magnitudes.length;
    if (mean < STILL_THRESHOLD) return 'still';
    if (mean < WALKING_THRESHOLD) return 'walking';
    if (mean < VEHICLE_THRESHOLD) return 'walking';
    return 'vehicle';
  }

  async getFeatures() {
    this.lastClass = this._classify();
    return {
      motion_class: this.lastClass,
      available: this.available && this.magnitudes.length > 0,
    };
  }

  reset() {
    this.magnitudes = [];
    this.lastClass = 'unknown';
  }
}
