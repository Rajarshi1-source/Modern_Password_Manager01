/**
 * UltrasonicPair.jsx
 *
 * Dual-mode pairing screen.
 *
 *   * Emit mode (initiator): generate an ECDH P-256 keypair, open a
 *     session, and broadcast the 6-byte nonce over 18.5/19.5 kHz FSK.
 *     Poll the server until the responder confirms, derive the shared
 *     secret, and display the SAS code.
 *   * Listen mode (responder): open the microphone, decode the nonce,
 *     generate our own keypair, claim the session, derive the shared
 *     secret, submit HMAC(shared, "sas"), and display the SAS code.
 *
 * Both sides see the same 6-digit SAS after confirmation; the user
 * reads it aloud as the final human-in-the-loop check. If the two
 * screens disagree, something MITM'd the audio.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ultrasonicPairingService, {
  abToB64,
  b64ToU8,
  deriveSharedBits,
  generateEcdhKeyPair,
  hmacSasCode,
  importRawEcdhPublicKey,
  shortAuthStringFromTag,
} from '../../services/ultrasonicPairingService';
import AudioEmitter from '../../services/ultrasonic/audioEmitter';
import AudioListener from '../../services/ultrasonic/audioListener';
import {
  buildFrameBits,
  decodeFrameFromPcm,
} from '../../services/ultrasonic/fsk';

const PURPOSES = [
  { value: 'device_enroll', label: 'Enroll new device on this account' },
  { value: 'item_share', label: 'Share one vault item in person' },
];

function Status({ label, value }) {
  return (
    <div style={{ margin: '4px 0' }}>
      <strong>{label}:</strong> <span>{value}</span>
    </div>
  );
}

function EmitMode({ onDone }) {
  const [purpose, setPurpose] = useState('device_enroll');
  const [stage, setStage] = useState('idle'); // idle|initiating|emitting|polling|confirmed|error
  const [error, setError] = useState('');
  const [sas, setSas] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const emitterRef = useRef(null);
  const keyPairRef = useRef(null);
  const pollRef = useRef(null);

  const stop = useCallback(() => {
    if (emitterRef.current) {
      try { emitterRef.current.close(); } catch { /* noop */ }
    }
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  const begin = async () => {
    setError('');
    setSas('');
    setStage('initiating');
    try {
      const { keyPair, publicKeyB64 } = await generateEcdhKeyPair();
      keyPairRef.current = keyPair;

      const resp = await ultrasonicPairingService.initiate({
        pub_key: publicKeyB64,
        purpose,
      });
      const { session_id: id, nonce: nonceB64 } = resp.data;
      setSessionId(id);

      setStage('emitting');
      const nonce = b64ToU8(nonceB64);
      const bits = buildFrameBits(nonce);
      emitterRef.current = new AudioEmitter();
      await emitterRef.current.emitFrame(bits);

      setStage('polling');
      pollRef.current = setInterval(async () => {
        try {
          const p = await ultrasonicPairingService.get(id);
          const s = p.data.session;
          if (s.status === 'confirmed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            const peer = await importRawEcdhPublicKey(s.responder_pub_key_b64);
            const sharedBits = await deriveSharedBits(keyPair.privateKey, peer);
            const tag = await hmacSasCode(sharedBits);
            const mySas = shortAuthStringFromTag(tag);
            const theirTag = b64ToU8(s.sas_hmac_b64);
            const theirSas = shortAuthStringFromTag(theirTag);
            if (mySas === theirSas) {
              setSas(mySas);
              setStage('confirmed');
              onDone?.({ sessionId: id, purpose, keyPair });
            } else {
              setError('SAS mismatch — a man-in-the-middle is likely.');
              setStage('error');
            }
          } else if (['expired', 'failed'].includes(s.status)) {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setError(`Session ended: ${s.status}`);
            setStage('error');
          }
        } catch (err) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setError(err?.response?.data?.message || err.message || 'poll_failed');
          setStage('error');
        }
      }, 1500);
    } catch (err) {
      setError(err?.response?.data?.message || err.message || 'emit_failed');
      setStage('error');
    }
  };

  return (
    <div>
      <h3>Emit (this device)</h3>
      <label>
        Purpose:{' '}
        <select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
          {PURPOSES.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </label>
      <div style={{ margin: '12px 0' }}>
        <button type="button" onClick={begin} disabled={stage !== 'idle' && stage !== 'error' && stage !== 'confirmed'}>
          Start pairing
        </button>{' '}
        <button type="button" onClick={stop}>Cancel</button>
      </div>
      <Status label="Stage" value={stage} />
      {sessionId ? <Status label="Session" value={sessionId} /> : null}
      {sas ? <Status label="SAS (say out loud)" value={sas} /> : null}
      {error ? <div style={{ color: 'crimson' }}>{error}</div> : null}
    </div>
  );
}

function ListenMode({ onDone }) {
  const [stage, setStage] = useState('idle'); // idle|listening|claiming|confirmed|error
  const [error, setError] = useState('');
  const [sas, setSas] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const listenerRef = useRef(null);

  const stop = useCallback(() => {
    if (listenerRef.current) {
      try { listenerRef.current.close(); } catch { /* noop */ }
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  const begin = async () => {
    setError('');
    setSas('');
    setStage('listening');
    try {
      listenerRef.current = new AudioListener();
      const pcm = await listenerRef.current.capture({ seconds: 4 });
      const sampleRate = listenerRef.current.sampleRate;
      const frame = decodeFrameFromPcm(pcm, sampleRate, 6 * 8);
      if (!frame || !frame.crcOk) {
        throw new Error('Could not decode ultrasonic nonce (move closer and retry).');
      }
      const nonceB64 = abToB64(frame.payload.buffer);

      setStage('claiming');
      const { keyPair, publicKeyB64 } = await generateEcdhKeyPair();
      const claimed = await ultrasonicPairingService.claim({
        nonce: nonceB64, pub_key: publicKeyB64,
      });
      const { session_id: id, initiator_pub_key } = claimed.data;
      setSessionId(id);

      const peer = await importRawEcdhPublicKey(initiator_pub_key);
      const sharedBits = await deriveSharedBits(keyPair.privateKey, peer);
      const tag = await hmacSasCode(sharedBits);
      const mySas = shortAuthStringFromTag(tag);

      await ultrasonicPairingService.confirm(id, {
        sas_hmac: abToB64(tag.buffer),
      });
      setSas(mySas);
      setStage('confirmed');
      onDone?.({ sessionId: id, keyPair });
    } catch (err) {
      setError(err?.response?.data?.message || err.message || 'listen_failed');
      setStage('error');
    }
  };

  return (
    <div>
      <h3>Listen (responder)</h3>
      <p>
        Hold this device near the emitter and press Listen. Your
        microphone will be used briefly to receive an inaudible tone.
      </p>
      <div style={{ margin: '12px 0' }}>
        <button type="button" onClick={begin} disabled={stage === 'listening' || stage === 'claiming'}>
          Start listening
        </button>{' '}
        <button type="button" onClick={stop}>Cancel</button>
      </div>
      <Status label="Stage" value={stage} />
      {sessionId ? <Status label="Session" value={sessionId} /> : null}
      {sas ? <Status label="SAS (should match emitter)" value={sas} /> : null}
      {error ? <div style={{ color: 'crimson' }}>{error}</div> : null}
    </div>
  );
}

export default function UltrasonicPair() {
  const [mode, setMode] = useState('emit');
  const modes = useMemo(() => ([
    { value: 'emit', label: 'Emit (I have the account)' },
    { value: 'listen', label: 'Listen (I want to join)' },
  ]), []);

  return (
    <div style={{ maxWidth: 720, margin: '24px auto', padding: 16 }}>
      <h2>Ultrasonic Device Pairing</h2>
      <p style={{ color: '#555' }}>
        Pair two devices over inaudible audio. Each side sees a 6-digit
        SAS code; read it aloud to confirm both devices agree before
        proceeding.
      </p>
      <div style={{ margin: '16px 0' }}>
        {modes.map((m) => (
          <label key={m.value} style={{ marginRight: 16 }}>
            <input
              type="radio"
              name="mode"
              value={m.value}
              checked={mode === m.value}
              onChange={(e) => setMode(e.target.value)}
            />{' '}
            {m.label}
          </label>
        ))}
      </div>
      {mode === 'emit' ? <EmitMode /> : <ListenMode />}
    </div>
  );
}
