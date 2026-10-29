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
import { newHolderKeyPair } from '../../../../services/recovery/sealedShareRecovery';
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

  it('reports a malformed or reused guardian key as an input error', async () => {
    const { container } = render(<CircleSetup />);
    await waitFor(() => expect(ApiService.socialRecovery.listCircles).toHaveBeenCalled());
    fireEvent.click(screen.getByText('+ New Circle'));
    fireEvent.change(screen.getByPlaceholderText(/64\+ hex chars/), { target: { value: 'ab'.repeat(32) } });
    const fill = (keys) => {
      screen.getAllByPlaceholderText('alice@example.com').forEach((el, i) =>
        fireEvent.change(el, { target: { value: `v${i}@example.com` } }));
      screen.getAllByPlaceholderText('64 hex chars').forEach((el) =>
        fireEvent.change(el, { target: { value: 'cd'.repeat(32) } }));
      screen.getAllByPlaceholderText(/copies this from/).forEach((el, i) =>
        fireEvent.change(el, { target: { value: keys[i] } }));
      fireEvent.submit(container.querySelector('form'));
    };
    const key = (c) => btoa(c.repeat(1216));
    fill([key('a'), btoa('short'), key('c')]);
    expect(await screen.findByText(/Voucher #2's guardian key is not a valid key/)).toBeTruthy();
    fill([key('a'), key('a'), key('c')]);
    expect(await screen.findByText(/Two vouchers have the same guardian key/)).toBeTruthy();
    expect(ApiService.socialRecovery.createCircle).not.toHaveBeenCalled();
  });

  it('sends each guardian key in canonical base64, as it was sealed to', async () => {
    ApiService.socialRecovery.createCircle.mockResolvedValueOnce({ data: {} });
    const { container } = render(<CircleSetup />);
    await waitFor(() => expect(ApiService.socialRecovery.listCircles).toHaveBeenCalled());
    fireEvent.click(screen.getByText('+ New Circle'));
    fireEvent.change(screen.getByPlaceholderText(/64\+ hex chars/), { target: { value: 'ab'.repeat(32) } });
    const keys = await Promise.all([1, 2, 3].map(async () => (await newHolderKeyPair()).publicKey));
    screen.getAllByPlaceholderText('alice@example.com').forEach((el, i) =>
      fireEvent.change(el, { target: { value: `v${i}@example.com` } }));
    screen.getAllByPlaceholderText('64 hex chars').forEach((el) =>
      fireEvent.change(el, { target: { value: 'cd'.repeat(32) } }));
    // As pasted from a chat: a line break inside, the padding dropped.
    screen.getAllByPlaceholderText(/copies this from/).forEach((el, i) =>
      fireEvent.change(el, { target: { value: `${keys[i].slice(0, 40)}\n${keys[i].slice(40)}`.replace(/=+$/, '') } }));
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(ApiService.socialRecovery.createCircle).toHaveBeenCalled());
    const sent = ApiService.socialRecovery.createCircle.mock.calls[0][0].vouchers;
    expect(sent.map((v) => v.hybrid_public_key)).toEqual(keys);
  });
});

describe('GuardianKey', () => {
  it('warns that the key lives only in this browser', async () => {
    render(<GuardianKey />);
    const note = await screen.findByTestId('guardian-key-storage-note');
    expect(note.textContent).toMatch(/only in this browser/);
  });
});
