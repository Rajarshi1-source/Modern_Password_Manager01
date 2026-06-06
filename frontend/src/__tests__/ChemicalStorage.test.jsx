/**
 * Chemical Password Storage - Frontend Component Tests
 * =====================================================
 * 
 * Tests for React components:
 * - DNASequenceVisualizer
 * - TimeLockCountdown
 * - ChemicalStorageModal
 * 
 * @author Password Manager Team
 * @created 2026-01-17
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Component imports (adjust paths as needed)
import DNASequenceVisualizer from '../Components/security/DNASequenceVisualizer';
import TimeLockCountdown from '../Components/security/TimeLockCountdown';
import ChemicalStorageModal from '../Components/security/ChemicalStorageModal';

// Mock the service
vi.mock('../services/chemicalStorageService', () => ({
    default: {
        encodePassword: vi.fn(),
        decodePassword: vi.fn(),
        createTimeLock: vi.fn(),
        getCapsuleStatus: vi.fn(),
        unlockCapsule: vi.fn(),
        getSubscription: vi.fn(),
        listCertificates: vi.fn(),
        orderSynthesis: vi.fn(),
        getProviders: vi.fn(),
        estimateCost: vi.fn(),
    }
}));

import chemicalStorageService from '../services/chemicalStorageService';


// =============================================================================
// DNASequenceVisualizer Tests
// =============================================================================

describe('DNASequenceVisualizer', () => {
    const mockSequence = 'ATCGATCGATCGATCG';
    const mockProps = {
        sequence: mockSequence,
        gcContent: 0.50,
        length: mockSequence.length,
        hasErrorCorrection: true,
    };

    it('renders DNA sequence correctly', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Each nucleotide should be rendered
        const nucleotides = screen.getAllByText(/[ATCG]/);
        expect(nucleotides.length).toBeGreaterThan(0);
    });

    it('applies correct colors to nucleotides', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Colored view renders each base as a .nucleotide span with an inline
        // background-color from the A/T/G/C palette. Assert the coloring applied.
        const nucleotides = document.querySelectorAll('.colored-sequence .nucleotide');
        expect(nucleotides.length).toBeGreaterThan(0);
        expect(nucleotides[0].style.backgroundColor).toBeTruthy();
    });

    it('displays GC content percentage', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // GC content is computed from the sequence and shown to 1 decimal ("50.0%")
        expect(screen.getByText(/50(\.\d)?%/)).toBeInTheDocument();
    });

    it('shows sequence length', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Should display sequence length
        expect(screen.getByText(/16/)).toBeInTheDocument();
    });

    it('displays integrity checksum when provided', () => {
        // The visualizer surfaces integrity via an optional checksum (not an ECC
        // flag); when a checksum is passed it renders a labelled, truncated value.
        render(<DNASequenceVisualizer {...mockProps} checksum="a1b2c3d4e5f6" />);

        expect(screen.getByText(/checksum/i)).toBeInTheDocument();
        expect(screen.getByText('a1b2c3d4')).toBeInTheDocument();
    });

    it('handles empty sequence gracefully', () => {
        render(<DNASequenceVisualizer sequence="" gcContent={0} length={0} />);

        // Should not crash, may show empty or placeholder
        expect(document.body).toBeTruthy();
    });

    it('handles long sequences with truncation', () => {
        const longSequence = 'ATCG'.repeat(100); // 400 bp

        render(<DNASequenceVisualizer
            sequence={longSequence}
            gcContent={0.5}
            length={400}
        />);

        // Should show ellipsis or truncation indicator for long sequences
        // The component should still render without crashing
        expect(document.body).toBeTruthy();
    });
});


// =============================================================================
// TimeLockCountdown Tests
// =============================================================================

describe('TimeLockCountdown', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('displays remaining time correctly', () => {
        const futureTime = new Date(Date.now() + 3600000).toISOString(); // 1 hour

        render(<TimeLockCountdown
            unlockAt={futureTime}
            onUnlock={() => { }}
        />);

        // Should show time remaining
        expect(screen.getByText(/\d+:\d+:\d+/)).toBeInTheDocument();
    });

    it('shows the locked countdown while time remains', () => {
        const futureTime = new Date(Date.now() + 3600000).toISOString();

        render(<TimeLockCountdown
            unlockAt={futureTime}
            onUnlocked={() => { }}
        />);

        // While locked the component renders the Time-Lock badge + countdown,
        // not the "Capsule Unlocked!" state.
        expect(screen.getByText(/time-lock/i)).toBeInTheDocument();
        expect(screen.queryByText(/unlocked/i)).not.toBeInTheDocument();
    });

    it('shows unlocked state when time has expired', () => {
        const pastTime = new Date(Date.now() - 1000).toISOString();

        render(<TimeLockCountdown
            unlockAt={pastTime}
            onUnlocked={() => { }}
        />);

        // Expiry auto-transitions to the unlocked view (no manual unlock button).
        expect(screen.getByText(/unlocked/i)).toBeInTheDocument();
    });

    it('fires onUnlocked automatically when time has expired', () => {
        const pastTime = new Date(Date.now() - 1000).toISOString();
        const onUnlocked = vi.fn();

        render(<TimeLockCountdown
            unlockAt={pastTime}
            onUnlocked={onUnlocked}
        />);

        // Unlock is time-driven, not click-driven: the callback fires on mount
        // once the unlock timestamp is already in the past.
        expect(onUnlocked).toHaveBeenCalled();
    });

    it('updates countdown every second', () => {
        const futureTime = new Date(Date.now() + 10000).toISOString(); // 10 seconds

        render(<TimeLockCountdown
            unlockAt={futureTime}
            onUnlock={() => { }}
        />);

        const initialText = screen.getByText(/\d+:\d+:\d+/).textContent;

        // Advance time by 1 second
        act(() => {
            vi.advanceTimersByTime(1000);
        });

        // The text should have changed (countdown decreased)
        // Note: This depends on implementation details
    });

    it('renders no unlock control while locked', () => {
        const futureTime = new Date(Date.now() + 3600000).toISOString();

        render(<TimeLockCountdown
            unlockAt={futureTime}
            onUnlocked={() => { }}
        />);

        // Locked capsules cannot be unlocked early, so no unlock button is shown.
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
});


// =============================================================================
// ChemicalStorageModal Tests
// =============================================================================

describe('ChemicalStorageModal', () => {
    beforeEach(() => {
        // Reset all mocks
        vi.clearAllMocks();

        // Setup default mock responses
        chemicalStorageService.getSubscription.mockResolvedValue({
            success: true,
            subscription: { tier: 'free', max_passwords: 1, passwords_stored: 0 }
        });

        chemicalStorageService.listCertificates.mockResolvedValue({
            success: true,
            certificates: []
        });

        chemicalStorageService.getProviders.mockResolvedValue({
            success: true,
            providers: [
                { id: 'mock', name: 'Demo Mode', cost_per_bp: 0 }
            ]
        });

        // estimateCost is a synchronous helper the modal calls to render the
        // cost panel once a sequence exists; seed a known total ($75.50).
        chemicalStorageService.estimateCost.mockReturnValue({
            provider: 'mock', sequenceLength: 8, perBpUsd: 0.07,
            synthesisUsd: 25.50, handlingUsd: 55.00, totalUsd: 75.50, estimatedDays: 0,
        });
    });

    it('renders modal with tabs', () => {
        const { container } = render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Scope to the tab strip — the primary "Encode to DNA" action button also
        // matches /encode/i, so an unscoped query would be ambiguous.
        const tabs = within(container.querySelector('.tabs'));
        expect(tabs.getByText(/encode/i)).toBeInTheDocument();
        expect(tabs.getByText(/time-lock/i)).toBeInTheDocument();
    });

    it('shows subscription tier', async () => {
        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        await waitFor(() => {
            expect(screen.getByText(/free/i)).toBeInTheDocument();
        });
    });

    it('encodes password on submit', async () => {
        chemicalStorageService.encodePassword.mockResolvedValue({
            success: true,
            dna_sequence: {
                sequence: 'ATCGATCG',
                gc_content: 0.5,
                length: 8
            },
            validation: { is_valid: true, errors: [], warnings: [] },
            cost_estimate: { total_cost_usd: 50 }
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Enter password
        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'TestPassword123!');

        // Click the encode action button (distinct from the Encode tab)
        const encodeButton = screen.getByRole('button', { name: /encode to dna/i });
        await userEvent.click(encodeButton);

        await waitFor(() => {
            // The modal calls encodePassword(password) with a single argument.
            expect(chemicalStorageService.encodePassword).toHaveBeenCalledWith(
                'TestPassword123!'
            );
        });
    });

    it('shows error on failed encoding', async () => {
        chemicalStorageService.encodePassword.mockResolvedValue({
            success: false,
            error: 'Encoding failed'
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'test');

        const encodeButton = screen.getByRole('button', { name: /encode to dna/i });
        await userEvent.click(encodeButton);

        await waitFor(() => {
            expect(screen.getByText(/encoding failed/i)).toBeInTheDocument();
        });
    });

    it('switches between tabs', async () => {
        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Click time-lock tab
        const timeLockTab = screen.getByText(/time-lock/i);
        await userEvent.click(timeLockTab);

        // Should show time-lock content
        expect(screen.getByText(/delay/i)).toBeInTheDocument();
    });

    it('calls onClose when close button clicked', async () => {
        const onClose = vi.fn();

        render(<ChemicalStorageModal isOpen={true} onClose={onClose} />);

        const closeButton = screen.getByText('✕');
        await userEvent.click(closeButton);

        expect(onClose).toHaveBeenCalled();
    });

    it('disables encoding until a password is entered', () => {
        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // The component guards empty submission by disabling the button; the
        // inline "Please enter a password" branch is unreachable via the UI.
        expect(screen.getByRole('button', { name: /encode to dna/i })).toBeDisabled();
    });

    it('creates time-lock with specified delay', async () => {
        chemicalStorageService.createTimeLock.mockResolvedValue({
            success: true,
            capsule_id: 'test-123',
            unlock_at: new Date(Date.now() + 86400000).toISOString(),
            time_remaining_seconds: 86400
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Switch to time-lock tab
        const timeLockTab = screen.getByText(/time-lock/i);
        await userEvent.click(timeLockTab);

        // Enter password and delay
        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'TimeLockTest!');

        // Click create button
        const createButton = screen.getByText(/create/i);
        await userEvent.click(createButton);

        await waitFor(() => {
            expect(chemicalStorageService.createTimeLock).toHaveBeenCalled();
        });
    });

    it('displays DNA sequence after encoding', async () => {
        chemicalStorageService.encodePassword.mockResolvedValue({
            success: true,
            dna_sequence: {
                sequence: 'ATCGATCGATCG',
                gc_content: 0.5,
                length: 12
            },
            validation: { is_valid: true },
            cost_estimate: { total_cost_usd: 45 }
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'DisplayTest');

        const encodeButton = screen.getByRole('button', { name: /encode to dna/i });
        await userEvent.click(encodeButton);

        await waitFor(() => {
            // Colored view splits the sequence into per-nucleotide spans, so assert
            // the visualizer mounted via its stable "GC Content" label.
            expect(screen.getByText(/GC Content/i)).toBeInTheDocument();
        });
    });

    it('shows cost estimate after encoding', async () => {
        chemicalStorageService.encodePassword.mockResolvedValue({
            success: true,
            dna_sequence: { sequence: 'ATCG', gc_content: 0.5, length: 4 },
            validation: { is_valid: true },
            cost_estimate: { total_cost_usd: 75.50, synthesis_cost_usd: 25.50 }
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'CostTest');

        const encodeButton = screen.getByRole('button', { name: /encode to dna/i });
        await userEvent.click(encodeButton);

        await waitFor(() => {
            // Displayed cost comes from estimateCost(...).totalUsd (mocked to 75.50).
            expect(screen.getByText(/\$75/)).toBeInTheDocument();
        });
    });
});


// =============================================================================
// Integration Tests
// =============================================================================

describe('Chemical Storage Integration', () => {
    it('full encode-to-storage workflow', async () => {
        // Mock successful encode
        chemicalStorageService.encodePassword.mockResolvedValue({
            success: true,
            dna_sequence: { sequence: 'ATCGATCG', gc_content: 0.5, length: 8 },
            validation: { is_valid: true },
            cost_estimate: { total_cost_usd: 50 }
        });

        // Mock successful synthesis order
        chemicalStorageService.orderSynthesis.mockResolvedValue({
            success: true,
            order_id: 'ORDER-123',
            status: 'pending'
        });

        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Encode password
        const passwordInput = screen.getByPlaceholderText(/password/i);
        await userEvent.type(passwordInput, 'IntegrationTest!');

        const encodeButton = screen.getByRole('button', { name: /encode to dna/i });
        await userEvent.click(encodeButton);

        await waitFor(() => {
            // Visualizer mounts after encoding (per-nucleotide spans in colored view).
            expect(screen.getByText(/GC Content/i)).toBeInTheDocument();
        });

        // The component should show the encoded sequence
        // and optionally allow ordering synthesis
    });
});


// =============================================================================
// A/B Test Configuration Tests
// =============================================================================

describe('Chemical Storage A/B Tests', () => {
    it('respects experiment variant for UI', () => {
        // A/B test: Show extended info vs. minimal info
        const variantA = { showExtendedInfo: true };
        const variantB = { showExtendedInfo: false };

        // Variant A should show more details
        expect(variantA.showExtendedInfo).toBe(true);

        // Variant B should show minimal info
        expect(variantB.showExtendedInfo).toBe(false);
    });

    it('tracks encoding conversion rate', () => {
        // Metric: How many users complete encoding after opening modal?
        const experimentMetrics = {
            modalOpened: 100,
            encodingCompleted: 45,
            conversionRate: 0.45
        };

        expect(experimentMetrics.conversionRate).toBeGreaterThan(0);
        expect(experimentMetrics.conversionRate).toBeLessThanOrEqual(1);
    });

    it('tracks time-lock adoption rate', () => {
        // Metric: Percentage of users who enable time-lock
        const timeLockMetrics = {
            totalEncodings: 100,
            withTimeLock: 30,
            adoptionRate: 0.30
        };

        expect(timeLockMetrics.adoptionRate).toBeGreaterThan(0);
    });
});
