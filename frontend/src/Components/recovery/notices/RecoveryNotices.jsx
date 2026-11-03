import React, { useEffect, useState } from 'react';
import ApiService from '../../../services/api';

/**
 * In-app list of the account's recovery and reset notices (the same events
 * the security emails report), newest first, and after a support unlock the
 * warning that the vault may have been read. Nothing can undo that, so the
 * warning stays, here and in VaultExposureBanner, until the owner says the
 * stored passwords are changed.
 */
export default function RecoveryNotices() {
  const [notices, setNotices] = useState(null);
  const [exposedSince, setExposedSince] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    ApiService.recoveryNotices.list()
      .then((resp) => {
        setNotices(resp.data?.notices || []);
        setExposedSince(resp.data?.vault_exposed_since || null);
      })
      .catch((err) => {
        const data = ApiService.handleError(err) || {};
        setError(data.error || data.detail || 'Could not load notices.');
      });
  }, []);

  async function acknowledge() {
    setError('');
    try {
      await ApiService.recoveryNotices.acknowledgeExposure();
      setExposedSince(null);
    } catch (err) {
      const data = ApiService.handleError(err) || {};
      setError(data.error || data.detail || 'Could not save that. Try again.');
    }
  }

  if (notices === null) return error ? <p role="alert">{error}</p> : <p>Loading…</p>;

  return (
    <section data-testid="recovery-notices">
      <h1>Recovery activity</h1>
      {error ? <p role="alert">{error}</p> : null}
      {exposedSince ? (
        <div data-testid="vault-exposure-warning">
          <h2>Your vault may have been read</h2>
          <p>
            Support unlocked your account on {new Date(exposedSince).toLocaleString()},
            after a recovery you reported as not yours. Whoever completed it may
            have seen everything stored in your vault.
          </p>
          <ol>
            <li>Change every password stored in your vault, on the sites they belong to.</li>
            <li>Replace other secrets stored there, such as notes, card numbers and authenticator seeds.</li>
            <li>Enroll a new recovery factor, and check the ones you already have are yours.</li>
          </ol>
          <button type="button" onClick={acknowledge} data-testid="vault-exposure-acknowledge">
            I have done this
          </button>
        </div>
      ) : null}
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
