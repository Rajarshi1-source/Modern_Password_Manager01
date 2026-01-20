/**
 * EntropyHistoryChart Component Tests
 * 
 * Tests for the entropy history visualization component.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import EntropyHistoryChart from '../EntropyHistoryChart';

// Mock Chart.js to avoid canvas issues in tests
jest.mock('react-chartjs-2', () => ({
    Line: () => <div data-testid="mock-chart">Chart Component</div>,
}));

// Mock fetch
global.fetch = jest.fn();

describe('EntropyHistoryChart Component', () => {
    const mockPairId = '550e8400-e29b-41d4-a716-446655440000';
    const mockAuthToken = 'test-auth-token';

    const mockEntropyData = {
        pair_id: mockPairId,
        measurements: [
            {
                id: '1',
                entropy_value: 7.92,
                kl_divergence: 0.05,
                is_healthy: true,
                is_warning: false,
                is_critical: false,
                measured_at: '2026-01-20T10:00:00Z',
                sample_size: 4096,
            },
            {
                id: '2',
                entropy_value: 7.88,
                kl_divergence: 0.06,
                is_healthy: true,
                is_warning: false,
                is_critical: false,
                measured_at: '2026-01-20T09:00:00Z',
                sample_size: 4096,
            },
        ],
        total_count: 2,
        average_entropy: 7.9,
        warning_count: 0,
        critical_count: 0,
    };

    beforeEach(() => {
        jest.clearAllMocks();
    });

    test('renders loading state initially', () => {
        global.fetch.mockImplementation(() => new Promise(() => { })); // Never resolves

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    test('renders chart with data after successful fetch', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockEntropyData,
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByTestId('mock-chart')).toBeInTheDocument();
        });

        // Check stats are displayed
        expect(screen.getByText('Entropy History')).toBeInTheDocument();
    });

    test('renders empty state when no data', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                ...mockEntropyData,
                measurements: [],
                total_count: 0,
            }),
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByText(/no entropy measurements/i)).toBeInTheDocument();
        });
    });

    test('renders error state on fetch failure', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ error: 'Not found' }),
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByText(/error/i)).toBeInTheDocument();
        });
    });

    test('calls API with correct parameters', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockEntropyData,
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining(`/entropy-history/${mockPairId}/`),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Authorization': `Bearer ${mockAuthToken}`,
                    }),
                })
            );
        });
    });

    test('refresh button refetches data', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => mockEntropyData,
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByTestId('mock-chart')).toBeInTheDocument();
        });

        // Find and click refresh button
        const refreshButton = screen.getByText(/refresh/i);
        fireEvent.click(refreshButton);

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledTimes(2);
        });
    });

    test('days filter changes API request', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => mockEntropyData,
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByTestId('mock-chart')).toBeInTheDocument();
        });

        // Change days filter
        const daysSelect = screen.getByRole('combobox');
        fireEvent.change(daysSelect, { target: { value: '30' } });

        await waitFor(() => {
            expect(global.fetch).toHaveBeenLastCalledWith(
                expect.stringContaining('days=30'),
                expect.any(Object)
            );
        });
    });

    test('displays correct stats from data', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                ...mockEntropyData,
                average_entropy: 7.85,
                warning_count: 2,
                critical_count: 1,
            }),
        });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByText('7.8500')).toBeInTheDocument();
            expect(screen.getByText('2')).toBeInTheDocument();
            expect(screen.getByText('1')).toBeInTheDocument();
        });
    });

    test('calls onError callback on fetch failure', async () => {
        const onErrorMock = jest.fn();

        global.fetch.mockRejectedValueOnce(new Error('Network error'));

        render(
            <EntropyHistoryChart
                pairId={mockPairId}
                authToken={mockAuthToken}
                onError={onErrorMock}
            />
        );

        await waitFor(() => {
            expect(onErrorMock).toHaveBeenCalled();
        });
    });

    test('try again button refetches after error', async () => {
        global.fetch
            .mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Error' }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => mockEntropyData,
            });

        render(
            <EntropyHistoryChart pairId={mockPairId} authToken={mockAuthToken} />
        );

        await waitFor(() => {
            expect(screen.getByText(/error/i)).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText(/try again/i));

        await waitFor(() => {
            expect(screen.getByTestId('mock-chart')).toBeInTheDocument();
        });
    });
});
