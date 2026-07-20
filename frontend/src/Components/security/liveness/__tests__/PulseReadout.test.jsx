/**
 * Tests for PulseReadout's heart-rate handling.
 *
 * Heart rate must clear when the backend streams heart_rate: null (signal lost),
 * mirroring the SpO2 handling -- otherwise a resolved rate would stay frozen on
 * screen after the signal is gone.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PulseReadout from '../PulseReadout';

describe('PulseReadout heart-rate handling', () => {
    it('clears the heart rate when the backend later reports null (no stale reading)', () => {
        const { rerender } = render(<PulseReadout pulseData={{ heart_rate: 72, quality: 0.8 }} />);
        expect(screen.getByText('72')).toBeInTheDocument();

        // Signal lost -> backend streams heart_rate: null. The displayed rate must
        // clear, not keep showing the stale value.
        rerender(<PulseReadout pulseData={{ heart_rate: null, quality: 0.5 }} />);
        expect(screen.queryByText('72')).toBeNull();
        expect(screen.getByText('--')).toBeInTheDocument();
    });
});
