import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

vi.mock('../../../../services/recovery/holderKeyStore', () => ({
  getOrCreateGuardianPublicKey: vi.fn(),
  replaceLostGuardianKey: vi.fn(),
}));

import {
  getOrCreateGuardianPublicKey,
  replaceLostGuardianKey,
} from '../../../../services/recovery/holderKeyStore';
import GuardianKey from '../GuardianKey';

describe('GuardianKey', () => {
  it('says why the key store failed when the store can explain it', async () => {
    getOrCreateGuardianPublicKey.mockRejectedValue(
      Object.assign(new Error('No IndexedDB here.'), { name: 'KeyStorageError' }),
    );
    render(<GuardianKey />);
    expect((await screen.findByRole('alert')).textContent).toBe('No IndexedDB here.');
    expect(screen.queryByTestId('guardian-key-replace')).toBeNull();
  });

  it('offers a new key only when the stored one is lost', async () => {
    getOrCreateGuardianPublicKey.mockRejectedValue(
      Object.assign(new Error('Lost.'), { name: 'KeyStorageError', keyLost: true }),
    );
    const replacement = 'AAECAw==';
    replaceLostGuardianKey.mockResolvedValue(replacement);
    render(<GuardianKey />);
    fireEvent.click(await screen.findByTestId('guardian-key-replace'));
    expect(replaceLostGuardianKey).toHaveBeenCalledTimes(1);
    expect((await screen.findByTestId('guardian-public-key')).value).toBe(replacement);
  });

  it('does not show other errors as they are', async () => {
    getOrCreateGuardianPublicKey.mockRejectedValue(new Error('internal detail'));
    render(<GuardianKey />);
    expect((await screen.findByRole('alert')).textContent)
      .toBe('Could not create a guardian key in this browser.');
  });
});
