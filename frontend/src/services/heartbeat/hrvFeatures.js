/**
 * HRV feature extraction from PPG samples.
 *
 * Pipeline:
 *   1. Resample/detrend the raw mean-red signal.
 *   2. Bandpass 0.7–4 Hz (biquad, applied forward then reversed for
 *      approximate zero-phase).
 *   3. Peak detection with refractory period (> 300 ms).
 *   4. R-R interval series in ms.
 *   5. Time-domain HRV: mean HR, RMSSD, SDNN, pNN50.
 *   6. Frequency-domain HRV: LF (0.04–0.15 Hz), HF (0.15–0.4 Hz),
 *      LF/HF ratio via a small embedded FFT over an interpolated
 *      R-R tachogram.
 *
 * The embedded FFT is a plain radix-2 Cooley–Tukey — the tachogram
 * length is always padded to a power of two so we avoid external
 * deps (no `fft.js`) and keep the bundle small.
 */

/** Mean of a numeric array. */
function mean(arr) {
  if (!arr.length) return 0;
  let s = 0;
  for (let i = 0; i < arr.length; i += 1) s += arr[i];
  return s / arr.length;
}

/** Sample standard deviation. */
function std(arr) {
  if (arr.length < 2) return 0;
  const mu = mean(arr);
  let s = 0;
  for (let i = 0; i < arr.length; i += 1) {
    const d = arr[i] - mu;
    s += d * d;
  }
  return Math.sqrt(s / (arr.length - 1));
}

/** Remove slow linear drift by subtracting the least-squares line. */
export function detrend(signal) {
  const n = signal.length;
  if (n < 2) return Float32Array.from(signal);
  const xs = new Array(n);
  const ys = new Array(n);
  for (let i = 0; i < n; i += 1) {
    xs[i] = i;
    ys[i] = signal[i];
  }
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i += 1) {
    num += (xs[i] - mx) * (ys[i] - my);
    den += (xs[i] - mx) ** 2;
  }
  const slope = den === 0 ? 0 : num / den;
  const intercept = my - slope * mx;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) out[i] = signal[i] - (slope * i + intercept);
  return out;
}

/**
 * Bi-quadratic bandpass filter.
 * Coefficients computed from the Robert Bristow-Johnson cookbook.
 * Applied forward then on the reversed signal to approximate a
 * zero-phase filter without pulling in a full filtfilt dependency.
 */
function biquadBandpass(sampleRate, fLow, fHigh) {
  const fCenter = Math.sqrt(fLow * fHigh);
  const bw = fHigh - fLow;
  const w0 = (2 * Math.PI * fCenter) / sampleRate;
  const alpha = Math.sin(w0) * Math.sinh(
    (Math.LN2 / 2) * (bw / fCenter) * (w0 / Math.sin(w0)),
  );
  const b0 = alpha;
  const b1 = 0;
  const b2 = -alpha;
  const a0 = 1 + alpha;
  const a1 = -2 * Math.cos(w0);
  const a2 = 1 - alpha;
  return {
    b: [b0 / a0, b1 / a0, b2 / a0],
    a: [1, a1 / a0, a2 / a0],
  };
}

function filterOnce(signal, coeffs) {
  const { b, a } = coeffs;
  const out = new Float32Array(signal.length);
  let x1 = 0;
  let x2 = 0;
  let y1 = 0;
  let y2 = 0;
  for (let i = 0; i < signal.length; i += 1) {
    const x = signal[i];
    const y = b[0] * x + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2;
    out[i] = y;
    x2 = x1; x1 = x;
    y2 = y1; y1 = y;
  }
  return out;
}

export function bandpass(signal, sampleRate, fLow = 0.7, fHigh = 4.0) {
  const coeffs = biquadBandpass(sampleRate, fLow, fHigh);
  const fwd = filterOnce(signal, coeffs);
  const reversed = new Float32Array(fwd.length);
  for (let i = 0; i < fwd.length; i += 1) reversed[i] = fwd[fwd.length - 1 - i];
  const back = filterOnce(reversed, coeffs);
  const out = new Float32Array(back.length);
  for (let i = 0; i < back.length; i += 1) out[i] = back[back.length - 1 - i];
  return out;
}

/**
 * Simple adaptive peak picker: local maxima above a rolling threshold
 * with a 300 ms refractory.
 */
export function detectPeaks(signal, sampleRate) {
  const n = signal.length;
  if (n < 3) return [];
  const sigma = std(signal);
  const threshold = 0.3 * sigma;
  const refractorySamples = Math.round(0.3 * sampleRate);
  const peaks = [];
  for (let i = 1; i < n - 1; i += 1) {
    if (signal[i] > signal[i - 1] && signal[i] > signal[i + 1] && signal[i] > threshold) {
      const last = peaks[peaks.length - 1];
      if (last === undefined || i - last >= refractorySamples) {
        peaks.push(i);
      } else if (signal[i] > signal[last]) {
        peaks[peaks.length - 1] = i;
      }
    }
  }
  return peaks;
}

export function rrIntervalsMs(peaks, sampleRate) {
  const rr = [];
  for (let i = 1; i < peaks.length; i += 1) {
    rr.push(((peaks[i] - peaks[i - 1]) / sampleRate) * 1000);
  }
  return rr;
}

/** Radix-2 Cooley–Tukey FFT on real input (imaginary part is zero). */
function fftRadix2(real, imag) {
  const n = real.length;
  if (n <= 1) return;
  const log2 = Math.log2(n);
  if (!Number.isInteger(log2)) throw new Error('FFT size must be a power of 2');

  for (let i = 1, j = 0; i < n; i += 1) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [real[i], real[j]] = [real[j], real[i]];
      [imag[i], imag[j]] = [imag[j], imag[i]];
    }
  }

  for (let size = 2; size <= n; size <<= 1) {
    const half = size >> 1;
    const ang = (-2 * Math.PI) / size;
    const wRe = Math.cos(ang);
    const wIm = Math.sin(ang);
    for (let i = 0; i < n; i += size) {
      let curRe = 1;
      let curIm = 0;
      for (let k = 0; k < half; k += 1) {
        const a = i + k;
        const b = a + half;
        const tRe = curRe * real[b] - curIm * imag[b];
        const tIm = curRe * imag[b] + curIm * real[b];
        real[b] = real[a] - tRe;
        imag[b] = imag[a] - tIm;
        real[a] += tRe;
        imag[a] += tIm;
        const nextRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = nextRe;
      }
    }
  }
}

function nextPow2(x) {
  let n = 1;
  while (n < x) n <<= 1;
  return n;
}

/**
 * LF/HF ratio from an R-R tachogram.
 * The tachogram is interpolated at 4 Hz, zero-padded to the next
 * power of two, and transformed with the radix-2 FFT above.
 * Returns ``{lf, hf, lfHf}``.
 */
export function lfHfRatio(rrMs) {
  if (rrMs.length < 8) return { lf: 0, hf: 0, lfHf: 0 };
  const timeStamps = [0];
  for (let i = 0; i < rrMs.length; i += 1) timeStamps.push(timeStamps[i] + rrMs[i] / 1000);
  const rrSeconds = rrMs.map((v) => v / 1000);
  const totalS = timeStamps[timeStamps.length - 1];
  if (totalS <= 0) return { lf: 0, hf: 0, lfHf: 0 };
  const fs = 4;
  const nSamples = Math.max(16, Math.floor(totalS * fs));
  const tachogram = new Float32Array(nSamples);
  for (let i = 0; i < nSamples; i += 1) {
    const t = i / fs;
    let k = 0;
    while (k < timeStamps.length - 1 && timeStamps[k + 1] < t) k += 1;
    tachogram[i] = rrSeconds[Math.min(k, rrSeconds.length - 1)];
  }
  const mu = mean(Array.from(tachogram));
  const N = nextPow2(nSamples);
  const real = new Float32Array(N);
  const imag = new Float32Array(N);
  for (let i = 0; i < nSamples; i += 1) real[i] = tachogram[i] - mu;
  fftRadix2(real, imag);

  let lf = 0;
  let hf = 0;
  for (let i = 0; i < N / 2; i += 1) {
    const freq = (i * fs) / N;
    const pwr = real[i] * real[i] + imag[i] * imag[i];
    if (freq >= 0.04 && freq < 0.15) lf += pwr;
    else if (freq >= 0.15 && freq < 0.4) hf += pwr;
  }
  const lfHf = hf === 0 ? 0 : lf / hf;
  return { lf, hf, lfHf };
}

/**
 * Compute the full HRV feature dict from a raw PPG sample buffer.
 */
export function extractHrvFeatures(samples, sampleRate) {
  const detrended = detrend(samples);
  const filtered = bandpass(detrended, sampleRate);
  const peaks = detectPeaks(filtered, sampleRate);
  const rr = rrIntervalsMs(peaks, sampleRate);
  const meanRr = mean(rr);
  const meanHr = meanRr > 0 ? 60000 / meanRr : 0;

  // RMSSD: RMS of successive differences.
  let sumSq = 0;
  let nDiffs = 0;
  let countOver50 = 0;
  for (let i = 1; i < rr.length; i += 1) {
    const d = rr[i] - rr[i - 1];
    sumSq += d * d;
    nDiffs += 1;
    if (Math.abs(d) > 50) countOver50 += 1;
  }
  const rmssd = nDiffs > 0 ? Math.sqrt(sumSq / nDiffs) : 0;
  const sdnn = std(rr);
  const pnn50 = nDiffs > 0 ? countOver50 / nDiffs : 0;
  const { lfHf } = lfHfRatio(rr);

  return {
    features: {
      mean_hr: meanHr,
      rmssd,
      sdnn,
      pnn50,
      lf_hf_ratio: lfHf,
    },
    peakCount: peaks.length,
    rrIntervalsMs: rr,
  };
}

export default {
  detrend,
  bandpass,
  detectPeaks,
  rrIntervalsMs,
  lfHfRatio,
  extractHrvFeatures,
};
