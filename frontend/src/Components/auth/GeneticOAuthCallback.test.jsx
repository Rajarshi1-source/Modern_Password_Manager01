import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GeneticOAuthCallback from './GeneticOAuthCallback';
import geneticService from '../../services/geneticService';

// The component reads OAuth params from window.location.search and calls
// geneticService.handleOAuthCallback(code, state); mock the service so the
// success path does not hit the network.
vi.mock('../../services/geneticService', () => ({
    default: {
        handleOAuthCallback: vi.fn(),
    },
}));

// Mock window.opener so we can assert the postMessage handshake.
const mockOpener = {
    postMessage: vi.fn(),
    closed: false,
};

// The component uses window.location.search (not the router), so drive the URL
// through the history API rather than MemoryRouter.
const setCallbackUrl = (search) => {
    window.history.replaceState({}, '', `/genetic-callback${search}`);
};

describe('GeneticOAuthCallback Component', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        global.window.opener = mockOpener;
    });

    afterAll(() => {
        delete global.window.opener;
        window.history.replaceState({}, '', '/');
    });

    test('handles successful callback parameters', async () => {
        const code = 'test_auth_code';
        const state = 'test_state_token';

        geneticService.handleOAuthCallback.mockResolvedValue({
            success: true,
            provider: 'sequencing',
            snpCount: 500000,
            geneticHashPrefix: 'abc123def456',
        });

        setCallbackUrl(`?code=${code}&state=${state}&provider=sequencing`);

        render(<GeneticOAuthCallback />);

        // Initial loading state
        expect(screen.getByText(/Connecting DNA/i)).toBeInTheDocument();

        // Exchanges the code/state via the service
        await waitFor(() => {
            expect(geneticService.handleOAuthCallback).toHaveBeenCalledWith(code, state);
        });

        // Posts the success handshake to the opener window
        await waitFor(() => {
            expect(mockOpener.postMessage).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'genetic_oauth_callback',
                    success: true,
                    provider: 'sequencing',
                    snpCount: 500000,
                    geneticHashPrefix: 'abc123def456',
                }),
                expect.any(String) // targetOrigin
            );
        });

        // Shows success UI
        await waitFor(() => {
            expect(screen.getByText(/DNA Connected!/i)).toBeInTheDocument();
        });
    });

    test('handles error callback parameters', async () => {
        // PR #290 contract: oidc_callback emits `error` + `error_description`.
        // The component surfaces error_description as the message it posts back.
        setCallbackUrl('?error=access_denied&error_description=User+denied+access');

        render(<GeneticOAuthCallback />);

        await waitFor(() => {
            expect(mockOpener.postMessage).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'genetic_oauth_callback',
                    success: false,
                    error: 'User denied access',
                }),
                expect.any(String)
            );
        });

        await waitFor(() => {
            expect(screen.getByText(/Connection Failed/i)).toBeInTheDocument();
        });

        // The service is never called when the provider returned an error.
        expect(geneticService.handleOAuthCallback).not.toHaveBeenCalled();
    });

    test('handles missing parameters', async () => {
        setCallbackUrl('');

        render(<GeneticOAuthCallback />);

        await waitFor(() => {
            expect(screen.getByText(/Connection Failed/i)).toBeInTheDocument();
        });

        expect(screen.getByText(/Missing authorization code or state/i)).toBeInTheDocument();
        expect(geneticService.handleOAuthCallback).not.toHaveBeenCalled();
    });
});
