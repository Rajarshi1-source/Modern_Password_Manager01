/**
 * HoneypotEventsTable.jsx
 *
 * Read-only forensic log of every time an attacker (or test) touched
 * one of the user's honeypots.
 */

import React, { useCallback, useEffect, useState } from 'react';
import honeypotCredentialService from '../../services/honeypotCredentialService';

function formatTs(ts) {
  if (!ts) return '-';
  try { return new Date(ts).toLocaleString(); } catch (_err) { return ts; }
}

export default function HoneypotEventsTable() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await honeypotCredentialService.listEvents();
      const data = res?.data?.results || res?.data || [];
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.message || 'Failed to load events.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: 16, maxWidth: 1080 }}>
      <h2>Honeypot access log</h2>
      <p>Each row is an interception event — treat it as a potential breach.</p>

      {error && (
        <div style={{ padding: 8, color: '#b00', border: '1px solid #b00', marginBottom: 12 }}>
          {error}
        </div>
      )}

      <button type="button" onClick={load} disabled={loading}>
        {loading ? 'Refreshing…' : 'Refresh'}
      </button>

      <table width="100%" cellPadding={6} style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th align="left">When</th>
            <th align="left">Honeypot</th>
            <th align="left">Access type</th>
            <th align="left">IP</th>
            <th align="left">Geo</th>
            <th align="left">User agent</th>
            <th align="left">Alert</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 ? (
            <tr><td colSpan={7}>No events yet.</td></tr>
          ) : events.map((ev) => (
            <tr key={ev.id}>
              <td>{formatTs(ev.accessed_at)}</td>
              <td>{ev.honeypot_label || ev.honeypot}</td>
              <td>{ev.access_type}</td>
              <td>{ev.ip || '-'}</td>
              <td>
                {[ev.geo_city, ev.geo_country].filter(Boolean).join(', ') || '-'}
              </td>
              <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {ev.user_agent || '-'}
              </td>
              <td>{ev.alert_sent ? 'sent' : 'pending'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
