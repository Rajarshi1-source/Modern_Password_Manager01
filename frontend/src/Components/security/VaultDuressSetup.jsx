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
 * solved here is the vault CONTENTS. `/api/vault/` returns one shared item
 * list for the account regardless of which slot's key unlocked the session,
 * so every DISPLAY surface now gates on `isDecoySession()` and renders an
 * EMPTY vault during a decoy session (`useDisplaySafeItems` in App.jsx) —
 * chosen because the alternative, rendering the real list with every row
 * failing to decrypt, outs the decoy instantly. An empty vault is still not
 * a BELIEVABLE one: anyone who knows the account is not empty may find it
 * suspicious. Populating a plausible decoy is a materially larger problem
 * and is intentionally not attempted here — see the integration plan §7.
 * Do not remove or soften this notice without solving that problem first.
 */

import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import * as unlockEnvelopeStore from '../../services/hiddenVault/unlockEnvelopeStore';
import { WrongPasswordError } from '../../services/hiddenVault/hiddenVaultEnvelope';
import { registerSignalToken } from '../../services/duressSignalService';
import sessionVaultCrypto from '../../services/sessionVaultCrypto';

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

  // Read live, not memoized, for the same reason the session gate below is:
  // `hasEnvelope` reads localStorage, which another tab -- or this tab's own
  // unlock modal, which provisions the envelope -- can populate while this
  // screen stays mounted. A memo keyed on `userId` alone keeps answering
  // "you haven't created one yet" until a remount, so the re-render nudge
  // below would repaint a stale answer.
  const envelopeReady = Boolean(userId) && unlockEnvelopeStore.hasEnvelope(userId);

  const [vaultPassword, setVaultPassword] = useState('');
  const [decoyPassword, setDecoyPassword] = useState('');
  const [decoyConfirm, setDecoyConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Recovery form state: independent of the setup form above. Deliberately
  // does NOT hold the duress token itself anywhere -- not in state, not in
  // storage. If setDecoySlot() saves a new decoy token but
  // registerSignalToken() then fails, the token is not lost: it already
  // lives inside the saved envelope's decoy slot. Recovery re-derives it by
  // asking the user to type the decoy password again and re-opening the
  // envelope with it (unlockEnvelopeStore.open), the same way a real decoy
  // unlock would. This also means recovery survives a reload or navigating
  // away -- nothing about it depends on this component's session state --
  // and needs no new persistent storage of a value that would otherwise be
  // plaintext secret material at rest.
  const [recoveryPassword, setRecoveryPassword] = useState('');
  // The real vault password, required to operate the recovery form at all --
  // see handleRecoverRegistration's gate for why. Held in state only for the
  // duration of the form, exactly like the setup form's own field.
  const [recoveryVaultPassword, setRecoveryVaultPassword] = useState('');
  // A re-render nudge ONLY. The session state itself is deliberately NOT
  // cached here: `handleLockVault` clears the session key without dispatching
  // any DOM event (it sets React state inside VaultContext instead), so the
  // manual, inactivity and cross-tab lock paths would all leave a cached copy
  // stale and this screen showing its forms after the vault had locked.
  // Enumerating lock events and hoping the list stays complete is the same
  // mistake in a new place; the gate below reads the live value instead, and
  // `sessionVaultCrypto.hasSessionKey()` is called again inside both submit
  // handlers so the security boundary never depends on a render happening.
  const [, setSessionTick] = useState(0);
  useEffect(() => {
    const nudge = () => setSessionTick((n) => n + 1);
    window.addEventListener('vault:updated', nudge);
    // Cross-tab lock writes `vaultLockState`; this only repaints the panel,
    // it is not what makes the gate correct.
    window.addEventListener('storage', nudge);
    return () => {
      window.removeEventListener('vault:updated', nudge);
      window.removeEventListener('storage', nudge);
    };
  }, []);

  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [recoveryError, setRecoveryError] = useState('');
  const [recoverySuccess, setRecoverySuccess] = useState(false);

  if (!isAuthenticated) {
    return (
      <div style={panelStyle}>
        <p>Sign in to configure duress protection for your vault.</p>
      </div>
    );
  }

  // A DECOY session must never reach the forms below, and the reason is not
  // the one an earlier round rejected this for.
  //
  // In a REAL session, "Incorrect vault password." for a decoy password is
  // fine: it is identical to what a garbage password produces (§21.1), so it
  // identifies nothing, and revealing that some OTHER string IS the real
  // password is inherent to any credential.
  //
  // In a DECOY session it is fatal. The coercer has just watched password D
  // unlock this vault. If they open this screen and type D, the app answers
  // "Incorrect vault password." -- a direct contradiction of what they just
  // saw with their own eyes, and one no innocent explanation covers. That
  // outs the decoy far more decisively than the empty item list does.
  //
  // Rendering a neutral panel with NO password fields is what actually closes
  // it: there is nothing to submit, so there is no outcome to contradict and
  // no request to observe. (That also answers the network-shape concern the
  // finding was originally filed under, in the only way that is coherent --
  // a decoy session makes no registration request because it makes no
  // submission at all.) Deliberately NOT reusing the "you haven't created a
  // vault password yet" copy below: that would be its own contradiction for
  // someone who just unlocked with one.
  if (sessionVaultCrypto.isDecoySession()) {
    return (
      <div style={panelStyle}>
        <h2>Vault duress protection</h2>
        <p style={{ color: '#6b7280' }}>
          This isn&apos;t available right now. Please try again later.
        </p>
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

  // A LOCKED vault must not reach the forms either, and this is a distinct
  // hole from the decoy gate above rather than a stricter version of it.
  //
  // `isDecoySession()` answers "is the CURRENT session a decoy". While the
  // vault is locked there IS no session, so it answers false -- and
  // `handleLockVault` calls `clearSessionKey()`, which sets `sessionIsDecoy`
  // back to false, so locking a decoy session turns the gate above OFF. Either
  // way the forms rendered to an operator who has proven nothing.
  //
  // That is a sharper oracle than the one the decoy gate closes. A coercer
  // holding password D, with the vault locked, opens this screen and types D
  // into the current-vault-password field: `setDecoySlot` decodes it to slot 1
  // and raises WrongPasswordError, so the app answers "Incorrect vault
  // password." for a password that visibly unlocks this very vault. The
  // contradiction §23.1 exists to prevent, reachable by visiting this screen
  // BEFORE unlocking instead of after -- or after locking a decoy session.
  //
  // Requiring a live session is what closes it, and it closes it on the same
  // principle §22 used for the recovery form: only the real vault password
  // produces a non-decoy session key, so an operator who passes this gate has
  // already demonstrated the real credential and learns nothing from the
  // verification below. Fails closed -- no session, no forms, no request.
  if (!sessionVaultCrypto.hasSessionKey()) {
    return (
      <div style={panelStyle}>
        <h2>Vault duress protection</h2>
        <p style={{ color: '#6b7280' }}>
          Unlock your vault first, then come back here to configure duress
          protection.
        </p>
      </div>
    );
  }

  const resetForm = () => {
    setVaultPassword('');
    setDecoyPassword('');
    setDecoyConfirm('');
  };

  // Never throws: a registration failure here is recoverable via the
  // "Recover unregistered alarm" section below, not fatal to the setup flow,
  // so it is handled in place rather than propagated to a caller that would
  // just show a dead-end error.
  const finishRegistration = async (token) => {
    try {
      await registerSignalToken(getAccessToken(), token);
      resetForm();
      setSuccess(true);
      setError('');
    } catch {
      setError(
        'Decoy password saved, but the alarm could not be registered -- it will '
        + 'not fire on a decoy unlock until registration succeeds. Use '
        + '"Recover unregistered alarm" below with this same decoy password to '
        + 'retry -- that works even if you reload this page first.'
      );
    }
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

    // Re-check at SUBMIT, not only at render. The render gate above is
    // correct whenever a render happens, but nothing forces one when the
    // vault locks: `handleLockVault` clears the session key and dispatches no
    // DOM event, so an already-mounted copy of this screen can still be
    // showing its forms. This is the check that actually closes the oracle,
    // because reaching it requires a SUBMISSION, and a submission always runs
    // this code. Placed before any envelope call, so nothing observable --
    // no decode, no request, no password-dependent message -- happens first.
    // The message is identical for every password class.
    if (!sessionVaultCrypto.hasSessionKey()) {
      setError('Unlock your vault first, then set up a decoy password.');
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
      const generation = sessionVaultCrypto.currentSessionGeneration();
      const { duressToken } = await unlockEnvelopeStore.setDecoySlot({
        userId,
        vaultPassword,
        decoyPassword,
      });
      // The session that authorised this operation must still be the one in
      // place when it finishes. `setDecoySlot` runs THREE Argon2 derivations,
      // so the vault can lock inside that window (inactivity, manual, or
      // cross-tab -- all `clearSessionKey()`, which bumps the generation),
      // and registering the alarm afterwards would fire an authenticated
      // request for a session that no longer exists.
      //
      // Compared by GENERATION, not by `hasSessionKey()`: a lock followed by
      // any unlock -- including a DECOY unlock -- leaves `hasSessionKey()`
      // true again, so that check would let the continuation run inside a
      // decoy session. The counter moves on every one of those transitions.
      //
      // The blob is already saved by this point and is deliberately left in
      // place: the decoy IS configured, only its token is unregistered, which
      // is exactly the state the recovery form below exists to finish. The
      // message is password-independent, so it classifies nothing.
      if (sessionVaultCrypto.currentSessionGeneration() !== generation) {
        setError('Unlock your vault first, then set up a decoy password.');
        return;
      }
      await finishRegistration(duressToken);
    } catch (err) {
      if (err instanceof WrongPasswordError) {
        // Covers BOTH "that password opens nothing" and "that password opens
        // the decoy slot" -- unlockEnvelopeStore.setDecoySlot raises the same
        // type for each, deliberately, so this screen cannot tell a coercer
        // which of the two they just typed. See that function's own comment.
        setError('Incorrect vault password.');
      } else {
        // Never echo `err.message`: it is where the slot-specific wording
        // used to reach the screen from, and any future service-layer error
        // string would land here unreviewed. Operational faults get one
        // fixed message that says nothing about which password was entered.
        setError('Could not save the decoy password. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  // Re-derives the duress token from the decoy slot itself rather than from
  // any state this component held earlier -- see recoveryPassword's own
  // comment. Works identically whether it is used seconds after a failed
  // registration or days later after this component has remounted many
  // times over.
  const handleRecoverRegistration = async (e) => {
    e.preventDefault();
    setRecoveryError('');
    setRecoverySuccess(false);

    if (!recoveryVaultPassword || !recoveryPassword) {
      setRecoveryError('Both your vault password and your decoy password are required.');
      return;
    }

    // Re-check at SUBMIT, not only at render. The render gate above is
    // correct whenever a render happens, but nothing forces one when the
    // vault locks: `handleLockVault` clears the session key and dispatches no
    // DOM event, so an already-mounted copy of this screen can still be
    // showing its forms. This is the check that actually closes the oracle,
    // because reaching it requires a SUBMISSION, and a submission always runs
    // this code. Placed before any envelope call, so nothing observable --
    // no decode, no request, no password-dependent message -- happens first.
    // The message is identical for every password class.
    if (!sessionVaultCrypto.hasSessionKey()) {
      setRecoveryError('Unlock your vault first, then try the recovery step again.');
      return;
    }


    setRecoveryBusy(true);
    try {
      // Same session-generation binding as the setup form above: this handler
      // awaits two `open()` calls before it registers anything, and a lock (or
      // a decoy unlock) landing in that window must not be followed by an
      // authenticated registration request.
      const generation = sessionVaultCrypto.currentSessionGeneration();
      // GATE: prove knowledge of the REAL vault password before this form
      // does anything observable at all.
      //
      // Why this field exists, since it is not needed to recover the token:
      // equalising the rendered output (below) did not equalise the NETWORK
      // request. A registration POST fires only when the decoy password is
      // correct, so anyone able to watch the network panel could still
      // classify a submitted password -- the same coercer-with-an-
      // authenticated-session the visible-output fix was about, one panel
      // over. Making the request pattern itself uniform is impossible here:
      // registering noise would deactivate the user's real alarm
      // (`register_signal_token` deactivates every active signal), and the
      // server cannot be taught to tell a recovered token from noise without
      // learning which slot a token belongs to -- exactly what DuressSignal's
      // zero-knowledge design forbids it from knowing.
      //
      // So instead of hiding the oracle, this removes ACCESS to it: operating
      // it now requires the real vault password, which the duress threat model
      // assumes the coercer does NOT have (if they did, they would already
      // have the real vault and the decoy would be moot). A coercer holding
      // only a password handed over under duress cannot submit this form at
      // all. See the plan's §22 for the full argument.
      let realPasswordOk = false;
      try {
        const openedReal = await unlockEnvelopeStore.open({
          userId,
          password: recoveryVaultPassword,
        });
        realPasswordOk = openedReal.slotIndex === 0;
      } catch (err) {
        if (!(err instanceof WrongPasswordError)) throw err;
      }
      if (!realPasswordOk) {
        // Identical for a wrong password AND for the decoy password typed
        // into this field -- the same non-classifying rule the setup form
        // follows. Revealing "that IS the real vault password" is
        // unavoidable (it is the credential that grants access); revealing
        // "that is the DECOY" is what must never happen.
        setRecoveryError('Incorrect vault password.');
        return;
      }

      let duressToken = null;
      try {
        const opened = await unlockEnvelopeStore.open({
          userId,
          password: recoveryPassword,
        });
        // Only a decoy slot carries a token. A real-slot open and a wrong
        // password both simply leave this null -- see the outcome note below
        // for why neither is reported as its own distinct result.
        if (opened.slotIndex === 1 && opened.duressToken) {
          duressToken = opened.duressToken;
        }
      } catch (err) {
        // A wrong password is NOT an error on this form: it is one of the
        // indistinguishable outcomes. Anything else (a corrupt envelope, a
        // storage failure) is a genuine operational fault and propagates.
        if (!(err instanceof WrongPasswordError)) throw err;
      }

      if (sessionVaultCrypto.currentSessionGeneration() !== generation) {
        setRecoveryError('Unlock your vault first, then try the recovery step again.');
        return;
      }

      if (duressToken) {
        await registerSignalToken(getAccessToken(), duressToken);
      }

      // ONE outcome for all three password classes -- decoy (registered),
      // real, and wrong. An earlier version reported each distinctly, on the
      // reasoning that this settings screen presupposes a user who already
      // knows about the feature. That reasoning was wrong, and the resulting
      // oracle is why this now reads the way it does: reaching this screen
      // needs only an AUTHENTICATED session, and a coerced unlock produces
      // exactly that. A coercer handed a password under duress could type it
      // here and be told "that opened the real vault, not the decoy slot" --
      // confirming, from the app itself, that they had been given a decoy.
      // That is precisely the disclosure the whole feature exists to
      // prevent, so this form must never classify a password. The legitimate
      // user loses nothing: they know which password they typed, and the
      // message is truthful for every case.
      setRecoveryVaultPassword('');
      setRecoveryPassword('');
      setRecoverySuccess(true);
    } catch (err) {
      // Operational faults only (registration request failed, envelope
      // unreadable) -- and the message is FIXED, never `err.message`.
      //
      // `registerSignalToken` runs on exactly one path: the one where the
      // submitted password opened slot 1. So its failure text ("Failed to
      // register duress signal token") is reachable ONLY for the decoy
      // password, while a real or wrong password takes the success path --
      // which makes the error string itself the classification this form was
      // rewritten to remove. Echoing `err.message` reintroduced the §22
      // oracle through the error channel, the same way §20.1's leak came back
      // through the network channel: the outcome must be indistinguishable on
      // EVERY surface, not only the ones already checked.
      console.warn('VaultDuressSetup: recovery submission failed.', err);
      setRecoveryError('Could not complete that request. Please try again.');
    } finally {
      setRecoveryBusy(false);
    }
  };

  return (
    <div style={panelStyle}>
      <h2>Vault duress protection</h2>
      <p style={{ color: '#6b7280' }}>
        Set up a second password for your vault. Entering it instead of your
        real password unlocks the decoy slot and silently alerts your
        configured contacts. The unlock request itself is indistinguishable
        from a normal one — same endpoint, same shape, same timing — but read
        the limitation below before relying on what appears on screen
        afterward.
      </p>

      <div style={noticeStyle}>
        <strong>Know the limits:</strong> the unlock itself is indistinguishable,
        but this does not yet build out believable decoy contents — a decoy
        unlock currently shows an <em>empty</em> vault, not a plausible,
        populated one. That is deliberate (an empty vault beats one that
        visibly fails to decrypt), but someone who knows your vault is not
        empty may still find it suspicious. Do not rely on this alone if that
        matters for your situation.
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

      <hr style={{ margin: '1.75rem 0', border: 'none', borderTop: '1px solid #e5e7eb' }} />

      <h3 style={{ fontSize: '1rem', margin: '0 0 0.5rem' }}>Recover unregistered alarm</h3>
      <p style={{ color: '#6b7280', fontSize: 13 }}>
        If a decoy password was saved but its alarm failed to register — even
        in an earlier session — enter both passwords here to retry. This
        re-reads the token already stored in the decoy slot; it never needs to
        be typed or stored anywhere else. Your vault password is required
        as well, so that this form cannot be used by someone who only knows
        the decoy password to check whether a password is the decoy.
      </p>
      <form onSubmit={handleRecoverRegistration}>
        <div className="form-group">
          <label htmlFor="duress-recovery-vault-password">Vault password</label>
          <input
            id="duress-recovery-vault-password"
            type="password"
            autoComplete="off"
            style={inputStyle}
            value={recoveryVaultPassword}
            onChange={(e) => setRecoveryVaultPassword(e.target.value)}
            disabled={recoveryBusy}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="duress-recovery-password">Decoy password</label>
          <input
            id="duress-recovery-password"
            type="password"
            autoComplete="off"
            style={inputStyle}
            value={recoveryPassword}
            onChange={(e) => setRecoveryPassword(e.target.value)}
            disabled={recoveryBusy}
            required
          />
        </div>

        {recoveryError && (
          <div role="alert" style={errorStyle}>{recoveryError}</div>
        )}
        {recoverySuccess && (
          <div role="status" style={successStyle}>
            If that was your decoy password, its alarm is now registered and
            will fire the next time it is used to unlock. This message is the
            same whichever password you entered.
          </div>
        )}

        <div style={{ marginTop: '0.75rem' }}>
          <button type="submit" style={buttonPrimary} disabled={recoveryBusy}>
            {recoveryBusy ? 'Recovering…' : 'Recover unregistered alarm'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default VaultDuressSetup;
