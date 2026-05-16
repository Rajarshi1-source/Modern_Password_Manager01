import React, { useCallback, useEffect, useState } from 'react';
import ApiService from '../../../services/api';
import './CircleSetup.css';

const EMPTY_VOUCHER = () => ({
  display_name: '',
  email: '',
  did_string: '',
  ed25519_public_key: '',
  relationship_label: '',
  vouch_weight: 1,
  stake_amount: 0,
});

const statusBadge = (status) => {
  const map = {
    active: '#28a745',
    pending: '#ffc107',
    revoked: '#dc3545',
    draft: '#6c757d',
  };
  return map[status] || '#6c757d';
};

/**
 * Guardian-circle management page. Used in two routes:
 *
 *   1. Legacy passkey recovery (/recovery/social/circles): the user
 *      types a master secret + voucher list and the page manages
 *      the full create/list/revoke workflow.
 *
 *   2. Layered Recovery Mesh tier-2 enroll (in `SocialMeshDEKEnroll`):
 *      the parent has ALREADY generated a 32-byte `recovery_seed`
 *      and wrapped the vault DEK under it; this component is then
 *      composed to split THAT same seed across guardians.
 *      `secretHex` is supplied, the master-secret input is hidden,
 *      and on successful create we hand the `circle_id` (the
 *      recovery_setup_id) back via `onComplete(id)` so the parent
 *      can PATCH it into the wdek factor row's meta.
 *
 * Optional props default the component to the legacy management
 * behavior so back-compat is preserved for the existing route.
 *
 * @param {object} [props]
 * @param {string} [props.secretHex]
 *   Pre-filled master secret (hex). When present the input is
 *   hidden and the value is used verbatim. When absent the user
 *   types it (legacy flow).
 * @param {string} [props.secretType]
 *   Informational — surfaces "vault_dek_seed" vs the implicit
 *   legacy "passkey_private_key". Not currently sent to the
 *   server; the existing createCircle endpoint doesn't yet
 *   accept a secret_type discriminator.
 * @param {(circleId: string) => void} [props.onComplete]
 *   Invoked with the server-issued `circle_id` after a successful
 *   create. Tier-2 wraps this in a PATCH to the wdek factor row's
 *   factor_meta so recovery-side code can locate the setup. When
 *   absent, the legacy flow just refreshes the local circle list
 *   and re-renders.
 */
const CircleSetup = ({ secretHex, secretType, onComplete } = {}) => {
  const [circles, setCircles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // When secretHex is supplied (tier-2 mode), use it verbatim and
  // hide the manual-entry field. We never let the parent's value
  // be re-typed — losing it would mean the parent's wdek envelope
  // (already wrapped under that exact seed) becomes orphaned.
  const externallyControlledSecret = typeof secretHex === 'string' && secretHex.length > 0;
  const [masterSecret, setMasterSecret] = useState(
    externallyControlledSecret ? secretHex : '',
  );
  const [threshold, setThreshold] = useState(3);
  const [minStake, setMinStake] = useState(0);
  const [cooldown, setCooldown] = useState(24);
  const [vouchers, setVouchers] = useState([EMPTY_VOUCHER(), EMPTY_VOUCHER(), EMPTY_VOUCHER()]);

  const loadCircles = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await ApiService.socialRecovery.listCircles();
      setCircles(resp.data || []);
      setError(null);
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to load circles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCircles();
  }, [loadCircles]);

  const addVoucher = () => setVouchers((v) => [...v, EMPTY_VOUCHER()]);
  const removeVoucher = (idx) =>
    setVouchers((v) => (v.length > 2 ? v.filter((_, i) => i !== idx) : v));

  const updateVoucher = (idx, field, value) => {
    setVouchers((v) => {
      const next = [...v];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError(null);

    // 🔴 ZK GUARD — tier-2 social-mesh DEK enrollment cannot use
    // the legacy `/api/social-recovery/circles/` endpoint.
    //
    // That endpoint takes `master_secret_hex` as plaintext and
    // performs the Shamir split + per-guardian Kyber wrap
    // SERVER-SIDE (see
    // password_manager/social_recovery/services/circle_service.py:
    // ~L116-L121). For the legacy passkey-recovery flow that's
    // tolerated because the secret being split is a passkey
    // private key the server already holds.
    //
    // In tier-2 mode (`externallyControlledSecret === true`) the
    // secret is the freshly-generated 32-byte recovery seed that
    // wraps the vault DEK. Letting the server see that seed AND
    // the wrapped factor blob (which it stores) collapses the
    // zero-knowledge property — the server could unwrap the DEK
    // and read the entire vault. That is exactly the situation
    // the layered-recovery design exists to prevent.
    //
    // The correct architecture is client-side Shamir + per-
    // guardian Kyber, then POST only the encrypted shards. That
    // pipeline doesn't exist yet (it's the "client-side share
    // split" follow-up tracked separately from this PR), so we
    // hard-refuse in tier-2 mode rather than silently committing
    // a ZK violation. The tier-2 enroll route stays unlinked
    // from the main UI in the meantime.
    if (externallyControlledSecret) {
      setError(
        'Tier-2 social-mesh DEK enrollment is not yet available. '
        + 'The current /api/social-recovery/circles/ endpoint performs '
        + 'the Shamir split server-side, which would expose your vault '
        + 'recovery seed to the server. A client-side split + Kyber '
        + 'wrap pipeline is required before this flow can be enabled; '
        + 'tracked as a follow-up to #233. Your wdek factor row from '
        + 'step (1) of enrollment remains valid for other recovery '
        + 'tiers; you can revoke it from /settings/security if you '
        + 'do not want it lingering.',
      );
      return;
    }

    if (!/^[0-9a-fA-F]+$/.test(masterSecret) || masterSecret.length < 32) {
      setError('Master secret must be a hex string of at least 32 chars.');
      return;
    }
    if (threshold > vouchers.length) {
      setError(`Threshold (${threshold}) cannot exceed voucher count (${vouchers.length}).`);
      return;
    }
    const invalid = vouchers.find(
      (v) =>
        !v.ed25519_public_key ||
        !(v.email || v.did_string)
    );
    if (invalid) {
      setError('Each voucher requires an Ed25519 public key and either email or DID.');
      return;
    }

    setSubmitting(true);
    try {
      const resp = await ApiService.socialRecovery.createCircle({
        master_secret_hex: masterSecret,
        threshold: Number(threshold),
        min_total_stake: Number(minStake),
        cooldown_hours: Number(cooldown),
        vouchers: vouchers.map((v) => ({
          ...v,
          vouch_weight: Number(v.vouch_weight) || 1,
          stake_amount: Number(v.stake_amount) || 0,
        })),
      });
      setShowForm(false);
      // Only clear the master secret in legacy / unmanaged mode.
      // In tier-2 mode the parent owns the value and clearing here
      // would also clear the parent's bound reference (since we
      // initialized state from props at mount); leave it alone so
      // the parent can finish its own cleanup after onComplete.
      if (!externallyControlledSecret) {
        setMasterSecret('');
      }
      setVouchers([EMPTY_VOUCHER(), EMPTY_VOUCHER(), EMPTY_VOUCHER()]);
      await loadCircles();
      // Tier-2 hand-off: surface the new circle's id so the
      // caller can PATCH it back onto the wdek factor row's
      // factor_meta (recovery_setup_id). The server's
      // createCircle response shape exposes the id at
      // `circle_id` (mirroring the model field used elsewhere in
      // this component, e.g. circle.circle_id at L318).
      if (typeof onComplete === 'function') {
        const circleId = resp?.data?.circle_id;
        onComplete(circleId);
      }
    } catch (err) {
      setError(ApiService.handleError(err).error || 'Failed to create circle.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="circle-setup">
      <div className="circle-setup-header">
        <div>
          <h1>🛡️ Social Recovery Circles</h1>
          <p className="subtitle">
            Manage your guardian network. Recovery requires M-of-N vouchers to
            attest before your secret can be reconstructed.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowForm((s) => !s)}
          disabled={submitting}
        >
          {showForm ? 'Cancel' : '+ New Circle'}
        </button>
      </div>

      {error && <div className="error-banner">❌ {error}</div>}

      {showForm && (
        <form className="circle-form" onSubmit={handleCreate}>
          <h3>Create Recovery Circle</h3>

          <div className="form-grid">
            {externallyControlledSecret ? (
              // Tier-2 mode: the parent has already wrapped the
              // vault DEK under THIS exact seed and POSTed the wdek
              // row. Letting the user retype it would silently
              // orphan that envelope. Hide the field and surface a
              // read-only badge so the user knows we have it.
              <div className="form-group full">
                <label>Recovery Seed</label>
                <p className="muted-note" role="alert">
                  <strong>⚠ Not yet available.</strong> Tier-2
                  social-mesh DEK enrollment is gated until the
                  client-side Shamir + Kyber pipeline lands —
                  the current backend endpoint would perform the
                  split server-side, breaking the zero-knowledge
                  property for your vault seed. Your wdek factor
                  row from step (1) is unaffected; submitting
                  this form will surface a clear error rather
                  than commit anything. (Tracked as a follow-up
                  to #233.)
                </p>
              </div>
            ) : (
              <div className="form-group full">
                <label>Master Secret (hex)</label>
                <input
                  type="text"
                  value={masterSecret}
                  onChange={(e) => setMasterSecret(e.target.value.trim())}
                  placeholder="64+ hex chars — generated from your vault key"
                  autoComplete="off"
                  spellCheck="false"
                  required
                />
                <small>Generated client-side from your vault KEK. Never sent in plaintext after sharing.</small>
              </div>
            )}

            <div className="form-group">
              <label>Threshold (M)</label>
              <input
                type="number"
                min="2"
                max="10"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Min Total Stake</label>
              <input
                type="number"
                min="0"
                value={minStake}
                onChange={(e) => setMinStake(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label>Cooldown (hours)</label>
              <input
                type="number"
                min="0"
                max="720"
                value={cooldown}
                onChange={(e) => setCooldown(e.target.value)}
              />
            </div>
          </div>

          <h4>Vouchers ({vouchers.length} / N)</h4>
          <div className="vouchers-list">
            {vouchers.map((v, idx) => (
              <div className="voucher-card" key={idx}>
                <div className="voucher-head">
                  <strong>Voucher #{idx + 1}</strong>
                  {vouchers.length > 2 && (
                    <button
                      type="button"
                      className="btn-link danger"
                      onClick={() => removeVoucher(idx)}
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="form-grid">
                  <div className="form-group">
                    <label>Display Name</label>
                    <input
                      type="text"
                      value={v.display_name}
                      onChange={(e) =>
                        updateVoucher(idx, 'display_name', e.target.value)
                      }
                      placeholder="Alice"
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      value={v.email}
                      onChange={(e) =>
                        updateVoucher(idx, 'email', e.target.value)
                      }
                      placeholder="alice@example.com"
                    />
                  </div>
                  <div className="form-group full">
                    <label>DID (optional if email given)</label>
                    <input
                      type="text"
                      value={v.did_string}
                      onChange={(e) =>
                        updateVoucher(idx, 'did_string', e.target.value)
                      }
                      placeholder="did:web:example.com:alice"
                    />
                  </div>
                  <div className="form-group full">
                    <label>Ed25519 Public Key (hex)</label>
                    <input
                      type="text"
                      value={v.ed25519_public_key}
                      onChange={(e) =>
                        updateVoucher(idx, 'ed25519_public_key', e.target.value.trim())
                      }
                      placeholder="64 hex chars"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Relationship</label>
                    <input
                      type="text"
                      value={v.relationship_label}
                      onChange={(e) =>
                        updateVoucher(idx, 'relationship_label', e.target.value)
                      }
                      placeholder="family / colleague"
                    />
                  </div>
                  <div className="form-group">
                    <label>Vouch Weight</label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      value={v.vouch_weight}
                      onChange={(e) =>
                        updateVoucher(idx, 'vouch_weight', e.target.value)
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label>Stake Amount</label>
                    <input
                      type="number"
                      min="0"
                      value={v.stake_amount}
                      onChange={(e) =>
                        updateVoucher(idx, 'stake_amount', e.target.value)
                      }
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="form-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={addVoucher}
            >
              + Add Voucher
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create Circle'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="placeholder">Loading circles...</div>
      ) : circles.length === 0 ? (
        <div className="placeholder empty">
          <h3>No recovery circles yet</h3>
          <p>Start by creating one and inviting trusted guardians.</p>
        </div>
      ) : (
        <div className="circle-grid">
          {circles.map((circle) => (
            <article className="circle-card" key={circle.circle_id}>
              <header>
                <h3>Circle {String(circle.circle_id).slice(0, 8)}…</h3>
                <span
                  className="status-pill"
                  style={{ background: statusBadge(circle.status) }}
                >
                  {circle.status}
                </span>
              </header>
              <ul className="meta">
                <li>Threshold: <b>{circle.threshold}-of-{circle.total_vouchers}</b></li>
                <li>Min Stake: {circle.min_total_stake}</li>
                <li>Cooldown: {circle.cooldown_hours}h</li>
              </ul>
              <div className="voucher-summary">
                <h4>Vouchers</h4>
                <ul>
                  {(circle.vouchers || []).map((v) => (
                    <li key={v.voucher_id}>
                      <span className="name">
                        {v.display_name || v.email || v.did_string || 'voucher'}
                      </span>
                      <span
                        className="status-chip"
                        style={{ background: statusBadge(v.status) }}
                      >
                        {v.status}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};

export default CircleSetup;
