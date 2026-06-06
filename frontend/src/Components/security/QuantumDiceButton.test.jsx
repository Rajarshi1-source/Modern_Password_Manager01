/**
 * QuantumDiceButton Component Tests
 * ==================================
 * 
 * Tests for the quantum dice button component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import QuantumDiceButton from './QuantumDiceButton';

// Mock quantumService
vi.mock('../../services/quantumService', () => ({
    default: {
        generateQuantumPassword: vi.fn(),
        getPoolStatus: vi.fn(),
        getProviderInfo: vi.fn((provider) => ({
            name: provider === 'anu_qrng' ? 'ANU Quantum RNG' : 'Fallback',
            icon: '🎲',
            color: '#FFD700'
        }))
    }
}));

import quantumService from '../../services/quantumService';

// Test theme
const theme = {
    backgroundSecondary: '#1a1a2e',
    textPrimary: '#ffffff',
    textSecondary: '#9ca3af',
    accent: '#667eea',
    success: '#22c55e',
    warning: '#f59e0b',
    error: '#ef4444'
};

const renderWithTheme = (component) => {
    return render(
        <ThemeProvider theme={theme}>
            {component}
        </ThemeProvider>
    );
};

describe('QuantumDiceButton', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('Rendering', () => {
        it('should render the button', () => {
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good', total_bytes_available: 2048 },
                providers: {}
            });

            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} />
            );

            expect(screen.getByRole('button')).toBeInTheDocument();
        });

        it('should display pool status when showStatus is true', async () => {
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good', total_bytes_available: 2048 },
                providers: {}
            });

            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} showStatus={true} />
            );

            await waitFor(() => {
                expect(quantumService.getPoolStatus).toHaveBeenCalled();
            });
        });

        it('should not fetch status when showStatus is false', () => {
            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} showStatus={false} />
            );

            expect(quantumService.getPoolStatus).not.toHaveBeenCalled();
        });

        it('should be disabled when disabled prop is true', () => {
            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} disabled={true} />
            );

            const button = screen.getByRole('button');
            expect(button).toBeDisabled();
        });
    });

    describe('Generation', () => {
        it('should call onGenerate with result on successful generation', async () => {
            const mockResult = {
                success: true,
                password: 'testPassword123',
                certificate: {
                    certificate_id: 'cert-123',
                    provider: 'anu_qrng'
                },
                quantumCertified: true
            };

            quantumService.generateQuantumPassword.mockResolvedValue(mockResult);
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });

            const onGenerate = vi.fn();

            renderWithTheme(
                <QuantumDiceButton onGenerate={onGenerate} length={16} />
            );

            const button = screen.getByRole('button');
            fireEvent.click(button);

            await waitFor(() => {
                // The button calls generateQuantumPassword({ length, ...options }).
                expect(quantumService.generateQuantumPassword).toHaveBeenCalledWith(
                    expect.objectContaining({ length: 16 })
                );
            });

            await waitFor(() => {
                // onGenerate receives the projected result (success / password /
                // certificate / quantumCertified), not the raw service response.
                expect(onGenerate).toHaveBeenCalledWith(
                    expect.objectContaining({
                        success: true,
                        password: 'testPassword123',
                        quantumCertified: true,
                        certificate: expect.objectContaining({ certificate_id: 'cert-123' }),
                    })
                );
            });
        });

        it('should show loading state during generation', async () => {
            quantumService.generateQuantumPassword.mockImplementation(
                () => new Promise(resolve => setTimeout(() => resolve({
                    success: true,
                    password: 'test',
                    certificate: {},
                    quantumCertified: true
                }), 100))
            );
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });

            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} />
            );

            const button = screen.getByRole('button');
            fireEvent.click(button);

            // Button should be disabled during generation
            expect(button).toBeDisabled();
        });

        it('surfaces an error and notifies onGenerate when generation fails', async () => {
            quantumService.generateQuantumPassword.mockResolvedValue({
                success: false,
                error: 'Generation failed'
            });
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });

            const onGenerate = vi.fn();

            renderWithTheme(
                <QuantumDiceButton onGenerate={onGenerate} />
            );

            const button = screen.getByRole('button');
            fireEvent.click(button);

            await waitFor(() => expect(quantumService.generateQuantumPassword).toHaveBeenCalled());

            // The failure is surfaced in the button's own error UI...
            await waitFor(() => {
                expect(screen.getByRole('alert')).toHaveTextContent('Generation failed');
            });

            // ...and the parent is notified with the discriminated failure shape.
            expect(onGenerate).toHaveBeenCalledWith(
                expect.objectContaining({ success: false, error: 'Generation failed' })
            );

            // Button re-enables so the user can retry.
            await waitFor(() => expect(button).not.toBeDisabled());
        });

        it('surfaces an error when generation throws', async () => {
            quantumService.generateQuantumPassword.mockRejectedValue(
                new Error('Network down')
            );
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });

            const onGenerate = vi.fn();

            renderWithTheme(
                <QuantumDiceButton onGenerate={onGenerate} />
            );

            fireEvent.click(screen.getByRole('button'));

            await waitFor(() => {
                expect(screen.getByRole('alert')).toHaveTextContent('Network down');
            });
            expect(onGenerate).toHaveBeenCalledWith(
                expect.objectContaining({ success: false, error: 'Network down' })
            );
        });

        it('clears a prior certificate banner when a later generation fails', async () => {
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });
            quantumService.generateQuantumPassword
                .mockResolvedValueOnce({
                    success: true,
                    password: 'ok',
                    certificate: { certificate_id: 'c1', provider: 'anu_qrng', entropy_bits: 128 },
                    quantumCertified: true
                })
                .mockResolvedValueOnce({ success: false, error: 'Generation failed' });

            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} />
            );
            const button = screen.getByRole('button');

            // First generation succeeds → certificate banner appears.
            fireEvent.click(button);
            await waitFor(() => expect(screen.getByText(/Quantum Certified/i)).toBeInTheDocument());

            // Second generation fails → error banner replaces the stale certificate.
            await waitFor(() => expect(button).not.toBeDisabled());
            fireEvent.click(button);
            await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Generation failed'));
            expect(screen.queryByText(/Quantum Certified/i)).not.toBeInTheDocument();
        });
    });

    describe('Options', () => {
        it('should pass custom options to generator', async () => {
            quantumService.generateQuantumPassword.mockResolvedValue({
                success: true,
                password: 'test',
                certificate: {},
                quantumCertified: true
            });
            quantumService.getPoolStatus.mockResolvedValue({
                success: true,
                pool: { health: 'good' },
                providers: {}
            });

            const options = {
                uppercase: true,
                lowercase: false,
                numbers: true,
                symbols: false
            };

            renderWithTheme(
                <QuantumDiceButton onGenerate={() => { }} length={24} options={options} />
            );

            const button = screen.getByRole('button');
            fireEvent.click(button);

            await waitFor(() => {
                expect(quantumService.generateQuantumPassword).toHaveBeenCalledWith(
                    expect.objectContaining({
                        length: 24,
                        uppercase: true,
                        lowercase: false,
                        numbers: true,
                        symbols: false
                    })
                );
            });
        });
    });
});
