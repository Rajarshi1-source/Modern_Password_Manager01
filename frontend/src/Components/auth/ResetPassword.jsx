import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ApiService from '../../services/api';
import { deriveAuthHash, deriveLoginVerifier } from '../../services/loginVerifier';

/**
 * The page the emailed reset link opens (/reset-password/:uid/:token).
 *
 * An email reset proves control of the inbox, not of any vault key, so it
 * changes only how the account signs in: the browser derives the new login
 * verifier and auth hash from the new master password and sends those,
 * never the password. Items saved before the reset stay encrypted under
 * the previous master password; the page says so before and after.
 */
const ResetPassword = () => {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  // The name the account signs in with (usually its email): the login
  // verifier is salted with it, so it must be that exact account name.
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [doneMessage, setDoneMessage] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const accountName = username.trim();
    if (!accountName) {
      setError('Enter the username you sign in with.');
      return;
    }
    if (password.length < 12) {
      setError('The new master password must be at least 12 characters.');
      return;
    }
    if (password !== confirm) {
      setError('The passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const [newAuthHash, newLoginVerifier] = await Promise.all([
        deriveAuthHash(password, accountName),
        deriveLoginVerifier(password, accountName),
      ]);
      const response = await ApiService.auth.resetPassword({
        uid,
        token,
        username: accountName,
        new_auth_hash: newAuthHash,
        new_login_verifier: newLoginVerifier,
      });
      setPassword('');
      setConfirm('');
      setDoneMessage(response.data?.message || 'Your sign-in password was reset.');
    } catch (err) {
      setError(err.response?.data?.error || 'The reset failed. The link may have expired; request a new one.');
    } finally {
      setBusy(false);
    }
  }

  if (doneMessage) {
    return (
      <div className="reset-password" data-testid="reset-password-done">
        <h1>Sign-in password reset</h1>
        <p>{doneMessage}</p>
        <p>
          If you have a recovery key or trusted contacts set up, use them now to restore access
          to your saved items. Recovery asks for a master password again: enter the new one.
        </p>
        <button type="button" onClick={() => navigate('/recovery/key/use-v2')}>Use a recovery key</button>
        <button type="button" onClick={() => navigate('/login')}>Sign in</button>
      </div>
    );
  }

  return (
    <form className="reset-password" onSubmit={handleSubmit}>
      <h1>Reset your sign-in password</h1>
      <p data-testid="reset-password-warning">
        This resets only how you sign in. Your saved items are encrypted with your previous
        master password and this link cannot decrypt them: you will need a recovery factor,
        such as your recovery key, to open them.
      </p>
      <label htmlFor="reset-username">Username you sign in with (usually your email)</label>
      <input id="reset-username" type="text" autoComplete="username" value={username}
        onChange={(e) => setUsername(e.target.value)} />
      <label htmlFor="reset-password">New master password</label>
      <input id="reset-password" type="password" autoComplete="new-password" value={password}
        onChange={(e) => setPassword(e.target.value)} />
      <label htmlFor="reset-confirm">Confirm new master password</label>
      <input id="reset-confirm" type="password" autoComplete="new-password" value={confirm}
        onChange={(e) => setConfirm(e.target.value)} />
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Resetting…' : 'Reset password'}</button>
    </form>
  );
};

export default ResetPassword;
