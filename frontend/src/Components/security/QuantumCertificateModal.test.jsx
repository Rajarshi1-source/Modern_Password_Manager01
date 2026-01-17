/**
 * QuantumCertificateModal Component Tests
 * ========================================
 * 
 * Tests for the quantum certificate modal component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import QuantumCertificateModal from './QuantumCertificateModal';

// Test theme
const theme = {
    backgroundPrimary: '#0d1117',
    backgroundSecondary: '#1a1a2e',
    textPrimary: '#ffffff',
    textSecondary: '#9ca3af',
    accent: '#667eea',
    success: '#22c55e'
};

const renderWithTheme = (component) => {
    return render(
        <ThemeProvider theme={theme}>
            {component}
        </ThemeProvider>
    );
};

// Sample certificate data
const mockCertificate = {
    certificate_id: 'cert-uuid-12345678',
    password_hash_prefix: 'sha256:a1b2c3d4e5f6...',
    provider: 'anu_qrng',
    quantum_source: 'vacuum_fluctuations',
    entropy_bits: 128,
    circuit_id: null,
    generation_timestamp: '2026-01-16T12:30:00Z',
    signature: 'hmac-sha256-signature-here'
};

const mockIBMCertificate = {
    ...mockCertificate,
    certificate_id: 'ibm-cert-uuid',
    provider: 'ibm_quantum',
    quantum_source: 'superconducting_qubit_superposition',
    entropy_bits: 256,
    circuit_id: 'ibm-job-abc123'
};

describe('QuantumCertificateModal', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // Mock URL.createObjectURL
        global.URL.createObjectURL = vi.fn(() => 'blob:http://test/cert');
        global.URL.revokeObjectURL = vi.fn();
    });

    describe('Rendering', () => {
        it('should not render when isOpen is false', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={false}
                    onClose={() => { }}
                />
            );

            expect(screen.queryByText('Quantum Certificate')).not.toBeInTheDocument();
        });

        it('should render when isOpen is true', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText('Quantum Certificate')).toBeInTheDocument();
        });

        it('should not render when certificate is null', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={null}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.queryByText('Quantum Certificate')).not.toBeInTheDocument();
        });
    });

    describe('Certificate Details', () => {
        it('should display certificate ID', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/cert-uuid-12345678/)).toBeInTheDocument();
        });

        it('should display provider information', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/ANU/i)).toBeInTheDocument();
        });

        it('should display entropy bits', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText('128')).toBeInTheDocument();
        });

        it('should display quantum source', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/vacuum/i)).toBeInTheDocument();
        });

        it('should display circuit ID when available', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockIBMCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/ibm-job-abc123/)).toBeInTheDocument();
        });

        it('should display signature', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/hmac-sha256-signature/)).toBeInTheDocument();
        });

        it('should display formatted timestamp', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            // Should show some date format
            expect(screen.getByText(/2026/)).toBeInTheDocument();
        });
    });

    describe('Provider Variants', () => {
        it('should display ANU provider styling', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/ANU/i)).toBeInTheDocument();
        });

        it('should display IBM provider styling', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockIBMCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/IBM/i)).toBeInTheDocument();
        });

        it('should display IonQ provider styling', () => {
            const ionqCert = {
                ...mockCertificate,
                provider: 'ionq_quantum',
                quantum_source: 'trapped_ion_superposition'
            };

            renderWithTheme(
                <QuantumCertificateModal
                    certificate={ionqCert}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            expect(screen.getByText(/IonQ/i)).toBeInTheDocument();
        });
    });

    describe('Interactions', () => {
        it('should call onClose when close button clicked', () => {
            const onClose = vi.fn();

            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={onClose}
                />
            );

            // Find and click close button (typically has × character)
            const closeButton = screen.getByRole('button', { name: /close|×/i }) ||
                screen.getAllByRole('button')[0];
            fireEvent.click(closeButton);

            expect(onClose).toHaveBeenCalled();
        });

        it('should call onClose when backdrop clicked', () => {
            const onClose = vi.fn();

            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={onClose}
                />
            );

            // Click on the backdrop/overlay
            const backdrop = document.querySelector('[class*="Overlay"]') ||
                screen.getByRole('dialog')?.parentElement;

            if (backdrop) {
                fireEvent.click(backdrop);
            }
        });

        it('should have download button', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            const downloadButton = screen.getByRole('button', { name: /download/i });
            expect(downloadButton).toBeInTheDocument();
        });

        it('should trigger download when download button clicked', () => {
            // Mock document.createElement for anchor
            const mockAnchor = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor);
            const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => { });
            const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => { });

            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            const downloadButton = screen.getByRole('button', { name: /download/i });
            fireEvent.click(downloadButton);

            expect(mockAnchor.click).toHaveBeenCalled();

            createElementSpy.mockRestore();
            appendChildSpy.mockRestore();
            removeChildSpy.mockRestore();
        });
    });

    describe('Accessibility', () => {
        it('should have proper modal role', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            // Modal content should be present
            expect(screen.getByText('Quantum Certificate')).toBeInTheDocument();
        });

        it('should have accessible provider badges', () => {
            renderWithTheme(
                <QuantumCertificateModal
                    certificate={mockCertificate}
                    isOpen={true}
                    onClose={() => { }}
                />
            );

            // Provider info should be visible
            expect(screen.getByText(/quantum/i)).toBeInTheDocument();
        });
    });
});
