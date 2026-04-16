/**
 * Scroll momentum capture.
 *
 * Listens to `wheel` events and computes the decay of wheel deltas over
 * short windows. Coarse bucketed feature only — no timestamps, no URLs.
 */

const WINDOW_MS = 1500;

function bucket(momentum) {
  if (momentum == null) return 'unknown';
  if (momentum < 40) return 'low';
  if (momentum < 200) return 'medium';
  if (momentum < 800) return 'high';
  return 'very_high';
}

export class ScrollMomentumCapture {
  constructor() {
    this.attached = false;
    this.events = []; // {t, dy}
    this.available = false;
    this._onWheel = this._record.bind(this);
  }

  attach() {
    if (this.attached || typeof window === 'undefined') return;
    this.attached = true;
    try {
      window.addEventListener('wheel', this._onWheel, { passive: true });
      this.available = true;
    } catch {
      this.available = false;
    }
  }

  detach() {
    if (!this.attached) return;
    try { window.removeEventListener('wheel', this._onWheel); } catch { /* ignore */ }
    this.attached = false;
  }

  _record(evt) {
    const t = Date.now();
    const dy = Math.abs(typeof evt.deltaY === 'number' ? evt.deltaY : 0);
    this.events.push({ t, dy });
    const cutoff = t - WINDOW_MS;
    while (this.events.length > 0 && this.events[0].t < cutoff) this.events.shift();
  }

  _momentum() {
    const now = Date.now();
    let total = 0;
    for (const e of this.events) {
      if (e.t < now - WINDOW_MS) continue;
      // Decay linearly with age within the window.
      const age = Math.max(0, now - e.t);
      const weight = 1 - age / WINDOW_MS;
      total += e.dy * weight;
    }
    return total;
  }

  async getFeatures() {
    const momentum = this._momentum();
    const available = this.available && this.events.length > 0;
    return {
      scroll_momentum_bucket: available ? bucket(momentum) : 'unknown',
      available,
    };
  }

  reset() {
    this.events = [];
  }
}
