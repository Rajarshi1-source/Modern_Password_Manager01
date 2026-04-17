/**
 * HRV feature extraction tests on synthetic signals.
 *
 * The PPG pipeline is built around a 1 Hz ≈ 60 BPM cardiac signal
 * buried in noise, so we drive it with exactly that and check the
 * extractor recovers the expected mean HR within a few BPM.
 */

import { describe, it, expect } from 'vitest';
import {
  bandpass,
  detectPeaks,
  extractHrvFeatures,
  rrIntervalsMs,
} from './hrvFeatures';

function syntheticPpg(frequencyHz, sampleRate, seconds, noiseAmp = 0.05) {
  const n = Math.round(sampleRate * seconds);
  const samples = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const t = i / sampleRate;
    samples[i] = Math.sin(2 * Math.PI * frequencyHz * t)
      + 0.1 * Math.sin(2 * Math.PI * 0.1 * t) // slow drift
      + (Math.random() - 0.5) * noiseAmp;
  }
  return samples;
}

describe('HRV pipeline', () => {
  const sampleRate = 30;

  it('recovers ~60 BPM from a 1 Hz synthetic signal', () => {
    const samples = syntheticPpg(1.0, sampleRate, 30);
    const { features, peakCount } = extractHrvFeatures(samples, sampleRate);
    expect(peakCount).toBeGreaterThan(20);
    expect(peakCount).toBeLessThan(35);
    expect(features.mean_hr).toBeGreaterThan(55);
    expect(features.mean_hr).toBeLessThan(65);
    expect(features.rmssd).toBeGreaterThanOrEqual(0);
    expect(features.sdnn).toBeGreaterThanOrEqual(0);
  });

  it('recovers ~90 BPM from a 1.5 Hz synthetic signal', () => {
    const samples = syntheticPpg(1.5, sampleRate, 20);
    const { features } = extractHrvFeatures(samples, sampleRate);
    expect(features.mean_hr).toBeGreaterThan(80);
    expect(features.mean_hr).toBeLessThan(100);
  });

  it('rrIntervalsMs derives ~1000ms intervals at 1 Hz', () => {
    const samples = syntheticPpg(1.0, sampleRate, 10);
    const filtered = bandpass(samples, sampleRate);
    const peaks = detectPeaks(filtered, sampleRate);
    const rr = rrIntervalsMs(peaks, sampleRate);
    expect(rr.length).toBeGreaterThan(5);
    const avg = rr.reduce((a, b) => a + b, 0) / rr.length;
    expect(avg).toBeGreaterThan(900);
    expect(avg).toBeLessThan(1100);
  });
});
