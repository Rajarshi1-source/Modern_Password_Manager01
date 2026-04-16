/**
 * ZK Session Join page (Phase 1b).
 *
 * An invitee lands here via `/security/zk-sessions/join/:token`. We:
 *   1. Resolve the token against /api/zk/sessions/join/:token/ — this binds
 *      the participant slot to the authenticated user (first touch) and
 *      returns the session's reference commitment (base64) so the client can
 *      produce a proof against it.
 *   2. Ask for a password and let the invitee pick one of their own local
 *      commitments (or register a fresh one derived from the password).
 *   3. Reconstruct the local Pedersen commitment, sanity-check it matches
 *      their stored commitment, produce a Schnorr equality proof against the
 *      reference commitment, and submit it.
 *   4. Display the verification result.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import zkProof, {
  getProvider,
  toBase64,
  fromBase64,
  zkProofApi,
  sessionsApi,
} from '../../services/zkProof';

const panelStyle = {
  maxWidth: 640,
  margin: '2rem auto',
  padding: '1.5rem 1.75rem',
  background: '#ffffff',
  border: '1px solid #e1e4ea',
  borderRadius: 10,
  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
};
const headingStyle = { fontSize: 22, margin: 0, color: '#1f2937' };
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
  marginTop: '1.1rem',
  padding: '0.65rem 1.4rem',
  borderRadius: 6,
  border: 'none',
  background: '#7B68EE',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
};

const ZKSessionJoinPage = () => {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [commitments, setCommitments] = useState([]);
  const [password, setPassword] = useState('');
  const [selectedCommitment, setSelectedCommitment] = useState('');
  const [bootstrapScopeId, setBootstrapScopeId] = useState('');
  const [mode, setMode] = useState('existing'); // 'existing' | 'bootstrap'

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const [joinInfo, myCommitments] = await Promise.all([
        sessionsApi.resolveInvite(token),
        zkProofApi.listCommitments(),
      ]);
      setInfo(joinInfo);
      setCommitments(myCommitments);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        detail ||
          err.message ||
          'Failed to resolve invite. The link may have expired or been revoked.',
      );
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const compatibleCommitments = useMemo(() => {
    if (!info) return [];
    return commitments.filter((c) => c.scheme === info.scheme);
  }, [commitments, info]);

  const handleSubmit = useCallback(async () => {
    if (!info) return;
    setError('');
    setResult(null);
    if (!password) {
      setError('Enter the shared password. It never leaves your browser.');
      return;
    }

    setBusy(true);
    try {
      const provider = getProvider(info.scheme);
      const refBytes = fromBase64(info.reference_commitment_b64);

      let participantCommitmentId = selectedCommitment;
      let participantCommitmentBytes = null;
      let scopeIdUsed = '';

      if (mode === 'existing') {
        if (!selectedCommitment) {
          setError('Pick a local commitment to prove equality from.');
          setBusy(false);
          return;
        }
        const detail = await zkProofApi.getCommitment(selectedCommitment);
        participantCommitmentBytes = fromBase64(detail.commitment);
        scopeIdUsed = detail.scope_id;
      } else {
        if (!bootstrapScopeId) {
          setError('Provide a scope id (e.g. your vault item ID) to register a commitment under.');
          setBusy(false);
          return;
        }
        scopeIdUsed = bootstrapScopeId;
        const bytes = provider.commitFromPassword(password, bootstrapScopeId);
        const registered = await zkProof.commitAndRegister({
          password,
          itemId: bootstrapScopeId,
          scopeType: 'vault_item',
          scheme: info.scheme,
        });
        participantCommitmentId = registered.id;
        participantCommitmentBytes = bytes;
      }

      // Rebuild our local (m, r) from the password and scope_id so we can
      // actually produce a Schnorr equality proof. If the commitment stored
      // server-side was derived differently (e.g. using a different password),
      // the recomputed bytes won't match and we abort before hitting the
      // network.
      const m = provider.deriveScalarFromPassword(password, scopeIdUsed);
      const r = provider.deriveBlinding(password, scopeIdUsed);
      const localPoint = provider.commit(m, r);
      const localBytes = provider.encodePoint(localPoint);

      if (toBase64(localBytes) !== toBase64(participantCommitmentBytes)) {
        setError(
          'Locally reconstructed commitment does not match your stored commitment. The password is probably different from the one used when the commitment was registered.',
        );
        setBusy(false);
        return;
      }

      // Derive (m_ref, r_ref). We don't have r_ref (that's held by the session
      // owner), so we use the "two commitments hide the same m" Schnorr on the
      // difference r - r_ref; Chaum-Pedersen needs both blindings. We instead
      // require the invitee to know the *reference* itemId too — it's part of
      // the join payload. m is derived from (password, scope_id) on each side
      // independently; equality in Pedersen terms requires both blindings. To
      // keep this a true equality proof (and not just "I can open my own
      // commitment"), we use the provider's equality proof assuming BOTH
      // blindings come from the same deterministic (password, scope_id)
      // schedule — the reference's scope_id is sent in the join payload, so
      // the invitee recomputes r_ref from the shared password + reference
      // scope_id. Knowledge of that password is what we're proving anyway.
      const rRef = provider.deriveBlinding(password, info.reference_scope_id);
      const mRef = provider.deriveScalarFromPassword(password, info.reference_scope_id);
      const refPoint = provider.commit(mRef, rRef);
      const refEncoded = provider.encodePoint(refPoint);
      if (toBase64(refEncoded) !== toBase64(refBytes)) {
        setError(
          "Your password does not open the session's reference commitment — either the shared password is different, or the session owner has rotated it.",
        );
        setBusy(false);
        return;
      }

      const { T, s } = provider.proveEquality(refPoint, localPoint, rRef, r);

      const response = await sessionsApi.submitSessionProof({
        invite_token: token,
        participant_commitment_id: participantCommitmentId,
        proof_T_b64: toBase64(T),
        proof_s_b64: toBase64(s),
      });
      setResult(response);
      // Refresh the info + commitment list so status badge updates.
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Proof submission failed.');
    } finally {
      setBusy(false);
    }
  }, [info, password, selectedCommitment, bootstrapScopeId, mode, token, load]);

  if (error && !info) {
    return (
      <div style={panelStyle}>
        <h2 style={headingStyle}>ZK session invite</h2>
        <p style={{ ...subheadingStyle, color: '#b91c1c' }}>{error}</p>
        <Link to="/security/zk-sessions">Back to sessions</Link>
      </div>
    );
  }

  if (!info) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Resolving invite…</div>;
  }

  const alreadyVerified = info.status === 'verified';

  return (
    <div style={panelStyle}>
      <h2 style={headingStyle}>Join ZK session</h2>
      <p style={subheadingStyle}>
        You have been invited to prove that you hold the same secret as the session owner. The
        password you enter never leaves this browser — only a zero-knowledge proof is sent to
        the server.
      </p>

      <div style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: 6, fontSize: 13 }}>
        <div><strong>Session:</strong> {info.title || '(untitled)'}</div>
        {info.description && <div style={{ marginTop: 4 }}>{info.description}</div>}
        <div style={{ marginTop: 4, color: '#6b7280' }}>
          Scheme: <code>{info.scheme}</code> · reference scope: {info.reference_scope_type}:{' '}
          <code>{info.reference_scope_id}</code> · expires {new Date(info.expires_at).toLocaleString()}
        </div>
        <div style={{ marginTop: 4, color: '#6b7280' }}>Status: <strong>{info.status}</strong></div>
      </div>

      {alreadyVerified && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem 1rem',
          background: '#e7f7ed',
          border: '1px solid #2da764',
          borderRadius: 6,
          fontSize: 14,
          color: '#166534',
        }}>
          This invite has already been verified. No further action needed.
        </div>
      )}

      {!alreadyVerified && (
        <>
          <label style={labelStyle}>
            Shared password
            <input
              type="password"
              style={inputStyle}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="off"
            />
          </label>

          <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
            <label style={{ fontSize: 13 }}>
              <input
                type="radio"
                checked={mode === 'existing'}
                onChange={() => setMode('existing')}
              />{' '}
              Use one of my commitments
            </label>
            <label style={{ fontSize: 13 }}>
              <input
                type="radio"
                checked={mode === 'bootstrap'}
                onChange={() => setMode('bootstrap')}
              />{' '}
              Register a new commitment now
            </label>
          </div>

          {mode === 'existing' && (
            <label style={labelStyle}>
              Local commitment
              <select
                style={selectStyle}
                value={selectedCommitment}
                onChange={(e) => setSelectedCommitment(e.target.value)}
              >
                <option value="">— pick —</option>
                {compatibleCommitments.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.scope_type}: {c.scope_id}
                  </option>
                ))}
              </select>
            </label>
          )}

          {mode === 'bootstrap' && (
            <label style={labelStyle}>
              Scope ID for new commitment
              <input
                type="text"
                style={inputStyle}
                value={bootstrapScopeId}
                onChange={(e) => setBootstrapScopeId(e.target.value)}
                placeholder="e.g. vault-item-uuid-on-your-side"
              />
            </label>
          )}

          <button
            type="button"
            style={primaryButtonStyle}
            disabled={busy}
            onClick={handleSubmit}
          >
            {busy ? 'Generating proof…' : 'Submit proof'}
          </button>
        </>
      )}

      {error && (
        <div style={{
          marginTop: '1rem',
          padding: '0.6rem 0.9rem',
          borderRadius: 6,
          background: '#fdebec',
          border: '1px solid #c33b3b',
          color: '#991b1b',
          fontSize: 13,
        }}>{error}</div>
      )}

      {result && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem 1rem',
          background: result.verified ? '#e7f7ed' : '#fdebec',
          border: `1px solid ${result.verified ? '#2da764' : '#c33b3b'}`,
          borderRadius: 6,
          fontSize: 14,
          color: '#1f2937',
        }}>
          <strong>{result.verified ? '✔ Verified' : '✘ Not verified'}</strong>
          <div style={{ marginTop: 4, color: '#4b5563', fontSize: 12 }}>
            Attempt: <code>{result.attempt_id}</code>
          </div>
        </div>
      )}
    </div>
  );
};

export default ZKSessionJoinPage;
