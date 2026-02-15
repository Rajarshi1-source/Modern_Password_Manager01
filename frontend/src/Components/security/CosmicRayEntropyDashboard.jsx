import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import cosmicRayService from '../../services/cosmicRayService';
import './CosmicRayEntropyDashboard.css';

/**
 * Cosmic Ray Entropy Dashboard
 * 
 * Interactive dashboard for generating passwords from cosmic ray detection.
 * Features:
 * - Real-time particle animation visualization
 * - Detector status monitoring
 * - Password generation with cosmic ray entropy
 * - Event history display
 */
const CosmicRayEntropyDashboard = () => {
    // State
    const [status, setStatus] = useState(null);
    const [events, setEvents] = useState([]);
    const [password, setPassword] = useState('');
    const [passwordInfo, setPasswordInfo] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState(null);
    const [copied, setCopied] = useState(false);
    const [continuousEnabled, setContinuousEnabled] = useState(false);

    // Password options
    const [passwordLength, setPasswordLength] = useState(20);
    const [includeUppercase, setIncludeUppercase] = useState(true);
    const [includeLowercase, setIncludeLowercase] = useState(true);
    const [includeDigits, setIncludeDigits] = useState(true);
    const [includeSymbols, setIncludeSymbols] = useState(true);

    // Animation state
    const [particles, setParticles] = useState([]);
    const canvasRef = useRef(null);
    const animationRef = useRef(null);

    // Load status and events
    const loadData = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);

            const [statusData, eventsData] = await Promise.all([
                cosmicRayService.getDetectorStatus(),
                cosmicRayService.getRecentEvents(10)
            ]);

            setStatus(statusData);
            setEvents(eventsData.events || []);
            setContinuousEnabled(statusData.config?.continuous_enabled || false);

        } catch (err) {
            console.error('Failed to load cosmic ray data:', err);
            setError(err.response?.data?.error || 'Failed to load cosmic ray data');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();

        // Refresh status every 30 seconds
        const interval = setInterval(loadData, 30000);
        return () => clearInterval(interval);
    }, [loadData]);

    // Particle animation
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.offsetWidth;
        const height = canvas.height = canvas.offsetHeight;

        const activeParticles = [];

        const addParticle = () => {
            activeParticles.push({
                x: Math.random() * width,
                y: 0,
                speed: 2 + Math.random() * 4,
                size: 1 + Math.random() * 2,
                trail: [],
                hue: 180 + Math.random() * 60 // Cyan to blue range
            });
        };

        const animate = () => {
            ctx.fillStyle = 'rgba(10, 15, 30, 0.15)';
            ctx.fillRect(0, 0, width, height);

            // Add new particles occasionally
            if (Math.random() < 0.05) {
                addParticle();
            }

            // Update and draw particles
            for (let i = activeParticles.length - 1; i >= 0; i--) {
                const p = activeParticles[i];

                // Store trail position
                p.trail.push({ x: p.x, y: p.y });
                if (p.trail.length > 20) p.trail.shift();

                // Move particle
                p.y += p.speed;
                p.x += Math.sin(p.y * 0.02) * 0.5;

                // Draw trail
                ctx.beginPath();
                ctx.strokeStyle = `hsla(${p.hue}, 80%, 60%, 0.3)`;
                ctx.lineWidth = p.size * 0.5;
                for (let j = 0; j < p.trail.length; j++) {
                    const t = p.trail[j];
                    if (j === 0) {
                        ctx.moveTo(t.x, t.y);
                    } else {
                        ctx.lineTo(t.x, t.y);
                    }
                }
                ctx.stroke();

                // Draw particle
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fillStyle = `hsla(${p.hue}, 90%, 70%, 0.9)`;
                ctx.fill();

                // Remove if off screen
                if (p.y > height) {
                    activeParticles.splice(i, 1);
                }
            }

            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, []);

    // Generate password
    const handleGeneratePassword = async () => {
        try {
            setIsGenerating(true);
            setError(null);

            // Add burst of particles during generation
            const canvas = canvasRef.current;
            if (canvas) {
                const ctx = canvas.getContext('2d');
                const width = canvas.width;

                // Flash effect
                ctx.fillStyle = 'rgba(100, 200, 255, 0.2)';
                ctx.fillRect(0, 0, width, canvas.height);
            }

            const result = await cosmicRayService.generateCosmicPassword({
                length: passwordLength,
                includeUppercase,
                includeLowercase,
                includeDigits,
                includeSymbols
            });

            if (result.success) {
                setPassword(result.password);
                setPasswordInfo(result);
            } else {
                throw new Error(result.error || 'Generation failed');
            }

        } catch (err) {
            console.error('Failed to generate password:', err);
            setError(err.response?.data?.error || err.message || 'Failed to generate password');
        } finally {
            setIsGenerating(false);
        }
    };

    // Copy password
    const handleCopyPassword = async () => {
        if (!password) return;

        try {
            await navigator.clipboard.writeText(password);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    // Toggle continuous collection
    const handleToggleContinuous = async () => {
        try {
            const newValue = !continuousEnabled;
            await cosmicRayService.updateCollectionSettings({
                continuousCollection: newValue
            });
            setContinuousEnabled(newValue);
        } catch (err) {
            console.error('Failed to toggle continuous collection:', err);
            setError('Failed to update settings');
        }
    };

    // Mode badge helper
    const getModeInfo = (mode) => {
        switch (mode) {
            case 'hardware':
                return { label: 'Hardware', className: 'mode-hardware', icon: '📡' };
            case 'simulation':
                return { label: 'Simulation', className: 'mode-simulation', icon: '💻' };
            default:
                return { label: 'Unknown', className: 'mode-unknown', icon: '❓' };
        }
    };

    if (isLoading && !status) {
        return (
            <div className="cosmic-dashboard loading">
                <div className="loading-spinner">
                    <div className="spinner-ring"></div>
                    <span>Initializing Cosmic Ray Detector...</span>
                </div>
            </div>
        );
    }

    const modeInfo = status?.status ? getModeInfo(status.status.mode) : getModeInfo('unknown');

    return (
        <div className="cosmic-dashboard">
            {/* Background particle animation */}
            <canvas
                ref={canvasRef}
                className="cosmic-canvas"
                aria-hidden="true"
            />

            {/* Header */}
            <header className="cosmic-header">
                <div className="header-content">
                    <h1>
                        <span className="icon">🌌</span>
                        Cosmic Ray Entropy
                    </h1>
                    <p className="subtitle">
                        True randomness from muon detection
                    </p>
                </div>

                <div className="detector-status">
                    <span className={`mode-badge ${modeInfo.className}`}>
                        {modeInfo.icon} {modeInfo.label}
                    </span>

                    <button
                        className="refresh-btn"
                        onClick={loadData}
                        title="Refresh status"
                    >
                        🔄
                    </button>
                </div>
            </header>

            {/* Error display */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        className="error-banner"
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                    >
                        <span className="error-icon">⚠️</span>
                        <span>{error}</span>
                        <button onClick={() => setError(null)}>✕</button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Main content grid */}
            <div className="cosmic-content">
                {/* Password Generator Card */}
                <motion.section
                    className="card password-generator"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <h2>🔐 Generate Cosmic Password</h2>

                    {/* Password options */}
                    <div className="password-options">
                        <div className="option-group">
                            <label>
                                Length: <strong>{passwordLength}</strong>
                            </label>
                            <input
                                type="range"
                                min="8"
                                max="64"
                                value={passwordLength}
                                onChange={(e) => setPasswordLength(Number(e.target.value))}
                            />
                        </div>

                        <div className="checkbox-group">
                            <label>
                                <input
                                    type="checkbox"
                                    checked={includeUppercase}
                                    onChange={(e) => setIncludeUppercase(e.target.checked)}
                                />
                                ABC
                            </label>
                            <label>
                                <input
                                    type="checkbox"
                                    checked={includeLowercase}
                                    onChange={(e) => setIncludeLowercase(e.target.checked)}
                                />
                                abc
                            </label>
                            <label>
                                <input
                                    type="checkbox"
                                    checked={includeDigits}
                                    onChange={(e) => setIncludeDigits(e.target.checked)}
                                />
                                123
                            </label>
                            <label>
                                <input
                                    type="checkbox"
                                    checked={includeSymbols}
                                    onChange={(e) => setIncludeSymbols(e.target.checked)}
                                />
                                !@#
                            </label>
                        </div>
                    </div>

                    {/* Generate button */}
                    <button
                        className={`generate-btn ${isGenerating ? 'generating' : ''}`}
                        onClick={handleGeneratePassword}
                        disabled={isGenerating}
                    >
                        {isGenerating ? (
                            <>
                                <span className="spinner"></span>
                                Harvesting Cosmic Rays...
                            </>
                        ) : (
                            <>✨ Generate Password</>
                        )}
                    </button>

                    {/* Password display */}
                    <AnimatePresence>
                        {password && (
                            <motion.div
                                className="password-result"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                            >
                                <div className="password-display">
                                    <code>{password}</code>
                                    <button
                                        className={`copy-btn ${copied ? 'copied' : ''}`}
                                        onClick={handleCopyPassword}
                                    >
                                        {copied ? '✓ Copied!' : '📋 Copy'}
                                    </button>
                                </div>

                                {passwordInfo && (
                                    <div className="password-meta">
                                        <span>🎲 Source: {passwordInfo.source}</span>
                                        <span>⚡ {passwordInfo.entropy_bits} bits</span>
                                        <span>🔬 {passwordInfo.events_used} events</span>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.section>

                {/* Detector Status Card */}
                <motion.section
                    className="card detector-status-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <h2>📡 Detector Status</h2>

                    <div className="status-grid">
                        <div className="status-item">
                            <span className="label">Mode</span>
                            <span className={`value ${modeInfo.className}`}>
                                {modeInfo.icon} {modeInfo.label}
                            </span>
                        </div>

                        <div className="status-item">
                            <span className="label">Available</span>
                            <span className={`value ${status?.status?.available ? 'available' : 'unavailable'}`}>
                                {status?.status?.available ? '✅ Ready' : '❌ Offline'}
                            </span>
                        </div>

                        <div className="status-item">
                            <span className="label">Continuous</span>
                            <button
                                className={`toggle-btn ${continuousEnabled ? 'enabled' : ''}`}
                                onClick={handleToggleContinuous}
                            >
                                {continuousEnabled ? '🟢 ON' : '⚫ OFF'}
                            </button>
                        </div>

                        {status?.config && (
                            <>
                                <div className="status-item">
                                    <span className="label">Buffer Size</span>
                                    <span className="value">{status.config.buffer_size}</span>
                                </div>

                                <div className="status-item">
                                    <span className="label">Simulation</span>
                                    <span className="value">
                                        {status.config.simulation_fallback ? '✅ Enabled' : '❌ Disabled'}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>
                </motion.section>

                {/* Recent Events Card */}
                <motion.section
                    className="card events-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <h2>⚡ Recent Cosmic Events</h2>

                    <div className="events-list">
                        {events.length > 0 ? (
                            events.slice(0, 5).map((event, index) => (
                                <motion.div
                                    key={index}
                                    className="event-item"
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                >
                                    <span className="event-icon">☄️</span>
                                    <div className="event-details">
                                        <span className="energy">
                                            Energy: {event.energy_adc} ADC
                                        </span>
                                        <span className="quality">
                                            Quality: {(event.quality_score * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                    <span className="timestamp">
                                        {new Date(event.timestamp).toLocaleTimeString()}
                                    </span>
                                </motion.div>
                            ))
                        ) : (
                            <div className="no-events">
                                <span>🔭 Waiting for cosmic events...</span>
                            </div>
                        )}
                    </div>
                </motion.section>

                {/* Info Card */}
                <motion.section
                    className="card info-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    <h2>ℹ️ How It Works</h2>

                    <div className="info-content">
                        <p>
                            Cosmic rays are high-energy particles from deep space—supernovae,
                            active galactic nuclei, and other astrophysical phenomena.
                        </p>
                        <p>
                            When cosmic rays hit Earth's atmosphere, they create particle
                            showers including <strong>muons</strong>. These muons reach sea
                            level at unpredictable times.
                        </p>
                        <p>
                            We harvest the precise timing and energy of muon detections to
                            generate <strong>true random numbers</strong>—no algorithm can
                            predict when the next cosmic ray will arrive.
                        </p>

                        <div className="source-badge">
                            <span className="badge hardware">📡 Hardware: CosmicWatch Detector</span>
                            <span className="badge simulation">💻 Simulation: Secure Fallback</span>
                        </div>
                    </div>
                </motion.section>
            </div>
        </div>
    );
};

export default CosmicRayEntropyDashboard;
