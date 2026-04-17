/**
 * Ultrasonic audio emitter.
 *
 * Schedules a frame of FSK bits as a sequence of OscillatorNodes on a
 * single shared AudioContext, with a short raised-cosine gain envelope
 * around each symbol to avoid clicks when the frequency changes.
 *
 * Usage:
 *   const emitter = new AudioEmitter();
 *   await emitter.emitFrame(bits);
 *   emitter.close();
 */

import { FSK_F0, FSK_F1, SYMBOL_DURATION_S } from './fsk';

export default class AudioEmitter {
  constructor(options = {}) {
    this.amplitude = options.amplitude ?? 0.4;
    this.symbolDuration = options.symbolDuration ?? SYMBOL_DURATION_S;
    this._ctx = null;
  }

  _ensureContext() {
    if (!this._ctx || this._ctx.state === 'closed') {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) throw new Error('Web Audio is not supported in this browser');
      this._ctx = new Ctor();
    }
    return this._ctx;
  }

  /**
   * Emit the bit array. Resolves once the final symbol has finished
   * playing. The caller is responsible for UI-facing "emitting..."
   * state; this method does not yield intermediate progress.
   */
  async emitFrame(bits) {
    if (!Array.isArray(bits) || bits.length === 0) return;
    const ctx = this._ensureContext();
    if (ctx.state === 'suspended') {
      try { await ctx.resume(); } catch { /* noop */ }
    }

    const start = ctx.currentTime + 0.05;
    const dur = this.symbolDuration;
    const rampS = Math.min(0.005, dur * 0.1);

    bits.forEach((bit, i) => {
      const freq = bit === 1 ? FSK_F1 : FSK_F0;
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const gain = ctx.createGain();
      const t0 = start + i * dur;
      gain.gain.setValueAtTime(0, t0);
      gain.gain.linearRampToValueAtTime(this.amplitude, t0 + rampS);
      gain.gain.setValueAtTime(this.amplitude, t0 + dur - rampS);
      gain.gain.linearRampToValueAtTime(0, t0 + dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t0);
      osc.stop(t0 + dur + 0.01);
    });

    const totalMs = Math.ceil((0.05 + bits.length * dur + 0.05) * 1000);
    await new Promise((resolve) => setTimeout(resolve, totalMs));
  }

  close() {
    if (this._ctx && this._ctx.state !== 'closed') {
      try { this._ctx.close(); } catch { /* noop */ }
    }
    this._ctx = null;
  }
}
