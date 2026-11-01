import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ApiService from '../../../services/api';

/**
 * Landing page for the cancel link in a time-locked recovery's canary email
 * (/recovery/time-lock/cancel?token=<token>).
 *
 * The cancel is a button, not something the page does on load: mail scanners
 * and link previews open links, and must not stop a recovery by doing so.
 * The server answers the same for any token, so neither does this page say
 * whether the token was valid.
 */
export default function TimeLockCancel() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [state, setState] = useState('ready'); // 'busy' | 'done' | 'error'
  const [message, setMessage] = useState('');

  async function handleCancel() {
    setState('busy');
    try {
      await ApiService.recoveryNotices.cancelTimeLock(token);
      setState('done');
    } catch (err) {
      setMessage(ApiService.handleError(err).error || 'Could not reach the server. Try again.');
      setState('error');
    }
  }

  if (!token) {
    return (
      <section data-testid="time-lock-cancel">
        <h1>Stop a time-locked recovery</h1>
        <p role="alert">This link is incomplete. Open the link from the email again.</p>
      </section>
    );
  }

  return (
    <section data-testid="time-lock-cancel">
      <h1>Stop a time-locked recovery</h1>
      {state === 'done' ? (
        <p data-testid="time-lock-cancel-done">
          If this link was still valid, the recovery is stopped and can no longer complete.
        </p>
      ) : (
        <>
          <p>Use this only if you did not start the recovery that the email describes.</p>
          {state === 'error' ? <p role="alert">{message}</p> : null}
          <button
            type="button"
            onClick={handleCancel}
            disabled={state === 'busy'}
            data-testid="time-lock-cancel-button"
          >
            {state === 'busy' ? 'Stopping…' : 'This wasn’t me: stop it'}
          </button>
        </>
      )}
    </section>
  );
}
