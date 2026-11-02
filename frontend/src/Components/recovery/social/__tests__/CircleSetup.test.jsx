import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const socialRecovery = vi.hoisted(() => ({ listCircles: vi.fn(), createCircle: vi.fn() }));

vi.mock('../../../../services/api', () => ({
  default: {
    socialRecovery,
    handleError: (err) => ({ error: err?.response?.data?.error }),
  },
}));
vi.mock('../../../../services/quantum/hybridKem', () => ({
  HYBRID_PUBLIC_KEY_SIZE: 1216,
  ensureHybridKemReady: vi.fn(), generateHybridKeyPair: vi.fn(), openSealed: vi.fn(), sealToHybridKey: vi.fn(),
}));

import CircleSetup from '../CircleSetup';

describe('CircleSetup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    socialRecovery.listCircles.mockResolvedValue({ data: [] });
  });

  it('offers no new circle and points at guardian recovery', async () => {
    render(<CircleSetup />);
    const notice = await screen.findByTestId('circle-setup-unavailable');
    expect(notice.querySelector('a').getAttribute('href')).toBe('/recovery/guardian/setup');
    expect(screen.queryByRole('button', { name: /new circle/i })).toBeNull();
    expect(screen.queryByText('Create Recovery Circle')).toBeNull();
    await screen.findByText('No recovery circles yet');
    expect(screen.queryByText(/Start by creating one/)).toBeNull();
  });

  it('still lists a circle made earlier, and says it cannot recover', async () => {
    socialRecovery.listCircles.mockResolvedValue({
      data: [{
        circle_id: '3f2b8c1e-7a4d-4e9b-8c21-5d6f7a8b9c0d', status: 'active',
        threshold: 2, total_vouchers: 3, vouchers: [],
      }],
    });
    render(<CircleSetup />);
    await screen.findByText(/3f2b8c1e/);
    expect(screen.getByTestId('circle-setup-unavailable').textContent).toMatch(/cannot\s+recover/);
  });
});
