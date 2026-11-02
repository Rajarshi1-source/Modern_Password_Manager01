import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GuardianRecoveryAttempt from './GuardianRecoveryAttempt';

const renderAt = (url) => render(
  <MemoryRouter initialEntries={[url]}>
    <GuardianRecoveryAttempt />
  </MemoryRouter>,
);

describe('GuardianRecoveryAttempt', () => {
  it('shows the recovery ID from the emailed link', () => {
    renderAt('/recovery/guardian-attempt?attempt=abc-123');
    expect(screen.getByTestId('guardian-recovery-attempt-id').textContent).toBe('abc-123');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('says so when the link has no recovery ID', () => {
    renderAt('/recovery/guardian-attempt');
    expect(screen.getByRole('alert').textContent).toMatch(/incomplete/);
    expect(screen.queryByTestId('guardian-recovery-attempt-id')).toBeNull();
  });
});
