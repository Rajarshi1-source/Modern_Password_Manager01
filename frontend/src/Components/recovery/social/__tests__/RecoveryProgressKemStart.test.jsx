import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// A failed ML-KEM start is local and transient: it must take the retry path,
// not abandon a request whose re-sealed shares are all valid.
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
  loadRequesterKeyPair: vi.fn().mockResolvedValue({ publicKey: 'pk', secretKey: 'sk' }),
  forgetRequesterKeyPair: vi.fn(),
}));
vi.mock('../../../../services/quantum/hybridKem', () => ({
  ensureHybridKemReady: vi.fn().mockRejectedValue(new Error('mlkem start failed')),
}));

import ApiService from '../../../../services/api';
import { forgetRequesterKeyPair } from '../../../../services/recovery/holderKeyStore';
import { ensureHybridKemReady } from '../../../../services/quantum/hybridKem';
import RecoveryProgress from '../RecoveryProgress';

describe('RecoveryProgress', () => {
  it('retries when ML-KEM fails to start instead of abandoning the request', async () => {
    render(
      <MemoryRouter>
        <RecoveryProgress recoveryAttemptId="r1" onSecretReconstructed={vi.fn()} />
      </MemoryRouter>,
    );
    await waitFor(() => expect(ensureHybridKemReady).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(ApiService.socialRecovery.completeRequest).not.toHaveBeenCalled();
    expect(ApiService.socialRecovery.abandonRequest).not.toHaveBeenCalled();
    expect(forgetRequesterKeyPair).not.toHaveBeenCalled();
  });
});
