/**
 * Tier-1 (Printable Recovery Key) enrollment page.
 *
 * Flow:
 *   1. Re-prompt for master password (need extractable DEK).
 *   2. Generate a 26-char recovery key in the browser
 *      (crypto.getRandomValues). Never leaves the device.
 *   3. Show the key once, with copy + download-as-.txt affordances.
 *   4. Require an explicit confirmation phrase before enrollment.
 *   5. enrollRecoveryFactor({factorType:'recovery_key', secret:key,...})
 *      wraps the DEK under a KEK derived from the key and POSTs the
 *      ciphertext to the server.
 *
 * ZK invariant: the recovery key is generated client-side and used as
 * the Argon2 secret. It is NEVER sent to the server.
 */
import React, { useMemo, useState } from 'react';
import sessionVaultCryptoV3 from '../../../services/sessionVaultCryptoV3';
import { generateRecoveryKey } from './generateRecoveryKey';

const CONFIRM_PHRASE = 'I have saved this key';

function downloadKeyAsText(key) {
  const blob = new Blob(
    [
      `Vault Recovery Key\n\n${key}\n\n` +
        'Keep this key offline and somewhere only you can reach.\n' +
        'Anyone holding this key can recover access to your vault.\n',
    ],
    { type: 'text/plain' },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `vault-recovery-key-${new Date().toISOString().slice(0, 10)}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function RecoveryKeyEnrollV2({ onSuccess }) {
  const [masterPassword, setMasterPassword] = useState('');
  const [phase, setPhase] = useState('await-password'); // -> 'show-key' -> 'enrolled'
  const [confirmInput, setConfirmInput] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const recoveryKey = useMemo(
    () => (phase === 'show-key' || phase === 'enrolled' ? generateRecoveryKey() : ''),
    // Generated exactly once when we transition into show-key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [phase === 'show-key'],
  );

  async function handleStart() {
    if (!masterPassword) {
      setError('Master password required.');
      return;
    }
    setError('');
    setPhase('show-key');
  }

  async function handleEnroll() {
    if (confirmInput.trim() !== CONFIRM_PHRASE) {
      setError(`Type "${CONFIRM_PHRASE}" exactly to continue.`);
      return;
    }
    setBusy(true);
    setError('');
    try {
      await sessionVaultCryptoV3.enrollRecoveryFactor({
        factorType: 'recovery_key',
        secret: recoveryKey,
        masterPassword,
      });
      setPhase('enrolled');
      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err?.message || 'Enrollment failed.');
    } finally {
      setBusy(false);
    }
  }

  if (phase === 'await-password') {
    return (
      <section data-testid="recovery-key-enroll-v2">
        <h1>Set up a Recovery Key</h1>
        <p>
          A recovery key lets you regain access to your vault if you forget your master
          password. The key is generated on this device and never sent to the server.
        </p>
        <label>
          Master password
          <input
            type="password"
            name="masterPassword"
            value={masterPassword}
            onChange={(e) => setMasterPassword(e.target.value)}
            data-testid="rk-enroll-master-password"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="button" onClick={handleStart} data-testid="rk-enroll-start">
          Generate
        </button>
      </section>
    );
  }

  if (phase === 'show-key') {
    return (
      <section data-testid="recovery-key-enroll-v2">
        <h1>Your Recovery Key</h1>
        <p>This key will not be shown again. Save it somewhere only you can reach.</p>
        <pre data-testid="recovery-key-display">{recoveryKey}</pre>
        <div>
          <button
            type="button"
            onClick={() => navigator.clipboard?.writeText(recoveryKey)}
            data-testid="rk-copy"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={() => downloadKeyAsText(recoveryKey)}
            data-testid="rk-download"
          >
            Download .txt
          </button>
        </div>
        <label>
          Type <strong>{CONFIRM_PHRASE}</strong> to confirm you saved it:
          <input
            type="text"
            name="confirmPhrase"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            data-testid="rk-confirm-phrase"
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          type="button"
          onClick={handleEnroll}
          disabled={busy || confirmInput.trim() !== CONFIRM_PHRASE}
          data-testid="rk-enroll-save"
        >
          {busy ? 'Saving…' : 'Save Recovery Key'}
        </button>
      </section>
    );
  }

  return (
    <section data-testid="recovery-key-enroll-v2">
      <h1>Recovery key saved</h1>
      <p data-testid="rk-enroll-success">
        Your recovery key is now active. Keep the copy you saved somewhere only you can reach.
      </p>
    </section>
  );
}
