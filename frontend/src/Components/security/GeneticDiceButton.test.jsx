import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GeneticDiceButton from './GeneticDiceButton';
import geneticService from '../../services/geneticService';

// Mock dependencies. Use vi.mock (not the jest alias) so Vitest hoists these
// above the imports above — jest.mock is only a runtime alias here and would
// not replace the already-loaded modules.
vi.mock('../../services/geneticService');
vi.mock('framer-motion', () => ({
    motion: {
        div: ({ children, ...props }) => <div {...props}>{children}</div>,
        button: ({ children, ...props }) => <button {...props}>{children}</button>,
    },
    AnimatePresence: ({ children }) => <>{children}</>,
}));

describe('GeneticDiceButton Component', () => {
    const mockOnGenerate = jest.fn();

    beforeEach(() => {
        jest.clearAllMocks();
    });

    test('renders correctly in disconnected state', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: false
        });

        render(<GeneticDiceButton onGenerate={mockOnGenerate} />);

        // Disconnected state renders the "Connect DNA" prompt (no "Initialize" label).
        await waitFor(() => {
            expect(screen.getByText(/Connect DNA/i)).toBeInTheDocument();
        });
    });

    test('renders correctly in connected state', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            connection: {
                provider: 'sequencing',
                snp_count: 500000,
                evolution_generation: 2
            }
        });

        render(<GeneticDiceButton onPasswordGenerated={mockOnGenerate} />);

        await waitFor(() => {
            expect(screen.getByText(/Generate Genetic/i)).toBeInTheDocument();
            // The evolution badge ("Gen N") only renders once generation > 1.
            expect(screen.getByText(/Gen 2/i)).toBeInTheDocument();
        });
    });

    test('requests connection when clicked while disconnected', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: false
        });
        const onConnectRequest = jest.fn();

        render(<GeneticDiceButton onConnectRequest={onConnectRequest} />);

        await waitFor(() => expect(screen.getByText(/Connect DNA/i)).toBeInTheDocument());

        // The disconnected prompt delegates to onConnectRequest rather than
        // opening an internal modal.
        fireEvent.click(screen.getByRole('button', { name: /Connect DNA/i }));

        expect(onConnectRequest).toHaveBeenCalled();
    });

    test('calls onPasswordGenerated when clicked while connected', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            connection: { evolution_generation: 1 }
        });

        geneticService.generateGeneticPassword.mockResolvedValue({
            success: true,
            password: 'genetic-password-123',
            certificate: { id: 'cert-123' }
        });

        render(<GeneticDiceButton onPasswordGenerated={mockOnGenerate} />);

        await waitFor(() => expect(screen.getByText(/Generate Genetic/i)).toBeInTheDocument());

        const button = screen.getByRole('button');
        fireEvent.click(button);

        await waitFor(() => {
            expect(geneticService.generateGeneticPassword).toHaveBeenCalled();
            // The component reports results via onPasswordGenerated(password, certificate).
            expect(mockOnGenerate).toHaveBeenCalledWith(
                'genetic-password-123',
                expect.objectContaining({ id: 'cert-123' })
            );
        });
    });

    test('shows the evolution generation badge when evolved', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            connection: { provider: 'sequencing', evolution_generation: 3 }
        });

        render(<GeneticDiceButton onPasswordGenerated={mockOnGenerate} showEvolution={true} />);

        // The evolution indicator is the "Gen N" badge (shown when generation > 1);
        // there is no separate "Evolve" control in the component.
        await waitFor(() => {
            expect(screen.getByText(/Gen 3/i)).toBeInTheDocument();
        });
    });
});
