/**
 * ZK Multi-Party Verification Sessions dashboard (Phase 1b).
 *
 * The session owner lists their sessions, opens a new "ceremony" against one
 * of their existing commitments, and invites other users (via one-time
 * tokens) to prove they hold the same secret. Invitees run through the
 * dedicated join page (`/security/zk-sessions/join/:token`); status updates
 * here via polling.
 *
 * The owner never sees any invitee's password or commitment bytes — only
 * whether each participant's Schnorr equality proof verified against the
 * shared reference commitment.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { sessionsApi, zkProofApi } from '../../services/zkProof';

const panelStyle = {
  maxWidth: 960,
  margin: '2rem auto',
  padding: '1.5rem 1.75rem',
  background: '#ffffff',
  border: '1px solid #e1e4ea',
  borderRadius: 10,
  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
};

const headingStyle = { fontSize: 24, margin: 0, color: '#1f2937' };
const subheadingStyle = {
  margin: '0.35rem 0 1.25rem',
  color: '#4b5563',
  fontSize: 14,
  lineHeight: 1.5,
};
const labelStyle = {
  display: 'block',
  fontSize: 13,
  color: '#374151',
  marginTop: '0.8rem',
  fontWeight: 600,
};
const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.55rem 0.65rem',
  marginTop: '0.3rem',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  fontSize: 14,
};
const selectStyle = { ...inputStyle, background: '#fff' };
const primaryButtonStyle = {
  padding: '0.55rem 1.2rem',
  borderRadius: 6,
  border: 'none',
  background: '#7B68EE',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
};
const secondaryButtonStyle = {
  padding: '0.4rem 0.85rem',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  background: '#f8fafc',
  color: '#1f2937',
  fontSize: 13,
  cursor: 'pointer',
};
const dangerButtonStyle = {
  ...secondaryButtonStyle,
  borderColor: '#fca5a5',
  color: '#b91c1c',
};

const STATUS_COLORS = {
  open: { bg: '#e0f2fe', border: '#0284c7', fg: '#075985' },
  closed: { bg: '#f1f5f9', border: '#64748b', fg: '#334155' },
  expired: { bg: '#fef3c7', border: '#b45309', fg: '#78350f' },
  pending: { bg: '#fef3c7', border: '#b45309', fg: '#78350f' },
  joined: { bg: '#e0f2fe', border: '#0369a1', fg: '#075985' },
  verified: { bg: '#e7f7ed', border: '#2da764', fg: '#166534' },
  failed: { bg: '#fdebec', border: '#c33b3b', fg: '#991b1b' },
  revoked: { bg: '#f1f5f9', border: '#64748b', fg: '#334155' },
};

const StatusBadge = ({ status }) => {
  const c = STATUS_COLORS[status] || STATUS_COLORS.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.15rem 0.55rem',
        fontSize: 12,
        fontWeight: 600,
        background: c.bg,
        border: `1px solid ${c.border}`,
        color: c.fg,
        borderRadius: 999,
        textTransform: 'uppercase',
        letterSpacing: 0.5,
      }}
    >
      {status}
    </span>
  );
};

const buildInviteUrl = (token) => {
  if (typeof window === 'undefined') return `/security/zk-sessions/join/${token}`;
  return `${window.location.origin}/security/zk-sessions/join/${token}`;
};

const ZKSessionsDashboard = () => {
  const [sessions, setSessions] = useState([]);
  const [commitments, setCommitments] = useState([]);
  const [myInvites, setMyInvites] = useState([]);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const [referenceId, setReferenceId] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [expiresHours, setExpiresHours] = useState(168);

  const [inviteInputs, setInviteInputs] = useState({});
  const [copiedToken, setCopiedToken] = useState('');

  const loadAll = useCallback(async () => {
    setError('');
    try {
      const [s, c, i] = await Promise.all([
        sessionsApi.listSessions(),
        zkProofApi.listCommitments(),
        sessionsApi.listMyInvites(),
      ]);
      setSessions(s);
      setCommitments(c);
      setMyInvites(i);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load sessions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Poll while any session is open — cheap way to reflect invitee progress
  // without adding a Channels consumer for this feature.
  useEffect(() => {
    const hasOpen = sessions.some((s) => s.status === 'open');
    if (!hasOpen) return undefined;
    const id = setInterval(loadAll, 8000);
    return () => clearInterval(id);
  }, [sessions, loadAll]);

  const handleCreate = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!referenceId) {
      setError('Pick a reference commitment first.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await sessionsApi.createSession({
        reference_commitment_id: referenceId,
        title,
        description,
        expires_in_hours: Number(expiresHours) || 168,
      });
      setTitle('');
      setDescription('');
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create session.');
    } finally {
      setBusy(false);
    }
  }, [referenceId, title, description, expiresHours, loadAll]);

  const handleInvite = useCallback(async (sessionId) => {
    const fields = inviteInputs[sessionId] || {};
    setBusy(true);
    setError('');
    try {
      await sessionsApi.inviteParticipant(sessionId, {
        invited_email: fields.email || '',
        invited_label: fields.label || '',
      });
      setInviteInputs((prev) => ({ ...prev, [sessionId]: { email: '', label: '' } }));
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Invite failed.');
    } finally {
      setBusy(false);
    }
  }, [inviteInputs, loadAll]);

  const handleRevoke = useCallback(async (sessionId, participantId) => {
    if (!window.confirm('Revoke this invite? The token will stop working immediately.')) return;
    setBusy(true);
    try {
      await sessionsApi.revokeParticipant(sessionId, participantId);
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Revoke failed.');
    } finally {
      setBusy(false);
    }
  }, [loadAll]);

  const handleClose = useCallback(async (sessionId) => {
    if (!window.confirm('Close this session? Pending invites will become unusable.')) return;
    setBusy(true);
    try {
      await sessionsApi.closeSession(sessionId);
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Close failed.');
    } finally {
      setBusy(false);
    }
  }, [loadAll]);

  const handleCopy = useCallback(async (token) => {
    const url = buildInviteUrl(token);
    try {
      await navigator.clipboard.writeText(url);
      setCopiedToken(token);
      setTimeout(() => setCopiedToken((t) => (t === token ? '' : t)), 2500);
    } catch {
      window.prompt('Copy this invite URL:', url);
    }
  }, []);

  const commitmentLabel = useCallback((id) => {
    const c = commitments.find((c) => c.id === id);
    if (!c) return id;
    return `${c.scope_type}:${c.scope_id}`;
  }, [commitments]);

  const canCreate = useMemo(() => commitments.length > 0, [commitments]);

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading sessions…</div>;
  }

  return (
    <div style={panelStyle}>
      <h2 style={headingStyle}>Multi-Party ZK Verification Sessions</h2>
      <p style={subheadingStyle}>
        Open a ceremony against one of your commitments and invite others to prove,
        via Schnorr equality, that their copy of the same secret matches — without
        revealing the secret itself. Nobody, including you, ever learns the
        participants' passwords.{' '}
        <Link to="/security/zk-verify">Single-party verifier →</Link>
      </p>

      {error && (
        <div style={{
          padding: '0.6rem 0.9rem',
          marginBottom: '1rem',
          borderRadius: 6,
          background: '#fdebec',
          border: '1px solid #c33b3b',
          color: '#991b1b',
          fontSize: 13,
        }}>{error}</div>
      )}

      <section style={{ marginBottom: '2rem' }}>
        <h3 style={{ ...headingStyle, fontSize: 18, marginBottom: '0.5rem' }}>Create a session</h3>
        {!canCreate && (
          <p style={{ ...subheadingStyle, margin: 0 }}>
            You need at least one registered commitment before you can open a session. Save a
            vault item to register one automatically.
          </p>
        )}
        {canCreate && (
          <form onSubmit={handleCreate}>
            <label style={labelStyle}>
              Reference commitment
              <select
                style={selectStyle}
                value={referenceId}
                onChange={(e) => setReferenceId(e.target.value)}
                required
              >
                <option value="">— pick one of your commitments —</option>
                {commitments.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.scope_type}: {c.scope_id} ({c.scheme})
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              Title (optional)
              <input
                type="text"
                style={inputStyle}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Family shared streaming password"
                maxLength={128}
              />
            </label>
            <label style={labelStyle}>
              Description (optional)
              <textarea
                style={{ ...inputStyle, minHeight: 64 }}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Context for the invitees."
              />
            </label>
            <label style={labelStyle}>
              Expires after (hours)
              <input
                type="number"
                min={1}
                max={24 * 30}
                style={inputStyle}
                value={expiresHours}
                onChange={(e) => setExpiresHours(e.target.value)}
              />
            </label>
            <button type="submit" style={{ ...primaryButtonStyle, marginTop: '1rem' }} disabled={busy}>
              {busy ? 'Creating…' : 'Create session'}
            </button>
          </form>
        )}
      </section>

      <section>
        <h3 style={{ ...headingStyle, fontSize: 18, marginBottom: '0.5rem' }}>Your sessions</h3>
        {sessions.length === 0 && (
          <p style={{ ...subheadingStyle, margin: 0 }}>No sessions yet.</p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            style={{
              border: '1px solid #e1e4ea',
              borderRadius: 8,
              padding: '1rem',
              marginTop: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>
                  {session.title || '(untitled session)'}{' '}
                  <StatusBadge status={session.status} />
                </div>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                  Reference: {commitmentLabel(session.reference_commitment)} ·{' '}
                  {session.verified_count}/{session.participant_count} verified ·{' '}
                  expires {new Date(session.expires_at).toLocaleString()}
                </div>
              </div>
              {session.status === 'open' && (
                <button
                  style={dangerButtonStyle}
                  onClick={() => handleClose(session.id)}
                  disabled={busy}
                >
                  Close
                </button>
              )}
            </div>
            {session.description && (
              <p style={{ fontSize: 13, color: '#4b5563', marginTop: '0.4rem' }}>{session.description}</p>
            )}

            <div style={{ marginTop: '0.75rem' }}>
              {(session.participants || []).map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.45rem 0',
                    borderTop: '1px dashed #e5e7eb',
                    gap: '0.75rem',
                    fontSize: 13,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div>
                      <StatusBadge status={p.status} />{' '}
                      <strong>{p.invited_label || p.invited_email || '(unnamed)'}</strong>
                    </div>
                    {p.error_message && (
                      <div style={{ color: '#b91c1c', fontSize: 12, marginTop: 2 }}>{p.error_message}</div>
                    )}
                    {p.verified_at && (
                      <div style={{ color: '#6b7280', fontSize: 12, marginTop: 2 }}>
                        Verified {new Date(p.verified_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    {p.status !== 'revoked' && p.status !== 'verified' && (
                      <>
                        <button
                          type="button"
                          style={secondaryButtonStyle}
                          onClick={() => handleCopy(p.invite_token)}
                        >
                          {copiedToken === p.invite_token ? 'Copied!' : 'Copy invite link'}
                        </button>
                        <button
                          type="button"
                          style={dangerButtonStyle}
                          onClick={() => handleRevoke(session.id, p.id)}
                          disabled={busy}
                        >
                          Revoke
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {session.status === 'open' && (
              <div
                style={{
                  marginTop: '0.75rem',
                  padding: '0.6rem',
                  background: '#f8fafc',
                  borderRadius: 6,
                  display: 'flex',
                  gap: '0.5rem',
                  flexWrap: 'wrap',
                  alignItems: 'flex-end',
                }}
              >
                <label style={{ flex: '1 1 200px' }}>
                  <span style={{ fontSize: 12, color: '#374151', fontWeight: 600 }}>Invitee email (optional)</span>
                  <input
                    type="email"
                    style={inputStyle}
                    value={(inviteInputs[session.id] || {}).email || ''}
                    onChange={(e) =>
                      setInviteInputs((prev) => ({
                        ...prev,
                        [session.id]: { ...(prev[session.id] || {}), email: e.target.value },
                      }))
                    }
                  />
                </label>
                <label style={{ flex: '1 1 200px' }}>
                  <span style={{ fontSize: 12, color: '#374151', fontWeight: 600 }}>Label</span>
                  <input
                    type="text"
                    style={inputStyle}
                    placeholder="e.g. Alice mobile"
                    value={(inviteInputs[session.id] || {}).label || ''}
                    onChange={(e) =>
                      setInviteInputs((prev) => ({
                        ...prev,
                        [session.id]: { ...(prev[session.id] || {}), label: e.target.value },
                      }))
                    }
                  />
                </label>
                <button
                  type="button"
                  style={primaryButtonStyle}
                  onClick={() => handleInvite(session.id)}
                  disabled={busy}
                >
                  Add invite
                </button>
              </div>
            )}
          </div>
        ))}
      </section>

      <section style={{ marginTop: '2.5rem' }}>
        <h3 style={{ ...headingStyle, fontSize: 18, marginBottom: '0.5rem' }}>Invites received</h3>
        {myInvites.length === 0 && (
          <p style={{ ...subheadingStyle, margin: 0 }}>
            You haven't joined any sessions. Open an invite URL a friend sent you to get started.
          </p>
        )}
        {myInvites.map((inv) => (
          <div
            key={inv.participant_id}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0.55rem 0',
              borderBottom: '1px dashed #e5e7eb',
              gap: '0.75rem',
              fontSize: 13,
            }}
          >
            <div>
              <strong>{inv.session_title || '(untitled session)'}</strong>{' '}
              <StatusBadge status={inv.participant_status} />
              <div style={{ color: '#6b7280', fontSize: 12 }}>
                Session status: {inv.session_status} · scheme {inv.scheme}
              </div>
            </div>
            <div style={{ color: '#6b7280', fontSize: 12 }}>
              {new Date(inv.created_at).toLocaleString()}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
};

export default ZKSessionsDashboard;
