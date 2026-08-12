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
import TypingPatternCapture, {
  adaptivePasswordService,
  ADAPTIVE_API_TIMEOUT_MS,
} from '../TypingPatternCapture';

vi.mock('axios');

const SECRET = 'Sup3rSecret-Passw0rd!';

// Fingerprint key era, as GET /adaptive/config/ reports it. Required on every
// v2 write: the server rejects a mismatch with HTTP 409 rather than recording
// fingerprints from a superseded key against a live profile.
const FP_KEY_VERSION = 1;

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

// Phase 2 added a strength gate in front of every suggestion, and the real
// zxcvbn estimator rejects *every* leet substitution on these fixtures (both
// SECRET and 'MySecret123!' de-leet straight onto dictionary hits — verified
// against the real estimator, not assumed). These tests are about what crosses
// the wire, not about the gate, so they inject a **neutral** estimator: the
// gate still runs end-to-end, it just has no reason to reject. Gate behaviour
// itself is covered in services/adaptive/__tests__/adaptiveFeatures.test.js.
const NEUTRAL_ESTIMATE = { guessesLog10: 12, sequence: [] };
const neutralEstimator = () => NEUTRAL_ESTIMATE;

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

    render(
      <TypingPatternCapture
        inputRef={inputRef}
        enabled
        fingerprint={fingerprint}
        fpKeyVersion={FP_KEY_VERSION}
      />
    );

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    await act(async () => {
      await inputRef.current.captureTypingPattern(SECRET);
    });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/adaptive/record-session/'),
      expect.objectContaining({
        schema_version: 2,
        fp_key_version: FP_KEY_VERSION,
        password_fingerprint: expect.any(String),
      }),
      expect.any(Object)
    );
    const body = vi.mocked(axios.post).mock.calls[0][1];
    expect(body).not.toHaveProperty('password');
    expect(body.password_fingerprint).toBeTruthy();
    assertNoSecret(vi.mocked(axios.post).mock.calls);
  });

  it('record-session reports substitution classes and an explicit outcome', async () => {
    // Phase 3, gap B2: without these the server's _record_substitution_classes
    // was unreachable from the real client path, and `success` fell back to a
    // "no backspaces" heuristic the service's own docstring warns against.
    const input = document.createElement('input');
    input.type = 'password';
    const inputRef = { current: input };

    render(
      <TypingPatternCapture
        inputRef={inputRef}
        enabled
        fingerprint={fingerprint}
        fpKeyVersion={FP_KEY_VERSION}
      />
    );

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    await act(async () => {
      await inputRef.current.captureTypingPattern(SECRET, { success: true });
    });

    const body = vi.mocked(axios.post).mock.calls[0][1];
    // SECRET is 'Sup3rSecret-Passw0rd!': a '3', a '0' — and a trailing '!',
    // which REVERSE_LEET_MAP resolves to 'i'. That last one is a known,
    // documented false positive: '!' as ordinary punctuation is
    // indistinguishable from '!' as leetspeak for 'i' without knowing the
    // un-leeted word. It costs the bandit a little signal quality; it leaks
    // nothing extra, since the class is reported either way.
    expect(body.substitution_classes_used).toEqual([
      { from: 'e', to: '3' },
      { from: 'o', to: '0' },
      { from: 'i', to: '!' },
    ]);
    expect(body.success).toBe(true);
    // Classes only: no positions, no context, nothing password-shaped.
    for (const entry of body.substitution_classes_used) {
      expect(Object.keys(entry).sort()).toEqual(['from', 'to']);
    }
    assertNoSecret(vi.mocked(axios.post).mock.calls);
  });

  it('omits success entirely when the caller does not know the outcome', async () => {
    // Absence means "fall back to the heuristic"; an invented `false` would
    // train the bandit that a successful entry failed.
    const input = document.createElement('input');
    input.type = 'password';
    const inputRef = { current: input };

    render(
      <TypingPatternCapture
        inputRef={inputRef}
        enabled
        fingerprint={fingerprint}
        fpKeyVersion={FP_KEY_VERSION}
      />
    );

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    await act(async () => {
      await inputRef.current.captureTypingPattern(SECRET);
    });

    const body = vi.mocked(axios.post).mock.calls[0][1];
    expect(body).not.toHaveProperty('success');
  });

  it('suggestAdaptation pulls the model and never POSTs the password', async () => {
    const result = await adaptivePasswordService.suggestAdaptation(SECRET, { estimator: neutralEstimator, explore: false });

    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining('/adaptive/preference-model/'),
      expect.objectContaining({ timeout: ADAPTIVE_API_TIMEOUT_MS })
    );
    expect(axios.post).not.toHaveBeenCalled();
    expect(result.has_suggestion).toBe(true);
    // Neither the suggestion object nor any GET arg leaks the password.
    expect(JSON.stringify(result)).not.toContain(SECRET);
    assertNoSecret(vi.mocked(axios.get).mock.calls);
  });

  it('applyAdaptation posts only fingerprints, masked previews, and classes', async () => {
    const suggestion = await adaptivePasswordService.suggestAdaptation(SECRET, { estimator: neutralEstimator, explore: false });
    const result = await adaptivePasswordService.applyAdaptation(
      SECRET, suggestion.substitutions, { fingerprint, fpKeyVersion: FP_KEY_VERSION }
    );

    const body = vi.mocked(axios.post).mock.calls[0][1];

    // The adapted password is returned to the caller (to update the stored
    // credential) but must never be transmitted — only its fingerprint is.
    expect(typeof result.adaptedPassword).toBe('string');
    expect(result.adaptedPassword).not.toBe(SECRET);
    expect(JSON.stringify(body)).not.toContain(result.adaptedPassword);
    expect(body).toMatchObject({
      schema_version: 2,
      fp_key_version: FP_KEY_VERSION,
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

  it('applyAdaptation includes a finite driver delta, omits a non-finite one', async () => {
    const suggestion = await adaptivePasswordService.suggestAdaptation(SECRET, { estimator: neutralEstimator, explore: false });

    await adaptivePasswordService.applyAdaptation(
      SECRET, suggestion.substitutions,
      {
        fingerprint, fpKeyVersion: FP_KEY_VERSION,
        memorabilityDriver: 'variety', memorabilityDriverDelta: -0.67,
      },
    );
    const withDelta = vi.mocked(axios.post).mock.calls.at(-1)[1];
    expect(withDelta.memorability_driver_delta).toBe(-0.67);

    vi.mocked(axios.post).mockClear();
    await adaptivePasswordService.applyAdaptation(
      SECRET, suggestion.substitutions,
      {
        fingerprint, fpKeyVersion: FP_KEY_VERSION,
        memorabilityDriver: 'variety', memorabilityDriverDelta: NaN,
      },
    );
    const withNaN = vi.mocked(axios.post).mock.calls.at(-1)[1];
    // Same failure mode the score fields already guard against: a NaN here
    // would 400 the whole apply request over an informational field.
    expect(withNaN).not.toHaveProperty('memorability_driver_delta');
  });
});

describe('adaptive ZK v2 — fingerprint key era', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(axios.post).mockResolvedValue({ data: { ok: true } });
    vi.mocked(axios.get).mockResolvedValue({ data: PREFERENCE_MODEL });
  });

  it('record-session refuses to post without an era', async () => {
    // Fail closed: recording under a guessed era would write fingerprints from
    // a possibly-dead key into a live profile, which nothing downstream can
    // detect or undo. Nothing must reach the wire.
    //
    // Note: TypingPatternCapture (the component) does not accept an `onError`
    // prop — internally it wires useTypingPattern's onError to its own local
    // setError, which isn't observable from outside. The one guaranteed
    // observable side effect on this path is console.error, which the catch
    // block calls unconditionally before checking for an onError handler.
    const input = document.createElement('input');
    input.type = 'password';
    const inputRef = { current: input };
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <TypingPatternCapture
        inputRef={inputRef}
        enabled
        fingerprint={fingerprint}
        onPatternCaptured={() => {}}
      />
    );

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    let pattern;
    await act(async () => {
      pattern = await inputRef.current.captureTypingPattern(SECRET);
    });

    expect(pattern).toBeNull();
    expect(axios.post).not.toHaveBeenCalled();
    // The fail-closed error must actually surface, not be swallowed silently.
    expect(consoleError).toHaveBeenCalledWith(
      'Error capturing pattern:',
      expect.objectContaining({ message: expect.stringContaining('fpKeyVersion') })
    );
    consoleError.mockRestore();
  });

  it('applyAdaptation refuses to post without an era', async () => {
    const suggestion = await adaptivePasswordService.suggestAdaptation(SECRET, { estimator: neutralEstimator, explore: false });
    vi.mocked(axios.post).mockClear();

    await expect(
      adaptivePasswordService.applyAdaptation(SECRET, suggestion.substitutions, {
        fingerprint,
      })
    ).rejects.toThrow(/fpKeyVersion/);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('makeFingerprinter binds the per-user salt and needs an unlocked service', () => {
    const cryptoService = { passwordFingerprint: vi.fn(async () => 'fp-stub') };
    const fp = adaptivePasswordService.makeFingerprinter(cryptoService, 'deadbeef');

    fp(SECRET);
    expect(cryptoService.passwordFingerprint).toHaveBeenCalledWith(SECRET, 'deadbeef');

    expect(() => adaptivePasswordService.makeFingerprinter(null, 'deadbeef')).toThrow();
    expect(() => adaptivePasswordService.makeFingerprinter(cryptoService, '')).toThrow();
  });

  it('rotateFingerprintKey sends an explicit confirmation', async () => {
    vi.mocked(axios.post).mockResolvedValue({
      data: { success: true, fingerprint_salt: 'cafebabe', fp_key_version: 2 },
    });

    const result = await adaptivePasswordService.rotateFingerprintKey();

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/adaptive/rotate-fingerprint-key/'),
      { confirm: true },
      expect.objectContaining({ timeout: ADAPTIVE_API_TIMEOUT_MS })
    );
    expect(result.fp_key_version).toBe(2);
  });
});
