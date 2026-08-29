import React, { useState, useMemo } from 'react';
import Modal from '../../Modal.jsx';
import sessionVaultCrypto from '../../services/sessionVaultCrypto';
import * as unlockEnvelopeStore from '../../services/hiddenVault/unlockEnvelopeStore';
import { WrongPasswordError } from '../../services/hiddenVault/hiddenVaultEnvelope';
import { reportUnlock, reportUnlockForSlot } from '../../services/duressSignalService';

/**
 * VaultUnlockModal
 *
 * For OAuth (social) logins the user has no master password, so we can't
 * derive the vault encryption key directly. This modal unlocks via the
 * hidden-vault envelope (`../../services/hiddenVault/unlockEnvelopeStore.js`)
 * -- see docs/vault-unlock-envelope-integration-plan.md for the full design.
 *
 * User-visible modes (this is all `mode` below exposes to the UI):
 *   - "setup"  -> no vault key of any kind yet. Creates the legacy
 *                 wrapped-DEK record (unchanged) AND provisions the new
 *                 envelope's real slot with that SAME DEK, so future
 *                 unlocks go through the envelope while old items stay
 *                 readable either way.
 *   - "unlock" -> a vault key already exists. Internally this covers two
 *                 different code paths that must look and feel identical to
 *                 the user (see `internalMode` below): a user who already
 *                 has an envelope decodes through it directly (and may be
 *                 opening either the real vault or, indistinguishably, a
 *                 configured decoy); a user who only has the legacy wrapped
 *                 record is unlocked through it as always, then upgraded to
 *                 an envelope transparently in the background so the NEXT
 *                 unlock goes through the envelope too. A failed upgrade
 *                 never fails the unlock itself.
 *
 * Indistinguishability (docs/vault-unlock-envelope-integration-plan.md §3.5):
 * every successful path here -- setup, envelope-real, envelope-decoy, and
 * upgrade -- ends by reporting to `duressSignalService`, fire-and-forget, so
 * the presence/timing of that network call never reveals which one ran.
 * Wrong-password errors from every path surface the IDENTICAL string for the
 * same reason -- never leak which slot (or which code path) rejected it.
 *
 * The component is dumb about auth state — parents decide when to show it
 * and supply `getAccessToken` for the duress report.
 */
const VaultUnlockModal = ({ isOpen, userId, getAccessToken, onUnlocked, onClose }) => {
  const { mode, internalMode } = useMemo(() => {
    if (!userId) return { mode: 'setup', internalMode: 'setup' };
    if (unlockEnvelopeStore.hasEnvelope(userId)) {
      return { mode: 'unlock', internalMode: 'envelope' };
    }
    if (sessionVaultCrypto.hasWrappedKey(userId)) {
      return { mode: 'unlock', internalMode: 'upgrade' };
    }
    return { mode: 'setup', internalMode: 'setup' };
    // Re-evaluate every time the modal opens so a fresh login picks up the
    // current storage state rather than a stale mode from a previous render.
  }, [userId, isOpen]);

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const resetLocal = () => {
    setPassword('');
    setConfirm('');
    setError('');
    setBusy(false);
  };

  // Fire-and-forget by design (§3.5): awaiting this would make a duress
  // unlock measurably slower than a normal one whenever the token and noise
  // paths differ in server-side cost, which is exactly the timing tell this
  // report exists to avoid creating. `reportUnlock` itself never throws (see
  // its own docstring), so nothing here needs to catch.
  const reportNoise = () => {
    reportUnlock(getAccessToken?.(), null);
  };

  const runSetup = async () => {
    await sessionVaultCrypto.setupVaultPassword(password, userId);
    try {
      const dekBytes = await sessionVaultCrypto.exportSessionDekRaw();
      const saltB64 = sessionVaultCrypto.getOrCreateUserSalt(userId);
      await unlockEnvelopeStore.provision({ userId, vaultPassword: password, dekBytes, saltB64 });
    } catch (envelopeErr) {
      // Non-fatal: the legacy wrapped-DEK record above is already live and
      // fully usable. A user who hits this simply stays on the "upgrade"
      // path (see runUpgrade) next time and gets the envelope then instead.
      console.warn('VaultUnlockModal: envelope provisioning failed during setup, will retry on next unlock.', envelopeErr);
    }
    reportNoise();
  };

  // `replaceExisting` is passed ONLY by the corrupt-envelope fallback below.
  // In the ordinary upgrade path no envelope exists (that is what selected
  // this mode), so provision's default refusal is correct and protects a
  // decoy another tab may have configured since `internalMode` was computed.
  const runUpgrade = async ({ replaceExisting = false } = {}) => {
    // The real unlock. If this throws, nothing below runs and the user sees
    // the standard "Incorrect vault password." error.
    await sessionVaultCrypto.unlockWithVaultPassword(password, userId);
    try {
      const { dekBytes, saltB64 } = await sessionVaultCrypto.exportWrappedDekRaw(password, userId);
      await unlockEnvelopeStore.provision({
        userId, vaultPassword: password, dekBytes, saltB64, replaceExisting,
      });
    } catch (envelopeErr) {
      // See runSetup — the unlock above already succeeded; failing the
      // user's login over an opportunistic upgrade would be a worse outcome
      // than simply retrying the upgrade on their next unlock.
      console.warn('VaultUnlockModal: envelope upgrade failed after unlock, will retry next time.', envelopeErr);
    }
    reportNoise();
  };

  const runEnvelopeUnlock = async () => {
    // Reserved BEFORE the slow step below (unlockEnvelopeStore.open() runs
    // two Argon2id derivations, §3.7 -- can take over a second), not after.
    // See sessionVaultCrypto.reserveSessionGeneration's docstring: capturing
    // this only once open() has already resolved would be blind to a
    // logout or a newer unlock that landed during that await, and could
    // resurrect a session nobody is in anymore.
    const generation = sessionVaultCrypto.reserveSessionGeneration();
    let opened;
    try {
      opened = await unlockEnvelopeStore.open({ userId, password });
    } catch (err) {
      if (err instanceof WrongPasswordError) {
        // Never surface hiddenVaultEnvelope's own message text here — see
        // the module docstring's indistinguishability note. Same string as
        // `sessionVaultCrypto.unlockWithVaultPassword`'s wrong-password path.
        throw new Error('Incorrect vault password.');
      }
      // Envelope itself is unusable (bad base64, MalformedBlobError, any
      // other decode-time failure) -- happened BEFORE installRawDek ever
      // ran, so it is unrelated to session timing. Tag it so the wrapper
      // below knows a legacy fallback is the right response to THIS
      // failure specifically, and not to the different failure below.
      err.envelopeUnusable = true;
      throw err;
    }
    const { slotIndex, dekBytes, saltB64, duressToken } = opened;
    // No `envelopeUnusable` tag on a failure here: the envelope decoded
    // fine, so a throw at this point (chiefly the stale-generation guard)
    // must propagate as-is, never trigger the corrupt-envelope fallback.
    // isDecoy = slotIndex !== 0: tells sessionVaultCrypto to refuse new
    // writes for this session, see installRawDek/encryptItem's own comments
    // on why a decoy-session write would otherwise permanently corrupt a
    // row in the real vault.
    await sessionVaultCrypto.installRawDek(dekBytes, saltB64, userId, generation, slotIndex !== 0);
    // Fire-and-forget, per §3.5 — see reportNoise above for why. Deliberately
    // NOT branching on slotIndex here beyond passing it through unchanged:
    // reportUnlockForSlot itself decides real-token-vs-noise from
    // `payloadJson.__duress_signal`, exactly as StegoVaultDashboard does.
    reportUnlockForSlot(getAccessToken?.(), slotIndex, { __duress_signal: duressToken });
  };

  // Only a failure explicitly tagged `envelopeUnusable` (see above — a
  // decode-time failure from unlockEnvelopeStore.open() itself, not a
  // wrong password and not a post-decode failure like the stale-generation
  // guard) triggers the legacy fallback. Falling back on anything else --
  // e.g. a session-superseded error from installRawDek — would be wrong:
  // the envelope was fine, something else already changed the session
  // state while this attempt was in flight, and running runUpgrade() on
  // top of that would just install a second, equally-discarded session
  // instead of correctly abandoning this stale attempt. If the legacy
  // wrapped-DEK record still exists for a genuinely unusable envelope, fall
  // back to it rather than locking the user out of a vault it could still
  // open: runUpgrade()'s own provisioning call overwrites the bad envelope
  // with a fresh, valid one on success, so this also self-heals the
  // corruption rather than just routing around it once.
  const runEnvelopeUnlockWithFallback = async () => {
    try {
      await runEnvelopeUnlock();
    } catch (err) {
      if (!err.envelopeUnusable || !sessionVaultCrypto.hasWrappedKey(userId)) {
        throw err;
      }
      console.warn('VaultUnlockModal: stored envelope is unusable, falling back to the legacy unlock path.', err);
      // The stored blob exists but cannot be decoded, so there is no decoy
      // left for provision's default refusal to protect -- replacing it is
      // the self-heal (§9.1), and refusing here would strand the user.
      await runUpgrade({ replaceExisting: true });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!password) {
      setError('Please enter your vault password.');
      return;
    }

    if (mode === 'setup') {
      if (password.length < 12) {
        setError('Vault password must be at least 12 characters.');
        return;
      }
      if (password !== confirm) {
        setError('Passwords do not match.');
        return;
      }
    }

    setBusy(true);
    try {
      if (internalMode === 'setup') {
        await runSetup();
      } else if (internalMode === 'envelope') {
        await runEnvelopeUnlockWithFallback();
      } else {
        await runUpgrade();
      }
      resetLocal();
      onUnlocked?.();
    } catch (err) {
      setError(err?.message || 'Failed to unlock the vault.');
    } finally {
      setBusy(false);
    }
  };

  const handleClose = () => {
    resetLocal();
    onClose?.();
  };

  const title = mode === 'setup' ? 'Set up your vault password' : 'Unlock your vault';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={title} size="small">
      <form onSubmit={handleSubmit}>
        <p style={{ marginBottom: '12px', lineHeight: 1.4 }}>
          {mode === 'setup' ? (
            <>
              You signed in with a social provider, which does not give the app a
              master password. Choose a <strong>vault password</strong> to protect
              your entries. This password never leaves your device — we store only
              a wrapped copy of the encryption key.
            </>
          ) : (
            <>
              Enter the vault password you set up previously. This password is
              different from your social sign-in and is required to decrypt your
              saved entries.
            </>
          )}
        </p>

        <div className="form-group">
          <label htmlFor="vault-password">
            {mode === 'setup' ? 'New vault password' : 'Vault password'}
          </label>
          <input
            id="vault-password"
            type="password"
            autoComplete={mode === 'setup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoFocus
            required
          />
        </div>

        {mode === 'setup' && (
          <div className="form-group">
            <label htmlFor="vault-password-confirm">Confirm vault password</label>
            <input
              id="vault-password-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={busy}
              required
            />
          </div>
        )}

        {error && (
          <div
            className="error-message"
            role="alert"
            style={{ marginTop: '8px', color: 'var(--danger)' }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            display: 'flex',
            gap: '8px',
            justifyContent: 'flex-end',
            marginTop: '16px',
          }}
        >
          <button
            type="button"
            className="text-btn"
            onClick={handleClose}
            disabled={busy}
          >
            Later
          </button>
          <button type="submit" className="submit-btn" disabled={busy}>
            {busy
              ? (mode === 'setup' ? 'Setting up…' : 'Unlocking…')
              : (mode === 'setup' ? 'Create vault password' : 'Unlock')}
          </button>
        </div>
      </form>
    </Modal>
  );
};

export default VaultUnlockModal;
