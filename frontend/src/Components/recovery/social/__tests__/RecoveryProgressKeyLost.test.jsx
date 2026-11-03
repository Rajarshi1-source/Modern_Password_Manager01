import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// A requester key that cannot be opened will not open on a later poll, so the
// page says so instead of retrying without a word.
vi.mock('../../../../services/api', () => ({
  default: {
    socialRecovery: {
      getRequest: vi.fn().mockResolvedValue({ data: { request_id: 'r1', status: 'approved' } }),
      completeRequest: vi.fn(),
      abandonRequest: vi.fn(),
    },
    handleError: () => ({ error: 'network' }),
  },
}));
vi.mock('../../../../services/recovery/holderKeyStore', () => ({
  loadRequesterKeyPair: vi.fn().mockRejectedValue(
    Object.assign(new Error('Start recovery again.'), { name: 'KeyStorageError', keyLost: true }),
  ),
  forgetRequesterKeyPair: vi.fn(),
}));

import ApiService from '../../../../services/api';
import { forgetRequesterKeyPair } from '../../../../services/recovery/holderKeyStore';
import RecoveryProgress from '../RecoveryProgress';

describe('RecoveryProgress', () => {
  it('explains a lost requester key and leaves the request alone', async () => {
    render(
      <MemoryRouter>
        <RecoveryProgress recoveryAttemptId="r1" onSecretReconstructed={vi.fn()} />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Start recovery again\./)).toBeTruthy();
    expect(ApiService.socialRecovery.completeRequest).not.toHaveBeenCalled();
    expect(ApiService.socialRecovery.abandonRequest).not.toHaveBeenCalled();
    expect(forgetRequesterKeyPair).not.toHaveBeenCalled();
  });
});
