/**
 * HeartbeatVerify.jsx — single-capture HRV authentication screen.
 *
 * Collects ONE 20-second PPG reading, extracts HRV features in
 * the browser, and posts them to /api/heartbeat/verify/.
 *
 * The server returns one of three outcomes:
 *   - success  → we redirect to the real vault.
 *   - duress   → the server silently activates the decoy vault and
 *                still returns 200; we show a benign "Authenticated"
 *                screen so an on-looker sees nothing unusual.
 *   - failed   → mismatch; show a retry button.
 *
 * The component NEVER tells the user that duress was triggered —
 * that would defeat the whole point. Ops see the silent alarm in
 * the admin side.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { capturePpg } from '../../services/heartbeat/ppgCapture';
import { extractHrvFeatures } from '../../services/heartbeat/hrvFeatures';
import heartbeatService from '../../services/heartbeatService';

const CAPTURE_SECONDS = 20;

export default function HeartbeatVerify() {
  const [phase, setPhase] = useState('idle');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Place your finger on the rear camera when ready.');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const abortRef = useRef(false);

  useEffect(() => () => { abortRef.current = true; }, []);

  const runCapture = useCallback(async () => {
    setError('');
    setResult(null);
    setPhase('capturing');
    setProgress(0);
    setStatus('Recording pulse...');
    try {
      const ppg = await capturePpg({
        seconds: CAPTURE_SECONDS,
        onFrame: (_v, elapsedMs) => {
          setProgress(Math.min(100, Math.floor((elapsedMs / 1000 / CAPTURE_SECONDS) * 100)));
        },
      });
      if (abortRef.current) return;
      setPhase('processing');
      setStatus('Analysing heart-rate variability...');
      const { features, peakCount } = extractHrvFeatures(ppg.samples, ppg.frameRate);
      if (peakCount < 8) {
        setError('Not enough heartbeats detected — try again with the finger fully covering the camera.');
        setPhase('idle');
        return;
      }

      setPhase('uploading');
      setStatus('Verifying...');
      const resp = await heartbeatService.verify(features);
      const data = resp?.data || {};
      // Intentionally do NOT branch on data.duress in the UI string —
      // the success/duress paths are indistinguishable to the user.
      if (data.success || data.duress) {
        setResult({ ok: true, vault: data.vault || null });
        setStatus('Authenticated.');
      } else {
        setResult({ ok: false });
        setStatus(data.detail || 'Heartbeat did not match. Try again.');
      }
      setPhase('done');
    } catch (err) {
      setError(err.message || 'Capture failed.');
      setPhase('idle');
    }
  }, []);

  return (
    <div style={{ maxWidth: 640, margin: '24px auto', color: '#eee' }}>
      <h2>Heartbeat Authentication</h2>
      <p style={{ opacity: 0.8 }}>
        Cover your rear camera with your fingertip for 20 seconds
        so we can verify your pulse signature.
      </p>

      <button
        type="button"
        onClick={runCapture}
        disabled={phase === 'capturing' || phase === 'processing' || phase === 'uploading'}
      >
        {phase === 'idle' || phase === 'done' ? 'Capture pulse' : 'Capturing…'}
      </button>

      {phase === 'capturing' && (
        <div style={{ marginTop: 12 }}>
          <div style={{ background: '#333', height: 10, borderRadius: 5, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', background: '#d54d66' }} />
          </div>
          <p>{progress}%</p>
        </div>
      )}

      <p style={{ opacity: 0.85 }}>{status}</p>
      {error && <p style={{ color: '#ff6868' }}>{error}</p>}
      {result && (
        <div style={{
          marginTop: 16,
          padding: 12,
          borderRadius: 6,
          background: result.ok ? '#1f7a3a' : '#5c1f1f',
        }}
        >
          {result.ok ? 'Vault unlocked.' : 'Authentication failed.'}
        </div>
      )}
    </div>
  );
}
