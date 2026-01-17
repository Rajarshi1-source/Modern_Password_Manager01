import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GeneticDiceButton from './GeneticDiceButton';
import geneticService from '../../services/geneticService';

// Mock dependencies
jest.mock('../../services/geneticService');
jest.mock('framer-motion', () => ({
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

        // Check for initial loading/status check
        await waitFor(() => {
            expect(screen.getByText(/Initialize Genetic/i)).toBeInTheDocument();
        });
    });

    test('renders correctly in connected state', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            connection: {
                provider: 'sequencing',
                snp_count: 500000,
                evolution_generation: 1
            }
        });

        render(<GeneticDiceButton onGenerate={mockOnGenerate} />);

        await waitFor(() => {
            expect(screen.getByText(/Generate Genetic/i)).toBeInTheDocument();
            expect(screen.getByText(/Gen 1/i)).toBeInTheDocument();
        });
    });

    test('opens connection modal when clicked while disconnected', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: false
        });

        render(<GeneticDiceButton onGenerate={mockOnGenerate} />);

        await waitFor(() => expect(screen.getByText(/Initialize Genetic/i)).toBeInTheDocument());

        const button = screen.getByRole('button');
        fireEvent.click(button);

        // Should see text indicating modal opening or connection prompt
        // Note: Since modal is internal state, we check if the button text triggers modal logic
        // In a real integration test we'd check for the modal itself
        expect(screen.queryByText(/Connect DNA/i)).toBeInTheDocument();
    });

    test('calls onGenerate when clicked while connected', async () => {
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

        render(<GeneticDiceButton onGenerate={mockOnGenerate} />);

        await waitFor(() => expect(screen.getByText(/Generate Genetic/i)).toBeInTheDocument());

        const button = screen.getByRole('button');
        fireEvent.click(button);

        await waitFor(() => {
            expect(geneticService.generateGeneticPassword).toHaveBeenCalled();
            expect(mockOnGenerate).toHaveBeenCalledWith(
                'genetic-password-123',
                expect.objectContaining({ id: 'cert-123' })
            );
        });
    });

    test('handles evolution trigger correctly', async () => {
        // Mock evolution status check
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            connection: { evolution_generation: 1 }
        });

        geneticService.getEvolutionStatus.mockResolvedValue({
            success: true,
            evolution: {
                can_use_epigenetic: true,
                evolution_ready: true,
                last_biological_age: 35.5
            }
        });

        render(<GeneticDiceButton onGenerate={mockOnGenerate} showEvolution={true} />);

        // Should show evolution indicator
        await waitFor(() => {
            expect(screen.getByText(/Evolve/i)).toBeInTheDocument();
        });
    });
});
