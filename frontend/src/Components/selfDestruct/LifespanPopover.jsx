/**
 * LifespanPopover.jsx
 *
 * Small inline popover attached to a vault entry. Lets the owner
 * configure a self-destruct policy: TTL, max uses, burn-after-reading,
 * or geofence. Shows the remaining lifetime when a policy is active.
 */

import React, { useCallback, useEffect, useState } from 'react';
import selfDestructService from '../../services/selfDestructService';

const KINDS = [
  { value: 'ttl', label: 'Expire after a date/time' },
  { value: 'use_limit', label: 'Expire after N accesses' },
  { value: 'burn', label: 'Burn after reading (single use)' },
  { value: 'geofence', label: 'Only within a geofence' },
];

function formatRemaining(policy) {
  if (!policy || policy.status !== 'active') return null;
  const parts = [];
  if (policy.expires_at) {
    const dt = new Date(policy.expires_at);
    if (!Number.isNaN(dt.getTime())) {
      const ms = dt.getTime() - Date.now();
      if (ms > 0) {
        const hrs = Math.floor(ms / 3_600_000);
        parts.push(hrs < 24 ? `${hrs}h left` : `${Math.floor(hrs / 24)}d left`);
      } else {
        parts.push('expired');
      }
    }
  }
  if (policy.max_uses != null) {
    parts.push(`${policy.max_uses - policy.access_count}/${policy.max_uses} uses left`);
  }
  return parts.join(' · ');
}

export default function LifespanPopover({ vaultItemId, onChanged }) {
  const [existing, setExisting] = useState(null);
  const [open, setOpen] = useState(false);
  const [kinds, setKinds] = useState([]);
  const [expiresAt, setExpiresAt] = useState('');
  const [maxUses, setMaxUses] = useState('');
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [radius, setRadius] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!vaultItemId) return;
    try {
      const res = await selfDestructService.listPolicies();
      const all = res?.data?.results || res?.data || [];
      const match = Array.isArray(all)
        ? all.find((p) => p.vault_item_id === vaultItemId && p.status === 'active')
        : null;
      setExisting(match || null);
    } catch (e) {
      setErr(e?.message || 'Failed to load policies.');
    }
  }, [vaultItemId]);

  useEffect(() => { load(); }, [load]);

  const toggleKind = (k) => {
    setKinds((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
  };

  const create = async () => {
    setErr('');
    setBusy(true);
    try {
      const payload = { vault_item_id: vaultItemId, kinds };
      if (kinds.includes('ttl')) payload.expires_at = expiresAt;
      if (kinds.includes('use_limit')) payload.max_uses = parseInt(maxUses, 10);
      if (kinds.includes('geofence')) {
        payload.geofence_lat = parseFloat(lat);
        payload.geofence_lng = parseFloat(lng);
        payload.geofence_radius_m = parseInt(radius, 10);
      }
      await selfDestructService.createPolicy(payload);
      setOpen(false);
      await load();
      onChanged?.();
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to save policy.');
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    if (!existing) return;
    setBusy(true);
    try {
      await selfDestructService.revokePolicy(existing.id);
      await load();
      onChanged?.();
    } catch (e) {
      setErr(e?.message || 'Revoke failed.');
    } finally {
      setBusy(false);
    }
  };

  const remaining = formatRemaining(existing);

  return (
    <div style={{ display: 'inline-block', position: 'relative' }}>
      <button type="button" onClick={() => setOpen((v) => !v)}>
        {existing ? `Self-destruct: ${remaining || 'active'}` : 'Add self-destruct'}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', left: 0, zIndex: 10,
            background: '#fff', border: '1px solid #999', padding: 12,
            width: 320,
          }}
        >
          {err && <div style={{ color: '#b00', marginBottom: 8 }}>{err}</div>}
          {existing ? (
            <>
              <p>Current policy: <code>{existing.kinds?.join(', ')}</code></p>
              {remaining && <p>{remaining}</p>}
              <button type="button" disabled={busy} onClick={revoke}>Revoke policy</button>
            </>
          ) : (
            <>
              {KINDS.map((k) => (
                <label key={k.value} style={{ display: 'block' }}>
                  <input type="checkbox" checked={kinds.includes(k.value)} onChange={() => toggleKind(k.value)} />
                  {k.label}
                </label>
              ))}
              {kinds.includes('ttl') && (
                <label>Expires at (ISO)
                  <input value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} placeholder="2026-12-31T23:59" type="datetime-local" />
                </label>
              )}
              {kinds.includes('use_limit') && (
                <label>Max uses
                  <input value={maxUses} onChange={(e) => setMaxUses(e.target.value)} type="number" min={1} />
                </label>
              )}
              {kinds.includes('geofence') && (
                <>
                  <label>Latitude
                    <input value={lat} onChange={(e) => setLat(e.target.value)} type="number" step="any" />
                  </label>
                  <label>Longitude
                    <input value={lng} onChange={(e) => setLng(e.target.value)} type="number" step="any" />
                  </label>
                  <label>Radius (m)
                    <input value={radius} onChange={(e) => setRadius(e.target.value)} type="number" min={10} />
                  </label>
                </>
              )}
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button type="button" onClick={create} disabled={busy || kinds.length === 0}>Save</button>
                <button type="button" onClick={() => setOpen(false)}>Cancel</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
