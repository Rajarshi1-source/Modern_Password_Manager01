import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import GeneticOAuthCallback from './GeneticOAuthCallback';

// Mock window.opener
const mockOpener = {
    postMessage: jest.fn(),
};

describe('GeneticOAuthCallback Component', () => {
    beforeEach(() => {
        // Setup window.opener mock
        global.window.opener = mockOpener;
        jest.clearAllMocks();
    });

    afterAll(() => {
        delete global.window.opener;
    });

    test('handles successful callback parameters', async () => {
        const code = 'test_auth_code';
        const state = 'test_state_token';
        const provider = 'sequencing';

        render(
            <MemoryRouter initialEntries={[`/genetic-callback?code=${code}&state=${state}&provider=${provider}`]}>
                <Routes>
                    <Route path="/genetic-callback" element={<GeneticOAuthCallback />} />
                </Routes>
            </MemoryRouter>
        );

        // Should demonstrate processing
        expect(screen.getByText(/Connecting to DNA Provider/i)).toBeInTheDocument();

        // Should post message to opener
        await waitFor(() => {
            expect(mockOpener.postMessage).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'GENETIC_OAUTH_SUCCESS',
                    code: code,
                    state: state,
                    provider: provider
                }),
                expect.any(String) // targetOrigin
            );
        });

        // Should show success message
        await waitFor(() => {
            expect(screen.getByText(/Connection Successful/i)).toBeInTheDocument();
        });
    });

    test('handles error callback parameters', async () => {
        const error = 'access_denied';

        render(
            <MemoryRouter initialEntries={[`/genetic-callback?error=${error}`]}>
                <Routes>
                    <Route path="/genetic-callback" element={<GeneticOAuthCallback />} />
                </Routes>
            </MemoryRouter>
        );

        // Should post error message
        await waitFor(() => {
            expect(mockOpener.postMessage).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'GENETIC_OAUTH_ERROR',
                    error: error
                }),
                expect.any(String)
            );
        });

        // Should show error UI
        await waitFor(() => {
            expect(screen.getByText(/Connection Failed/i)).toBeInTheDocument();
        });
    });

    test('handles missing parameters', async () => {
        render(
            <MemoryRouter initialEntries={['/genetic-callback']}>
                <Routes>
                    <Route path="/genetic-callback" element={<GeneticOAuthCallback />} />
                </Routes>
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.getByText(/Invalid Request/i)).toBeInTheDocument();
        });
    });
});
