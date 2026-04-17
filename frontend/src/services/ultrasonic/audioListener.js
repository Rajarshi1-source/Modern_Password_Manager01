/**
 * Ultrasonic audio listener.
 *
 * Opens a microphone stream via ``getUserMedia`` and records a fixed
 * capture window into a Float32 buffer. The full PCM buffer is then
 * handed to the FSK decoder in :mod:`./fsk`, which does its own
 * preamble search — this module is intentionally "dumb" to keep the
 * real-time path lean and to make the decoder independently testable
 * with synthetic PCM.
 *
 * Usage:
 *   const listener = new AudioListener();
 *   const pcm = await listener.capture({ seconds: 3 });
 *   listener.close();
 *   const frame = decodeFrameFromPcm(pcm, listener.sampleRate, 6 * 8);
 */

export default class AudioListener {
  constructor() {
    this._stream = null;
    this._ctx = null;
    this.sampleRate = 48000;
  }

  async _openStream() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      video: false,
    });
    this._stream = stream;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    this._ctx = new Ctor();
    if (this._ctx.state === 'suspended') {
      try { await this._ctx.resume(); } catch { /* noop */ }
    }
    this.sampleRate = this._ctx.sampleRate;
    return stream;
  }

  /**
   * Capture ``seconds`` of mono PCM from the microphone and resolve
   * with the concatenated Float32Array. Uses a ScriptProcessorNode
   * intentionally — AudioWorkletNode would be cleaner but is a
   * material pain to set up inside a Vite test environment and the
   * extra latency is not visible in the preamble search.
   */
  async capture({ seconds = 3 } = {}) {
    await this._openStream();
    const src = this._ctx.createMediaStreamSource(this._stream);
    const bufferSize = 4096;
    const processor = this._ctx.createScriptProcessor(bufferSize, 1, 1);
    const chunks = [];
    return new Promise((resolve, reject) => {
      let totalSamples = 0;
      const target = Math.ceil(seconds * this._ctx.sampleRate);
      processor.onaudioprocess = (ev) => {
        const data = ev.inputBuffer.getChannelData(0);
        const copy = new Float32Array(data.length);
        copy.set(data);
        chunks.push(copy);
        totalSamples += copy.length;
        if (totalSamples >= target) {
          processor.disconnect();
          src.disconnect();
          const out = new Float32Array(totalSamples);
          let off = 0;
          for (const c of chunks) {
            out.set(c, off);
            off += c.length;
          }
          resolve(out);
        }
      };
      src.connect(processor);
      processor.connect(this._ctx.destination);
      setTimeout(() => {
        if (totalSamples === 0) {
          try { processor.disconnect(); src.disconnect(); } catch { /* noop */ }
          reject(new Error('microphone did not produce audio within capture window'));
        }
      }, seconds * 1000 + 2000);
    });
  }

  close() {
    if (this._stream) {
      this._stream.getTracks().forEach((t) => {
        try { t.stop(); } catch { /* noop */ }
      });
      this._stream = null;
    }
    if (this._ctx && this._ctx.state !== 'closed') {
      try { this._ctx.close(); } catch { /* noop */ }
    }
    this._ctx = null;
  }
}
