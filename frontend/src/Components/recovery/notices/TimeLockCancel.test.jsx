import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../services/api', () => ({
  default: {
    recoveryNotices: { cancelTimeLock: vi.fn() },
    handleError: vi.fn(),
  },
}));

import ApiService from '../../../services/api';
import TimeLockCancel from './TimeLockCancel';

const renderAt = (url) => render(
  <MemoryRouter initialEntries={[url]}>
    <TimeLockCancel />
  </MemoryRouter>,
);

describe('TimeLockCancel', () => {
  // In braces: a function returned from beforeEach runs as a teardown.
  beforeEach(() => { ApiService.recoveryNotices.cancelTimeLock.mockReset(); });

  it('does nothing until the button is pressed, so link scanners cannot trigger it', async () => {
    ApiService.recoveryNotices.cancelTimeLock.mockResolvedValue({ data: { success: true } });
    renderAt('/recovery/time-lock/cancel?token=tok-123');
    expect(ApiService.recoveryNotices.cancelTimeLock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('time-lock-cancel-button'));
    await waitFor(() => expect(screen.getByTestId('time-lock-cancel-done')).toBeTruthy());
    expect(ApiService.recoveryNotices.cancelTimeLock).toHaveBeenCalledWith('tok-123');
  });

  it.each([
    [{ error: 'failed' }, 'failed'],
    [{ detail: 'Request was throttled.' }, 'Request was throttled.'],
    [undefined, 'Could not reach the server. Try again.'],
  ])('shows why a cancel failed: %j', async (body, shown) => {
    ApiService.recoveryNotices.cancelTimeLock.mockRejectedValue(new Error('rejected'));
    ApiService.handleError.mockReturnValue(body);
    renderAt('/recovery/time-lock/cancel?token=tok-123');
    fireEvent.click(screen.getByTestId('time-lock-cancel-button'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe(shown));
  });

  it('explains an incomplete link', () => {
    renderAt('/recovery/time-lock/cancel');
    expect(screen.queryByTestId('time-lock-cancel-button')).toBeNull();
  });
});
