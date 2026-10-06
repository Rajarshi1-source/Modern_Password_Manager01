import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BreachAlertsDashboard from './BreachAlertsDashboard';
import { api } from '../../../services/api';

// The dashboard must list BreachAlert records and mark *those* read (Greptile,
// PR #515): the old breach_matches / resolve_match pair carried no `is_read`,
// so an alert that was already read came back unread after every reload.

vi.mock('../../../services/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../services/errorTracker', () => ({
  errorTracker: { captureError: vi.fn() },
}));
vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 7 } }),
}));
// Captures the dashboard's WebSocket callbacks so tests can push live events.
const ws = vi.hoisted(() => ({ onAlert: null, onUpdate: null }));

vi.mock('../../../hooks/useBreachWebSocket', () => ({
  default: (_userId, onAlert, onUpdate) => {
    ws.onAlert = onAlert;
    ws.onUpdate = onUpdate;
    return {
      isConnected: true,
      connectionQuality: 'good',
      reconnectAttempts: 0,
      unreadCount: 0,
      connectionError: null,
      reconnect: vi.fn(),
    };
  },
}));

// Shape returned by GET /api/ml-darkweb/breach-alerts/ (see get_breach_alerts).
const unreadAlert = {
  id: 11,
  breach_name: 'Acme breach',
  breach_description: 'Acme leaked credentials',
  severity: 'high', // stored lowercase on BreachAlert
  detected_at: '2026-09-20T10:00:00Z',
  is_read: false,
  resolved: false,
  identifier: 'acme.example',
  exposed_data: { types: ['email'], confidence: 0.87 },
};
const readAlert = {
  ...unreadAlert,
  id: 12,
  breach_name: 'Globex breach',
  severity: 'critical',
  is_read: true,
  identifier: 'globex.example',
  exposed_data: { types: ['email'], confidence: 0.5 },
};

describe('BreachAlertsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({
      data: { success: true, count: 2, alerts: [unreadAlert, readAlert] },
    });
    api.post.mockResolvedValue({ data: { success: true } });
  });

  test('lists alert records and keeps an already-read alert read after a reload', async () => {
    render(<BreachAlertsDashboard />);

    expect(await screen.findByText('Acme breach')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/api/ml-darkweb/breach-alerts/', { params: { offset: 0 } });

    // Card fields come from the alert record, not from a match row.
    expect(screen.getByText('HIGH')).toBeInTheDocument(); // upper-cased for the card
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.getByText('acme.example')).toBeInTheDocument();
    expect(screen.getByText(/Match Confidence: 87\.0%/)).toBeInTheDocument();

    // The persisted-read alert is shown as reviewed, not offered "Mark as Read".
    expect(screen.getByText('Globex breach')).toBeInTheDocument();
    expect(screen.getAllByText('Mark as Read')).toHaveLength(1);
    expect(screen.getByText('Reviewed')).toBeInTheDocument();
    expect(screen.getByText('1 unread')).toBeInTheDocument();
  });

  test('"Mark as Read" persists through mark-alert-read, not resolve_match', async () => {
    render(<BreachAlertsDashboard />);
    await screen.findByText('Acme breach');

    await userEvent.click(screen.getByText('Mark as Read'));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    // Alert id travels in the URL; the view takes no body.
    expect(api.post).toHaveBeenCalledWith('/api/ml-darkweb/mark-alert-read/11/');
    expect(api.post.mock.calls[0]).toHaveLength(1);

    await waitFor(() => expect(screen.queryByText('Mark as Read')).not.toBeInTheDocument());
    expect(screen.queryByText(/unread/)).not.toBeInTheDocument();
  });

  test('loads every page so older unread alerts are reachable', async () => {
    api.get
      .mockResolvedValueOnce({ data: { has_more: true, alerts: [unreadAlert] } })
      .mockResolvedValueOnce({
        data: { has_more: false, alerts: [{ ...unreadAlert, id: 13, breach_name: 'Older breach' }] },
      });
    render(<BreachAlertsDashboard />);

    expect(await screen.findByText('Older breach')).toBeInTheDocument();
    expect(screen.getByText('Acme breach')).toBeInTheDocument();
    expect(api.get).toHaveBeenNthCalledWith(2, '/api/ml-darkweb/breach-alerts/', {
      params: { offset: 1 },
    });
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  test('shows a breach-scan alert\'s affected item under an accurate label, with no 0.0% confidence', async () => {
    // Breach-scan alerts store an email / vault item id in `identifier` and
    // have no exposed_data.confidence.
    const scan = { ...unreadAlert, exposed_data: {} };
    api.get.mockResolvedValue({
      data: {
        alerts: [
          { ...scan, id: 21, breach_name: 'Email scan hit', data_type: 'email', identifier: 'person@example.net' },
          { ...scan, id: 22, breach_name: 'Password scan hit', data_type: 'password', identifier: '4821' },
        ],
      },
    });
    render(<BreachAlertsDashboard />);

    expect(await screen.findByText('Email scan hit')).toBeInTheDocument();
    expect(screen.getByText('Affected Email: person@example.net')).toBeInTheDocument();
    expect(screen.getByText('Vault Item ID: 4821')).toBeInTheDocument();
    expect(screen.queryByText(/Match Confidence/)).not.toBeInTheDocument();
  });

  test('keeps a WebSocket alert that arrived while the pages were loading', async () => {
    let release;
    api.get.mockReturnValue(new Promise((resolve) => { release = resolve; }));
    render(<BreachAlertsDashboard />);
    await waitFor(() => expect(ws.onAlert).toBeTruthy());

    act(() => {
      ws.onAlert({ alert_id: 99, title: 'Live breach', severity: 'high', detected_at: '2026-10-05T10:00:00Z' });
    });
    release({ data: { has_more: false, alerts: [unreadAlert] } });

    // Card titles are headings (the toast repeats the title as plain text).
    expect(await screen.findByRole('heading', { name: 'Acme breach' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Live breach' })).toBeInTheDocument();
  });

  test('renders a live alert from the exact payload send_breach_notification emits', async () => {
    // Mirrors ml_dark_web/tests/test_breach_notification_payload.py: `title` and
    // UPPERCASE `severity` for every alert, `confidence` + `domain` for ML alerts.
    // With the old producer (breach_name, lowercase severity, no confidence) this
    // showed a generic title, MEDIUM styling and no filter match.
    api.get.mockResolvedValue({ data: { alerts: [] } });
    render(<BreachAlertsDashboard />);
    await waitFor(() => expect(ws.onAlert).toBeTruthy());

    act(() => {
      ws.onAlert({
        alert_id: 77,
        breach_name: 'Live ML breach',
        title: 'Live ML breach',
        severity: 'HIGH',
        detected_at: '2026-10-05T10:00:00Z',
        description: 'Leaked credentials',
        confidence: 0.66,
        domain: 'live.example',
      });
    });

    expect(await screen.findByRole('heading', { name: 'Live ML breach' })).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument(); // badge: uppercase, not the lowercase fallback
    expect(screen.getByText(/Match Confidence: 66\.0%/)).toBeInTheDocument();
    expect(screen.getByText('live.example')).toBeInTheDocument();
    expect(screen.getByText(/Confidence: 66%/)).toBeInTheDocument(); // the toast reads the same payload
    expect(screen.queryByText('New Breach Detected')).not.toBeInTheDocument(); // no generic-title fallback

    // The Critical/High filter only matches UPPERCASE severity.
    await userEvent.click(screen.getByText('Critical/High'));
    expect(screen.getByRole('heading', { name: 'Live ML breach' })).toBeInTheDocument();
  });

  test('a read update received mid-load is not reverted by the fetched copy', async () => {
    let release;
    api.get.mockReturnValue(new Promise((resolve) => { release = resolve; }));
    render(<BreachAlertsDashboard />);
    await waitFor(() => expect(ws.onAlert).toBeTruthy());

    act(() => {
      ws.onAlert({ alert_id: 11, title: 'Acme breach', severity: 'high' });
      ws.onUpdate({ update_type: 'marked_read', alert_id: 11 });
    });
    release({ data: { has_more: false, alerts: [unreadAlert] } }); // fetched copy is still unread

    expect(await screen.findByText('Reviewed')).toBeInTheDocument();
    expect(screen.queryByText('Mark as Read')).not.toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: 'Acme breach' })).toHaveLength(1); // merged, not duplicated
  });

  test('keeps earlier pages and flags the list as incomplete when a later page fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.get
      .mockResolvedValueOnce({ data: { has_more: true, alerts: [unreadAlert] } })
      .mockRejectedValueOnce(new Error('network down'));
    render(<BreachAlertsDashboard />);

    expect(await screen.findByRole('heading', { name: 'Acme breach' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/may be incomplete/);
    expect(screen.queryByText('All Clear!')).not.toBeInTheDocument();
  });

  test('shows an error, not "All Clear!", when the first request fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.get.mockRejectedValue(new Error('boom'));
    render(<BreachAlertsDashboard />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/Could not load/);
    expect(screen.queryByText('All Clear!')).not.toBeInTheDocument();
  });

  test('tolerates an empty or malformed list response', async () => {
    api.get.mockResolvedValue({ data: {} });
    render(<BreachAlertsDashboard />);

    expect(await screen.findByText('All Clear!')).toBeInTheDocument();
  });
});
