import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../services/api', () => ({
  default: {
    recoveryNotices: { cancel: vi.fn() },
    handleError: vi.fn(),
  },
}));

import ApiService from '../../../services/api';
import RecoveryNoticeCancel from './RecoveryNoticeCancel';

const renderAt = (url) => render(
  <MemoryRouter initialEntries={[url]}>
    <RecoveryNoticeCancel />
  </MemoryRouter>,
);

describe('RecoveryNoticeCancel', () => {
  // In braces: a function returned from beforeEach runs as a teardown.
  beforeEach(() => { ApiService.recoveryNotices.cancel.mockReset(); });

  it('does nothing until the button is pressed, so link scanners cannot trigger it', async () => {
    ApiService.recoveryNotices.cancel.mockResolvedValue({ data: { message: 'stopped' } });
    renderAt('/recovery/cancel?notice=tok-123');
    expect(ApiService.recoveryNotices.cancel).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('recovery-notice-cancel-button'));
    await waitFor(() => expect(screen.getByTestId('recovery-notice-cancel-done').textContent).toBe('stopped'));
    expect(ApiService.recoveryNotices.cancel).toHaveBeenCalledWith('tok-123');
  });

  it.each([
    [{ error: 'failed' }, 'failed'],
    [{ detail: 'Request was throttled.' }, 'Request was throttled.'],
    [undefined, 'Could not reach the server. Try again.'],
  ])('shows why a cancel failed: %j', async (body, shown) => {
    ApiService.recoveryNotices.cancel.mockRejectedValue(new Error('rejected'));
    ApiService.handleError.mockReturnValue(body);
    renderAt('/recovery/cancel?notice=tok-123');
    fireEvent.click(screen.getByTestId('recovery-notice-cancel-button'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe(shown));
  });

  it('explains an incomplete link', () => {
    renderAt('/recovery/cancel');
    expect(screen.queryByTestId('recovery-notice-cancel-button')).toBeNull();
  });
});
