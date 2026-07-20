/**
 * Regression test for the CameraCapture unmount race.
 *
 * initCamera() awaits getUserMedia(); if the component unmounts while that
 * promise is still pending, cleanup() runs with no stream to stop, and the
 * late-resolving stream must be stopped rather than left live.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import CameraCapture from '../CameraCapture';

describe('CameraCapture unmount race', () => {
    const originalMediaDevices = navigator.mediaDevices;

    afterEach(() => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: originalMediaDevices,
            configurable: true,
        });
    });

    it('stops a stream that resolves after unmount instead of leaving the camera live', async () => {
        let resolveGetUserMedia;
        const track = { stop: vi.fn() };
        const stream = { getTracks: () => [track] };
        Object.defineProperty(navigator, 'mediaDevices', {
            value: {
                getUserMedia: vi.fn(() => new Promise((res) => { resolveGetUserMedia = res; })),
            },
            configurable: true,
        });

        const { unmount } = render(<CameraCapture />);
        // Unmount while getUserMedia() is still pending.
        unmount();
        // The camera promise now resolves -- its tracks must be stopped.
        await act(async () => { resolveGetUserMedia(stream); });

        expect(track.stop).toHaveBeenCalledTimes(1);
    });
});
