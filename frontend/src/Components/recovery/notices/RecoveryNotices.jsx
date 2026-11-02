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
      .catch((err) => {
        const data = ApiService.handleError(err) || {};
        setError(data.error || data.detail || 'Could not load notices.');
      });
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
        Did not do one of these? Use the link in its email while the link is
        valid. If it is still in progress, the link stops it. If it already
        completed, the link locks your account and signs out every session:
        contact support to restore access, then change the passwords stored
        in your vault.
      </p>
    </section>
  );
}
