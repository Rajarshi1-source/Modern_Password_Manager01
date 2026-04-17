/**
 * HeartbeatEnroll.jsx — baseline enrollment wizard.
 *
 * Collects THREE 30-second PPG recordings so the server-side
 * feature matcher has enough samples to build a covariance.
 * Between captures the UI asks the user to rest briefly, since
 * enrollment is supposed to lock in a CALM baseline (stress will
 * later trigger duress).
 *
 * Every capture:
 *   1. getUserMedia rear camera + torch (services/heartbeat/ppgCapture).
 *   2. Extract HRV features client-side (services/heartbeat/hrvFeatures).
 *   3. POST features to /api/heartbeat/enroll/ (heartbeatService).
 *
 * The raw PPG buffer never leaves the browser.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { capturePpg } from '../../services/heartbeat/ppgCapture';
import { extractHrvFeatures } from '../../services/heartbeat/hrvFeatures';
import heartbeatService from '../../services/heartbeatService';

const CAPTURE_SECONDS = 30;
const REQUIRED_READINGS = 3;

function Step({ n, current, label }) {
  const active = n === current;
  const done = n < current;
  return (
    <div style={{
      padding: '4px 10px', margin: '0 4px',
      borderRadius: 14,
      background: done ? '#1f7a3a' : (active ? '#2d5ef1' : '#444'),
      color: '#fff',
      fontSize: 13,
    }}
    >
      {n}. {label}
    </div>
  );
}

export default function HeartbeatEnroll() {
  const [step, setStep] = useState(1);
  const [phase, setPhase] = useState('idle');
  const [progress, setProgress] = useState(0);
  const [capturedCount, setCapturedCount] = useState(0);
  const [lastFeatures, setLastFeatures] = useState(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const abortRef = useRef(false);

  useEffect(() => () => { abortRef.current = true; }, []);

  const runCapture = useCallback(async () => {
    setError('');
    setPhase('capturing');
    setProgress(0);
    setStatus('Place your fingertip gently on the rear camera (cover it fully).');
    try {
      const result = await capturePpg({
        seconds: CAPTURE_SECONDS,
        onFrame: (_v, elapsedMs) => {
          setProgress(Math.min(100, Math.floor((elapsedMs / 1000 / CAPTURE_SECONDS) * 100)));
        },
      });
      if (abortRef.current) return;
      setPhase('processing');
      setStatus('Extracting heart-rate variability features...');
      const { features, peakCount } = extractHrvFeatures(
        result.samples, result.frameRate,
      );
      if (peakCount < 10) {
        setError('Not enough heartbeats detected. Try again with the finger covering the camera and the torch on.');
        setPhase('idle');
        return;
      }
      setLastFeatures(features);
      setPhase('uploading');
      setStatus('Uploading baseline features...');
      const resp = await heartbeatService.enroll(features);
      if (!resp?.data?.success) {
        setError(resp?.data?.detail || 'Server rejected baseline reading.');
        setPhase('idle');
        return;
      }
      setCapturedCount((c) => c + 1);
      setPhase('done');
      setStatus(`Reading ${capturedCount + 1}/${REQUIRED_READINGS} accepted.`);
    } catch (err) {
      setError(err.message || 'Capture failed.');
      setPhase('idle');
    }
  }, [capturedCount]);

  const next = () => setStep((s) => Math.min(s + 1, 3));
  const canFinish = capturedCount >= REQUIRED_READINGS;

  return (
    <div style={{ maxWidth: 640, margin: '24px auto', color: '#eee' }}>
      <h2>Heartbeat Enrollment</h2>
      <p style={{ opacity: 0.8 }}>
        We capture your heart-rate variability over three 30-second
        windows so the system can recognise your signal and detect
        when you're under duress.
      </p>

      <div style={{ display: 'flex', margin: '12px 0 18px' }}>
        <Step n={1} current={step} label="Permissions" />
        <Step n={2} current={step} label="Record" />
        <Step n={3} current={step} label="Finish" />
      </div>

      {step === 1 && (
        <div>
          <ol>
            <li>Stay seated and calm for the duration of each capture.</li>
            <li>Cover the rear camera with a fingertip (the flashlight will turn on if supported).</li>
            <li>Keep your hand still; we need clean samples for a good baseline.</li>
          </ol>
          <button type="button" onClick={next}>I'm ready</button>
        </div>
      )}

      {step === 2 && (
        <div>
          <p>
            <strong>Readings captured:</strong> {capturedCount} / {REQUIRED_READINGS}
          </p>
          <div style={{ margin: '8px 0' }}>
            <button type="button" onClick={runCapture} disabled={phase === 'capturing' || phase === 'processing' || phase === 'uploading' || canFinish}>
              {canFinish ? 'All readings collected' : `Capture reading ${capturedCount + 1}`}
            </button>
          </div>
          {phase === 'capturing' && (
            <div>
              <div style={{ background: '#333', height: 10, borderRadius: 5, overflow: 'hidden' }}>
                <div style={{ width: `${progress}%`, height: '100%', background: '#3bb273' }} />
              </div>
              <p>{progress}% — hold still.</p>
            </div>
          )}
          {status && <p style={{ opacity: 0.85 }}>{status}</p>}
          {error && <p style={{ color: '#ff6868' }}>{error}</p>}
          {lastFeatures && (
            <details>
              <summary>Last reading (features, stays on device)</summary>
              <pre>{JSON.stringify(lastFeatures, null, 2)}</pre>
            </details>
          )}
          {canFinish && (
            <button type="button" onClick={next} style={{ marginTop: 12 }}>
              Finish enrollment
            </button>
          )}
        </div>
      )}

      {step === 3 && (
        <div>
          <p>Your heartbeat baseline is now active.</p>
          <p>You can use <code>/auth/heartbeat/verify</code> to authenticate with your pulse.</p>
        </div>
      )}
    </div>
  );
}
