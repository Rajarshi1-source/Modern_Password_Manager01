/**
 * StegoVaultDashboard must not tell a coercer WHICH slot an extraction
 * opened.
 *
 * The extract handler already strips `__duress_signal` from the rendered
 * payload (PR #486 round 3), for an explicitly stated reason: someone
 * watching this screen during a "successful" decoy extraction must not see
 * anything revealing that an alarm fired. But the panel then printed
 * "Unlocked slot index: 1" directly above that payload, which states the
 * same fact in plainer words -- making the strip pointless against exactly
 * the observer it was written for.
 *
 * These tests pin the fix and, just as importantly, pin that the ALARM still
 * receives the true slot: the disclosure is a display concern, and removing
 * it must not weaken the duress reporting that depends on the same value.
 */
import React from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

const { mockExtractVault, mockReportUnlockForSlot } = vi.hoisted(() => ({
  mockExtractVault: vi.fn(),
  mockReportUnlockForSlot: vi.fn(),
}));

vi.mock('../../../services/stego', () => ({
  TIERS: { TIER0_32K: 0 },
  capacityReport: vi.fn(() => ({ ok: true })),
  computeCoverHash: vi.fn(async () => 'hash'),
  embedVault: vi.fn(),
  extractVault: (...args) => mockExtractVault(...args),
}));

vi.mock('../../../services/stego/stegoApi', () => ({
  deleteStegoVault: vi.fn(),
  downloadStegoImage: vi.fn(),
  fetchStegoConfig: vi.fn(async () => ({})),
  listStegoEvents: vi.fn(async () => []),
  listStegoVaults: vi.fn(async () => []),
  storeStegoImage: vi.fn(),
}));

vi.mock('../../../services/duressSignalService', () => ({
  generateSignalToken: vi.fn(() => 'a'.repeat(44)),
  registerSignalToken: vi.fn(),
  reportUnlockForSlot: (...args) => mockReportUnlockForSlot(...args),
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: 'user-1' },
    getAccessToken: () => 'jwt-token',
  }),
}));

vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  Link: ({ children }) => <span>{children}</span>,
}));

import StegoVaultDashboard from '../StegoVaultDashboard';

// The decoy payload a user authored, and the real one. Deliberately the same
// SHAPE, so any difference the panel shows comes from the app, not the data.
const REAL_JSON = { entries: [{ site: 'bank.example', password: 'r3al' }] };
const DECOY_JSON = { entries: [{ site: 'forum.example', password: 'dec0y' }] };

// There are two PNG inputs: [0] is the cover image for EMBEDDING, [1] is the
// stego image for EXTRACTING. Only the second one matters here; feeding the
// first drags in the capacity-report path this test has no interest in.
const pickExtractImage = async (container) => {
  const fileInputs = container.querySelectorAll('input[type="file"]');
  const file = new File([new Uint8Array([1, 2, 3])], 'stego.png', { type: 'image/png' });
  Object.defineProperty(file, 'arrayBuffer', {
    value: async () => new Uint8Array([1, 2, 3]).buffer,
  });
  fireEvent.change(fileInputs[1], { target: { files: [file] } });
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('StegoVaultDashboard extraction result', () => {
  const renderAndExtract = async (slotIndex, json) => {
    mockExtractVault.mockResolvedValue({ slotIndex, json });

    const { container, getByText, findByText } = render(<StegoVaultDashboard />);
    await pickExtractImage(container);

    // The extract password is the last password field on the page.
    await waitFor(() => {
      expect(container.querySelectorAll('input[type="password"]').length).toBeGreaterThan(0);
    });
    const passwordInputs = container.querySelectorAll('input[type="password"]');
    fireEvent.change(passwordInputs[passwordInputs.length - 1], {
      target: { value: 'whatever-password' },
    });
    fireEvent.click(getByText('Extract'));

    await waitFor(() => expect(mockExtractVault).toHaveBeenCalled());
    await findByText(/entries/);
    return container;
  };

  test('a DECOY extraction never names the slot it opened', async () => {
    const container = await renderAndExtract(1, DECOY_JSON);

    // Scoped to the RESULT PANEL, not the whole page: the section's intro
    // copy legitimately says "password-unlocked slots with plausible
    // deniability", which a page-wide match on /unlocked slot/i would flag.
    // What matters is that the panel reporting THIS extraction says nothing
    // about which slot produced it.
    const panel = container.querySelector('pre').parentElement;
    expect(panel.textContent).not.toMatch(/slot/i);
    expect(panel.textContent).not.toMatch(/\b[01]\b/);
    expect(container.textContent).not.toMatch(/slot index/i);
    // The decoy's own payload IS shown -- that is the decoy working, not a
    // leak. What must not appear is anything identifying it AS the decoy.
    expect(panel.textContent).toContain('forum.example');
  });

  test('the alarm still receives the true slot index -- display change only', async () => {
    await renderAndExtract(1, DECOY_JSON);

    // reportUnlockForSlot decides real-token-vs-noise from this value, so
    // removing it from the UI must not remove it from the report.
    expect(mockReportUnlockForSlot).toHaveBeenCalledWith(
      'jwt-token',
      1,
      expect.objectContaining({ entries: expect.any(Array) })
    );
  });

  test('real and decoy extractions render the same structure, differing only in their own payloads', async () => {
    const realContainer = await renderAndExtract(0, REAL_JSON);
    const realHtml = realContainer.innerHTML;
    cleanup();

    const decoyContainer = await renderAndExtract(1, DECOY_JSON);
    const decoyHtml = decoyContainer.innerHTML;

    // Normalise away each slot's own contents; everything the COMPONENT
    // decides must then be identical. Before the fix this failed on the
    // "Unlocked slot index: 0" / ": 1" line.
    const normalise = (html) =>
      html.replace(/bank\.example|forum\.example/g, 'SITE')
        .replace(/r3al|dec0y/g, 'SECRET');

    expect(normalise(decoyHtml)).toBe(normalise(realHtml));
  });
});
