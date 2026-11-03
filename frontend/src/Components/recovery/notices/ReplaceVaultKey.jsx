import React, { useState } from 'react';
import ApiService from '../../../services/api';
import { replaceVaultKey } from '../../../services/vaultEnvelope';

/**
 * Replaces the vault key after a recovery compromise, so what whoever completed
 * the recovery may hold stops opening the vault. Done in the browser: the server
 * receives the new key only wrapped under the master password.
 */
export default function ReplaceVaultKey({ username }) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await replaceVaultKey(password, username);
      setDone(true);
    } catch (err) {
      // A failure in the browser carries its own message; a server one is in the response.
      const data = err?.response ? ApiService.handleError(err) || {} : {};
      setError(data.error || data.detail || err?.message || 'Could not replace the vault key.');
    } finally {
      setPassword('');
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div data-testid="replace-vault-key-done">
        <p>
          Your vault key was replaced and every session has ended. Sign in again
          with the same master password, then enroll new recovery factors.
        </p>
        <button type="button" onClick={() => window.location.assign('/')}>Sign in again</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} data-testid="replace-vault-key">
      <h3>Replace your vault key</h3>
      <p>
        Do this first. Whoever completed the recovery may still hold your current
        key. Your items stay readable and your master password stays the same, but
        <strong> every recovery factor is removed</strong>, so you have no way back
        into the vault if you forget that password until you enroll new ones. You
        will be signed out everywhere.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      <label htmlFor="replace-vault-key-password">Master password</label>
      <input
        id="replace-vault-key-password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />
      <button type="submit" disabled={busy || !password}>
        {busy ? 'Replacing…' : 'Replace vault key'}
      </button>
    </form>
  );
}
