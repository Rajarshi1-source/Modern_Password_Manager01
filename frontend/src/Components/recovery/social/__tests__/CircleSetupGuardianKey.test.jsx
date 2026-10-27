import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../../../services/api', () => ({
  default: {
    socialRecovery: { listCircles: vi.fn().mockResolvedValue({ data: [] }), createCircle: vi.fn() },
    handleError: () => ({ error: 'network' }),
  },
}));
vi.mock('../../../../services/recovery/holderKeyStore', () => ({
  getOrCreateGuardianPublicKey: vi.fn().mockResolvedValue(btoa('k'.repeat(1216))),
}));

import ApiService from '../../../../services/api';
import CircleSetup from '../CircleSetup';
import GuardianKey from '../GuardianKey';

describe('CircleSetup', () => {
  it('refuses an odd-length hex secret with the validation message', async () => {
    const { container } = render(<CircleSetup />);
    await waitFor(() => expect(ApiService.socialRecovery.listCircles).toHaveBeenCalled());
    fireEvent.click(screen.getByText('+ New Circle'));
    fireEvent.change(screen.getByPlaceholderText(/64\+ hex chars/), { target: { value: 'a'.repeat(33) } });
    fireEvent.submit(container.querySelector('form'));
    expect(await screen.findByText(/even-length hex string/)).toBeTruthy();
    expect(ApiService.socialRecovery.createCircle).not.toHaveBeenCalled();
  });
});

describe('GuardianKey', () => {
  it('warns that the key lives only in this browser', async () => {
    render(<GuardianKey />);
    const note = await screen.findByTestId('guardian-key-storage-note');
    expect(note.textContent).toMatch(/only in this browser/);
  });
});
