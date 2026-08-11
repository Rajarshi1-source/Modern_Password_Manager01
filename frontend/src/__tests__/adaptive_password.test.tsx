/**
 * Unit Tests for Adaptive Password Frontend Components
 * ====================================================
 *
 * Tests for React components, hooks, and the service used in the
 * Epigenetic Password Adaptation feature.
 *
 * NOTE: these tests are aligned to the *implemented* design:
 *  - `adaptivePasswordService` lives in `Components/security/TypingPatternCapture`
 *    and is axios-based (not a `fetch` service).
 *  - `TypingProfileCard` self-fetches via that service (it has no `profile` prop).
 *  - `TypingPatternCapture` is a headless component (renders null); the visible
 *    password-input/privacy UI it was originally specced with was never built,
 *    so those rendering tests are skipped (see below) rather than asserting
 *    non-existent markup.
 */

import React from 'react';
import { render, screen, act, renderHook, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';

// The adaptive service and the self-fetching TypingProfileCard use axios; mock
// it so we control responses and assert request shapes.
vi.mock('axios');

// Some code paths may also use fetch.
global.fetch = vi.fn();

// A low-entropy, obviously-fake stand-in for a client fingerprint. Referenced by
// name (not inlined next to `password_fingerprint`) so secret scanners don't
// mistake a base64url-looking literal for a real credential. The real value is
// produced by cryptoService.passwordFingerprint at runtime.
const FINGERPRINT_STUB = 'fp-not-a-real-fingerprint';
// Fingerprint key era, as GET /adaptive/config/ reports it. Required alongside
// the fingerprint fn on every v2 write (the server 409s on a mismatch).
const FP_KEY_VERSION = 1;

// The headless TypingPatternCapture attaches its capture/reset helpers directly
// onto the password input DOM node at mount, so tests that drive capture read
// them off `inputRef.current`. Model that augmented shape for type-check.
type CaptureCapableInput = HTMLInputElement & {
    captureTypingPattern: (password: string) => Promise<void>;
    resetTypingSession: () => void;
};

// =============================================================================
// useTypingPatternCapture Hook Tests
// =============================================================================

describe('useTypingPatternCapture Hook', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    test('initializes with default state', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
        }));

        expect(result.current.isCapturing).toBe(false);
        expect(result.current.sessionData).toBeNull();
    });

    test('startCapture sets isCapturing to true', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
        }));

        act(() => {
            result.current.startCapture();
        });

        expect(result.current.isCapturing).toBe(true);
    });

    test('captureKeystroke records timing', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
        }));

        act(() => {
            result.current.startCapture();
        });

        // Simulate keystrokes
        act(() => {
            result.current.captureKeystroke({ key: 'a' });
        });

        // Wait a bit and capture another
        await new Promise((r) => setTimeout(r, 50));

        act(() => {
            result.current.captureKeystroke({ key: 'b' });
        });

        expect(result.current.isCapturing).toBe(true);
    });

    test('captureError records error position', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
        }));

        act(() => {
            result.current.startCapture();
        });
        act(() => {
            result.current.captureError(5);
        });

        expect(result.current.isCapturing).toBe(true);
    });

    test('endCapture returns pattern data', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const mockCallback = vi.fn();
        // Zero-knowledge v2: a keyed-fingerprint fn is injected; endCapture emits
        // a fingerprint, not the raw password.
        const fingerprint = vi.fn(async () => FINGERPRINT_STUB);
        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
            fingerprint,
            fpKeyVersion: FP_KEY_VERSION,
            onPatternCaptured: mockCallback,
        }));

        act(() => {
            result.current.startCapture();
        });

        // The first keystroke only establishes the timing baseline; a second
        // keystroke is required before any inter-key timing is recorded, and
        // each call needs its own act() so isCapturing has flushed.
        act(() => {
            result.current.captureKeystroke({ key: 'a' });
        });
        act(() => {
            result.current.captureKeystroke({ key: 'b' });
        });

        let patternData: Record<string, unknown> | null = null;
        await act(async () => {
            patternData = await result.current.endCapture('testpass');
        });

        // Should return a v2 pattern: timing fields + keyed fingerprint, no password.
        expect(patternData).toBeDefined();
        expect(patternData).toHaveProperty('keystroke_timings');
        expect(patternData).toHaveProperty('backspace_positions');
        expect(patternData).toHaveProperty('device_type');
        expect(patternData).toHaveProperty('password_fingerprint');
        expect(patternData).toHaveProperty('fp_key_version', FP_KEY_VERSION);
        expect(patternData).not.toHaveProperty('password');
        expect(JSON.stringify(patternData)).not.toContain('testpass');
    });

    test('resetSession clears all data', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
        }));

        act(() => {
            result.current.startCapture();
            result.current.captureKeystroke({ key: 'a' });
            result.current.resetSession();
        });

        expect(result.current.isCapturing).toBe(false);
        expect(result.current.sessionData).toBeNull();
    });

    test('disabled hook does not capture', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: false,  // Disabled
        }));

        act(() => {
            result.current.startCapture();
        });

        // Should not be capturing when disabled
        expect(result.current.isCapturing).toBe(false);
    });
});

// =============================================================================
// TypingPatternCapture Component Tests
// =============================================================================
//
// The implemented `TypingPatternCapture` is a *headless* component: it renders
// `null` and wires keystroke capture onto a password input via a ref. These
// tests assert that real contract — no visible UI, ref wiring, and capture that
// reports timings (never the raw password) + auto-submits to the API.

describe('TypingPatternCapture Component (headless)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    test('renders no visible output (headless)', async () => {
        const { default: TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        const { container } = render(
            <TypingPatternCapture inputRef={{ current: null }} enabled={false} />
        );

        // The component returns null — it contributes no DOM.
        expect(container.firstChild).toBeNull();
    });

    test('exposes capture controls on the input ref', async () => {
        const { default: TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        const input = document.createElement('input');
        input.type = 'password';
        const inputRef = { current: input as CaptureCapableInput };

        render(<TypingPatternCapture inputRef={inputRef} enabled />);

        // On mount the component attaches its capture/reset helpers to the input.
        expect(typeof inputRef.current.captureTypingPattern).toBe('function');
        expect(typeof inputRef.current.resetTypingSession).toBe('function');
    });

    test('captures a zero-knowledge v2 pattern (keyed fingerprint, never the password)', async () => {
        const { default: TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        vi.mocked(axios.post).mockResolvedValue({ data: { recorded: true } });

        const input = document.createElement('input');
        input.type = 'password';
        const inputRef = { current: input as CaptureCapableInput };
        const onPatternCaptured = vi.fn();
        const onSessionRecorded = vi.fn();
        // Injected keyed-fingerprint fn (in the app: cryptoService.passwordFingerprint).
        const fingerprint = vi.fn(async () => FINGERPRINT_STUB);

        render(
            <TypingPatternCapture
                inputRef={inputRef}
                enabled
                fingerprint={fingerprint}
                fpKeyVersion={FP_KEY_VERSION}
                onPatternCaptured={onPatternCaptured}
                onSessionRecorded={onSessionRecorded}
            />
        );

        // The first keydown only sets the timing baseline; the second records a
        // (bucketized) inter-key timing.
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));

        await act(async () => {
            await inputRef.current.captureTypingPattern('testpass');
        });

        // The fingerprint is computed from the password locally...
        expect(fingerprint).toHaveBeenCalledWith('testpass');

        // ...and the reported pattern carries the v2 fields — and crucially NOT
        // the raw password.
        const pattern = onPatternCaptured.mock.calls[0][0];
        expect(pattern).toMatchObject({
            schema_version: 2,
            fp_key_version: FP_KEY_VERSION,
            password_fingerprint: FINGERPRINT_STUB,
            length_bucket: expect.any(Number),
            keystroke_timings: expect.any(Array),
            backspace_positions: expect.any(Array),
            device_type: expect.any(String),
        });
        expect(pattern).not.toHaveProperty('password');
        expect(JSON.stringify(pattern)).not.toContain('testpass');

        // ...and auto-submitted to record-session with no plaintext in the body.
        await waitFor(() => {
            expect(axios.post).toHaveBeenCalledWith(
                expect.stringContaining('/adaptive/record-session/'),
                expect.objectContaining({ schema_version: 2, password_fingerprint: expect.any(String) }),
                expect.any(Object)
            );
        });
        const postBody = vi.mocked(axios.post).mock.calls[0][1];
        expect(JSON.stringify(postBody)).not.toContain('testpass');
        expect(postBody).not.toHaveProperty('password');

        await waitFor(() => {
            expect(onSessionRecorded).toHaveBeenCalledWith({ recorded: true });
        });
    });
});

// =============================================================================
// AdaptivePasswordSuggestion Component Tests
// =============================================================================

describe('AdaptivePasswordSuggestion Component', () => {
    // The component bails out unless `has_suggestion` is truthy, and reads
    // original_char/suggested_char/reason/confidence on each substitution.
    const mockSuggestion = {
        has_suggestion: true,
        reason: 'Improves memorability',
        original_preview: 'te***23',
        adapted_preview: 't3***23',
        substitutions: [
            { position: 1, original_char: 'e', suggested_char: '3', reason: 'leet', confidence: 0.9 },
        ],
        confidence_score: 0.85,
        // Phase 4 shape: the panel now needs the two ABSOLUTE readings, not
        // just the delta. Before Phase 4 it rendered a hard-coded 0.65
        // "Current Memorability" placeholder and derived the "after" value
        // from it, so it displayed a number no one had measured.
        memorability_improvement: 0.15,
        memorability_score_before: 0.50,
        memorability_score_after: 0.65,
    };

    test('displays suggestion details', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        expect(screen.getByText(/Adaptation/i)).toBeInTheDocument();  // Title: "Password Adaptation Suggested"
        expect(screen.getByText(/15%/)).toBeInTheDocument();  // Memorability improvement
        expect(screen.getByText(/85%/)).toBeInTheDocument();  // Confidence
        // The absolute scores are the measured ones, not the old placeholder.
        expect(screen.getByTestId('memorability-before')).toHaveTextContent('50');
        expect(screen.getByTestId('memorability-after')).toHaveTextContent('65');
    });

    test('renders a measured drop as a drop, never as "+X% easier"', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        // The ordinary case for canonical leetspeak: replacing a letter with a
        // symbol lowers two of the four scored features, so the honest reading
        // is negative. The pre-Phase-4 formula could not produce this at all
        // (it was positive by construction), which is why it never measured
        // anything.
        render(
            <AdaptivePasswordSuggestion
                suggestion={{
                    ...mockSuggestion,
                    memorability_improvement: -0.30,
                    memorability_score_before: 0.55,
                    memorability_score_after: 0.25,
                }}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        const badge = screen.getByTestId('memorability-badge');
        // Magnitude only, no leading "-": "-30% harder to read" reads as a
        // double negative next to the word "harder". This was itself a real
        // bug caught by a fresh review pass -- this assertion originally
        // asserted the buggy "-30%" text as if it were correct.
        expect(badge).toHaveTextContent(/30%/);
        expect(badge).not.toHaveTextContent(/-30%/);
        expect(badge).not.toHaveTextContent(/easier to remember/i);
    });

    test('omits the memorability panel when no reading was supplied', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        // A pre-Phase-4 caller sends only the delta. Showing the panel would
        // mean inventing the two absolute numbers, which is exactly the
        // placeholder bug Phase 4 removed — so the panel is dropped instead.
        const { memorability_score_before: _b, memorability_score_after: _a, ...legacy } =
            mockSuggestion;

        render(
            <AdaptivePasswordSuggestion
                suggestion={legacy}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        expect(screen.queryByTestId('memorability-badge')).toBeNull();
        expect(screen.queryByTestId('memorability-before')).toBeNull();
        // The rest of the modal still renders — the panel is optional, not a
        // precondition for showing a suggestion at all.
        expect(screen.getByText(/Adaptation/i)).toBeInTheDocument();
    });

    test('lists substitutions', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        // Positions are rendered 1-based ("Position 2" for index 1).
        expect(screen.getByText(/position 2/i)).toBeInTheDocument();
    });

    test('accept button works', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        const mockAccept = vi.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={mockAccept}
                onReject={vi.fn()}
            />
        );

        const acceptButton = screen.getByRole('button', { name: /accept/i });
        await userEvent.click(acceptButton);

        expect(mockAccept).toHaveBeenCalled();
    });

    test('reject button works', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        const mockReject = vi.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={mockReject}
            />
        );

        const rejectButton = screen.getByRole('button', { name: /reject/i });
        await userEvent.click(rejectButton);

        expect(mockReject).toHaveBeenCalled();
    });

    test('ignores Escape and outside-click while an accept is in flight', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        // Real bug: `applyToVault` (the dashboard's `onAccept`) reads
        // `pendingRef.current` ONCE at the start and does not re-check it
        // before writing to the vault, so dismissing this dialog mid-flight
        // only hid it -- the vault write still landed afterward, changing
        // the credential the user believed they had just cancelled. The
        // explicit Accept/Reject buttons are already `disabled={isLoading}`;
        // Escape and outside-click were the two paths that weren't gated.
        const mockClose = vi.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={vi.fn()}
                onClose={mockClose}
                isLoading={true}
            />
        );

        await userEvent.keyboard('{Escape}');
        expect(mockClose).not.toHaveBeenCalled();

        const overlay = screen.getByTestId('adaptation-suggestion-modal').parentElement;
        await userEvent.click(overlay as Element);
        expect(mockClose).not.toHaveBeenCalled();
    });

    test('allows Escape to dismiss once loading has finished', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        const mockClose = vi.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={vi.fn()}
                onClose={mockClose}
                isLoading={false}
            />
        );

        await userEvent.keyboard('{Escape}');
        expect(mockClose).toHaveBeenCalledTimes(1);
    });

    test('shows the password diff (current vs suggested)', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        // The diff is always visible (no separate toggle); both sides render.
        expect(screen.getAllByText(/current/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/suggested/i).length).toBeGreaterThan(0);
    });
});

// =============================================================================
// TypingProfileCard Component Tests
// =============================================================================
//
// TypingProfileCard self-fetches via adaptivePasswordService (axios) on mount;
// it does not take a `profile` prop. We drive it by mocking the axios responses.

describe('TypingProfileCard Component', () => {
    const profileData = {
        has_profile: true,
        total_sessions: 25,
        success_rate: 0.85,
        average_wpm: 45,
        profile_confidence: 0.75,
        top_substitutions: {},
        error_prone_positions: {},
    };

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(axios.get).mockImplementation((url: string) => {
            if (url.includes('/config/')) return Promise.resolve({ data: { enabled: true } });
            if (url.includes('/profile/')) return Promise.resolve({ data: profileData });
            if (url.includes('/history/')) return Promise.resolve({ data: [] });
            if (url.includes('/stats/')) return Promise.resolve({ data: {} });
            return Promise.resolve({ data: {} });
        });
        vi.mocked(axios.post).mockResolvedValue({ data: {} });
    });

    test('displays profile statistics', async () => {
        const { default: TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard />);

        expect(await screen.findByText('25')).toBeInTheDocument();  // Sessions
        expect(screen.getByText('85%')).toBeInTheDocument();        // Success rate
        expect(screen.getByText('45')).toBeInTheDocument();         // WPM
    });

    test('shows confidence indicator', async () => {
        const { default: TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard />);

        expect(await screen.findByText('75%')).toBeInTheDocument();  // Profile confidence
    });

    test('shows building state for a brand-new (empty) profile', async () => {
        vi.mocked(axios.get).mockImplementation((url: string) => {
            if (url.includes('/config/')) return Promise.resolve({ data: { enabled: true } });
            if (url.includes('/profile/')) return Promise.resolve({ data: { has_profile: false } });
            return Promise.resolve({ data: {} });
        });

        const { default: TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard />);

        // With no profile yet, the card shows the "building profile" empty state.
        expect(await screen.findByText(/Building Your Profile/i)).toBeInTheDocument();
    });

    test('renders without crashing', async () => {
        const { default: TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        const { container } = render(<TypingProfileCard />);

        expect(container.firstChild).toBeInTheDocument();
    });
});

// =============================================================================
// Adaptive Password API Service Tests (axios-based)
// =============================================================================

describe('Adaptive Password API Service', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    test('enable sends correct request', async () => {
        const { adaptivePasswordService, ADAPTIVE_API_TIMEOUT_MS } =
            await import('../Components/security/TypingPatternCapture');

        vi.mocked(axios.post).mockResolvedValueOnce({ data: { enabled: true } });

        await adaptivePasswordService.enable({ frequencyDays: 30 });

        expect(axios.post).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/enable/'),
            expect.objectContaining({ consent: true }),
            expect.objectContaining({ timeout: ADAPTIVE_API_TIMEOUT_MS })
        );
    });

    test('suggestAdaptation generates the suggestion client-side (no password POST)', async () => {
        const { adaptivePasswordService, ADAPTIVE_API_TIMEOUT_MS } =
            await import('../Components/security/TypingPatternCapture');

        // v2: the client pulls the learned preference model and ranks locally.
        vi.mocked(axios.get).mockResolvedValueOnce({
            data: {
                model_version: 3,
                substitution_weights: { o: { '0': 0.9 }, e: { '3': 0.7 }, a: { '@': 0.8 } },
                memorability_params: {},
            },
        });

        // Phase 2 put a strength gate in front of every suggestion. Against the
        // real zxcvbn estimator this fixture keeps nothing (every leet variant
        // of 'MySecret123!' de-leets onto a dictionary hit — verified, not
        // assumed), so a neutral estimator is injected: the gate still runs, it
        // simply has no reason to reject. Gate behaviour has its own tests in
        // services/adaptive/__tests__/adaptiveFeatures.test.js.
        const neutralEstimator = () => ({ guessesLog10: 12, sequence: [] });
        // explore: false pins this test to ranking off substitution_weights
        // alone. suggestAdaptation defaults to explore: true, and the mocked
        // model above happens to carry no `exploration` table today, so
        // Thompson sampling is a no-op either way -- but that's an accident
        // of this fixture, not something this test is about. Pinning it
        // explicitly means a later fixture that adds an exploration table
        // can't turn this into a seed-dependent test by surprise.
        const result = await adaptivePasswordService.suggestAdaptation('MySecret123!', {
            estimator: neutralEstimator,
            explore: false,
        });

        // Fetched the preference model; never POSTed the password anywhere.
        expect(axios.get).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/preference-model/'),
            expect.objectContaining({ timeout: ADAPTIVE_API_TIMEOUT_MS })
        );
        expect(axios.post).not.toHaveBeenCalled();

        // Returns the shape the suggestion modal consumes, with masked previews.
        expect(result.has_suggestion).toBe(true);
        expect(result.substitutions?.length).toBeGreaterThan(0);
        expect(result.original_preview).toMatch(/\*/);
        // The strength gate's reading is surfaced so the UI can show it.
        expect(result.guesses_log10_before).toBe(12);
        expect(result.guesses_log10_after).toBe(12);
        expect(result.guesses_log10_delta).toBe(0);
        // The raw password never appears anywhere in the suggestion object.
        expect(JSON.stringify(result)).not.toContain('MySecret123!');
    });

    test('suggestAdaptation fails closed when the preference model is unreachable', async () => {
        const { adaptivePasswordService } = await import('../Components/security/TypingPatternCapture');

        // Unlike getProfile (see 'propagates API errors' below), suggestAdaptation
        // must resolve with a structured has_suggestion: false result rather than
        // reject -- the strength gate a few lines later already establishes this
        // contract for its own failures, and a caller that only inspects
        // has_suggestion should not need a second try/catch for this call.
        vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'));

        const result = await adaptivePasswordService.suggestAdaptation('MySecret123!');

        expect(result).toEqual({
            has_suggestion: false,
            preference_model_error: true,
            reason: expect.stringContaining('Could not load your preference model'),
        });
    });

    test('getProfile returns profile data', async () => {
        const { adaptivePasswordService, ADAPTIVE_API_TIMEOUT_MS } =
            await import('../Components/security/TypingPatternCapture');

        const mockProfile = { has_profile: true, total_sessions: 10 };
        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile });

        const result = await adaptivePasswordService.getProfile();

        expect(axios.get).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/profile/'),
            expect.objectContaining({ timeout: ADAPTIVE_API_TIMEOUT_MS })
        );
        expect(result).toEqual(mockProfile);
    });

    test('propagates API errors', async () => {
        const { adaptivePasswordService } = await import('../Components/security/TypingPatternCapture');

        vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'));

        await expect(adaptivePasswordService.getProfile()).rejects.toThrow('Network error');
    });
});

// =============================================================================
// Accessibility Tests
// =============================================================================

describe('Component Accessibility', () => {
    test('TypingPatternCapture is invisible to assistive tech (no a11y surface)', async () => {
        const { default: TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        const inputRef = { current: document.createElement('input') };
        const { container } = render(<TypingPatternCapture inputRef={inputRef} enabled />);

        // A headless capture wrapper must not inject focusable/labelled nodes.
        expect(container.firstChild).toBeNull();
        expect(container.querySelector('input, button, [role], [aria-label], [tabindex]')).toBeNull();
    });

    test('buttons have accessible names', async () => {
        const { default: AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={{
                    has_suggestion: true,
                    confidence_score: 0.85,
                    memorability_improvement: 0.15,
                    substitutions: [],
                }}
                onAccept={vi.fn()}
                onReject={vi.fn()}
            />
        );

        const acceptButton = screen.getByRole('button', { name: /accept/i });
        const rejectButton = screen.getByRole('button', { name: /reject/i });

        expect(acceptButton).toBeInTheDocument();
        expect(rejectButton).toBeInTheDocument();
    });
});
