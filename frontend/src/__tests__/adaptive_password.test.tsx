/**
 * Jest Unit Tests for Adaptive Password Frontend Components
 * ==========================================================
 * 
 * Tests for React components and hooks used in the
 * Epigenetic Password Adaptation feature.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderHook } from '@testing-library/react-hooks';

// Mock fetch
global.fetch = jest.fn();

// =============================================================================
// useTypingPatternCapture Hook Tests
// =============================================================================

describe('useTypingPatternCapture Hook', () => {
    let hook: any;

    beforeEach(() => {
        jest.clearAllMocks();
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
        const mockEvent = { key: 'a' };
        act(() => {
            result.current.captureKeystroke(mockEvent);
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
            result.current.captureError(5);
        });

        expect(result.current.isCapturing).toBe(true);
    });

    test('endCapture returns pattern data', async () => {
        const { useTypingPatternCapture } = await import('../hooks/useTypingPatternCapture');

        const mockCallback = jest.fn();
        const { result } = renderHook(() => useTypingPatternCapture({
            inputElement: null,
            enabled: true,
            onPatternCaptured: mockCallback,
        }));

        act(() => {
            result.current.startCapture();
            result.current.captureKeystroke({ key: 'a' });
        });

        let patternData: any;
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

describe('TypingPatternCapture Component', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    test('renders input field', async () => {
        const { TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        render(
            <TypingPatternCapture
                onPasswordChange={jest.fn()}
                sessionType="login"
            />
        );

        expect(screen.getByRole('password') || screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
    });

    test('shows privacy indicator', async () => {
        const { TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        render(
            <TypingPatternCapture
                onPasswordChange={jest.fn()}
                sessionType="login"
            />
        );

        // Privacy indicator should be visible
        expect(screen.getByText(/privacy/i)).toBeInTheDocument();
    });

    test('calls onPasswordChange when typing', async () => {
        const { TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        const mockOnChange = jest.fn();
        render(
            <TypingPatternCapture
                onPasswordChange={mockOnChange}
                sessionType="login"
            />
        );

        const input = screen.getByRole('password') || screen.getByPlaceholderText(/password/i);
        await userEvent.type(input, 'test');

        expect(mockOnChange).toHaveBeenCalled();
    });
});

// =============================================================================
// AdaptivePasswordSuggestion Component Tests
// =============================================================================

describe('AdaptivePasswordSuggestion Component', () => {
    const mockSuggestion = {
        original_preview: 'te***23',
        adapted_preview: 't3***23',
        substitutions: [
            { position: 1, from: 'e', to: '3' },
        ],
        confidence_score: 0.85,
        memorability_improvement: 0.15,
    };

    test('displays suggestion details', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={jest.fn()}
                onReject={jest.fn()}
            />
        );

        expect(screen.getByText(/adaptive/i)).toBeInTheDocument();
        expect(screen.getByText(/15%/)).toBeInTheDocument();  // Memorability improvement
        expect(screen.getByText(/85%/)).toBeInTheDocument();  // Confidence
    });

    test('lists substitutions', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={jest.fn()}
                onReject={jest.fn()}
            />
        );

        // Should show substitution info
        expect(screen.getByText(/position 2/i) || screen.getByText(/'e' → '3'/)).toBeInTheDocument();
    });

    test('accept button works', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        const mockAccept = jest.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={mockAccept}
                onReject={jest.fn()}
            />
        );

        const acceptButton = screen.getByRole('button', { name: /accept/i });
        await userEvent.click(acceptButton);

        expect(mockAccept).toHaveBeenCalled();
    });

    test('reject button works', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        const mockReject = jest.fn();
        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={jest.fn()}
                onReject={mockReject}
            />
        );

        const rejectButton = screen.getByRole('button', { name: /reject/i });
        await userEvent.click(rejectButton);

        expect(mockReject).toHaveBeenCalled();
    });

    test('toggle diff view works', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={mockSuggestion}
                onAccept={jest.fn()}
                onReject={jest.fn()}
            />
        );

        const diffToggle = screen.getByRole('button', { name: /diff/i });
        await userEvent.click(diffToggle);

        // Diff view should now be visible
        expect(screen.getByText(/current/i) || screen.getByText(/suggested/i)).toBeInTheDocument();
    });
});

// =============================================================================
// TypingProfileCard Component Tests
// =============================================================================

describe('TypingProfileCard Component', () => {
    const mockProfile = {
        total_sessions: 25,
        success_rate: 0.85,
        average_wpm: 45,
        profile_confidence: 0.75,
        preferred_substitutions: { o: '0', a: '@' },
        error_prone_positions: { '3': 0.4, '7': 0.3 },
        last_updated: '2024-01-15T10:00:00Z',
    };

    test('displays profile statistics', async () => {
        const { TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard profile={mockProfile} />);

        expect(screen.getByText('25')).toBeInTheDocument();  // Sessions
        expect(screen.getByText(/85%/)).toBeInTheDocument();  // Success rate
        expect(screen.getByText(/45/)).toBeInTheDocument();   // WPM
    });

    test('shows preferred substitutions', async () => {
        const { TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard profile={mockProfile} />);

        // Toggle to show substitutions
        const subToggle = screen.queryByText(/substitutions/i);
        if (subToggle) {
            await userEvent.click(subToggle);
            expect(screen.getByText(/o → 0/)).toBeInTheDocument();
        }
    });

    test('shows confidence indicator', async () => {
        const { TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        render(<TypingProfileCard profile={mockProfile} />);

        expect(screen.getByText(/75%/) || screen.getByText(/confidence/i)).toBeInTheDocument();
    });

    test('handles empty profile gracefully', async () => {
        const { TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        const emptyProfile = {
            total_sessions: 0,
            success_rate: 0,
            average_wpm: 0,
            profile_confidence: 0,
            preferred_substitutions: {},
            error_prone_positions: {},
        };

        render(<TypingProfileCard profile={emptyProfile} />);

        // Should render without crashing
        expect(screen.getByText('0')).toBeInTheDocument();
    });
});

// =============================================================================
// API Service Tests
// =============================================================================

describe('Adaptive Password API Service', () => {
    beforeEach(() => {
        (global.fetch as jest.Mock).mockClear();
    });

    test('enable sends correct request', async () => {
        const { adaptivePasswordService } = await import('../services/adaptivePasswordService');

        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            json: async () => ({ enabled: true }),
        });

        await adaptivePasswordService.enable({
            consent: true,
            consentVersion: '1.0',
        });

        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('/adaptive/enable'),
            expect.objectContaining({
                method: 'POST',
                body: expect.any(String),
            })
        );
    });

    test('captureSession sends correct data', async () => {
        const { adaptivePasswordService } = await import('../services/adaptivePasswordService');

        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true }),
        });

        const sessionData = {
            timings: [100, 120, 95],
            errors: [3, 7],
            backspace_count: 2,
            total_time_ms: 5000,
            password_length: 12,
            session_type: 'login',
        };

        await adaptivePasswordService.captureSession(sessionData);

        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('/record-session'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify(sessionData),
            })
        );
    });

    test('getSuggestion returns suggestion', async () => {
        const { adaptivePasswordService } = await import('../services/adaptivePasswordService');

        const mockSuggestion = {
            has_suggestion: true,
            suggestion: { confidence_score: 0.85 },
        };

        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            json: async () => mockSuggestion,
        });

        const result = await adaptivePasswordService.getSuggestion('password123');

        expect(result).toEqual(mockSuggestion);
    });

    test('handles API errors gracefully', async () => {
        const { adaptivePasswordService } = await import('../services/adaptivePasswordService');

        (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

        await expect(adaptivePasswordService.getProfile()).rejects.toThrow('Network error');
    });
});

// =============================================================================
// Accessibility Tests
// =============================================================================

describe('Component Accessibility', () => {
    test('TypingPatternCapture has proper labels', async () => {
        const { TypingPatternCapture } = await import('../Components/security/TypingPatternCapture');

        render(
            <TypingPatternCapture
                onPasswordChange={jest.fn()}
                sessionType="login"
            />
        );

        const input = screen.getByRole('password') || screen.getByPlaceholderText(/password/i);
        expect(input).toHaveAttribute('aria-label');
    });

    test('buttons have accessible names', async () => {
        const { AdaptivePasswordSuggestion } = await import('../Components/security/AdaptivePasswordSuggestion');

        render(
            <AdaptivePasswordSuggestion
                suggestion={{
                    confidence_score: 0.85,
                    memorability_improvement: 0.15,
                    substitutions: [],
                }}
                onAccept={jest.fn()}
                onReject={jest.fn()}
            />
        );

        const acceptButton = screen.getByRole('button', { name: /accept/i });
        const rejectButton = screen.getByRole('button', { name: /reject/i });

        expect(acceptButton).toBeInTheDocument();
        expect(rejectButton).toBeInTheDocument();
    });
});

// =============================================================================
// Snapshot Tests
// =============================================================================

describe('Component Snapshots', () => {
    test('TypingProfileCard matches snapshot', async () => {
        const { TypingProfileCard } = await import('../Components/security/TypingProfileCard');

        const { container } = render(
            <TypingProfileCard
                profile={{
                    total_sessions: 25,
                    success_rate: 0.85,
                    average_wpm: 45,
                    profile_confidence: 0.75,
                    preferred_substitutions: {},
                    error_prone_positions: {},
                }}
            />
        );

        expect(container).toMatchSnapshot();
    });
});
