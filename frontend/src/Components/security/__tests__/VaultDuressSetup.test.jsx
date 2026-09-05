/**
 * Targeted regression tests for VaultDuressSetup's alarm-registration recovery.
 *
 * setDecoySlot() persists the new decoy envelope BEFORE registerSignalToken()
 * runs (correct ordering, per the #486 §10.3 lesson) -- but if registration
 * then fails, the decoy password is already live while its alarm is not
 * registered anywhere. The original fix (round 2 on PR #489) held the failed
 * token in React state for an in-session "Finish registration" retry --
 * CodeRabbit's round-4 review correctly flagged that state as lost on any
 * remount (reload, navigation), leaving no way back in without reconfiguring
 * the decoy slot from scratch. The current design instead re-derives the
 * token on demand via a standing "Recover unregistered alarm" form that
 * re-opens the existing envelope with the decoy password -- the token is
 * never held in state or storage, so recovery works regardless of how much
 * time or how many remounts have passed.
 */
import React from 'react';
import { render, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';

// hiddenVaultEnvelope.js imports argon2-browser at module scope; mock it so
// merely importing WrongPasswordError from it doesn't touch the WASM loader
// under jsdom (same reasoning as VaultUnlockModal.test.jsx).
vi.mock('argon2-browser', () => {
  const ArgonType = { Argon2id: 2 };
  const hash = vi.fn();
  return { ArgonType, hash, default: { ArgonType, hash } };
});

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../../services/hiddenVault/unlockEnvelopeStore', () => ({
  hasEnvelope: vi.fn(),
  setDecoySlot: vi.fn(),
  open: vi.fn(),
}));

vi.mock('../../../services/duressSignalService', () => ({
  registerSignalToken: vi.fn(),
}));

const { mockIsDecoySession, mockHasSessionKey, mockGeneration } = vi.hoisted(() => ({
  mockIsDecoySession: vi.fn(() => false),
  // Default: a live REAL session, which is what every pre-existing test here
  // assumes -- the forms only render for an operator who has already proven
  // the real vault password by unlocking with it.
  mockHasSessionKey: vi.fn(() => true),
  // Stable by default: the session does not change under any pre-existing
  // test. The lock-race tests move it, which is what `clearSessionKey()` does.
  mockGeneration: vi.fn(() => 7),
}));
vi.mock('../../../services/sessionVaultCrypto', () => ({
  default: {
    isDecoySession: mockIsDecoySession,
    hasSessionKey: mockHasSessionKey,
    currentSessionGeneration: mockGeneration,
  },
}));

import VaultDuressSetup from '../VaultDuressSetup';
import { useAuth } from '../../../hooks/useAuth';
import * as unlockEnvelopeStore from '../../../services/hiddenVault/unlockEnvelopeStore';
import { registerSignalToken } from '../../../services/duressSignalService';
import { WrongPasswordError } from '../../../services/hiddenVault/hiddenVaultEnvelope';

const USER_ID = 'user-1';
const TOKEN = 'jwt-token';
const DURESS_TOKEN = 'freshly-minted-duress-token';

const fillAndSubmit = (getByLabelText, getByRole, { vaultPassword = 'real-password', decoyPassword = 'a decoy password 12+', confirm } = {}) => {
  fireEvent.change(getByLabelText(/current vault password/i), { target: { value: vaultPassword } });
  fireEvent.change(getByLabelText(/new decoy password/i), { target: { value: decoyPassword } });
  fireEvent.change(getByLabelText(/confirm decoy password/i), { target: { value: confirm ?? decoyPassword } });
  fireEvent.click(getByRole('button', { name: /save decoy password/i }));
};

const REAL_PASSWORD = 'real-password';

// Recovery is gated behind the REAL vault password as well as the decoy one,
// so that someone holding only a password handed over under duress cannot use
// this form to check whether it is the decoy (see the component's own gate
// comment and the plan's §22). Tests default to supplying the correct vault
// password so they exercise the path past the gate.
const submitRecovery = (
  getByLabelText, getByRole, password, { vaultPassword = REAL_PASSWORD } = {}
) => {
  fireEvent.change(getByLabelText(/vault password/i, { selector: '#duress-recovery-vault-password' }), {
    target: { value: vaultPassword },
  });
  fireEvent.change(getByLabelText(/decoy password/i, { selector: '#duress-recovery-password' }), {
    target: { value: password },
  });
  fireEvent.click(getByRole('button', { name: /recover unregistered alarm/i }));
};

// `open()` is now called twice per recovery attempt: once for the vault-password
// gate, once for the decoy password. Route by the password actually supplied so
// each test can describe both slots independently.
const mockOpenBySlot = ({ decoyPassword, decoyToken = DURESS_TOKEN }) => {
  unlockEnvelopeStore.open.mockImplementation(async ({ password }) => {
    // A test double routing to a canned slot result, not a credential check --
    // the real comparison is Argon2id inside hiddenVaultEnvelope.
    // eslint-disable-next-line security/detect-possible-timing-attacks
    if (password === REAL_PASSWORD) {
      return { slotIndex: 0, duressToken: null, dekBytes: new Uint8Array(32), saltB64: 's' };
    }
    if (decoyPassword !== undefined && password === decoyPassword) {
      return { slotIndex: 1, duressToken: decoyToken, dekBytes: new Uint8Array(32), saltB64: 's' };
    }
    throw new WrongPasswordError('No slot decrypted successfully with the supplied password.');
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({
    isAuthenticated: true,
    user: { id: USER_ID },
    getAccessToken: () => TOKEN,
  });
  unlockEnvelopeStore.hasEnvelope.mockReturnValue(true);
  mockIsDecoySession.mockReturnValue(false);
  mockHasSessionKey.mockReturnValue(true);
  mockGeneration.mockReturnValue(7);
});

afterEach(() => {
  cleanup();
});

test('full success: registers the token and shows the success message', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockResolvedValue({ success: true });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const status = await findByRole('status');
  expect(status).toHaveTextContent('Decoy password saved.');
  expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN);
});

test('registration failure points at the recovery section, and touches the envelope only once', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockRejectedValueOnce(new Error('network error'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/could not be registered/i);
  expect(alert).toHaveTextContent(/recover unregistered alarm/i);
  expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalledTimes(1);
});

test('the recovery form is present even before any failure, and survives independently of the setup form', async () => {
  const { getByRole } = render(<VaultDuressSetup />);
  expect(getByRole('button', { name: /recover unregistered alarm/i })).toBeInTheDocument();
});

test('recovery re-opens the envelope with the decoy password and registers the token it finds, without touching setDecoySlot', async () => {
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });
  registerSignalToken.mockResolvedValue({ success: true });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  const status = await findByRole('status');
  expect(status).toHaveTextContent(/alarm is now registered/i);
  expect(unlockEnvelopeStore.open).toHaveBeenCalledWith({ userId: USER_ID, password: 'my-decoy-password' });
  expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN);
  // Recovery must never re-run setDecoySlot -- that would mint a brand-new
  // random token via generateSignalToken() and orphan whatever was already
  // registered or pending.
  expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
});

test('recovery survives a full remount (simulated by rendering a fresh instance with no prior state)', async () => {
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });
  registerSignalToken.mockResolvedValue({ success: true });

  // A fresh render with zero component history -- nothing was carried over
  // from an earlier failed attempt, proving recovery does not depend on any
  // in-memory state from the session that saw the original failure.
  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  await waitFor(() => expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN));
  expect(await findByRole('status')).toHaveTextContent(/alarm is now registered/i);
});

test('recovery with the wrong decoy password reports the same outcome as success, and registers nothing', async () => {
  // Correct vault password (passes the gate), but nothing matches the decoy.
  mockOpenBySlot({ decoyPassword: undefined });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'wrong-password');

  // No error surface at all -- a wrong password is one of the deliberately
  // indistinguishable outcomes, not a fault.
  await findByRole('status');
  expect(getByRole('status')).toBeInTheDocument();
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('recovery with the REAL vault password in the decoy field reports the same outcome, and registers nothing', async () => {
  mockOpenBySlot({ decoyPassword: undefined });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, REAL_PASSWORD);

  await findByRole('status');
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a registerSignalToken failure on the RECOVERY form never echoes its message', async () => {
  // registerSignalToken runs on exactly one recovery path -- the one where the
  // submitted password opened slot 1 -- so echoing err.message made the error
  // text itself the classification the form was rewritten to remove: only a
  // DECOY submission could ever produce "Failed to register duress signal
  // token", while a real or wrong password takes the success path.
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });
  registerSignalToken.mockRejectedValueOnce(new Error('Failed to register duress signal token'));
  vi.spyOn(console, 'warn').mockImplementation(() => {});

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Could not complete that request. Please try again.');
  expect(alert.textContent).not.toMatch(/duress|decoy|signal|token|slot/i);
});

test('the SETUP form renders one fixed outcome for ANY WrongPasswordError', async () => {
  // §21.1's oracle was setDecoySlot throwing a slot-naming Error for "you
  // typed the decoy password here", which the catch echoed via err.message,
  // while a garbage password produced "Incorrect vault password."
  //
  // The half of that fix which lives HERE is the only half this file can
  // test: whatever WrongPasswordError arrives, the screen renders the same
  // fixed text and names no slot. The other half -- that setDecoySlot raises
  // the SAME type and a byte-identical message for a decoy password as for
  // garbage -- is a property of the store, and is asserted against the real
  // implementation in unlockEnvelopeStore.test.js ("the decoy password in the
  // vault-password field is rejected exactly like garbage"). An earlier
  // version of this test fed two identical mock errors in here and compared
  // the rendered HTML; that comparison was true by construction and could not
  // fail, which made it read as coverage it never provided.
  unlockEnvelopeStore.setDecoySlot.mockRejectedValue(
    new WrongPasswordError('No slot decrypted successfully with the supplied password.')
  );

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alertText = (await findByRole('alert')).textContent;
  expect(alertText).toBe('Incorrect vault password.');
  // Scoped to the ERROR text: the page's own static copy legitimately
  // explains the decoy slot to the user configuring it, so asserting on the
  // whole container would fail on that unrelated (and correct) prose.
  expect(alertText).not.toMatch(/decoy|real slot|did not resolve/i);
});

test('a vault:locked event repaints the panel, so the forms do not linger after a lock', async () => {
  // Display freshness, not the boundary. Every lock path runs handleLockVault,
  // which now dispatches this; before it, nothing inside the locking tab told
  // this screen to re-render, so its password forms stayed visible until some
  // unrelated render happened. The submit-time checks already refused those
  // submissions -- this is what stops it LOOKING like the gate failed.
  mockHasSessionKey.mockReturnValue(true);
  const { getByLabelText, container } = render(<VaultDuressSetup />);
  expect(getByLabelText(/current vault password/i)).toBeInTheDocument();

  mockHasSessionKey.mockReturnValue(false);
  await act(async () => { window.dispatchEvent(new Event('vault:locked')); });

  expect(container.querySelector('input')).toBeNull();
  expect(container.textContent).toMatch(/unlock your vault first/i);
});

test('a DECOY unlock between render and submit blocks the submission', async () => {
  // hasSessionKey() alone is not "a real session": a decoy unlock installs a
  // session DEK too. So a decoy unlock landing after this screen rendered
  // leaves the key present and the form live, and the generation check inside
  // the try block cannot help -- it captures AFTER this point, so it already
  // reflects the decoy install. The submit gate must check both predicates,
  // exactly as the render gate does.
  mockHasSessionKey.mockReturnValue(true);
  mockIsDecoySession.mockReturnValue(false);
  const { getByLabelText, getByRole, container } = render(<VaultDuressSetup />);

  fireEvent.change(getByLabelText(/current vault password/i), { target: { value: REAL_PASSWORD } });
  fireEvent.change(getByLabelText(/new decoy password/i), { target: { value: 'a decoy password 12+' } });
  fireEvent.change(getByLabelText(/confirm decoy password/i), { target: { value: 'a decoy password 12+' } });

  // Another tab unlocks with the DECOY password: key still present, flag set.
  mockIsDecoySession.mockReturnValue(true);
  fireEvent.click(getByRole('button', { name: /save decoy password/i }));

  // The submit gate refuses, and the re-render its setError triggers then hits
  // the §23.1 decoy render gate, so the neutral panel replaces the form
  // entirely. Asserted on the CALLS rather than the message, because that is
  // the property at stake: no envelope work and no registration happened.
  await waitFor(() => expect(container.querySelector('input')).toBeNull());
  expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
  expect(registerSignalToken).not.toHaveBeenCalled();
  expect(container.textContent).not.toMatch(/incorrect/i);
});

test('a lock that happens AFTER the form is filled still blocks the submission', async () => {
  // The lock paths -- manual, inactivity, cross-tab -- all go through
  // handleLockVault, which calls clearSessionKey() and dispatches NO DOM
  // event, so nothing forces this screen to re-render. Filling first and
  // locking second reproduces that exactly: the click lands on a form that was
  // rendered while the vault was still unlocked, so only the submit-time
  // re-check can stop it.
  mockHasSessionKey.mockReturnValue(true);
  const { getByLabelText, getByRole, container } = render(<VaultDuressSetup />);

  fireEvent.change(getByLabelText(/current vault password/i), { target: { value: REAL_PASSWORD } });
  fireEvent.change(getByLabelText(/new decoy password/i), { target: { value: 'a decoy password 12+' } });
  fireEvent.change(getByLabelText(/confirm decoy password/i), { target: { value: 'a decoy password 12+' } });

  // Vault locks while this screen sits mounted. No event, no re-render.
  mockHasSessionKey.mockReturnValue(false);
  fireEvent.click(getByRole('button', { name: /save decoy password/i }));

  await waitFor(() => expect(container.textContent).toMatch(/unlock your vault first/i));
  // Nothing password-dependent ran: no decode, no request, and above all no
  // "Incorrect vault password." for a password that opens this very vault.
  expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
  expect(registerSignalToken).not.toHaveBeenCalled();
  expect(container.textContent).not.toMatch(/incorrect/i);
});

test('a post-lock submission renders identically for a real, decoy and garbage password', async () => {
  // The refusal must not become the classifier it was added to remove.
  const outcomeFor = async (password) => {
    mockHasSessionKey.mockReturnValue(true);
    const { getByLabelText, getByRole, container, unmount } = render(<VaultDuressSetup />);
    fireEvent.change(getByLabelText(/current vault password/i), { target: { value: password } });
    fireEvent.change(getByLabelText(/new decoy password/i), { target: { value: 'a decoy password 12+' } });
    fireEvent.change(getByLabelText(/confirm decoy password/i), { target: { value: 'a decoy password 12+' } });
    mockHasSessionKey.mockReturnValue(false);
    fireEvent.click(getByRole('button', { name: /save decoy password/i }));
    await waitFor(() => expect(container.textContent).toMatch(/unlock your vault first/i));
    const html = container.innerHTML;
    unmount();
    return html;
  };

  const real = await outcomeFor(REAL_PASSWORD);
  const decoy = await outcomeFor('my-decoy-password');
  const garbage = await outcomeFor('not any password at all');

  expect(real).toBe(decoy);
  expect(decoy).toBe(garbage);
});

test('a post-lock RECOVERY submission is blocked before it opens the envelope', async () => {
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });
  mockHasSessionKey.mockReturnValue(true);
  const { getByLabelText, getByRole, container } = render(<VaultDuressSetup />);

  fireEvent.change(getByLabelText(/vault password/i, { selector: '#duress-recovery-vault-password' }), {
    target: { value: REAL_PASSWORD },
  });
  fireEvent.change(getByLabelText(/decoy password/i, { selector: '#duress-recovery-password' }), {
    target: { value: 'my-decoy-password' },
  });

  mockHasSessionKey.mockReturnValue(false);
  fireEvent.click(getByRole('button', { name: /recover unregistered alarm/i }));

  await waitFor(() => expect(container.textContent).toMatch(/unlock your vault first/i));
  expect(unlockEnvelopeStore.open).not.toHaveBeenCalled();
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a lock DURING the decoy save stops the registration that follows it', async () => {
  // setDecoySlot runs three Argon2 derivations. The pre-submit gate cannot see
  // a lock that lands inside that window, and the continuation would then fire
  // an authenticated registration request for a session that no longer exists.
  let resolveSave;
  unlockEnvelopeStore.setDecoySlot.mockReturnValue(
    new Promise((resolve) => { resolveSave = resolve; })
  );

  const { getByLabelText, getByRole, container } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  await waitFor(() => expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalled());
  expect(registerSignalToken).not.toHaveBeenCalled();

  // The vault locks mid-save: clearSessionKey() nulls the key AND bumps the
  // generation. Then the save resolves.
  mockHasSessionKey.mockReturnValue(false);
  mockGeneration.mockReturnValue(8);
  await act(async () => { resolveSave({ duressToken: DURESS_TOKEN }); });

  // With the key gone the live render gate also replaces the form, so the
  // observable outcome is the neutral panel rather than an inline alert --
  // what matters is that no registration request followed the save.
  expect(container.textContent).toMatch(/unlock your vault first/i);
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a lock-then-DECOY-unlock during the save is caught too, which hasSessionKey alone would miss', async () => {
  // The reason the check compares generations rather than re-reading
  // hasSessionKey(): a lock followed by ANY unlock leaves hasSessionKey() true
  // again, so that check would let the continuation register an alarm from
  // inside a decoy session.
  let resolveSave;
  unlockEnvelopeStore.setDecoySlot.mockReturnValue(
    new Promise((resolve) => { resolveSave = resolve; })
  );

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);
  await waitFor(() => expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalled());

  // Locked and re-unlocked with the decoy password: key present again...
  mockHasSessionKey.mockReturnValue(true);
  // ...but two clearSessionKey/install transitions have moved the counter.
  mockGeneration.mockReturnValue(9);
  await act(async () => { resolveSave({ duressToken: DURESS_TOKEN }); });

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/unlock your vault first/i);
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a lock DURING the recovery opens stops its registration as well', async () => {
  // Same window in the sibling handler: two open() calls before the register.
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });
  let resolveOpen;
  const realOpen = unlockEnvelopeStore.open.getMockImplementation();
  unlockEnvelopeStore.open.mockImplementationOnce(realOpen)
    .mockImplementationOnce(() => new Promise((resolve) => { resolveOpen = resolve; }));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  await waitFor(() => expect(unlockEnvelopeStore.open).toHaveBeenCalledTimes(2));
  mockGeneration.mockReturnValue(8);
  await act(async () => {
    resolveOpen({ slotIndex: 1, duressToken: DURESS_TOKEN, dekBytes: new Uint8Array(32), saltB64: 's' });
  });

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/unlock your vault first/i);
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('the setup form never echoes a raw service error message', async () => {
  // The `else` branch used to surface err.message verbatim, which is how the
  // slot-specific string reached the screen. Any future service error string
  // must not reach the user either.
  unlockEnvelopeStore.setDecoySlot.mockRejectedValue(
    new Error('setDecoySlot: some internal detail that must not be shown')
  );

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Could not save the decoy password. Please try again.');
  expect(alert.textContent).not.toMatch(/internal detail|setDecoySlot/i);
});

test('the recovery form is not a password oracle: decoy, real, and wrong passwords all render byte-identical output', async () => {
  // The security property Greptile's P1 finding was about. Reaching this
  // screen needs only an authenticated session, which a coerced unlock
  // produces -- so a coercer must not be able to type a password here and
  // learn which slot (if any) it opens. Asserted on the serialized container
  // rather than hand-picked strings, so a future contributor reintroducing a
  // branch anywhere in this form's output fails this test.
  // All three attempts supply the CORRECT vault password, so each gets past
  // the gate -- the property under test is that what happens after the gate
  // still cannot classify the decoy-field value.
  const renderOutcome = async (password) => {
    mockOpenBySlot({ decoyPassword: 'my-decoy-password', decoyToken: 'a'.repeat(44) });
    const { getByLabelText, getByRole, findByRole, container, unmount } =
      render(<VaultDuressSetup />);
    submitRecovery(getByLabelText, getByRole, password);
    await findByRole('status');
    const html = container.innerHTML;
    unmount();
    return html;
  };

  const decoyHtml = await renderOutcome('my-decoy-password');
  const realHtml = await renderOutcome(REAL_PASSWORD);
  const wrongHtml = await renderOutcome('wrong-password');

  expect(realHtml).toBe(decoyHtml);
  expect(wrongHtml).toBe(decoyHtml);
});

test('recovery does nothing observable at all without the real vault password -- the gate that closes the network-side oracle', async () => {
  // Greptile P1 (§22): equalising the rendered output did not equalise the
  // NETWORK request -- a registration POST fires only for the correct decoy
  // password, so an observer of the network panel could still classify. That
  // cannot be equalised (registering noise would deactivate the user's real
  // alarm, and the server cannot be taught to tell a recovered token from
  // noise without learning which slot it came from -- which ZK forbids). So
  // the oracle is closed by ACCESS instead: operating it requires the real
  // vault password, which the duress threat model assumes the coercer lacks.
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password', {
    vaultPassword: 'not-the-real-vault-password',
  });

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Incorrect vault password.');
  // The whole point: NO registration request, even though the decoy password
  // supplied was correct. Without this, the request itself is the oracle.
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('the vault-password gate does not itself classify: the decoy password typed into it is rejected exactly like garbage', async () => {
  mockOpenBySlot({ decoyPassword: 'my-decoy-password' });

  const attempt = async (vaultPassword) => {
    const { getByLabelText, getByRole, findByRole, container, unmount } =
      render(<VaultDuressSetup />);
    submitRecovery(getByLabelText, getByRole, 'my-decoy-password', { vaultPassword });
    await findByRole('alert');
    // Strip the inputs' own `value` attributes: those echo what the TEST
    // typed, not anything the app decided, and would make any two attempts
    // with different passwords differ trivially. Everything the component
    // actually produces is still compared.
    const html = container.innerHTML.replace(/value="[^"]*"/g, 'value="[typed]"');
    unmount();
    return html;
  };

  // Typing the DECOY password into the vault-password field must look
  // identical to typing nonsense -- otherwise the gate becomes the oracle it
  // was added to close.
  const decoyInGate = await attempt('my-decoy-password');
  const garbageInGate = await attempt('nonsense-password');

  expect(decoyInGate).toBe(garbageInGate);
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a wrong vault password on the setup form does not touch recovery or registration', async () => {
  unlockEnvelopeStore.setDecoySlot.mockRejectedValue(new WrongPasswordError('no slot matched'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Incorrect vault password.');
  expect(registerSignalToken).not.toHaveBeenCalled();
  expect(unlockEnvelopeStore.open).not.toHaveBeenCalled();
});

describe('during a DECOY session', () => {
  // The coercer has just watched password D unlock this vault. If this screen
  // then tells them D is "Incorrect vault password.", that contradicts what
  // they saw with their own eyes and outs the decoy -- a sharper tell than
  // the empty item list, and one no innocent explanation covers. Neither form
  // may render, so there is nothing to submit, nothing to contradict, and no
  // request to observe.
  test('renders no password fields and no forms at all', () => {
    mockIsDecoySession.mockReturnValue(true);

    const { queryByLabelText, queryByRole, container } = render(<VaultDuressSetup />);

    expect(queryByLabelText(/current vault password/i)).toBeNull();
    expect(queryByLabelText(/decoy password/i)).toBeNull();
    expect(queryByRole('button', { name: /save decoy password/i })).toBeNull();
    expect(queryByRole('button', { name: /recover unregistered alarm/i })).toBeNull();
    expect(container.querySelector('form')).toBeNull();
    expect(container.querySelector('input')).toBeNull();
  });

  test('never says a password is incorrect, and never registers anything', () => {
    mockIsDecoySession.mockReturnValue(true);

    const { container } = render(<VaultDuressSetup />);

    // The specific contradiction this gate exists to prevent.
    expect(container.textContent).not.toMatch(/incorrect/i);
    expect(registerSignalToken).not.toHaveBeenCalled();
    expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
    expect(unlockEnvelopeStore.open).not.toHaveBeenCalled();
  });

  test('a LOCKED vault renders no forms either -- the decoy gate does not cover it', () => {
    // `isDecoySession()` answers "is the CURRENT session a decoy", and while
    // the vault is locked there is no session, so it answers false. The decoy
    // gate therefore does NOT fire here, and without its own gate this screen
    // rendered a password-verifying form to an operator who had proven
    // nothing -- who could type the password handed to them under duress and
    // be told "Incorrect vault password." for a password that visibly unlocks
    // this vault.
    mockHasSessionKey.mockReturnValue(false);
    mockIsDecoySession.mockReturnValue(false);

    const { queryByLabelText, queryByRole, container } = render(<VaultDuressSetup />);

    expect(queryByLabelText(/current vault password/i)).toBeNull();
    expect(queryByRole('button', { name: /save decoy password/i })).toBeNull();
    expect(queryByRole('button', { name: /recover unregistered alarm/i })).toBeNull();
    expect(container.querySelector('input')).toBeNull();
    expect(container.textContent).not.toMatch(/incorrect/i);
  });

  test('locking a DECOY session does not reopen the screen', () => {
    // handleLockVault calls clearSessionKey(), which sets sessionIsDecoy back
    // to false -- so after a coercer locks the decoy session they had, the
    // decoy gate stops firing. Only the session gate still holds.
    mockIsDecoySession.mockReturnValue(false);
    mockHasSessionKey.mockReturnValue(false);

    const { container } = render(<VaultDuressSetup />);

    expect(container.querySelector('form')).toBeNull();
    expect(registerSignalToken).not.toHaveBeenCalled();
    expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
    expect(unlockEnvelopeStore.open).not.toHaveBeenCalled();
  });

  test('a real session still renders both forms', () => {
    const { getByLabelText, getByRole } = render(<VaultDuressSetup />);

    expect(getByLabelText(/current vault password/i)).toBeInTheDocument();
    expect(getByRole('button', { name: /recover unregistered alarm/i })).toBeInTheDocument();
  });
});
