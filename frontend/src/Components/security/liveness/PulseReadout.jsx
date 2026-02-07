/**
 * PulseReadout Component
 * 
 * Real-time pulse and SpO2 display for liveness verification.
 */

import React, { useState, useEffect, useRef } from 'react';
import './PulseReadout.css';

const PulseReadout = ({ pulseData, isActive = true }) => {
    const [heartRate, setHeartRate] = useState(null);
    const [spo2, setSpo2] = useState(null);
    const [signalQuality, setSignalQuality] = useState(0);
    const [history, setHistory] = useState([]);
    const canvasRef = useRef(null);

    useEffect(() => {
        if (pulseData) {
            if (pulseData.heart_rate_bpm) setHeartRate(pulseData.heart_rate_bpm);
            if (pulseData.spo2) setSpo2(pulseData.spo2);
            if (pulseData.signal_quality) setSignalQuality(pulseData.signal_quality);

            // Add to waveform history
            if (pulseData.ppg_value !== undefined) {
                setHistory(prev => {
                    const updated = [...prev, pulseData.ppg_value];
                    return updated.slice(-100); // Keep last 100 points
                });
            }
        }
    }, [pulseData]);

    useEffect(() => {
        drawWaveform();
    }, [history]);

    const drawWaveform = () => {
        const canvas = canvasRef.current;
        if (!canvas || history.length < 2) return;

        const ctx = canvas.getContext('2d');
        const { width, height } = canvas;

        // Clear
        ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
        ctx.fillRect(0, 0, width, height);

        // Normalize data
        const min = Math.min(...history);
        const max = Math.max(...history);
        const range = max - min || 1;

        // Draw waveform
        ctx.beginPath();
        ctx.strokeStyle = isActive ? '#ff4757' : '#666';
        ctx.lineWidth = 2;

        history.forEach((value, i) => {
            const x = (i / history.length) * width;
            const y = height - ((value - min) / range) * (height * 0.8) - height * 0.1;

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.stroke();

        // Draw gradient below line
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, 'rgba(255, 71, 87, 0.3)');
        gradient.addColorStop(1, 'rgba(255, 71, 87, 0)');

        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
    };

    const getHeartRateStatus = () => {
        if (!heartRate) return 'measuring';
        if (heartRate < 60) return 'low';
        if (heartRate > 100) return 'high';
        return 'normal';
    };

    const getSpo2Status = () => {
        if (!spo2) return 'measuring';
        if (spo2 < 95) return 'low';
        return 'normal';
    };

    return (
        <div className={`pulse-readout ${isActive ? 'active' : ''}`}>
            <div className="readout-header">
                <span className="readout-icon">❤️</span>
                <h3>Pulse Detection</h3>
                <div className={`signal-indicator ${signalQuality > 0.6 ? 'good' : signalQuality > 0.3 ? 'fair' : 'poor'}`}>
                    <div className="signal-bar"></div>
                    <div className="signal-bar"></div>
                    <div className="signal-bar"></div>
                </div>
            </div>

            <div className="waveform-container">
                <canvas ref={canvasRef} width={300} height={80} />
            </div>

            <div className="vitals-row">
                <div className={`vital-card ${getHeartRateStatus()}`}>
                    <div className="vital-icon">💓</div>
                    <div className="vital-value">
                        {heartRate ? `${Math.round(heartRate)}` : '--'}
                    </div>
                    <div className="vital-unit">BPM</div>
                    <div className="vital-label">Heart Rate</div>
                </div>

                <div className={`vital-card ${getSpo2Status()}`}>
                    <div className="vital-icon">🩸</div>
                    <div className="vital-value">
                        {spo2 ? `${Math.round(spo2)}` : '--'}
                    </div>
                    <div className="vital-unit">%</div>
                    <div className="vital-label">SpO2</div>
                </div>

                <div className="vital-card">
                    <div className="vital-icon">📊</div>
                    <div className="vital-value">
                        {Math.round(signalQuality * 100)}
                    </div>
                    <div className="vital-unit">%</div>
                    <div className="vital-label">Signal</div>
                </div>
            </div>

            {isActive && (
                <div className="measuring-notice">
                    <div className="pulse-dot"></div>
                    <span>Measuring cardiovascular signals...</span>
                </div>
            )}
        </div>
    );
};

export default PulseReadout;
