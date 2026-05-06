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
import React, { useRef, useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import recoveryFactorService from '../../../services/recoveryFactorService';
import { split2of2, _b64 } from '../../../services/shamir2of2';

const DLREC_VERSION = 'dlrec-1';

/**
 * Render a `Uint8Array` as a lowercase hex string. Used to format the
 * recovery seed before passing it to the Argon2id KDF, which expects
 * a string secret rather than raw bytes.
 *
 * @param {Uint8Array} bytes
 * @returns {string}
 */
function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Trigger a browser download of the user-facing `.dlrec` recovery
 * file containing the user's Shamir half. Generated entirely in the
 * browser; never uploaded.
 *
 * @param {object} args
 * @param {string} args.username  - Account the file is bound to.
 * @param {Uint8Array} args.halfA - The user's share of the recovery seed.
 */
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
  // Defer revocation to the next macrotask. Synchronous
  // URL.revokeObjectURL() right after a.click() is documented to
  // suppress the download in Firefox (Mozilla bug 1282407): the
  // browser hasn't fetched the blob yet, the URL is invalidated,
  // and the download silently fails. setTimeout(..., 0) lets the
  // browser pick up the blob first. The .dlrec file is the user's
  // ONLY offline share of the recovery seed for this enrollment —
  // we cannot afford a silent download failure here.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/**
 * Tier-3 recovery enrollment page. The component is a small state
 * machine across three phases:
 *
 *   await-password → user re-prompts for the master password (we need
 *                    it to extract the DEK from the master-wrapped row
 *                    before we can re-wrap it under the new seed).
 *   downloaded     → server half stored, factor row created, `.dlrec`
 *                    file downloaded — user must confirm they moved
 *                    the file offline before we consider enrollment
 *                    done.
 *   done           → terminal success state.
 *
 * @param {object} props
 * @param {string} props.username         - Authenticated user's username.
 * @param {() => void} [props.onSuccess]  - Optional callback for navigation.
 */
export default function TimeLockedEnroll({ username, onSuccess }) {
  const [masterPassword, setMasterPassword] = useState('');
  const [phase, setPhase] = useState('await-password'); // -> 'downloaded' -> 'done'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // Persist the user's local Shamir half across renders so the
  // 'downloaded' screen can offer a "Download again" affordance.
  // Browsers commonly block programmatic downloads triggered without
  // an explicit user gesture; if the first download was suppressed,
  // without a re-download path the user would have to re-run the full
  // enrollment (which produces a NEW factor row and orphans the
  // first). Held in a ref because there is nothing render-dependent
  // here — and refs avoid the React-warning about storing
  // non-serialisable objects in state.
  const halfARef = useRef(null);

  /**
   * Run the full enroll sequence: split a fresh seed, persist the
   * server half, wrap the DEK under a KEK from the seed, download
   * the `.dlrec` file. See the inline numbered comments for the
   * order-of-operations rationale (orphan-row avoidance on partial
   * failure).
   */
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

      // (a) Split the seed locally before any server call so we
      //     fail closed if either step fails.
      const { halfA, halfB } = split2of2(timeSeed);

      // (b) Persist the SERVER half FIRST. The order matters: if
      //     this call fails, we have not yet created any
      //     RecoveryWrappedDEK row, so there is nothing to clean up.
      //     If we did this in the opposite order and step (c) failed,
      //     we'd leave behind an orphan wdek row pointing at a seed
      //     that never had a server-stored half. The user would
      //     retry, get a NEW row, and the orphan would linger as
      //     accidental factor-list noise.
      await recoveryFactorService.enrollTimeLock({
        serverHalf: _b64.encode(halfB),
        halfMetadata: { v: DLREC_VERSION },
      });

      // (c) Wrap the DEK under a KEK derived from the seed and POST
      //     it as the time_locked recovery factor. If THIS fails the
      //     user has a server half but no factor row; the next retry
      //     overwrites the server half (TimeLockedEnrollView's
      //     deactivate-then-create logic) and adds a fresh factor row
      //     for the new seed. The retry path is clean.
      await sessionVaultCryptoV3.enrollRecoveryFactor({
        factorType: 'time_locked',
        secret: seedHex,
        masterPassword,
      });

      // (d) Download halfA. (No way to know in-script whether the
      //     download dialog actually saved — we ask the user to
      //     confirm before considering enrollment complete, and we
      //     stash halfA in a ref so the "Download again" button on
      //     the next phase can re-trigger the download without
      //     reissuing the enroll calls in (b)/(c).)
      halfARef.current = halfA;
      downloadDlrecFile({ username, halfA });

      // Zero the master password out of React state now that we're
      // past the point where we needed it. React still keeps a
      // reference to the previous value in its update history during
      // the same render — that's unavoidable — but at least the
      // controlled input no longer holds it on the next render and a
      // user who walks away from the screen at the 'downloaded' or
      // 'done' phase isn't leaving the master password in a DOM
      // input value attribute.
      setMasterPassword('');
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
        <p>
          If your browser blocked the download, use <em>Download again</em> below — this
          re-triggers the same file (no new enrollment, no new factor row).
        </p>
        <div>
          <button
            type="button"
            onClick={() => {
              if (halfARef.current) {
                downloadDlrecFile({ username, halfA: halfARef.current });
              }
            }}
            data-testid="tl-enroll-redownload"
            disabled={!halfARef.current}
          >
            Download again
          </button>
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
        </div>
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
