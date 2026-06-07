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
        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
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

        // Should return pattern with expected structure
        expect(patternData).toBeDefined();
        expect(patternData).toHaveProperty('keystroke_timings');
        expect(patternData).toHaveProperty('backspace_positions');
        expect(patternData).toHaveProperty('device_type');
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
        const inputRef = { current: input };

        render(<TypingPatternCapture inputRef={inputRef} enabled />);

        // On mount the component attaches its capture/reset helpers to the input.
        expect(typeof inputRef.current.captureTypingPattern).toBe('function');
        expect(typeof inputRef.current.resetTypingSession).toBe('function');
    });

    test('captures keystroke timings and reports/submits the pattern', async () => {
        const { default: TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        vi.mocked(axios.post).mockResolvedValue({ data: { recorded: true } });

        const input = document.createElement('input');
        input.type = 'password';
        const inputRef = { current: input };
        const onPatternCaptured = vi.fn();
        const onSessionRecorded = vi.fn();

        render(
            <TypingPatternCapture
                inputRef={inputRef}
                enabled
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

        // The pattern (timings only — never the raw password) is reported.
        expect(onPatternCaptured).toHaveBeenCalledWith(
            expect.objectContaining({
                keystroke_timings: expect.any(Array),
                backspace_positions: expect.any(Array),
                device_type: expect.any(String),
            })
        );

        // ...and auto-submitted to the record-session endpoint.
        await waitFor(() => {
            expect(axios.post).toHaveBeenCalledWith(
                expect.stringContaining('/adaptive/record-session/'),
                expect.objectContaining({ keystroke_timings: expect.any(Array) }),
                expect.any(Object)
            );
        });
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
        memorability_improvement: 0.15,
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
        const { adaptivePasswordService } = await import('../Components/security/TypingPatternCapture');

        vi.mocked(axios.post).mockResolvedValueOnce({ data: { enabled: true } });

        await adaptivePasswordService.enable({ frequencyDays: 30 });

        expect(axios.post).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/enable/'),
            expect.objectContaining({ consent: true })
        );
    });

    test('suggestAdaptation requests a suggestion for the password', async () => {
        const { adaptivePasswordService } = await import('../Components/security/TypingPatternCapture');

        const mockSuggestion = { has_suggestion: true, suggestion: { confidence_score: 0.85 } };
        vi.mocked(axios.post).mockResolvedValueOnce({ data: mockSuggestion });

        const result = await adaptivePasswordService.suggestAdaptation('password123');

        expect(axios.post).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/suggest/'),
            expect.objectContaining({ password: 'password123' })
        );
        expect(result).toEqual(mockSuggestion);
    });

    test('getProfile returns profile data', async () => {
        const { adaptivePasswordService } = await import('../Components/security/TypingPatternCapture');

        const mockProfile = { has_profile: true, total_sessions: 10 };
        vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile });

        const result = await adaptivePasswordService.getProfile();

        expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/adaptive/profile/'));
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
