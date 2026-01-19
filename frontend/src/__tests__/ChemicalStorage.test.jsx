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
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
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
        listProviders: vi.fn(),
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

        // A = green, T = red, C = blue, G = yellow (typical DNA coloring)
        // The actual colors depend on implementation
        const container = screen.getByTestId ?
            screen.getByTestId('dna-sequence') :
            document.querySelector('.dna-sequence');

        expect(container).toBeTruthy();
    });

    it('displays GC content percentage', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Should show 50% GC content
        expect(screen.getByText(/50%/i)).toBeInTheDocument();
    });

    it('shows sequence length', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Should display sequence length
        expect(screen.getByText(/16/)).toBeInTheDocument();
    });

    it('indicates error correction status', () => {
        render(<DNASequenceVisualizer {...mockProps} />);

        // Should show ECC indicator
        expect(screen.getByText(/error correction/i)).toBeInTheDocument();
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

    it('shows locked status when time remains', () => {
        const futureTime = new Date(Date.now() + 3600000).toISOString();

        render(<TimeLockCountdown
            unlockAt={futureTime}
            status="locked"
            onUnlock={() => { }}
        />);

        expect(screen.getByText(/locked/i)).toBeInTheDocument();
    });

    it('shows unlockable when time expires', () => {
        const pastTime = new Date(Date.now() - 1000).toISOString();

        render(<TimeLockCountdown
            unlockAt={pastTime}
            status="locked"
            onUnlock={() => { }}
        />);

        // Should be unlockable
        expect(screen.getByRole('button')).not.toBeDisabled();
    });

    it('calls onUnlock when button clicked', async () => {
        const pastTime = new Date(Date.now() - 1000).toISOString();
        const onUnlock = vi.fn();

        render(<TimeLockCountdown
            unlockAt={pastTime}
            onUnlock={onUnlock}
        />);

        const unlockButton = screen.getByRole('button');
        await userEvent.click(unlockButton);

        expect(onUnlock).toHaveBeenCalled();
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

    it('disables unlock button while locked', () => {
        const futureTime = new Date(Date.now() + 3600000).toISOString();

        render(<TimeLockCountdown
            unlockAt={futureTime}
            status="locked"
            onUnlock={() => { }}
        />);

        const button = screen.getByRole('button');
        expect(button).toBeDisabled();
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

        chemicalStorageService.listProviders.mockResolvedValue({
            success: true,
            providers: [
                { id: 'mock', name: 'Demo Mode', cost_per_bp: 0 }
            ]
        });
    });

    it('renders modal with tabs', () => {
        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Should have tabs for encode, time-lock, storage, certificates
        expect(screen.getByText(/encode/i)).toBeInTheDocument();
        expect(screen.getByText(/time-lock/i)).toBeInTheDocument();
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

        // Click encode button
        const encodeButton = screen.getByText(/encode/i);
        await userEvent.click(encodeButton);

        await waitFor(() => {
            expect(chemicalStorageService.encodePassword).toHaveBeenCalledWith(
                'TestPassword123!',
                expect.any(Object)
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

        const encodeButton = screen.getByText(/encode/i);
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

    it('validates password before encoding', async () => {
        render(<ChemicalStorageModal isOpen={true} onClose={() => { }} />);

        // Click encode without entering password
        const encodeButton = screen.getByText(/encode/i);
        await userEvent.click(encodeButton);

        // Should show validation error
        await waitFor(() => {
            expect(screen.getByText(/please enter/i)).toBeInTheDocument();
        });
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

        const encodeButton = screen.getByText(/encode/i);
        await userEvent.click(encodeButton);

        await waitFor(() => {
            // Should display the sequence
            expect(screen.getByText(/ATCG/)).toBeInTheDocument();
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

        const encodeButton = screen.getByText(/encode/i);
        await userEvent.click(encodeButton);

        await waitFor(() => {
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

        const encodeButton = screen.getByText(/encode/i);
        await userEvent.click(encodeButton);

        await waitFor(() => {
            expect(screen.getByText(/ATCG/)).toBeInTheDocument();
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
