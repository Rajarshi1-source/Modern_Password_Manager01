import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GuardianRecoveryAttempt from './GuardianRecoveryAttempt';

const ATTEMPT_ID = '3f2b8c1e-7a4d-4e9b-8c21-5d6f7a8b9c0d';

const renderAt = (url) => render(
  <MemoryRouter initialEntries={[url]}>
    <GuardianRecoveryAttempt />
  </MemoryRouter>,
);

describe('GuardianRecoveryAttempt', () => {
  it('shows the recovery ID from the emailed link', () => {
    renderAt(`/recovery/guardian-attempt?attempt=${ATTEMPT_ID}`);
    expect(screen.getByTestId('guardian-recovery-attempt-id').textContent).toBe(ATTEMPT_ID);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('does not offer a step this app cannot do', () => {
    renderAt(`/recovery/guardian-attempt?attempt=${ATTEMPT_ID}`);
    expect(screen.getByTestId('guardian-recovery-attempt').textContent).toMatch(/cannot be finished\s+from this page/);
  });

  it.each(['abc-123', ATTEMPT_ID.slice(0, -1), `${ATTEMPT_ID}x`])('treats %s as an incomplete link', (value) => {
    renderAt(`/recovery/guardian-attempt?attempt=${value}`);
    expect(screen.getByRole('alert').textContent).toMatch(/incomplete/);
    expect(screen.queryByTestId('guardian-recovery-attempt-id')).toBeNull();
  });

  it('says so when the link has no recovery ID', () => {
    renderAt('/recovery/guardian-attempt');
    expect(screen.getByRole('alert').textContent).toMatch(/incomplete/);
    expect(screen.queryByTestId('guardian-recovery-attempt-id')).toBeNull();
  });
});
