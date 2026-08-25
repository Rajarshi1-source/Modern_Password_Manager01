/**
 * Vault duress (decoy password) setup.
 *
 * Configures the decoy slot of the hidden-vault unlock envelope
 * (`../../services/hiddenVault/unlockEnvelopeStore.js`) — see
 * docs/vault-unlock-envelope-integration-plan.md §3.6.
 *
 * Deliberately NOT part of `VaultUnlockModal`: putting a "decoy password"
 * field on the unlock form itself would advertise the feature's existence to
 * anyone who coerces the user into opening the app. This is a separate,
 * opt-in settings page instead.
 *
 * SCOPE: only meaningful for the vault-password (OAuth) unlock path that
 * `VaultUnlockModal` owns. Password-login users unlock a different way and
 * are out of scope here — see the integration plan §7.
 *
 * LIMITATION, stated plainly rather than implied: the unlock MECHANISM is
 * genuinely indistinguishable (same endpoint, same request size, same
 * constant-time slot check — see `unlockEnvelopeStore.open`). What is NOT
 * solved here is the vault CONTENTS: `/api/vault/` returns one shared item
 * list for the account regardless of which slot's key unlocked the session,
 * so a decoy unlock currently shows the same items as the real vault, each
 * failing to decrypt under the decoy key. That is a materially different,
 * larger problem (populating or filtering a believable decoy vault) and is
 * intentionally not attempted here — see the integration plan §7. Do not
 * remove or soften this notice without solving that problem first.
 */

import React, { useMemo, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as unlockEnvelopeStore from '../../services/hiddenVault/unlockEnvelopeStore';
import { WrongPasswordError } from '../../services/hiddenVault/hiddenVaultEnvelope';
import { registerSignalToken } from '../../services/duressSignalService';

const panelStyle = {
  maxWidth: 640,
  margin: '2rem auto',
  padding: '1.5rem 1.75rem',
  background: '#ffffff',
  border: '1px solid #e1e4ea',
  borderRadius: 10,
  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
  color: '#1f2937',
};

const noticeStyle = {
  background: '#fffbeb',
  border: '1px solid #fcd34d',
  borderRadius: 8,
  padding: '0.75rem 1rem',
  fontSize: 13,
  color: '#92400e',
  margin: '1rem 0',
  lineHeight: 1.5,
};

const inputStyle = {
  width: '100%',
  padding: '0.45rem 0.65rem',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 14,
  fontFamily: 'inherit',
  marginTop: 4,
};

const buttonPrimary = {
  background: '#7B68EE',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '0.55rem 1.1rem',
  fontWeight: 600,
  cursor: 'pointer',
};

const errorStyle = {
  color: '#b91c1c',
  fontSize: 13,
  marginTop: '0.5rem',
};

const successStyle = {
  color: '#15803d',
  fontSize: 13,
  marginTop: '0.5rem',
};

const MIN_LENGTH = 12;

const VaultDuressSetup = () => {
  const { isAuthenticated, user, getAccessToken } = useAuth();
  const userId = user?.id ?? user?.email ?? null;

  const envelopeReady = useMemo(
    () => Boolean(userId) && unlockEnvelopeStore.hasEnvelope(userId),
    [userId]
  );

  const [vaultPassword, setVaultPassword] = useState('');
  const [decoyPassword, setDecoyPassword] = useState('');
  const [decoyConfirm, setDecoyConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  if (!isAuthenticated) {
    return (
      <div style={panelStyle}>
        <p>Sign in to configure duress protection for your vault.</p>
      </div>
    );
  }

  if (!envelopeReady) {
    return (
      <div style={panelStyle}>
        <h2>Vault duress protection</h2>
        <p style={{ color: '#6b7280' }}>
          This unlocks with your vault password (the one set up for social
          sign-in accounts). You haven&apos;t created one yet — open the vault
          from the main app first, which will prompt you to set it up, then
          come back here.
        </p>
      </div>
    );
  }

  const resetForm = () => {
    setVaultPassword('');
    setDecoyPassword('');
    setDecoyConfirm('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);

    if (!vaultPassword || !decoyPassword) {
      setError('Both your current vault password and a new decoy password are required.');
      return;
    }
    if (decoyPassword.length < MIN_LENGTH) {
      setError(`Decoy password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (decoyPassword !== decoyConfirm) {
      setError('Decoy passwords do not match.');
      return;
    }
    if (decoyPassword === vaultPassword) {
      setError('Decoy password must be different from your real vault password.');
      return;
    }

    setBusy(true);
    try {
      // Save the re-encoded blob FIRST, register the alarm token only after
      // it succeeds -- registering first and having the encode/save fail
      // would deactivate the user's previous signal (if any) and leave the
      // new token orphaned server-side with no envelope anywhere that
      // actually releases it. Same ordering bug, same fix, as
      // StegoVaultDashboard.onEmbed (docs/privacy-features-gap-remediation-plan.md §10.3).
      const { duressToken } = await unlockEnvelopeStore.setDecoySlot({
        userId,
        vaultPassword,
        decoyPassword,
      });
      await registerSignalToken(getAccessToken(), duressToken);
      resetForm();
      setSuccess(true);
    } catch (err) {
      if (err instanceof WrongPasswordError) {
        setError('Incorrect vault password.');
      } else {
        setError(err?.message || 'Failed to set up the decoy password.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={panelStyle}>
      <h2>Vault duress protection</h2>
      <p style={{ color: '#6b7280' }}>
        Set up a second password for your vault. Entering it instead of your
        real password opens a separate, empty decoy vault and silently alerts
        your configured contacts — the app behaves identically either way, so
        there is nothing on screen to give it away.
      </p>

      <div style={noticeStyle}>
        <strong>Know the limits:</strong> the unlock itself is indistinguishable,
        but this does not yet build out believable decoy contents — a decoy
        unlock currently shows your real vault&apos;s item list with each entry
        failing to open, not a plausible empty or curated vault. Do not rely on
        this alone if that visual difference matters for your situation.
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="duress-vault-password">Current vault password</label>
          <input
            id="duress-vault-password"
            type="password"
            autoComplete="current-password"
            style={inputStyle}
            value={vaultPassword}
            onChange={(e) => setVaultPassword(e.target.value)}
            disabled={busy}
            required
          />
        </div>

        <div className="form-group" style={{ marginTop: '0.75rem' }}>
          <label htmlFor="duress-decoy-password">New decoy password</label>
          <input
            id="duress-decoy-password"
            type="password"
            autoComplete="new-password"
            style={inputStyle}
            value={decoyPassword}
            onChange={(e) => setDecoyPassword(e.target.value)}
            disabled={busy}
            required
          />
        </div>

        <div className="form-group" style={{ marginTop: '0.75rem' }}>
          <label htmlFor="duress-decoy-confirm">Confirm decoy password</label>
          <input
            id="duress-decoy-confirm"
            type="password"
            autoComplete="new-password"
            style={inputStyle}
            value={decoyConfirm}
            onChange={(e) => setDecoyConfirm(e.target.value)}
            disabled={busy}
            required
          />
        </div>

        {error && (
          <div role="alert" style={errorStyle}>{error}</div>
        )}
        {success && (
          <div role="status" style={successStyle}>
            Decoy password saved. It will open the decoy vault and silently
            alert your contacts the next time it is used to unlock.
          </div>
        )}

        <div style={{ marginTop: '1.25rem' }}>
          <button type="submit" style={buttonPrimary} disabled={busy}>
            {busy ? 'Saving…' : 'Save decoy password'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default VaultDuressSetup;
