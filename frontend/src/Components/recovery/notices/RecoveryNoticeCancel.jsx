import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ApiService from '../../../services/api';

/**
 * Landing page for the "this wasn't me" link in a recovery notice email
 * (/recovery/cancel?notice=<token>).
 *
 * The cancel is a button, not something the page does on load: mail
 * scanners and link previews open links, and must not stop a recovery or
 * lock an account by doing so.
 */
export default function RecoveryNoticeCancel() {
  const [params] = useSearchParams();
  const token = params.get('notice') || '';
  const [state, setState] = useState('ready'); // 'busy' | 'done' | 'error'
  const [message, setMessage] = useState('');

  async function handleCancel() {
    setState('busy');
    try {
      const resp = await ApiService.recoveryNotices.cancel(token);
      setMessage(resp.data?.message || '');
      setState('done');
    } catch (err) {
      setMessage(ApiService.handleError(err).error || 'Could not reach the server. Try again.');
      setState('error');
    }
  }

  if (!token) {
    return (
      <section data-testid="recovery-notice-cancel">
        <h1>Stop a recovery</h1>
        <p role="alert">This link is incomplete. Open the link from the email again.</p>
      </section>
    );
  }

  return (
    <section data-testid="recovery-notice-cancel">
      <h1>Stop a recovery</h1>
      {state === 'done' ? (
        <p data-testid="recovery-notice-cancel-done">{message}</p>
      ) : (
        <>
          <p>
            Use this only if you did not start the recovery or reset that the
            email describes. If it already completed, your account is locked
            and every session is signed out; contact support to restore access.
            Your vault stays encrypted: you open it again with your own
            recovery key.
          </p>
          {state === 'error' ? <p role="alert">{message}</p> : null}
          <button
            type="button"
            onClick={handleCancel}
            disabled={state === 'busy'}
            data-testid="recovery-notice-cancel-button"
          >
            {state === 'busy' ? 'Stopping…' : 'This wasn’t me: stop it'}
          </button>
        </>
      )}
    </section>
  );
}
