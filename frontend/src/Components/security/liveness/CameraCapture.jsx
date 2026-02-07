/**
 * CameraCapture Component
 * 
 * Video camera capture with face overlay guide for liveness verification.
 */

import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import './CameraCapture.css';

const CameraCapture = forwardRef(({
    onFrame,
    fps = 10,
    showGuide = true,
    guideShape = 'oval',
    onCameraReady,
    onError
}, ref) => {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const captureIntervalRef = useRef(null);

    const [isReady, setIsReady] = useState(false);
    const [isFaceDetected, setIsFaceDetected] = useState(false);

    useImperativeHandle(ref, () => ({
        captureFrame: () => captureFrame(),
        startCapture: () => startCapture(),
        stopCapture: () => stopCapture(),
        getStream: () => streamRef.current,
    }));

    useEffect(() => {
        initCamera();
        return () => cleanup();
    }, []);

    const initCamera = async () => {
        try {
            const constraints = {
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user',
                    frameRate: { ideal: 30 },
                },
                audio: false,
            };

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            streamRef.current = stream;

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.onloadedmetadata = () => {
                    setIsReady(true);
                    if (onCameraReady) onCameraReady();
                };
            }
        } catch (err) {
            console.error('Camera init error:', err);
            if (onError) onError(err.message);
        }
    };

    const captureFrame = useCallback(() => {
        if (!videoRef.current || !canvasRef.current || !isReady) return null;

        const video = videoRef.current;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        // Mirror horizontally
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        ctx.setTransform(1, 0, 0, 1, 0, 0);

        const base64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];

        return {
            base64,
            width: canvas.width,
            height: canvas.height,
            timestamp: Date.now(),
        };
    }, [isReady]);

    const startCapture = useCallback(() => {
        if (captureIntervalRef.current) return;

        const interval = 1000 / fps;
        captureIntervalRef.current = setInterval(() => {
            const frame = captureFrame();
            if (frame && onFrame) {
                onFrame(frame);
            }
        }, interval);
    }, [fps, captureFrame, onFrame]);

    const stopCapture = useCallback(() => {
        if (captureIntervalRef.current) {
            clearInterval(captureIntervalRef.current);
            captureIntervalRef.current = null;
        }
    }, []);

    const cleanup = () => {
        stopCapture();
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
        }
    };

    return (
        <div className="camera-capture">
            <div className="video-container">
                <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className={isReady ? 'ready' : ''}
                />
                <canvas ref={canvasRef} style={{ display: 'none' }} />

                {showGuide && (
                    <div className="face-overlay">
                        <div className={`face-guide ${guideShape} ${isFaceDetected ? 'detected' : ''}`}>
                            <div className="guide-corner top-left"></div>
                            <div className="guide-corner top-right"></div>
                            <div className="guide-corner bottom-left"></div>
                            <div className="guide-corner bottom-right"></div>
                        </div>
                        <p className="guide-instruction">
                            Position your face within the frame
                        </p>
                    </div>
                )}

                {!isReady && (
                    <div className="loading-overlay">
                        <div className="spinner"></div>
                        <p>Starting camera...</p>
                    </div>
                )}
            </div>
        </div>
    );
});

CameraCapture.displayName = 'CameraCapture';

export default CameraCapture;
