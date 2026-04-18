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

const CircleSetup = () => {
  const [circles, setCircles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [masterSecret, setMasterSecret] = useState('');
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
      await ApiService.socialRecovery.createCircle({
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
      setMasterSecret('');
      setVouchers([EMPTY_VOUCHER(), EMPTY_VOUCHER(), EMPTY_VOUCHER()]);
      await loadCircles();
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
