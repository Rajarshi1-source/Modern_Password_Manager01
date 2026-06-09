/**
 * Adaptive ZK v2 — "no plaintext on the wire" leak/contract test (PR-4).
 *
 * This is the frontend half of the leak test from
 * docs/adaptive-password-zk-remediation-plan.md §8: intercept axios and, for
 * every adaptive call (record / suggest / apply), assert the serialized request
 * never contains the raw password (or its substring) — only keyed fingerprints,
 * coarse features, substitution *classes*, and masked previews.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, act } from '@testing-library/react';
import axios from 'axios';
import TypingPatternCapture, { adaptivePasswordService } from '../TypingPatternCapture';

vi.mock('axios');

const SECRET = 'Sup3rSecret-Passw0rd!';

// Deterministic, non-leaking keyed-fingerprint stand-in (real impl:
// cryptoService.passwordFingerprint). Differs per password; never contains it.
const fingerprint = vi.fn(async (pw) =>
  'fp' + [...pw].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7).toString(36).padStart(20, '0')
);

const PREFERENCE_MODEL = {
  model_version: 4,
  substitution_weights: {
    o: { 0: 0.9 }, a: { '@': 0.8 }, e: { 3: 0.7 }, s: { $: 0.4, 5: 0.6 },
  },
  memorability_params: {},
};

function assertNoSecret(calls) {
  for (const call of calls) {
    expect(JSON.stringify(call)).not.toContain(SECRET);
  }
}

describe('adaptive ZK v2 — no plaintext on the wire', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(axios.post).mockResolvedValue({ data: { ok: true } });
    vi.mocked(axios.get).mockResolvedValue({ data: PREFERENCE_MODEL });
    vi.mocked(axios.delete).mockResolvedValue({ data: {} });
  });

  it('record-session posts a keyed fingerprint, never the password', async () => {
    const input = document.createElement('input');
    input.type = 'password';
    const inputRef = { current: input };

    render(<TypingPatternCapture inputRef={inputRef} enabled fingerprint={fingerprint} />);

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    await act(async () => {
      await inputRef.current.captureTypingPattern(SECRET);
    });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/adaptive/record-session/'),
      expect.objectContaining({ schema_version: 2, password_fingerprint: expect.any(String) }),
      expect.any(Object)
    );
    const body = vi.mocked(axios.post).mock.calls[0][1];
    expect(body).not.toHaveProperty('password');
    expect(body.password_fingerprint).toBeTruthy();
    assertNoSecret(vi.mocked(axios.post).mock.calls);
  });

  it('suggestAdaptation pulls the model and never POSTs the password', async () => {
    const result = await adaptivePasswordService.suggestAdaptation(SECRET);

    expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/adaptive/preference-model/'));
    expect(axios.post).not.toHaveBeenCalled();
    expect(result.has_suggestion).toBe(true);
    // Neither the suggestion object nor any GET arg leaks the password.
    expect(JSON.stringify(result)).not.toContain(SECRET);
    assertNoSecret(vi.mocked(axios.get).mock.calls);
  });

  it('applyAdaptation posts only fingerprints, masked previews, and classes', async () => {
    const suggestion = await adaptivePasswordService.suggestAdaptation(SECRET);
    const result = await adaptivePasswordService.applyAdaptation(
      SECRET, suggestion.substitutions, { fingerprint }
    );

    const body = vi.mocked(axios.post).mock.calls[0][1];

    // The adapted password is returned to the caller (to update the stored
    // credential) but must never be transmitted — only its fingerprint is.
    expect(typeof result.adaptedPassword).toBe('string');
    expect(result.adaptedPassword).not.toBe(SECRET);
    expect(JSON.stringify(body)).not.toContain(result.adaptedPassword);
    expect(body).toMatchObject({
      schema_version: 2,
      original_fingerprint: expect.any(String),
      adapted_fingerprint: expect.any(String),
    });
    expect(body).not.toHaveProperty('original_password');
    expect(body).not.toHaveProperty('adapted_password');
    expect(body.original_fingerprint).not.toBe(body.adapted_fingerprint);

    // Masked previews must actually be masked.
    expect(body.previews.original_masked).toMatch(/\*/);
    expect(body.previews.adapted_masked).toMatch(/\*/);

    // Substitutions are class-level only — no positions or password characters.
    for (const sub of body.substitutions) {
      expect(sub).not.toHaveProperty('position');
      expect(sub).not.toHaveProperty('original_char');
      expect(Object.keys(sub).every((k) => ['from', 'to', 'confidence'].includes(k))).toBe(true);
      expect(sub.from).toHaveLength(1);
      expect(sub.to).toHaveLength(1);
    }

    assertNoSecret(vi.mocked(axios.post).mock.calls);
  });
});
