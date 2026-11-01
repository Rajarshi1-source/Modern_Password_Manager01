import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import BehavioralRecoveryFlow from '../BehavioralRecoveryFlow';

// Raw typing and mouse data must not leave the browser: an existing attempt
// loads no challenge and sends nothing.
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe('BehavioralRecoveryFlow', () => {
  it('shows the retired state for an existing attempt without any request', async () => {
    render(
      <MemoryRouter>
        <BehavioralRecoveryFlow attemptId="11111111-1111-1111-1111-111111111111" />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/no longer available/)).toBeTruthy();
    expect(screen.getByText('Use my recovery key')).toBeTruthy();
    expect(axios.get).not.toHaveBeenCalled();
    expect(axios.post).not.toHaveBeenCalled();
  });
});
