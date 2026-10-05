import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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
vi.mock('../../../hooks/useBreachWebSocket', () => ({
  default: () => ({
    isConnected: true,
    connectionQuality: 'good',
    reconnectAttempts: 0,
    unreadCount: 0,
    connectionError: null,
    reconnect: vi.fn(),
  }),
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
    expect(api.get).toHaveBeenCalledWith('/api/ml-darkweb/breach-alerts/');

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

  test('tolerates an empty or malformed list response', async () => {
    api.get.mockResolvedValue({ data: {} });
    render(<BreachAlertsDashboard />);

    expect(await screen.findByText('All Clear!')).toBeInTheDocument();
  });
});
