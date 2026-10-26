import React, { useEffect, useState } from 'react';
import ApiService from '../../../services/api';

/**
 * In-app list of the account's recovery and reset notices (the same events
 * the security emails report), newest first.
 */
export default function RecoveryNotices() {
  const [notices, setNotices] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    ApiService.recoveryNotices.list()
      .then((resp) => setNotices(resp.data?.notices || []))
      .catch((err) => setError(ApiService.handleError(err).error || 'Could not load notices.'));
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (notices === null) return <p>Loading…</p>;

  return (
    <section data-testid="recovery-notices">
      <h1>Recovery activity</h1>
      {notices.length === 0 ? (
        <p>No recovery or reset activity on this account.</p>
      ) : (
        <ul>
          {notices.map((n) => (
            <li key={n.id} data-testid="recovery-notice">
              <strong>{n.description}</strong>
              {' '}{new Date(n.created_at).toLocaleString()}
              {n.ip_address ? ` from ${n.ip_address}` : ''}
              {n.cancelled_at ? ' (stopped)' : ''}
            </li>
          ))}
        </ul>
      )}
      <p>
        Did not do one of these? Use the link in its email to stop it while
        the link is valid, then change your master password.
      </p>
    </section>
  );
}
