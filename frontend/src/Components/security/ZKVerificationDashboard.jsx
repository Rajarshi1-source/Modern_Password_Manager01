/**
 * Zero-Knowledge Vault Verification Dashboard.
 *
 * Lets a user prove that two of their own vault commitments hide the same
 * password without revealing the password to anyone — not the browser's
 * network layer, not the server, not even the audit log. Uses Pedersen
 * commitments + Schnorr proofs of equality on secp256k1.
 *
 * Typical flow:
 *   1. User saves a password. App.jsx hook registers a commitment under
 *      scope_type="vault_item".
 *   2. User creates a backup / imports the same password elsewhere — another
 *      commitment gets registered.
 *   3. User opens this dashboard, picks the two commitments, enters the
 *      password they *expect* both to represent, and generates a proof.
 *   4. Client recomputes both commitments locally; mismatch means wrong
 *      password OR different underlying secret. If both match, a Schnorr
 *      equality proof is generated and posted to /api/zk/verify-equality/.
 *   5. Server verifies the proof, records a ZKVerificationAttempt, returns
 *      { verified, attempt_id }.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import zkProof, {
  getProvider,
  toBase64,
  zkProofApi,
} from '../../services/zkProof';

const SCOPE_LABELS = {
  vault_item: 'Vault item',
  vault_backup: 'Vault backup',
  user_password: 'Master password',
};

const panelStyle = {
  maxWidth: 880,
  margin: '2rem auto',
  padding: '1.5rem 1.75rem',
  background: '#ffffff',
  border: '1px solid #e1e4ea',
  borderRadius: 10,
  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
};

const headingStyle = {
  fontSize: 24,
  margin: 0,
  color: '#1f2937',
};

const subheadingStyle = {
  margin: '0.35rem 0 1.25rem',
  color: '#4b5563',
  fontSize: 14,
  lineHeight: 1.5,
};

const selectStyle = {
  display: 'block',
  width: '100%',
  padding: '0.55rem 0.65rem',
  marginTop: '0.3rem',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  background: '#fff',
  fontSize: 14,
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

const resultBannerStyle = (ok) => ({
  marginTop: '1.1rem',
  padding: '0.75rem 1rem',
  borderRadius: 6,
  background: ok ? '#e7f7ed' : '#fdebec',
  border: `1px solid ${ok ? '#2da764' : '#c33b3b'}`,
  color: '#1f2937',
});

const CommitmentPicker = ({ label, value, onChange, commitments, disabledId }) => (
  <label style={{ display: 'block' }}>
    <span style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>{label}</span>
    <select
      style={selectStyle}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">— select commitment —</option>
      {commitments.map((c) => (
        <option key={c.id} value={c.id} disabled={c.id === disabledId}>
          {(SCOPE_LABELS[c.scope_type] || c.scope_type)} · {c.scope_id.slice(0, 14)}
          {c.scope_id.length > 14 ? '…' : ''} · {new Date(c.created_at).toLocaleDateString()}
        </option>
      ))}
    </select>
  </label>
);

const ZKVerificationDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [commitments, setCommitments] = useState([]);
  const [leftId, setLeftId] = useState('');
  const [rightId, setRightId] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [attempts, setAttempts] = useState([]);

  const loadCommitments = useCallback(async () => {
    setLoading(true);
    try {
      const list = await zkProofApi.listCommitments();
      setCommitments(Array.isArray(list) ? list : []);
      setError(null);
    } catch (err) {
      console.error('ZK: failed to load commitments', err);
      setError('Failed to load commitments. Make sure you are signed in.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAttempts = useCallback(async () => {
    try {
      const list = await zkProofApi.listAttempts();
      setAttempts(Array.isArray(list) ? list : []);
    } catch (err) {
      console.warn('ZK: failed to load verification history', err);
    }
  }, []);

  useEffect(() => {
    loadCommitments();
    loadAttempts();
  }, [loadCommitments, loadAttempts]);

  const handleVerify = useCallback(async () => {
    setBusy(true);
    setResult(null);
    try {
      if (!leftId || !rightId) {
        setResult({ ok: false, detail: 'Pick two different commitments.' });
        return;
      }
      if (leftId === rightId) {
        setResult({ ok: false, detail: 'Commitments must differ.' });
        return;
      }
      if (!password) {
        setResult({ ok: false, detail: 'Enter the password you expect both commitments to represent. It never leaves your browser.' });
        return;
      }

      const [left, right] = await Promise.all([
        zkProofApi.getCommitment(leftId),
        zkProofApi.getCommitment(rightId),
      ]);

      const provider = getProvider(left.scheme);
      if (left.scheme !== right.scheme) {
        setResult({ ok: false, detail: 'The two commitments use different ZK schemes. Pick commitments with matching schemes.' });
        return;
      }

      // Derive both sides locally. For the equality proof to succeed, the
      // derived (m, r) must match whatever was stored when the commitment
      // was registered — identical domain separation on both client and
      // server guarantees this is deterministic.
      const m1 = provider.deriveScalarFromPassword(password, left.scope_id);
      const m2 = provider.deriveScalarFromPassword(password, right.scope_id);
      const r1 = provider.deriveBlinding(password, left.scope_id);
      const r2 = provider.deriveBlinding(password, right.scope_id);

      const c1Point = provider.commit(m1, r1);
      const c2Point = provider.commit(m2, r2);
      const c1B64 = toBase64(provider.encodePoint(c1Point));
      const c2B64 = toBase64(provider.encodePoint(c2Point));

      if (c1B64 !== left.commitment || c2B64 !== right.commitment) {
        setResult({
          ok: false,
          detail:
            'Locally reconstructed commitments do not match the stored values. Either the password is wrong for at least one entry, or the two entries hide different passwords.',
        });
        return;
      }

      const { T, s } = provider.proveEquality(c1Point, c2Point, r1, r2);
      const response = await zkProofApi.verifyEqualityApi({
        commitment_a_id: leftId,
        commitment_b_id: rightId,
        proof_T_b64: toBase64(T),
        proof_s_b64: toBase64(s),
      });

      if (response.verified) {
        setResult({
          ok: true,
          attemptId: response.attempt_id,
          detail:
            'Verified. Both commitments provably hide the same password. Your browser produced this proof without transmitting the password.',
        });
      } else {
        setResult({
          ok: false,
          attemptId: response.attempt_id,
          detail: 'The server rejected the equality proof. The commitments do not hide the same password.',
        });
      }
      // Refresh audit log in the background.
      loadAttempts();
    } catch (err) {
      console.error('ZK verify error', err);
      setResult({ ok: false, detail: 'Verification request failed.' });
    } finally {
      setBusy(false);
    }
  }, [leftId, rightId, password, loadAttempts]);

  const downloadAudit = useCallback(() => {
    if (!result || !result.attemptId) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            scheme: zkProof.DEFAULT_SCHEME,
            commitment_a_id: leftId,
            commitment_b_id: rightId,
            verified: result.ok,
            attempt_id: result.attemptId,
            generated_at: new Date().toISOString(),
          },
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zk-verification-${result.attemptId}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result, leftId, rightId]);

  return (
    <div style={panelStyle}>
      <h1 style={headingStyle}>Zero-Knowledge Vault Verification</h1>
      <p style={subheadingStyle}>
        Prove that two vault entries hold the same password without revealing
        either one. Uses Pedersen commitments + Schnorr proofs of equality on
        secp256k1. Your password never leaves this browser.
      </p>

      {loading && <p>Loading commitments…</p>}
      {error && <p style={{ color: '#b00020' }}>{error}</p>}

      {!loading && commitments.length === 0 && !error && (
        <div
          style={{
            padding: '1rem',
            border: '1px dashed #94a3b8',
            borderRadius: 6,
            color: '#475569',
          }}
        >
          No commitments are registered for your account yet. Save a password
          in the vault — a commitment is registered automatically — then come
          back to verify backups against it.
        </div>
      )}

      {!loading && commitments.length > 0 && (
        <section>
          <div style={{ display: 'grid', gap: '0.85rem', gridTemplateColumns: '1fr 1fr' }}>
            <CommitmentPicker
              label="Commitment A"
              value={leftId}
              onChange={setLeftId}
              commitments={commitments}
              disabledId={rightId}
            />
            <CommitmentPicker
              label="Commitment B"
              value={rightId}
              onChange={setRightId}
              commitments={commitments}
              disabledId={leftId}
            />
          </div>

          <label style={{ display: 'block', marginTop: '1rem' }}>
            <span style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>
              Password (never transmitted)
            </span>
            <input
              type="password"
              style={inputStyle}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder="Enter the password you expect both entries to hold"
            />
          </label>

          <button
            type="button"
            style={{ ...primaryButtonStyle, opacity: busy ? 0.7 : 1 }}
            onClick={handleVerify}
            disabled={busy || !leftId || !rightId}
          >
            {busy ? 'Proving…' : 'Generate & verify equality proof'}
          </button>

          {result && (
            <div style={resultBannerStyle(result.ok)}>
              <strong>{result.ok ? '✓ Verified' : '✗ Not verified'}</strong>
              <p style={{ margin: '0.3rem 0 0', fontSize: 14 }}>{result.detail}</p>
              {result.attemptId && (
                <p style={{ margin: '0.4rem 0 0', fontSize: 12, color: '#4b5563' }}>
                  Audit attempt ID:{' '}
                  <code style={{ fontSize: 12 }}>{result.attemptId}</code>
                  {' · '}
                  <button
                    type="button"
                    onClick={downloadAudit}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#4f46e5',
                      cursor: 'pointer',
                      padding: 0,
                      textDecoration: 'underline',
                      fontSize: 12,
                    }}
                  >
                    download audit certificate
                  </button>
                </p>
              )}
            </div>
          )}
        </section>
      )}

      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: 16, color: '#1f2937', marginBottom: '0.5rem' }}>
          Recent verification history
        </h2>
        {attempts.length === 0 ? (
          <p style={{ fontSize: 13, color: '#6b7280' }}>No attempts yet.</p>
        ) : (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
              color: '#374151',
            }}
          >
            <thead>
              <tr style={{ textAlign: 'left', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '0.4rem 0.5rem' }}>When</th>
                <th style={{ padding: '0.4rem 0.5rem' }}>Result</th>
                <th style={{ padding: '0.4rem 0.5rem' }}>Scheme</th>
                <th style={{ padding: '0.4rem 0.5rem' }}>Attempt ID</th>
              </tr>
            </thead>
            <tbody>
              {attempts.slice(0, 20).map((a) => (
                <tr key={a.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '0.35rem 0.5rem' }}>
                    {new Date(a.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '0.35rem 0.5rem', color: a.result ? '#1f7a3a' : '#b00020' }}>
                    {a.result ? 'verified' : 'rejected'}
                  </td>
                  <td style={{ padding: '0.35rem 0.5rem' }}>{a.scheme}</td>
                  <td style={{ padding: '0.35rem 0.5rem', fontFamily: 'monospace', fontSize: 11 }}>
                    {a.id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p style={{ marginTop: '2rem', fontSize: 14 }}>
        <Link to="/security/dashboard">← Back to Security</Link>
      </p>
    </div>
  );
};

export default ZKVerificationDashboard;
