/**
 * HoneypotSettings.jsx
 *
 * Owner-only page to plant, rotate, or remove honeypot credentials and
 * inspect the decoy each one hands out. We deliberately keep the UI
 * plain — this is not a customer-facing wonderpage, it is an operator
 * console.
 */

import React, { useCallback, useEffect, useState } from 'react';
import honeypotCredentialService from '../../services/honeypotCredentialService';

const DEFAULT_CHANNELS = ['email'];
const STRATEGIES = [
  { value: 'static', label: 'Static decoy' },
  { value: 'rotating', label: 'Rotating decoy (nightly)' },
  { value: 'from_template', label: 'From template' },
];

function EmptyState({ onCreate }) {
  return (
    <div style={{ padding: 24, border: '1px dashed #aaa', textAlign: 'center' }}>
      <p style={{ marginBottom: 12 }}>
        No honeypot credentials planted yet. Plant a honeypot that looks
        like a real login — any access fires an immediate silent alert.
      </p>
      <button type="button" onClick={onCreate}>Plant a honeypot</button>
    </div>
  );
}

function HoneypotRow({ hp, onRotate, onDelete, onReveal, onToggle }) {
  return (
    <tr>
      <td>{hp.label}</td>
      <td>{hp.fake_site}</td>
      <td>{hp.fake_username}</td>
      <td>{hp.decoy_strategy}</td>
      <td>{(hp.alert_channels || []).join(', ') || '-'}</td>
      <td>{hp.access_count ?? 0}</td>
      <td>
        <label>
          <input
            type="checkbox"
            checked={!!hp.is_active}
            onChange={(e) => onToggle(hp, e.target.checked)}
          />
          active
        </label>
      </td>
      <td style={{ whiteSpace: 'nowrap' }}>
        <button type="button" onClick={() => onReveal(hp)}>Reveal</button>{' '}
        <button type="button" onClick={() => onRotate(hp)}>Rotate</button>{' '}
        <button type="button" onClick={() => onDelete(hp)}>Delete</button>
      </td>
    </tr>
  );
}

export default function HoneypotSettings() {
  const [honeypots, setHoneypots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [reveal, setReveal] = useState(null);

  const [label, setLabel] = useState('');
  const [strategy, setStrategy] = useState('static');
  const [fakeSite, setFakeSite] = useState('');
  const [fakeUsername, setFakeUsername] = useState('');
  const [channels, setChannels] = useState(DEFAULT_CHANNELS);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await honeypotCredentialService.list();
      const data = res?.data?.results || res?.data || [];
      setHoneypots(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.message || 'Failed to load honeypots.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e?.preventDefault?.();
    setError('');
    try {
      await honeypotCredentialService.create({
        label: label || 'Honeypot',
        strategy,
        fake_site: fakeSite || undefined,
        fake_username: fakeUsername || undefined,
        alert_channels: channels,
      });
      setLabel('');
      setFakeSite('');
      setFakeUsername('');
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create honeypot.');
    }
  };

  const handleRotate = async (hp) => {
    try {
      await honeypotCredentialService.rotate(hp.id);
      await load();
    } catch (err) {
      setError(err?.message || 'Rotate failed.');
    }
  };

  const handleDelete = async (hp) => {
    if (!window.confirm(`Delete honeypot "${hp.label}"? This cannot be undone.`)) return;
    try {
      await honeypotCredentialService.remove(hp.id);
      await load();
    } catch (err) {
      setError(err?.message || 'Delete failed.');
    }
  };

  const handleReveal = async (hp) => {
    try {
      const res = await honeypotCredentialService.reveal(hp.id);
      setReveal(res.data);
    } catch (err) {
      setError(err?.message || 'Reveal failed.');
    }
  };

  const handleToggle = async (hp, active) => {
    try {
      await honeypotCredentialService.update(hp.id, { is_active: active });
      await load();
    } catch (err) {
      setError(err?.message || 'Update failed.');
    }
  };

  const toggleChannel = (ch) => {
    setChannels((prev) => (prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]));
  };

  return (
    <div style={{ padding: 16, maxWidth: 1080 }}>
      <h2>Honeypot credentials</h2>
      <p>
        Honeypots look like real logins but alert you the moment someone
        touches them. Treat any access as a breach signal.
      </p>

      {error && (
        <div style={{ padding: 8, color: '#b00', border: '1px solid #b00', marginBottom: 12 }}>
          {error}
        </div>
      )}

      <form
        onSubmit={handleCreate}
        style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 16 }}
      >
        <label>
          Label
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Corporate admin backup" />
        </label>
        <label>
          Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
          </select>
        </label>
        <label>
          Fake site (optional)
          <input value={fakeSite} onChange={(e) => setFakeSite(e.target.value)} placeholder="internal-portal.example.com" />
        </label>
        <label>
          Fake username (optional)
          <input value={fakeUsername} onChange={(e) => setFakeUsername(e.target.value)} placeholder="admin_backup@example.com" />
        </label>
        <fieldset style={{ gridColumn: '1 / span 2' }}>
          <legend>Alert channels</legend>
          {['email', 'sms', 'webhook', 'signal'].map((ch) => (
            <label key={ch} style={{ marginRight: 12 }}>
              <input type="checkbox" checked={channels.includes(ch)} onChange={() => toggleChannel(ch)} />
              {ch}
            </label>
          ))}
        </fieldset>
        <button type="submit" style={{ gridColumn: '1 / span 2' }}>
          Plant honeypot
        </button>
      </form>

      {loading ? (
        <p>Loading honeypots…</p>
      ) : honeypots.length === 0 ? (
        <EmptyState onCreate={() => setLabel('New honeypot')} />
      ) : (
        <table width="100%" cellPadding={6}>
          <thead>
            <tr>
              <th align="left">Label</th>
              <th align="left">Fake site</th>
              <th align="left">Fake username</th>
              <th align="left">Strategy</th>
              <th align="left">Alert channels</th>
              <th align="left">Hits</th>
              <th align="left">Status</th>
              <th align="left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {honeypots.map((hp) => (
              <HoneypotRow
                key={hp.id}
                hp={hp}
                onRotate={handleRotate}
                onDelete={handleDelete}
                onReveal={handleReveal}
                onToggle={handleToggle}
              />
            ))}
          </tbody>
        </table>
      )}

      {reveal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)' }}>
          <div style={{ background: '#fff', maxWidth: 500, margin: '10vh auto', padding: 16 }}>
            <h3>Decoy peek</h3>
            <p>Owner-only. Does NOT fire alerts.</p>
            <pre style={{ background: '#f5f5f5', padding: 8 }}>{JSON.stringify(reveal, null, 2)}</pre>
            <button type="button" onClick={() => setReveal(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
