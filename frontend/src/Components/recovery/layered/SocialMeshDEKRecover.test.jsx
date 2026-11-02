import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../../services/sessionVaultCryptoV3', () => ({ default: {} }));
vi.mock('../../../services/recoveryFactorService', () => ({ default: {} }));

import SocialMeshDEKRecover from './SocialMeshDEKRecover';

describe('SocialMeshDEKRecover', () => {
  it('says a circle is not guardian recovery, and names the other ways back', () => {
    render(<MemoryRouter><SocialMeshDEKRecover /></MemoryRouter>);
    const notice = within(screen.getByRole('alert'));
    expect(screen.getByRole('alert').textContent).toMatch(/circle alone will not send/);
    const href = (name) => notice.getByRole('link', { name }).getAttribute('href');
    expect(href('guardian recovery')).toBe('/recovery/guardian/start');
    expect(href('recovery key')).toBe('/recovery/key/use-v2');
    expect(href('time-locked recovery')).toBe('/recovery/time-lock/recover');
  });
});
