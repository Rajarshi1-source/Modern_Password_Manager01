import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RecoveryNotices from './RecoveryNotices';
import VaultExposureBanner from './VaultExposureBanner';
import ApiService from '../../../services/api';

vi.mock('../../../services/api', () => ({
  default: {
    recoveryNotices: { list: vi.fn(), acknowledgeExposure: vi.fn() },
    handleError: vi.fn(),
  },
}));

const exposed = { data: { notices: [], vault_exposed_since: '2026-11-01T10:00:00Z' } };
const clear = { data: { notices: [], vault_exposed_since: null } };

describe('vault exposure warning', () => {
  beforeEach(() => vi.clearAllMocks());

  it('stays until the owner acknowledges it', async () => {
    ApiService.recoveryNotices.list.mockResolvedValue(exposed);
    ApiService.recoveryNotices.acknowledgeExposure.mockResolvedValue({ data: {} });
    render(<MemoryRouter><RecoveryNotices /></MemoryRouter>);
    await screen.findByTestId('vault-exposure-warning');
    expect(ApiService.recoveryNotices.acknowledgeExposure).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('vault-exposure-acknowledge'));
    await waitFor(() => expect(screen.queryByTestId('vault-exposure-warning')).toBeNull());
  });

  it('keeps the warning when the acknowledgement fails', async () => {
    ApiService.recoveryNotices.list.mockResolvedValue(exposed);
    ApiService.recoveryNotices.acknowledgeExposure.mockRejectedValue(new Error('down'));
    ApiService.handleError.mockReturnValue({});
    render(<MemoryRouter><RecoveryNotices /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId('vault-exposure-acknowledge'));
    await screen.findByRole('alert');
    expect(screen.getByTestId('vault-exposure-warning')).toBeTruthy();
  });

  it('is absent with nothing to acknowledge', async () => {
    ApiService.recoveryNotices.list.mockResolvedValue(clear);
    render(<MemoryRouter><RecoveryNotices /></MemoryRouter>);
    await screen.findByTestId('recovery-notices');
    expect(screen.queryByTestId('vault-exposure-warning')).toBeNull();
  });

  it('banner links to what to do, and not on that page itself', async () => {
    ApiService.recoveryNotices.list.mockResolvedValue(exposed);
    const { unmount } = render(<MemoryRouter initialEntries={['/']}><VaultExposureBanner /></MemoryRouter>);
    const banner = await screen.findByTestId('vault-exposure-banner');
    expect(banner.querySelector('a').getAttribute('href')).toBe('/security/recovery-notices');
    unmount();
    render(<MemoryRouter initialEntries={['/security/recovery-notices']}><VaultExposureBanner /></MemoryRouter>);
    await waitFor(() => expect(ApiService.recoveryNotices.list).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId('vault-exposure-banner')).toBeNull();
  });

  it('banner shows nothing when the check fails', async () => {
    ApiService.recoveryNotices.list.mockRejectedValue(new Error('down'));
    render(<MemoryRouter><VaultExposureBanner /></MemoryRouter>);
    await act(async () => {
      await ApiService.recoveryNotices.list.mock.results[0].value.catch(() => {});
    });
    expect(screen.queryByTestId('vault-exposure-banner')).toBeNull();
  });

  it('banner checks again after a failed check', async () => {
    vi.useFakeTimers();
    try {
      ApiService.recoveryNotices.list.mockRejectedValueOnce(new Error('down'));
      ApiService.recoveryNotices.list.mockResolvedValue(exposed);
      render(<MemoryRouter><VaultExposureBanner /></MemoryRouter>);
      await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
      expect(ApiService.recoveryNotices.list).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId('vault-exposure-banner')).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it('page offers a retry when the notices do not load', async () => {
    ApiService.recoveryNotices.list.mockRejectedValueOnce(new Error('down'));
    ApiService.recoveryNotices.list.mockResolvedValue(exposed);
    ApiService.handleError.mockReturnValue({});
    render(<MemoryRouter><RecoveryNotices /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId('recovery-notices-retry'));
    await screen.findByTestId('vault-exposure-warning');
  });
});

describe('recovery notice requests', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    ['cancel', (n) => n.cancel('tok-123'),
      ['/auth/recovery-notices/cancel/', { token: 'tok-123' }, { _noAuthRedirect: true }]],
    ['acknowledgeExposure', (n) => n.acknowledgeExposure(),
      ['/auth/recovery-notices/acknowledge-exposure/']],
  ])('%s sends what the endpoint reads', async (_name, call, expected) => {
    const { default: RealApi, api } = await vi.importActual('../../../services/api');
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} });
    await call(RealApi.recoveryNotices);
    expect(post).toHaveBeenCalledWith(...expected);
    post.mockRestore();
  });
});
