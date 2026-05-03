/**
 * Tier-3 (Self-Time-Locked) ENROLLMENT page.
 *
 * Flow:
 *   1. Re-prompt for master password.
 *   2. Generate `time_seed` (32 random bytes) in the browser.
 *   3. Wrap the DEK under a KEK derived from `time_seed` and POST
 *      it as a `time_locked` recovery factor.
 *   4. Split `time_seed` Shamir 2-of-2; download halfA as a `.dlrec`
 *      JSON file the user keeps offline; POST halfB to the server.
 *   5. The user must confirm they downloaded the file before we
 *      consider enrollment complete.
 *
 * ZK invariant: `time_seed` is generated client-side, used as the
 * Argon2 secret, and split before we send anything. The server never
 * sees `time_seed` itself, only the wrapped DEK and an opaque half.
 */
import React, { useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { split2of2, _b64 } from '../../../services/shamir2of2';

const DLREC_VERSION = 'dlrec-1';

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

function downloadDlrecFile({ username, halfA }) {
  const payload = {
    v: DLREC_VERSION,
    username,
    halfA: _b64.encode(halfA),
    createdAt: new Date().toISOString(),
    warning:
      'Keep this file offline. Combined with your account it is the only way ' +
      'to self-recover after the time-lock delay. If anyone else has both this ' +
      'file and access to your account email, they can recover your vault.',
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `vault-recovery-${username}-${new Date().toISOString().slice(0, 10)}.dlrec`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function TimeLockedEnroll({ username, onSuccess }) {
  const [masterPassword, setMasterPassword] = useState('');
  const [phase, setPhase] = useState('await-password'); // -> 'downloaded' -> 'done'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleEnroll() {
    if (!masterPassword) {
      setError('Master password required.');
      return;
    }
    if (!username) {
      setError('Username unknown — sign in first.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const timeSeed = window.crypto.getRandomValues(new Uint8Array(32));
      const seedHex = bytesToHex(timeSeed);

      // (a) Wrap the DEK under a KEK derived from the seed.
      await sessionVaultCryptoV3.enrollRecoveryFactor({
        factorType: 'time_locked',
        secret: seedHex,
        masterPassword,
      });

      // (b) Split the seed; user keeps halfA offline, server keeps halfB.
      const { halfA, halfB } = split2of2(timeSeed);

      // (c) POST halfB BEFORE downloading halfA — if the server call
      //     fails we don't want the user to think they have a working
      //     `.dlrec` when no row exists server-side yet.
      await recoveryFactorService.enrollTimeLock({
        serverHalf: _b64.encode(halfB),
        halfMetadata: { v: DLREC_VERSION },
      });

      // (d) Download halfA. (No way to know in-script whether the
      //     download dialog actually saved — we ask the user to
      //     confirm before considering enrollment complete.)
      downloadDlrecFile({ username, halfA });

      setPhase('downloaded');
    } catch (err) {
      setError(err?.message || 'Enrollment failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-password') {
    return (
      <section data-testid="time-locked-enroll">
        <h1>Set up Self-Recovery (Time-Locked)</h1>
        <p>
          Time-locked recovery lets you regain access to your vault after a delay
          (typically 7 days) without recovery keys or guardians. We will give you a small
          recovery file to keep offline. Combined with your account it can recover your
          vault — but only after the delay window, during which you will get warning
          emails so you can cancel an unauthorized attempt.
        </p>
        <label>
          Master password
          <input
            type="password"
            name="masterPassword"
            value={masterPassword}
            onChange={(e) => setMasterPassword(e.target.value)}
            data-testid="tl-enroll-master-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleEnroll}
          disabled={busy}
          data-testid="tl-enroll-generate"
        >
          {busy ? 'Generating…' : 'Generate Recovery File'}
        </button>
      </section>
    );
  }

  if (phase === 'downloaded') {
    return (
      <section data-testid="time-locked-enroll">
        <h1>Recovery file generated</h1>
        <p>
          Your <code>.dlrec</code> file should have downloaded just now. Move it to a
          location only you can reach (USB drive, encrypted backup, etc.) — not your
          regular synced documents folder.
        </p>
        <button
          type="button"
          onClick={() => {
            setPhase('done');
            if (onSuccess) onSuccess();
          }}
          data-testid="tl-enroll-confirm"
        >
          I have moved the file offline
        </button>
      </section>
    );
  }

  return (
    <section data-testid="time-locked-enroll">
      <h1>Time-locked recovery enabled</h1>
      <p data-testid="tl-enroll-success">
        You can now self-recover after the time-lock delay using the file you saved.
      </p>
    </section>
  );
}
