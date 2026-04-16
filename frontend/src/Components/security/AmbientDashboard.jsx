/**
 * Ambient Biometric Fusion dashboard.
 *
 * Lets the signed-in user inspect and manage their ambient-signal
 * profile:
 *   * per-signal toggles (with availability badges per surface),
 *   * named contexts ("Home", "Office") with trust + rename/delete,
 *   * recent observations timeline with structured reasons[] cloud,
 *   * "Teach me this place" (promote latest observation to a trusted
 *     context),
 *   * "Reset baseline" (privacy escape hatch).
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import { ambientApi, rotateLocalSalt } from '../../services/ambient';

const panelStyle = {
  maxWidth: 1100,
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

const chipRow = { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' };

const chip = (accent) => ({
  background: '#f9fafb',
  border: `1px solid ${accent || '#e5e7eb'}`,
  borderLeft: `4px solid ${accent || '#7B68EE'}`,
  borderRadius: 8,
  padding: '0.5rem 0.75rem',
  minWidth: 140,
  fontSize: 13,
});

const mutedText = { color: '#6b7280', fontSize: 13 };
const buttonPrimary = {
  background: '#7B68EE',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '0.45rem 0.9rem',
  fontWeight: 600,
  cursor: 'pointer',
};
const buttonGhost = {
  background: '#fff',
  color: '#374151',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '0.35rem 0.7rem',
  cursor: 'pointer',
};

const trustColor = (score) => {
  if (score >= 0.85) return '#16a34a';
  if (score >= 0.6) return '#3b82f6';
  if (score >= 0.3) return '#f59e0b';
  return '#ef4444';
};

const noveltyColor = (score) => {
  if (score >= 0.7) return '#ef4444';
  if (score >= 0.4) return '#f59e0b';
  return '#16a34a';
};

function Gauge({ label, value, colorFn }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const color = colorFn(value);
  return (
    <div style={{ minWidth: 200 }}>
      <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color }}>
          {Number.isFinite(value) ? value.toFixed(2) : '—'}
        </div>
        <div style={{ flex: 1, height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: color }} />
        </div>
      </div>
    </div>
  );
}

function ReasonPills({ reasons }) {
  if (!Array.isArray(reasons) || reasons.length === 0) return <span style={mutedText}>no reasons</span>;
  return (
    <div style={chipRow}>
      {reasons.map((r, i) => {
        let text = r.kind;
        let accent = '#7B68EE';
        if (r.kind === 'matched_context') {
          text = `matched: ${r.label}${r.trusted ? ' ✓' : ''} (d=${r.distance})`;
          accent = r.trusted ? '#16a34a' : '#3b82f6';
        } else if (r.kind === 'novel_context') {
          text = `novel context (nov=${r.novelty})`;
          accent = '#ef4444';
        } else if (r.kind === 'no_known_context') {
          text = `no match (d=${r.distance})`;
          accent = '#f59e0b';
        } else if (r.kind === 'signals_captured') {
          text = `captured: ${r.signals?.join(', ') || ''}`;
          accent = '#16a34a';
        } else if (r.kind === 'signals_missing') {
          text = `missing: ${r.signals?.join(', ') || ''}`;
          accent = '#9ca3af';
        } else if (r.kind === 'coarse_features') {
          const pairs = Object.entries(r.features || {}).map(([k, v]) => `${k}=${v}`);
          text = pairs.join(' · ');
          accent = '#6366f1';
        }
        return (
          <span key={i} style={{ ...chip(accent), minWidth: 0, padding: '0.35rem 0.6rem' }}>{text}</span>
        );
      })}
    </div>
  );
}

export default function AmbientDashboard() {
  const { isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [config, setConfig] = useState(null);
  const [contexts, setContexts] = useState([]);
  const [observations, setObservations] = useState([]);
  const [signalCfg, setSignalCfg] = useState({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [c, ctx, obs, sc] = await Promise.all([
        ambientApi.getConfig(),
        ambientApi.listContexts(),
        ambientApi.listObservations(25),
        ambientApi.getSignalConfig(),
      ]);
      setConfig(c);
      setContexts(Array.isArray(ctx) ? ctx : []);
      setObservations(Array.isArray(obs) ? obs : []);
      setSignalCfg(sc || {});
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Failed to load ambient data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    refresh();
  }, [isAuthenticated, refresh]);

  const latestObs = observations[0] || null;

  const promoteLatest = useCallback(async () => {
    if (!latestObs) return;
    const label = window.prompt('Name this place (e.g. "Home", "Office"):', 'Home');
    if (!label) return;
    try {
      await ambientApi.promoteContext({ observationId: latestObs.id, label });
      await refresh();
    } catch (err) {
      alert(err?.response?.data?.error || err.message || 'Promotion failed.');
    }
  }, [latestObs, refresh]);

  const onRename = useCallback(async (ctx) => {
    const label = window.prompt('Rename context:', ctx.label);
    if (!label || label === ctx.label) return;
    try {
      await ambientApi.renameContext({ contextId: ctx.id, label });
      await refresh();
    } catch (err) {
      alert(err?.response?.data?.error || err.message || 'Rename failed.');
    }
  }, [refresh]);

  const onDelete = useCallback(async (ctx) => {
    if (!window.confirm(`Delete context "${ctx.label}"?`)) return;
    try {
      await ambientApi.deleteContext({ contextId: ctx.id });
      await refresh();
    } catch (err) {
      alert(err?.response?.data?.error || err.message || 'Delete failed.');
    }
  }, [refresh]);

  const onToggleSignal = useCallback(async (signalKey, patch) => {
    try {
      await ambientApi.patchSignalConfig({ [signalKey]: patch });
      await refresh();
    } catch (err) {
      alert(err?.response?.data?.error || err.message || 'Update failed.');
    }
  }, [refresh]);

  const onResetBaseline = useCallback(async () => {
    if (!window.confirm(
      'This permanently deletes your ambient profile, contexts, and observations. Continue?',
    )) return;
    try {
      await ambientApi.resetBaseline();
      rotateLocalSalt();
      await refresh();
    } catch (err) {
      alert(err?.response?.data?.error || err.message || 'Reset failed.');
    }
  }, [refresh]);

  const summary = useMemo(() => {
    if (!latestObs) return { trust: 0, novelty: 0, recommendation: 'no_change' };
    return {
      trust: latestObs.trust_score || 0,
      novelty: latestObs.novelty_score || 0,
      recommendation: latestObs.matched_context?.is_trusted && latestObs.trust_score >= 0.85
        ? 'step_down'
        : latestObs.novelty_score >= 0.7
          ? 'step_up'
          : 'no_change',
    };
  }, [latestObs]);

  if (!isAuthenticated) {
    return (
      <div style={panelStyle}>
        <p>Please <Link to="/">sign in</Link> to view your ambient profile.</p>
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0 }}>Ambient Biometric Fusion</h2>
          <p style={mutedText}>
            Passive environmental signals (light, motion, connection, battery curve, and salted
            digests of Wi-Fi / BLE / ambient audio that never leave your device) fuse into a
            trust score and a recognized context. Used to step-down friction in familiar places
            and step-up verification in novel ones.
          </p>
        </div>
        <button type="button" style={buttonGhost} onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 12, padding: '0.6rem 0.8rem', background: '#fef2f2',
          border: '1px solid #fecaca', color: '#991b1b', borderRadius: 6,
        }}>
          {error}
        </div>
      )}

      <h3 style={sectionHeading}>Current state</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
        <Gauge label="Trust score" value={summary.trust} colorFn={trustColor} />
        <Gauge label="Novelty" value={summary.novelty} colorFn={noveltyColor} />
        <div style={{ ...chip('#6366f1'), minWidth: 220 }}>
          <div style={{ fontSize: 12, color: '#6b7280' }}>MFA recommendation</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>{summary.recommendation}</div>
        </div>
        <div style={{ ...chip('#9ca3af'), minWidth: 220 }}>
          <div style={{ fontSize: 12, color: '#6b7280' }}>Matched context</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>
            {latestObs?.matched_context?.label || 'None'}
            {latestObs?.matched_context?.is_trusted ? ' ✓' : ''}
          </div>
        </div>
        {latestObs && !latestObs.matched_context && (
          <button type="button" style={buttonPrimary} onClick={promoteLatest}>
            Teach me this place
          </button>
        )}
      </div>

      {latestObs && (
        <div style={{ marginTop: 12 }}>
          <div style={mutedText}>Reasons for latest observation</div>
          <ReasonPills reasons={latestObs.reasons_json} />
        </div>
      )}

      <h3 style={sectionHeading}>Known contexts</h3>
      {contexts.length === 0 ? (
        <p style={mutedText}>No named contexts yet. Use “Teach me this place” on a fresh observation to create one.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
          {contexts.map((c) => (
            <div key={c.id} style={{ ...chip(c.is_trusted ? '#16a34a' : '#9ca3af'), minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong>{c.label}</strong>
                <span style={mutedText}>{c.is_trusted ? 'trusted' : 'untrusted'}</span>
              </div>
              <div style={mutedText}>
                samples: {c.samples_used} · radius: {c.radius} ·
                {c.last_matched_at ? ` last match ${new Date(c.last_matched_at).toLocaleString()}` : ' never matched'}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <button type="button" style={buttonGhost} onClick={() => onRename(c)}>Rename</button>
                <button type="button" style={buttonGhost} onClick={() => onDelete(c)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 style={sectionHeading}>Signal controls</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
        {Object.entries(signalCfg).map(([key, value]) => (
          <div key={key} style={{ ...chip(value.enabled ? '#7B68EE' : '#9ca3af'), minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>{key}</strong>
              <label style={{ fontSize: 12 }}>
                <input
                  type="checkbox"
                  checked={Boolean(value.enabled)}
                  onChange={(e) => onToggleSignal(key, { enabled: e.target.checked })}
                />{' '}enabled
              </label>
            </div>
            <div style={mutedText}>surfaces: {(value.enabled_on_surfaces || []).join(', ') || '—'}</div>
          </div>
        ))}
      </div>

      <h3 style={sectionHeading}>Recent observations</h3>
      {observations.length === 0 ? (
        <p style={mutedText}>No observations yet — the engine posts one every ~5 minutes while you use the app.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8, fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              <th style={{ textAlign: 'left', padding: 6 }}>When</th>
              <th style={{ textAlign: 'left', padding: 6 }}>Surface</th>
              <th style={{ textAlign: 'left', padding: 6 }}>Trust</th>
              <th style={{ textAlign: 'left', padding: 6 }}>Novelty</th>
              <th style={{ textAlign: 'left', padding: 6 }}>Context</th>
              <th style={{ textAlign: 'left', padding: 6 }}>Reasons</th>
            </tr>
          </thead>
          <tbody>
            {observations.map((o) => (
              <tr key={o.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                <td style={{ padding: 6 }}>{new Date(o.created_at).toLocaleString()}</td>
                <td style={{ padding: 6 }}>{o.surface}</td>
                <td style={{ padding: 6, color: trustColor(o.trust_score || 0), fontWeight: 600 }}>
                  {(o.trust_score || 0).toFixed(2)}
                </td>
                <td style={{ padding: 6, color: noveltyColor(o.novelty_score || 0), fontWeight: 600 }}>
                  {(o.novelty_score || 0).toFixed(2)}
                </td>
                <td style={{ padding: 6 }}>
                  {o.matched_context ? `${o.matched_context.label}${o.matched_context.is_trusted ? ' ✓' : ''}` : '—'}
                </td>
                <td style={{ padding: 6 }}><ReasonPills reasons={o.reasons_json} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={sectionHeading}>Privacy</h3>
      <p style={mutedText}>
        Sensitive raw signals (Wi-Fi BSSIDs, BLE device addresses, ambient audio samples) never
        leave your device — only salted locality-sensitive hash digests are transmitted. The server
        stores only bucketed features, the opaque digest, and derived scores.
      </p>
      <div style={{ display: 'flex', gap: 10 }}>
        <button type="button" style={buttonGhost} onClick={onResetBaseline}>
          Reset baseline & rotate salt
        </button>
        {config && (
          <span style={{ ...chip(config.enabled ? '#16a34a' : '#ef4444'), minWidth: 0 }}>
            Feature flag: {config.enabled ? 'enabled' : 'disabled'}
          </span>
        )}
      </div>
    </div>
  );
}
