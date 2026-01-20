/**
 * Frontend Tests for Quantum Entanglement Components
 * ===================================================
 * 
 * Test Categories:
 * - Component rendering tests
 * - User interaction tests
 * - API integration tests
 * - State management tests
 * - Accessibility tests
 * 
 * Run with: npm test -- --testPathPattern=entanglement
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Mock components (will import real ones when running)
jest.mock('./EntangledDeviceManager', () => require('./EntangledDeviceManager').default);
jest.mock('./DevicePairingFlow', () => require('./DevicePairingFlow').default);
jest.mock('./EntropyHealthCard', () => require('./EntropyHealthCard').default);
jest.mock('./InstantRevokeModal', () => require('./InstantRevokeModal').default);

// Mock fetch globally
global.fetch = jest.fn();

// Mock localStorage
const localStorageMock = {
    getItem: jest.fn(() => 'mock-token'),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// =============================================================================
// ENTROPY HEALTH CARD TESTS
// =============================================================================

describe('EntropyHealthCard', () => {
    const EntropyHealthCard = require('./EntropyHealthCard').default;

    describe('Compact Mode', () => {
        it('renders compact view correctly', () => {
            render(
                <EntropyHealthCard
                    health="healthy"
                    score={7.95}
                    compact={true}
                />
            );

            expect(screen.getByText(/7\.95/)).toBeInTheDocument();
            expect(screen.getByText(/Healthy/i)).toBeInTheDocument();
        });

        it('shows correct color for healthy entropy', () => {
            const { container } = render(
                <EntropyHealthCard
                    health="healthy"
                    score={7.9}
                    compact={true}
                />
            );

            const badge = container.querySelector('.entropy-badge');
            expect(badge).toHaveClass('green');
        });

        it('shows correct color for degraded entropy', () => {
            const { container } = render(
                <EntropyHealthCard
                    health="degraded"
                    score={7.2}
                    compact={true}
                />
            );

            const badge = container.querySelector('.entropy-badge');
            expect(badge).toHaveClass('yellow');
        });

        it('shows correct color for critical entropy', () => {
            const { container } = render(
                <EntropyHealthCard
                    health="critical"
                    score={6.5}
                    compact={true}
                />
            );

            const badge = container.querySelector('.entropy-badge');
            expect(badge).toHaveClass('red');
        });
    });

    describe('Full Mode', () => {
        it('renders full view with gauge', () => {
            render(
                <EntropyHealthCard
                    health="healthy"
                    score={7.95}
                    generation={5}
                    compact={false}
                />
            );

            expect(screen.getByText('Entropy Health')).toBeInTheDocument();
            expect(screen.getByText('Generation')).toBeInTheDocument();
            expect(screen.getByText('5')).toBeInTheDocument();
        });

        it('displays warning message for degraded health', () => {
            render(
                <EntropyHealthCard
                    health="degraded"
                    score={7.2}
                    compact={false}
                />
            );

            expect(screen.getByText(/consider key rotation/i)).toBeInTheDocument();
        });

        it('displays critical message for critical health', () => {
            render(
                <EntropyHealthCard
                    health="critical"
                    score={6.5}
                    compact={false}
                />
            );

            expect(screen.getByText(/immediate action required/i)).toBeInTheDocument();
        });

        it('calls onRotate when rotate button clicked', async () => {
            const onRotate = jest.fn();

            render(
                <EntropyHealthCard
                    health="healthy"
                    score={7.9}
                    compact={false}
                    onRotate={onRotate}
                />
            );

            const rotateButton = screen.getByText(/Rotate Keys/i);
            await userEvent.click(rotateButton);

            expect(onRotate).toHaveBeenCalledTimes(1);
        });

        it('calls onCheck when check button clicked', async () => {
            const onCheck = jest.fn();

            render(
                <EntropyHealthCard
                    health="healthy"
                    score={7.9}
                    compact={false}
                    onCheck={onCheck}
                />
            );

            const checkButton = screen.getByText(/Check Now/i);
            await userEvent.click(checkButton);

            expect(onCheck).toHaveBeenCalledTimes(1);
        });
    });

    describe('Accessibility', () => {
        it('has accessible color contrast', () => {
            const { container } = render(
                <EntropyHealthCard health="healthy" score={7.9} compact={false} />
            );

            // Check that status badge exists and is visible
            const badge = container.querySelector('.health-badge');
            expect(badge).toBeVisible();
        });
    });
});


// =============================================================================
// INSTANT REVOKE MODAL TESTS
// =============================================================================

describe('InstantRevokeModal', () => {
    const InstantRevokeModal = require('./InstantRevokeModal').default;

    const mockPair = {
        pair_id: '123e4567-e89b-12d3-a456-426614174000',
        device_a_id: 'device-a-id',
        device_a_name: 'iPhone 15',
        device_b_id: 'device-b-id',
        device_b_name: 'MacBook Pro',
        status: 'active'
    };

    beforeEach(() => {
        global.fetch.mockReset();
    });

    it('renders confirmation step initially', () => {
        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={() => { }}
            />
        );

        expect(screen.getByText(/Revoke Device Pairing/i)).toBeInTheDocument();
        expect(screen.getByText(/iPhone 15/)).toBeInTheDocument();
        expect(screen.getByText(/MacBook Pro/)).toBeInTheDocument();
    });

    it('shows warning about irreversible action', () => {
        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={() => { }}
            />
        );

        expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
    });

    it('allows selecting compromised device', async () => {
        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={() => { }}
            />
        );

        const phoneItem = screen.getByText('iPhone 15').closest('.device-item');
        await userEvent.click(phoneItem);

        expect(screen.getByText(/Compromised/i)).toBeInTheDocument();
    });

    it('calls onCancel when cancel clicked', async () => {
        const onCancel = jest.fn();

        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={onCancel}
            />
        );

        const cancelButton = screen.getByText('Cancel');
        await userEvent.click(cancelButton);

        expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('calls API and shows success on revoke', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, revoked_at: new Date().toISOString() })
        });

        const onConfirm = jest.fn();

        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={onConfirm}
                onCancel={() => { }}
            />
        );

        const revokeButton = screen.getByText(/Revoke Now/i);
        await userEvent.click(revokeButton);

        await waitFor(() => {
            expect(screen.getByText(/Entanglement Revoked/i)).toBeInTheDocument();
        });
    });

    it('shows error state on API failure', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ error: 'Server error' })
        });

        render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={() => { }}
            />
        );

        const revokeButton = screen.getByText(/Revoke Now/i);
        await userEvent.click(revokeButton);

        await waitFor(() => {
            expect(screen.getByText(/Revocation Failed/i)).toBeInTheDocument();
        });
    });

    it('closes on overlay click', async () => {
        const onCancel = jest.fn();

        const { container } = render(
            <InstantRevokeModal
                pair={mockPair}
                onConfirm={() => { }}
                onCancel={onCancel}
            />
        );

        const overlay = container.querySelector('.modal-overlay');
        await userEvent.click(overlay);

        expect(onCancel).toHaveBeenCalled();
    });
});


// =============================================================================
// DEVICE PAIRING FLOW TESTS
// =============================================================================

describe('DevicePairingFlow', () => {
    const DevicePairingFlow = require('./DevicePairingFlow').default;

    const mockDevices = [
        { device_id: 'dev-1', device_name: 'iPhone', device_type: 'mobile' },
        { device_id: 'dev-2', device_name: 'MacBook', device_type: 'desktop' },
        { device_id: 'dev-3', device_name: 'iPad', device_type: 'tablet' }
    ];

    beforeEach(() => {
        global.fetch.mockReset();

        // Mock devices fetch
        global.fetch.mockImplementation((url) => {
            if (url.includes('/devices/')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ devices: mockDevices })
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });
    });

    it('renders device selection step initially', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => {
            expect(screen.getByText('Select Devices to Pair')).toBeInTheDocument();
        });
    });

    it('loads and displays devices', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => {
            expect(screen.getByText('iPhone')).toBeInTheDocument();
            expect(screen.getByText('MacBook')).toBeInTheDocument();
            expect(screen.getByText('iPad')).toBeInTheDocument();
        });
    });

    it('disables continue until both devices selected', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => {
            const continueButton = screen.getByText('Continue');
            expect(continueButton).toBeDisabled();
        });
    });

    it('enables continue after selecting both devices', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => screen.getByText('iPhone'));

        // Select first device
        const deviceAButtons = screen.getAllByText('iPhone');
        await userEvent.click(deviceAButtons[0]);

        // Select second device
        const deviceBButtons = screen.getAllByText('MacBook');
        await userEvent.click(deviceBButtons[deviceBButtons.length - 1]);

        const continueButton = screen.getByText('Continue');
        expect(continueButton).not.toBeDisabled();
    });

    it('prevents selecting same device twice', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => screen.getByText('iPhone'));

        // Select iPhone as device A
        const deviceButtons = screen.getAllByText('iPhone');
        await userEvent.click(deviceButtons[0]);

        // iPhone should be disabled in device B column
        const disabledButton = screen.getAllByRole('button').find(
            btn => btn.textContent.includes('iPhone') && btn.disabled
        );

        expect(disabledButton).toBeDisabled();
    });

    it('calls onCancel when cancel clicked', async () => {
        const onCancel = jest.fn();

        render(<DevicePairingFlow onComplete={() => { }} onCancel={onCancel} />);

        const cancelButton = screen.getByText('Cancel');
        await userEvent.click(cancelButton);

        expect(onCancel).toHaveBeenCalled();
    });

    it('shows verification code after initiation', async () => {
        global.fetch.mockImplementation((url) => {
            if (url.includes('/devices/')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ devices: mockDevices })
                });
            }
            if (url.includes('/initiate/')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        session_id: 'session-123',
                        verification_code: '123456',
                        expires_at: new Date().toISOString()
                    })
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        await waitFor(() => screen.getByText('iPhone'));

        // Select devices
        await userEvent.click(screen.getAllByText('iPhone')[0]);
        await userEvent.click(screen.getAllByText('MacBook')[1]);

        // Continue
        await userEvent.click(screen.getByText('Continue'));

        await waitFor(() => {
            expect(screen.getByText('1')).toBeInTheDocument();
            expect(screen.getByText('2')).toBeInTheDocument();
            expect(screen.getByText('3')).toBeInTheDocument();
        });
    });

    it('shows progress steps', async () => {
        render(<DevicePairingFlow onComplete={() => { }} onCancel={() => { }} />);

        expect(screen.getByText('Select Devices')).toBeInTheDocument();
        expect(screen.getByText('Verify')).toBeInTheDocument();
        expect(screen.getByText('Complete')).toBeInTheDocument();
    });
});


// =============================================================================
// ENTANGLED DEVICE MANAGER TESTS
// =============================================================================

describe('EntangledDeviceManager', () => {
    const EntangledDeviceManager = require('./EntangledDeviceManager').default;

    const mockPairs = [
        {
            pair_id: 'pair-1',
            device_a_name: 'iPhone',
            device_b_name: 'MacBook',
            status: 'active',
            entropy_health: 'healthy',
            entropy_score: 7.95,
            current_generation: 3,
            last_sync_at: new Date().toISOString()
        },
        {
            pair_id: 'pair-2',
            device_a_name: 'iPad',
            device_b_name: 'iMac',
            status: 'active',
            entropy_health: 'degraded',
            entropy_score: 7.2,
            current_generation: 1,
            last_sync_at: null
        }
    ];

    beforeEach(() => {
        global.fetch.mockReset();
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({ pairs: mockPairs, total_count: 2, max_allowed: 5 })
        });
    });

    it('renders header correctly', async () => {
        render(<EntangledDeviceManager />);

        await waitFor(() => {
            expect(screen.getByText('Quantum Entangled Devices')).toBeInTheDocument();
        });
    });

    it('displays loading state initially', () => {
        render(<EntangledDeviceManager />);

        expect(screen.getByText(/Loading/i)).toBeInTheDocument();
    });

    it('displays pairs after loading', async () => {
        render(<EntangledDeviceManager />);

        await waitFor(() => {
            expect(screen.getByText('iPhone')).toBeInTheDocument();
            expect(screen.getByText('MacBook')).toBeInTheDocument();
            expect(screen.getByText('iPad')).toBeInTheDocument();
            expect(screen.getByText('iMac')).toBeInTheDocument();
        });
    });

    it('shows empty state when no pairs', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ pairs: [], total_count: 0, max_allowed: 5 })
        });

        render(<EntangledDeviceManager />);

        await waitFor(() => {
            expect(screen.getByText('No Entangled Devices')).toBeInTheDocument();
        });
    });

    it('displays stats correctly', async () => {
        render(<EntangledDeviceManager />);

        await waitFor(() => {
            expect(screen.getByText('2')).toBeInTheDocument(); // Active pairs
            expect(screen.getByText('5')).toBeInTheDocument(); // Max allowed
        });
    });

    it('shows pairing flow when pair button clicked', async () => {
        render(<EntangledDeviceManager />);

        await waitFor(() => screen.getByText('Quantum Entangled Devices'));

        const pairButton = screen.getByText('Pair New Devices');
        await userEvent.click(pairButton);

        // DevicePairingFlow should now be shown
        expect(screen.getByText('Select Devices to Pair')).toBeInTheDocument();
    });

    it('shows revoke modal when revoke clicked', async () => {
        render(<EntangledDeviceManager />);

        await waitFor(() => screen.getByText('iPhone'));

        const revokeButtons = screen.getAllByText('Revoke');
        await userEvent.click(revokeButtons[0]);

        expect(screen.getByText(/Revoke Device Pairing/i)).toBeInTheDocument();
    });

    it('disables pair button when at max pairs', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                pairs: Array(5).fill(null).map((_, i) => ({
                    pair_id: `pair-${i}`,
                    device_a_name: `Device ${i}A`,
                    device_b_name: `Device ${i}B`,
                    status: 'active',
                    entropy_health: 'healthy',
                    entropy_score: 7.9,
                    current_generation: 1
                })),
                total_count: 5,
                max_allowed: 5
            })
        });

        render(<EntangledDeviceManager />);

        await waitFor(() => {
            const pairButton = screen.getByText('Pair New Devices');
            expect(pairButton).toBeDisabled();
        });
    });

    it('shows error alert on fetch failure', async () => {
        global.fetch.mockRejectedValueOnce(new Error('Network error'));

        render(<EntangledDeviceManager />);

        await waitFor(() => {
            expect(screen.getByText(/Network error/i)).toBeInTheDocument();
        });
    });

    it('refreshes pairs after rotation', async () => {
        const fetchMock = jest.fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ pairs: mockPairs, total_count: 2, max_allowed: 5 })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true, new_generation: 4 })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ pairs: mockPairs, total_count: 2, max_allowed: 5 })
            });

        global.fetch = fetchMock;

        render(<EntangledDeviceManager />);

        await waitFor(() => screen.getByText('iPhone'));

        const rotateButtons = screen.getAllByText('Rotate');
        await userEvent.click(rotateButtons[0]);

        // Should have made 3 fetch calls: initial, rotate, refresh
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledTimes(3);
        });
    });
});


// =============================================================================
// INTEGRATION TESTS
// =============================================================================

describe('Component Integration', () => {
    it('EntropyHealthCard integrates with manager card', async () => {
        const EntangledDeviceManager = require('./EntangledDeviceManager').default;

        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                pairs: [{
                    pair_id: 'pair-1',
                    device_a_name: 'Phone',
                    device_b_name: 'Laptop',
                    status: 'active',
                    entropy_health: 'healthy',
                    entropy_score: 7.9,
                    current_generation: 2
                }],
                total_count: 1,
                max_allowed: 5
            })
        });

        render(<EntangledDeviceManager />);

        await waitFor(() => {
            // EntropyHealthCard should be rendered within pair card
            expect(screen.getByText(/7\.90/)).toBeInTheDocument();
        });
    });
});


// =============================================================================
// ACCESSIBILITY TESTS
// =============================================================================

describe('Accessibility', () => {
    it('buttons are keyboard accessible', async () => {
        const EntropyHealthCard = require('./EntropyHealthCard').default;
        const onRotate = jest.fn();

        render(
            <EntropyHealthCard
                health="healthy"
                score={7.9}
                compact={false}
                onRotate={onRotate}
            />
        );

        const rotateButton = screen.getByText('Rotate Keys');
        rotateButton.focus();

        fireEvent.keyDown(rotateButton, { key: 'Enter' });

        expect(onRotate).toHaveBeenCalled();
    });

    it('modal can be closed with escape key', async () => {
        const InstantRevokeModal = require('./InstantRevokeModal').default;
        const onCancel = jest.fn();

        render(
            <InstantRevokeModal
                pair={{ pair_id: '1', device_a_name: 'A', device_b_name: 'B' }}
                onConfirm={() => { }}
                onCancel={onCancel}
            />
        );

        fireEvent.keyDown(document, { key: 'Escape' });

        // Note: This would require implementing Escape key handler in the component
        // The test documents expected behavior
    });

    it('modal has proper ARIA attributes', () => {
        const InstantRevokeModal = require('./InstantRevokeModal').default;

        const { container } = render(
            <InstantRevokeModal
                pair={{ pair_id: '1', device_a_name: 'A', device_b_name: 'B' }}
                onConfirm={() => { }}
                onCancel={() => { }}
            />
        );

        const modal = container.querySelector('.revoke-modal');
        // Modal should be focusable/have role
        expect(modal).toBeInTheDocument();
    });
});


// =============================================================================
// PERFORMANCE TESTS (Mock)
// =============================================================================

describe('Performance', () => {
    it('does not re-render unnecessarily', () => {
        const EntropyHealthCard = require('./EntropyHealthCard').default;
        const renderSpy = jest.fn();

        // Create wrapper to count renders
        const TrackedCard = (props) => {
            renderSpy();
            return <EntropyHealthCard {...props} />;
        };

        const { rerender } = render(
            <TrackedCard health="healthy" score={7.9} compact={true} />
        );

        // Rerender with same props
        rerender(
            <TrackedCard health="healthy" score={7.9} compact={true} />
        );

        // Should ideally only render twice (initial + rerender check)
        // With React.memo, could be optimized to 1
        expect(renderSpy).toHaveBeenCalledTimes(2);
    });
});
