/**
 * A reload after the recovery key was accepted resumes the new-passkey
 * registration: the key is already spent and the lost passkey revoked, so
 * starting over from step 1 would strand the user.
 */
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, test, vi } from 'vitest';

vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));

const beginRegistration = vi.fn();
vi.mock('../../../services/api', () => ({
  default: {
    passkeyPrimaryRecovery: {
      beginRegistration: (...args) => beginRegistration(...args),
      initiateRecovery: vi.fn(),
      completeRecovery: vi.fn(),
      completeRegistration: vi.fn(),
      fallbackToSocialMesh: vi.fn(),
    },
  },
}));

import PasskeyPrimaryRecoveryInitiate from '../PasskeyPrimaryRecoveryInitiate';

const renderPage = () => render(
  <MemoryRouter><PasskeyPrimaryRecoveryInitiate /></MemoryRouter>,
);

afterEach(() => {
  cleanup();
  beginRegistration.mockReset();
});

describe('PasskeyPrimaryRecoveryInitiate', () => {
  test('resumes at the new-passkey step when the session still holds a grant', async () => {
    beginRegistration.mockResolvedValue({
      data: { registration_options: { challenge: 'Y2g', user: { id: 'dQ' } } },
    });
    renderPage();
    expect(await screen.findByText('Create New Passkey')).toBeInTheDocument();
    expect(beginRegistration).toHaveBeenCalledTimes(1);
  });

  test('starts at account identification without a grant', async () => {
    beginRegistration.mockRejectedValue(Object.assign(new Error('no grant'), { response: { status: 400 } }));
    renderPage();
    await waitFor(() => expect(beginRegistration).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Create New Passkey')).not.toBeInTheDocument();
  });
});
