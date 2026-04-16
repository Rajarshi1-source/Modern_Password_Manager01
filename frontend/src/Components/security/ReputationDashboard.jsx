/**
 * Decentralized Password Reputation Network dashboard.
 *
 * Shows the signed-in user's reputation score, tokens, recent events, and
 * recent on-chain anchor batches. Also exposes a manual "submit a reputation
 * proof" flow — useful in the dashboard UX (the vault-save hook submits
 * automatically in the background, but users sometimes want to retry or
 * re-claim for an existing secret).
 *
 * The frontend never sends the password plaintext; it derives a Pedersen
 * commitment locally and sends `(commitment, claimed_entropy_bits, binding_hash)`.
 * See `password_reputation/providers/commitment_claim.py` for the server side
 * of the contract.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import {
  commitmentForReputation,
  computeBindingHash,
  estimateEntropyBits,
  reputationApi,
} from '../../services/reputation';

const panelStyle = {
  maxWidth: 980,
  margin: '2rem auto',
  padding: '1.5rem 1.75rem',
  background: '#ffffff',
  border: '1px solid #e1e4ea',
  borderRadius: 10,
  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
  color: '#1f2937',
};

const sectionHeading = {
  fontSize: 16,
  margin: '1.5rem 0 0.5rem',
  color: '#111827',
  borderBottom: '1px solid #e5e7eb',
  paddingBottom: 4,
};

const chipRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '0.75rem',
  marginTop: '0.5rem',
};

const chip = (accent) => ({
  background: '#f9fafb',
  border: `1px solid ${accent || '#e5e7eb'}`,
  borderLeft: `4px solid ${accent || '#7B68EE'}`,
  borderRadius: 8,
  padding: '0.75rem 1rem',
  minWidth: 160,
  flex: '1 1 180px',
});

const chipLabel = { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 };
const chipValue = { fontSize: 22, fontWeight: 700, color: '#111827', marginTop: 2 };

const inputStyle = {
  width: '100%',
  padding: '0.5rem 0.65rem',
  marginTop: '0.3rem',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  fontSize: 14,
};

const primaryBtn = {
  padding: '0.55rem 1.2rem',
  borderRadius: 6,
  border: 'none',
  background: '#7B68EE',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  marginTop: '0.5rem',
  fontSize: 13,
};
const thStyle = {
  textAlign: 'left',
  padding: '6px 8px',
  background: '#f9fafb',
  borderBottom: '1px solid #e5e7eb',
  fontWeight: 600,
};
const tdStyle = { padding: '6px 8px', borderBottom: '1px solid #f3f4f6' };

const EVENT_LABELS = {
  proof_accepted: { label: 'Proof accepted', color: '#16a34a' },
  proof_rejected: { label: 'Proof rejected', color: '#dc2626' },
  bonus: { label: 'Bonus', color: '#2563eb' },
  slash: { label: 'Slash', color: '#dc2626' },
  anchor_confirmed: { label: 'Anchor confirmed', color: '#0891b2' },
};

const ANCHOR_LABELS = {
  pending: { label: 'Pending', color: '#9ca3af' },
  included: { label: 'In batch', color: '#2563eb' },
  confirmed: { label: 'On-chain', color: '#16a34a' },
  skipped: { label: 'Null-anchor', color: '#9ca3af' },
  failed: { label: 'Failed', color: '#dc2626' },
};

const shortHash = (h) => (h ? `${h.slice(0, 10)}…${h.slice(-6)}` : '—');

const ReputationDashboard = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [account, setAccount] = useState(null);
  const [events, setEvents] = useState([]);
  const [batches, setBatches] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [config, setConfig] = useState(null);

  const [submitPassword, setSubmitPassword] = useState('');
  const [submitScope, setSubmitScope] = useState('');
  const [submitBits, setSubmitBits] = useState(null);
  const [busy, setBusy] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [acct, evts, bs, lb, cfg] = await Promise.all([
        reputationApi.getMyAccount(),
        reputationApi.getMyEvents(50),
        reputationApi.getRecentBatches(),
        reputationApi.getLeaderboard(10),
        reputationApi.getConfig(),
      ]);
      setAccount(acct);
      setEvents(evts || []);
      setBatches(bs || []);
      setLeaderboard(lb || []);
      setConfig(cfg);
      setError(null);
    } catch (err) {
      console.error('Reputation: load failed', err);
      setError('Failed to load reputation state. Make sure you are signed in.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const liveBits = useMemo(() => {
    if (submitBits != null) return submitBits;
    if (!submitPassword) return 0;
    return estimateEntropyBits(submitPassword);
  }, [submitPassword, submitBits]);

  const onSubmitProof = async (e) => {
    e.preventDefault();
    if (!submitPassword || !submitScope) {
      setSubmitResult({ ok: false, message: 'Password and scope are required.' });
      return;
    }
    if (!user || (user.id == null && user.user_id == null)) {
      setSubmitResult({ ok: false, message: 'Cannot determine user id.' });
      return;
    }
    setBusy(true);
    setSubmitResult(null);
    try {
      const userId = user.id ?? user.user_id;
      const commitment = commitmentForReputation(submitPassword, submitScope);
      const bits = submitBits ?? estimateEntropyBits(submitPassword);
      const bindingHash = computeBindingHash({
        commitment,
        claimedBits: bits,
        userId,
      });
      const resp = await reputationApi.submitProof({
        scopeId: submitScope,
        commitment,
        claimedEntropyBits: bits,
        bindingHash,
      });
      setSubmitResult({
        ok: !!resp.accepted,
        message: resp.accepted
          ? `Accepted: +${resp.event?.score_delta || 0} score, +${resp.event?.tokens_delta || 0} tokens.`
          : `Rejected: ${resp.error || 'see server log'}`,
      });
      setSubmitPassword('');
      await loadAll();
    } catch (err) {
      console.error('Reputation submit failed', err);
      setSubmitResult({ ok: false, message: err?.response?.data?.detail || err.message });
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div style={panelStyle}>
        <h2 style={{ margin: 0 }}>Reputation Network</h2>
        <p style={{ color: '#6b7280' }}>Loading reputation state…</p>
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2 style={{ margin: 0 }}>Reputation Network</h2>
        <Link to="/" style={{ fontSize: 13, color: '#6b7280' }}>← back to vault</Link>
      </div>
      <p style={{ margin: '0.35rem 0 1rem', color: '#4b5563', fontSize: 14, lineHeight: 1.5 }}>
        Earn reputation by proving your passwords are strong — without ever revealing them.
        Proofs are batched into a Merkle root and{' '}
        {config?.adapter === 'arbitrum' ? (
          <strong>anchored on Arbitrum via the existing CommitmentRegistry contract.</strong>
        ) : (
          <strong>queued for on-chain anchoring (currently using the null adapter).</strong>
        )}
      </p>

      {error && (
        <div style={{ ...chip('#dc2626'), marginBottom: '0.75rem' }}>
          <div style={{ ...chipLabel, color: '#dc2626' }}>Error</div>
          <div style={{ fontSize: 13 }}>{error}</div>
        </div>
      )}

      <div style={chipRow}>
        <div style={chip('#16a34a')}>
          <div style={chipLabel}>Score</div>
          <div style={chipValue}>{account?.score ?? 0}</div>
        </div>
        <div style={chip('#0891b2')}>
          <div style={chipLabel}>Tokens</div>
          <div style={chipValue}>{account?.tokens ?? 0}</div>
        </div>
        <div style={chip('#7B68EE')}>
          <div style={chipLabel}>Accepted</div>
          <div style={chipValue}>{account?.proofs_accepted ?? 0}</div>
        </div>
        <div style={chip('#dc2626')}>
          <div style={chipLabel}>Rejected</div>
          <div style={chipValue}>{account?.proofs_rejected ?? 0}</div>
        </div>
        <div style={chip('#9ca3af')}>
          <div style={chipLabel}>Anchor adapter</div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, textTransform: 'capitalize' }}>
            {config?.adapter || 'null'}
          </div>
        </div>
      </div>

      <h3 style={sectionHeading}>Submit a new proof</h3>
      <p style={{ fontSize: 13, color: '#6b7280', marginTop: 0 }}>
        Enter a password and a scope identifier (e.g. the vault-item UUID). The plaintext
        never leaves your browser — we derive a Pedersen commitment, estimate entropy, and
        bind them to your user id before submission.
      </p>
      <form onSubmit={onSubmitProof} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>
          Scope id
          <input
            style={inputStyle}
            value={submitScope}
            onChange={(e) => setSubmitScope(e.target.value)}
            placeholder="e.g. vault-item-uuid"
          />
        </label>
        <label style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>
          Password (kept client-side)
          <input
            type="password"
            style={inputStyle}
            value={submitPassword}
            onChange={(e) => setSubmitPassword(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>
          Claimed entropy bits{' '}
          <span style={{ fontWeight: 400, color: '#6b7280' }}>
            (auto: {estimateEntropyBits(submitPassword)} bits)
          </span>
          <input
            type="number"
            min={0}
            max={256}
            style={inputStyle}
            value={submitBits ?? ''}
            onChange={(e) => setSubmitBits(e.target.value === '' ? null : Number(e.target.value))}
            placeholder={String(estimateEntropyBits(submitPassword))}
          />
        </label>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button type="submit" style={primaryBtn} disabled={busy}>
            {busy ? 'Submitting…' : `Submit (${liveBits} bits)`}
          </button>
        </div>
      </form>
      {submitResult && (
        <div
          style={{
            marginTop: 12,
            padding: '0.75rem 1rem',
            borderRadius: 6,
            background: submitResult.ok ? '#e7f7ed' : '#fdebec',
            border: `1px solid ${submitResult.ok ? '#2da764' : '#c33b3b'}`,
            fontSize: 13,
          }}
        >
          {submitResult.message}
        </div>
      )}

      <h3 style={sectionHeading}>Recent events</h3>
      {events.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 13 }}>No events yet. Submit a proof to get started.</p>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>When</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Score</th>
              <th style={thStyle}>Tokens</th>
              <th style={thStyle}>Anchor</th>
              <th style={thStyle}>Note</th>
            </tr>
          </thead>
          <tbody>
            {events.slice(0, 15).map((evt) => {
              const label = EVENT_LABELS[evt.event_type] || { label: evt.event_type, color: '#6b7280' };
              const anchor = ANCHOR_LABELS[evt.anchor_status] || { label: evt.anchor_status, color: '#6b7280' };
              return (
                <tr key={evt.id}>
                  <td style={tdStyle}>{new Date(evt.created_at).toLocaleString()}</td>
                  <td style={{ ...tdStyle, color: label.color, fontWeight: 600 }}>{label.label}</td>
                  <td style={tdStyle}>{evt.score_delta > 0 ? `+${evt.score_delta}` : evt.score_delta}</td>
                  <td style={tdStyle}>{evt.tokens_delta > 0 ? `+${evt.tokens_delta}` : evt.tokens_delta}</td>
                  <td style={{ ...tdStyle, color: anchor.color }}>{anchor.label}</td>
                  <td style={{ ...tdStyle, color: '#6b7280' }}>{evt.note}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <h3 style={sectionHeading}>Anchor batches</h3>
      {batches.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 13 }}>No batches yet.</p>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Created</th>
              <th style={thStyle}>Adapter</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Size</th>
              <th style={thStyle}>Merkle root</th>
              <th style={thStyle}>Tx hash</th>
              <th style={thStyle}>Block</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.id}>
                <td style={tdStyle}>{new Date(b.created_at).toLocaleString()}</td>
                <td style={tdStyle}>{b.adapter}</td>
                <td style={tdStyle}>{b.status}</td>
                <td style={tdStyle}>{b.batch_size}</td>
                <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{shortHash(b.merkle_root)}</td>
                <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{b.tx_hash ? shortHash(b.tx_hash) : '—'}</td>
                <td style={tdStyle}>{b.block_number || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={sectionHeading}>Leaderboard</h3>
      {leaderboard.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 13 }}>Empty.</p>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>#</th>
              <th style={thStyle}>User</th>
              <th style={thStyle}>Score</th>
              <th style={thStyle}>Tokens</th>
              <th style={thStyle}>Accepted</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((row) => (
              <tr key={`${row.rank}-${row.user_id}`}>
                <td style={tdStyle}>{row.rank}</td>
                <td style={tdStyle}>{row.username || `user#${row.user_id}`}</td>
                <td style={tdStyle}>{row.score}</td>
                <td style={tdStyle}>{row.tokens}</td>
                <td style={tdStyle}>{row.proofs_accepted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ReputationDashboard;
