/**
 * Steganographic Hidden Vault dashboard.
 *
 * Lets the signed-in user:
 *   * pick an innocuous cover PNG,
 *   * enter a real + (optional) decoy password and the JSON payloads
 *     they unlock,
 *   * export the resulting stego image locally, optionally upload it
 *     to the server as a ``StegoVault`` record for cross-device
 *     retrieval,
 *   * re-extract a vault from a stego PNG by entering the matching
 *     password, and
 *   * browse past stego vaults + audit events.
 *
 * The server *never* sees plaintext; the only thing it stores is the
 * already-opaque stego PNG plus metadata.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  TIERS,
  capacityReport,
  computeCoverHash,
  embedVault,
  extractVault,
} from '../../services/stego';
import {
  deleteStegoVault,
  downloadStegoImage,
  fetchStegoConfig,
  listStegoEvents,
  listStegoVaults,
  storeStegoImage,
} from '../../services/stego/stegoApi';
import { useAuth } from '../../hooks/useAuth';

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

const buttonPrimary = {
  background: '#7B68EE',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '0.5rem 1rem',
  fontWeight: 600,
  cursor: 'pointer',
};

const buttonGhost = {
  background: '#fff',
  color: '#374151',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '0.4rem 0.8rem',
  cursor: 'pointer',
};

const inputStyle = {
  width: '100%',
  padding: '0.45rem 0.65rem',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 14,
  fontFamily: 'inherit',
};

const mutedText = { color: '#6b7280', fontSize: 13 };

async function readFileAsBytes(file) {
  return new Uint8Array(await file.arrayBuffer());
}

function downloadBytes(bytes, filename, mime = 'image/png') {
  const blob = new Blob([bytes], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

const TIER_OPTIONS = [
  { value: TIERS.TIER0_32K, label: '32 KB — smallest, fastest' },
  { value: TIERS.TIER1_128K, label: '128 KB — balanced (recommended)' },
  { value: TIERS.TIER2_1M, label: '1 MB — large vaults, needs big cover' },
];

// -------------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------------

const StegoVaultDashboard = () => {
  const { isAuthenticated } = useAuth();
  const [config, setConfig] = useState(null);
  const [vaults, setVaults] = useState([]);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  // Embed form state
  const [coverBytes, setCoverBytes] = useState(null);
  const [coverMeta, setCoverMeta] = useState(null);
  const [label, setLabel] = useState('Default');
  const [tier, setTier] = useState(TIERS.TIER1_128K);
  const [realPassword, setRealPassword] = useState('');
  const [decoyPassword, setDecoyPassword] = useState('');
  const [realVaultJson, setRealVaultJson] = useState(
    '{\n  "items": [\n    { "name": "bank", "secret": "replace-me" }\n  ]\n}',
  );
  const [decoyVaultJson, setDecoyVaultJson] = useState(
    '{\n  "items": [\n    { "name": "email", "secret": "public-looking-fake" }\n  ]\n}',
  );

  // Extract form state
  const [extractBytes, setExtractBytes] = useState(null);
  const [extractPassword, setExtractPassword] = useState('');
  const [extractResult, setExtractResult] = useState(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [cfg, v, ev] = await Promise.all([
        fetchStegoConfig(),
        listStegoVaults(),
        listStegoEvents(),
      ]);
      setConfig(cfg);
      setVaults(v || []);
      setEvents(ev || []);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load stego state.');
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onPickCover = useCallback(async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    setError(null);
    setStatus(null);
    try {
      const bytes = await readFileAsBytes(file);
      const report = await capacityReport(bytes);
      setCoverBytes(bytes);
      setCoverMeta({ name: file.name, size: bytes.length, ...report });
      if (report.fitsTier1) setTier(TIERS.TIER1_128K);
      else if (report.fitsTier0) setTier(TIERS.TIER0_32K);
    } catch (err) {
      setError(err.message || 'Could not read cover image.');
      setCoverBytes(null);
      setCoverMeta(null);
    }
  }, []);

  const onEmbed = useCallback(
    async (uploadAfter) => {
      setError(null);
      setStatus(null);
      if (!coverBytes) {
        setError('Pick a cover PNG first.');
        return;
      }
      if (!realPassword) {
        setError('Real password is required.');
        return;
      }
      const realVault = safeJson(realVaultJson);
      if (!realVault) {
        setError('Real vault must be valid JSON.');
        return;
      }
      const decoyVault = decoyVaultJson.trim() ? safeJson(decoyVaultJson) : null;
      if (decoyVaultJson.trim() && !decoyVault) {
        setError('Decoy vault must be valid JSON (or left empty).');
        return;
      }
      setBusy(true);
      try {
        const { stegoPng, tier: chosenTier, blobBytes } = await embedVault({
          coverBytes,
          realPassword,
          realVault,
          decoyPassword: decoyPassword || null,
          decoyVault,
          tier,
        });
        const coverHash = await computeCoverHash(coverBytes);
        const filename = `${label || 'stego'}.png`;
        downloadBytes(stegoPng, filename);
        if (uploadAfter) {
          await storeStegoImage({
            imageBytes: stegoPng,
            label: label || 'Default',
            tier: chosenTier,
            coverHash,
          });
          await refresh();
          setStatus(`Stego image stored on server (${blobBytes}B blob, tier ${chosenTier}).`);
        } else {
          setStatus(`Stego image exported locally (${blobBytes}B blob, tier ${chosenTier}).`);
        }
      } catch (err) {
        setError(err?.response?.data?.detail || err.message || 'Embed failed.');
      } finally {
        setBusy(false);
      }
    },
    [
      coverBytes,
      realPassword,
      realVaultJson,
      decoyVaultJson,
      decoyPassword,
      tier,
      label,
      refresh,
    ],
  );

  const onPickExtract = useCallback(async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    setError(null);
    setStatus(null);
    setExtractResult(null);
    try {
      const bytes = await readFileAsBytes(file);
      setExtractBytes(bytes);
    } catch (err) {
      setError(err.message || 'Could not read stego image.');
      setExtractBytes(null);
    }
  }, []);

  const onExtract = useCallback(async () => {
    setError(null);
    setStatus(null);
    setExtractResult(null);
    if (!extractBytes) {
      setError('Pick a stego PNG first.');
      return;
    }
    if (!extractPassword) {
      setError('Password is required.');
      return;
    }
    setBusy(true);
    try {
      const { slotIndex, json } = await extractVault({
        stegoBytes: extractBytes,
        password: extractPassword,
      });
      setExtractResult({ slotIndex, json });
    } catch (err) {
      setError(err?.message || 'Extraction failed. Wrong password or corrupt image.');
    } finally {
      setBusy(false);
    }
  }, [extractBytes, extractPassword]);

  const onLoadServerVault = useCallback(
    async (vault) => {
      setError(null);
      setStatus(null);
      setExtractResult(null);
      try {
        const bytes = await downloadStegoImage(vault.id);
        setExtractBytes(bytes);
        setStatus(`Loaded server-side stego image "${vault.label}" for extraction.`);
      } catch (err) {
        setError(err.message || 'Download failed.');
      }
    },
    [],
  );

  const onDeleteServerVault = useCallback(
    async (vault) => {
      if (!window.confirm(`Delete server copy of "${vault.label}"?`)) return;
      try {
        await deleteStegoVault(vault.id);
        await refresh();
      } catch (err) {
        setError(err.message || 'Delete failed.');
      }
    },
    [refresh],
  );

  const enabled = config?.enabled;

  const capacitySummary = useMemo(() => {
    if (!coverMeta) return null;
    return (
      <div style={{ ...mutedText, marginTop: 6 }}>
        Cover: <strong>{coverMeta.name}</strong> ({(coverMeta.size / 1024).toFixed(1)} KB).
        Embeddable capacity: {coverMeta.capacityBytes.toLocaleString()} bytes.{' '}
        {coverMeta.fitsTier2
          ? '✅ Fits all tiers.'
          : coverMeta.fitsTier1
            ? '✅ Fits 32 KB & 128 KB tiers.'
            : coverMeta.fitsTier0
              ? '⚠️ Only fits 32 KB tier.'
              : '❌ Too small for any tier.'}
      </div>
    );
  }, [coverMeta]);

  if (!isAuthenticated) {
    return (
      <div style={panelStyle}>
        <h2 style={{ margin: 0 }}>Steganographic Hidden Vault</h2>
        <p style={mutedText}>You must be signed in to manage stego vaults.</p>
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h2 style={{ margin: 0 }}>🖼️ Steganographic Hidden Vault</h2>
          <p style={{ ...mutedText, margin: '4px 0 0' }}>
            Hide an encrypted vault inside an innocuous PNG. The image
            looks identical to any viewer but holds two independent,
            password-unlocked slots with plausible deniability.
          </p>
        </div>
        <Link to="/security/duress" style={buttonGhost}>
          ← Back to Duress Protection
        </Link>
      </div>

      {config && enabled === false && (
        <div
          style={{
            marginTop: 16,
            padding: '0.75rem 1rem',
            background: '#fef3c7',
            border: '1px solid #fde68a',
            borderRadius: 6,
            color: '#92400e',
          }}
        >
          Stego vault is currently disabled in the server configuration. You can
          still embed and extract locally, but server-side storage is off.
        </div>
      )}

      {error && (
        <div
          style={{
            marginTop: 16,
            padding: '0.75rem 1rem',
            background: '#fee2e2',
            border: '1px solid #fecaca',
            borderRadius: 6,
            color: '#991b1b',
          }}
        >
          ⚠️ {error}
        </div>
      )}
      {status && (
        <div
          style={{
            marginTop: 16,
            padding: '0.75rem 1rem',
            background: '#dcfce7',
            border: '1px solid #bbf7d0',
            borderRadius: 6,
            color: '#166534',
          }}
        >
          {status}
        </div>
      )}

      {/* --------------------------------------------------------------- */}
      {/* Embed form                                                      */}
      {/* --------------------------------------------------------------- */}
      <h3 style={sectionHeading}>Create / export stego image</h3>

      <div style={{ display: 'grid', gap: '0.75rem', gridTemplateColumns: '1fr 1fr' }}>
        <label>
          <div style={mutedText}>Label</div>
          <input
            value={label}
            onChange={(ev) => setLabel(ev.target.value)}
            style={inputStyle}
            placeholder="e.g. vacation-photo"
          />
        </label>
        <label>
          <div style={mutedText}>Tier</div>
          <select
            value={tier}
            onChange={(ev) => setTier(Number(ev.target.value))}
            style={inputStyle}
          >
            {TIER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <div style={mutedText}>Real password</div>
          <input
            type="password"
            value={realPassword}
            onChange={(ev) => setRealPassword(ev.target.value)}
            style={inputStyle}
            autoComplete="new-password"
          />
        </label>
        <label>
          <div style={mutedText}>Decoy password (optional)</div>
          <input
            type="password"
            value={decoyPassword}
            onChange={(ev) => setDecoyPassword(ev.target.value)}
            style={inputStyle}
            autoComplete="new-password"
          />
        </label>
      </div>

      <div style={{ marginTop: '0.75rem' }}>
        <div style={mutedText}>Real vault (JSON)</div>
        <textarea
          value={realVaultJson}
          onChange={(ev) => setRealVaultJson(ev.target.value)}
          style={{ ...inputStyle, fontFamily: 'monospace', minHeight: 90 }}
        />
      </div>

      <div style={{ marginTop: '0.75rem' }}>
        <div style={mutedText}>Decoy vault (JSON, optional)</div>
        <textarea
          value={decoyVaultJson}
          onChange={(ev) => setDecoyVaultJson(ev.target.value)}
          style={{ ...inputStyle, fontFamily: 'monospace', minHeight: 80 }}
        />
      </div>

      <div style={{ marginTop: '0.75rem' }}>
        <div style={mutedText}>Cover image (PNG only — lossy formats will destroy the payload)</div>
        <input type="file" accept="image/png" onChange={onPickCover} />
        {capacitySummary}
      </div>

      <div style={{ marginTop: '1rem', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          style={buttonPrimary}
          disabled={busy}
          onClick={() => onEmbed(false)}
          type="button"
        >
          Export stego image (local only)
        </button>
        <button
          style={buttonGhost}
          disabled={busy || enabled === false}
          onClick={() => onEmbed(true)}
          type="button"
        >
          Export + upload to server
        </button>
      </div>

      {/* --------------------------------------------------------------- */}
      {/* Extract form                                                    */}
      {/* --------------------------------------------------------------- */}
      <h3 style={sectionHeading}>Unlock a stego image</h3>
      <div style={{ display: 'grid', gap: '0.75rem', gridTemplateColumns: '1fr 1fr' }}>
        <label>
          <div style={mutedText}>Stego PNG</div>
          <input type="file" accept="image/png" onChange={onPickExtract} />
        </label>
        <label>
          <div style={mutedText}>Password (real or decoy)</div>
          <input
            type="password"
            value={extractPassword}
            onChange={(ev) => setExtractPassword(ev.target.value)}
            style={inputStyle}
            autoComplete="current-password"
          />
        </label>
      </div>
      <div style={{ marginTop: '0.75rem' }}>
        <button style={buttonPrimary} disabled={busy} onClick={onExtract} type="button">
          Extract
        </button>
      </div>
      {extractResult && (
        <div style={{ marginTop: '0.75rem', background: '#f9fafb', padding: 12, borderRadius: 6 }}>
          <div style={mutedText}>Unlocked slot index: {extractResult.slotIndex}</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13 }}>
            {JSON.stringify(extractResult.json, null, 2)}
          </pre>
        </div>
      )}

      {/* --------------------------------------------------------------- */}
      {/* Server-side vaults                                              */}
      {/* --------------------------------------------------------------- */}
      <h3 style={sectionHeading}>Server-stored stego images</h3>
      {!vaults.length && (
        <p style={mutedText}>
          No stego images stored on this account yet. Use “Export + upload
          to server” above to create one.
        </p>
      )}
      {vaults.map((v) => (
        <div
          key={v.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.5rem 0.75rem',
            border: '1px solid #e5e7eb',
            borderRadius: 6,
            marginBottom: 8,
          }}
        >
          <div>
            <strong>{v.label}</strong>
            <div style={mutedText}>
              Tier {v.blob_size_tier} · {v.size_bytes ? `${Math.round(v.size_bytes / 1024)} KB` : 'n/a'} ·{' '}
              updated {new Date(v.updated_at).toLocaleString()}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={buttonGhost} onClick={() => onLoadServerVault(v)} type="button">
              Load for extraction
            </button>
            <button
              style={{ ...buttonGhost, color: '#991b1b', borderColor: '#fecaca' }}
              onClick={() => onDeleteServerVault(v)}
              type="button"
            >
              Delete
            </button>
          </div>
        </div>
      ))}

      {/* --------------------------------------------------------------- */}
      {/* Audit events                                                    */}
      {/* --------------------------------------------------------------- */}
      <h3 style={sectionHeading}>Recent stego events</h3>
      {!events.length && <p style={mutedText}>No stego events yet.</p>}
      {!!events.length && (
        <div style={{ fontSize: 13 }}>
          {events.slice(0, 25).map((ev) => (
            <div
              key={ev.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '4px 0',
                borderBottom: '1px dashed #e5e7eb',
              }}
            >
              <span>
                <strong>{ev.kind}</strong>
                {ev.stego_vault_label ? ` · ${ev.stego_vault_label}` : ''}
              </span>
              <span style={mutedText}>{new Date(ev.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default StegoVaultDashboard;
