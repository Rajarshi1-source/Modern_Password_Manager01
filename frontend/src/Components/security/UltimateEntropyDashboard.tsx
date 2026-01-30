import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    EntropyGlobe,
    EntropyMixingParticles,
    InteractiveCertificateBadge,
    EntropySourceCard
} from './EnhancedEntropyVisualizations';
import './UltimateEntropyDashboard.css';

// =============================================================================
// Types
// =============================================================================

interface EntropySource {
    id: string;
    name: string;
    icon: string;
    color: string;
    available: boolean;
    quality: number;
    description: string;
    activity?: any;
}

interface GlobalStatus {
    sources: Record<string, any>;
    available_sources: number;
    total_sources: number;
    timestamp: string;
}

interface GeneratedPassword {
    password: string;
    sources_used: string[];
    quality_score: number;
    certificate: any;
}

// =============================================================================
// API Functions
// =============================================================================

const API_BASE = '/api/security';

async function fetchGlobalStatus(): Promise<GlobalStatus> {
    const response = await fetch(`${API_BASE}/natural/status/`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    });
    if (!response.ok) throw new Error('Failed to fetch status');
    return response.json();
}

async function generateNaturalPassword(
    sources: string[],
    length: number,
    charset: string = 'standard'
): Promise<GeneratedPassword> {
    const response = await fetch(`${API_BASE}/natural/generate-password/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ sources, length, charset })
    });
    if (!response.ok) throw new Error('Failed to generate password');
    return response.json();
}

// =============================================================================
// Main Dashboard Component
// =============================================================================

export default function UltimateEntropyDashboard() {
    // State
    const [status, setStatus] = useState<GlobalStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedSources, setSelectedSources] = useState<string[]>(['ocean', 'lightning', 'seismic', 'solar']);
    const [passwordLength, setPasswordLength] = useState(24);
    const [charset, setCharset] = useState('standard');

    const [isGenerating, setIsGenerating] = useState(false);
    const [generatedPassword, setGeneratedPassword] = useState<GeneratedPassword | null>(null);
    const [showPassword, setShowPassword] = useState(false);

    // Fetch status on mount
    useEffect(() => {
        const loadStatus = async () => {
            try {
                setLoading(true);
                const data = await fetchGlobalStatus();
                setStatus(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load status');
            } finally {
                setLoading(false);
            }
        };

        loadStatus();
        const interval = setInterval(loadStatus, 60000);
        return () => clearInterval(interval);
    }, []);

    // Convert status to source objects
    const sources: EntropySource[] = status ? [
        {
            id: 'ocean',
            name: 'Ocean Waves',
            icon: '🌊',
            color: '#06b6d4',
            available: status.sources.ocean?.available ?? false,
            quality: 0.85,
            description: 'NOAA Pacific buoy network',
            activity: status.sources.ocean,
        },
        {
            id: 'lightning',
            name: 'Lightning',
            icon: '⚡',
            color: '#eab308',
            available: status.sources.lightning?.available ?? false,
            quality: 0.8,
            description: 'NOAA GOES satellite GLM',
            activity: status.sources.lightning,
        },
        {
            id: 'seismic',
            name: 'Seismic',
            icon: '🌍',
            color: '#22c55e',
            available: status.sources.seismic?.available ?? false,
            quality: 0.75,
            description: 'USGS global earthquake network',
            activity: status.sources.seismic,
        },
        {
            id: 'solar',
            name: 'Solar Wind',
            icon: '☀️',
            color: '#f97316',
            available: status.sources.solar?.available ?? false,
            quality: 0.7,
            description: 'NOAA DSCOVR spacecraft',
            activity: status.sources.solar,
        },
    ] : [];

    // Toggle source selection
    const toggleSource = (sourceId: string) => {
        setSelectedSources(prev =>
            prev.includes(sourceId)
                ? prev.filter(s => s !== sourceId)
                : [...prev, sourceId]
        );
    };

    // Generate password
    const handleGenerate = useCallback(async () => {
        if (selectedSources.length === 0) return;

        setIsGenerating(true);
        setGeneratedPassword(null);
        setShowPassword(true);

        try {
            // Artificial delay for animation
            await new Promise(resolve => setTimeout(resolve, 2000));

            const result = await generateNaturalPassword(
                selectedSources,
                passwordLength,
                charset
            );
            setGeneratedPassword(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Generation failed');
        } finally {
            setIsGenerating(false);
        }
    }, [selectedSources, passwordLength, charset]);

    // Copy password
    const copyPassword = async () => {
        if (generatedPassword?.password) {
            await navigator.clipboard.writeText(generatedPassword.password);
        }
    };

    if (loading) {
        return (
            <div className="ultimate-dashboard loading">
                <div className="loading-spinner">
                    <span className="loading-icon">🌐</span>
                    <span>Connecting to entropy sources...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="ultimate-dashboard">
            {/* Header */}
            <motion.header
                className="dashboard-header"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <h1>
                    <span className="icon-group">🌊⚡🌍☀️</span>
                    Ultimate Natural Entropy
                </h1>
                <p className="subtitle">
                    Harness the chaos of Earth and space for ultimate password security
                </p>
            </motion.header>

            {/* Error Banner */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        className="error-banner"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                    >
                        ⚠️ {error}
                        <button onClick={() => setError(null)}>✕</button>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="dashboard-grid">
                {/* Left Column - Globe & Status */}
                <div className="globe-section">
                    <div className="section-card globe-card">
                        <h2>🌐 Global Entropy Sources</h2>
                        <EntropyGlobe
                            sources={sources}
                            onSourceClick={(s) => toggleSource(s.id)}
                            showParticles={true}
                        />
                        <div className="status-bar">
                            <span className="status-dot active" />
                            {status?.available_sources}/{status?.total_sources} sources online
                        </div>
                    </div>
                </div>

                {/* Center Column - Generation */}
                <div className="generation-section">
                    {/* Source Selection */}
                    <div className="section-card sources-card">
                        <h2>⚡ Select Entropy Sources</h2>
                        <div className="sources-grid">
                            {sources.map(source => (
                                <EntropySourceCard
                                    key={source.id}
                                    source={source}
                                    selected={selectedSources.includes(source.id)}
                                    onToggle={() => toggleSource(source.id)}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Generation Controls */}
                    <div className="section-card controls-card">
                        <h2>🔐 Generate Password</h2>

                        <div className="control-group">
                            <label>Password Length: {passwordLength}</label>
                            <input
                                type="range"
                                min={8}
                                max={64}
                                value={passwordLength}
                                onChange={e => setPasswordLength(parseInt(e.target.value))}
                                className="length-slider"
                            />
                        </div>

                        <div className="control-group">
                            <label>Character Set</label>
                            <select
                                value={charset}
                                onChange={e => setCharset(e.target.value)}
                                className="charset-select"
                            >
                                <option value="standard">Standard (letters + numbers + symbols)</option>
                                <option value="alphanumeric">Alphanumeric (no symbols)</option>
                                <option value="max_entropy">Maximum Entropy (all printable)</option>
                            </select>
                        </div>

                        <button
                            className="generate-button"
                            onClick={handleGenerate}
                            disabled={isGenerating || selectedSources.length === 0}
                        >
                            {isGenerating ? (
                                <>
                                    <span className="spinner" />
                                    Mixing Entropy...
                                </>
                            ) : (
                                <>
                                    🎲 Generate from {selectedSources.length} Source{selectedSources.length !== 1 ? 's' : ''}
                                </>
                            )}
                        </button>
                    </div>

                    {/* Generated Password Display */}
                    <AnimatePresence>
                        {showPassword && (
                            <motion.div
                                className="section-card password-card"
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                            >
                                <h2>🔑 Your Password</h2>

                                {isGenerating ? (
                                    <div className="mixing-animation">
                                        <EntropyMixingParticles
                                            sources={sources.filter(s => selectedSources.includes(s.id))}
                                            isGenerating={true}
                                        />
                                        <p>Mixing entropy from nature's chaos...</p>
                                    </div>
                                ) : generatedPassword ? (
                                    <>
                                        <div className="password-display">
                                            <code>{generatedPassword.password}</code>
                                            <button onClick={copyPassword} title="Copy">📋</button>
                                        </div>

                                        <div className="password-meta">
                                            <div className="meta-item">
                                                <span className="label">Sources</span>
                                                <span className="value">
                                                    {generatedPassword.sources_used.map(s =>
                                                        sources.find(src => src.id === s)?.icon
                                                    ).join(' ')}
                                                </span>
                                            </div>
                                            <div className="meta-item">
                                                <span className="label">Quality</span>
                                                <span className="value quality-score">
                                                    {(generatedPassword.quality_score * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                        </div>

                                        {generatedPassword.certificate && (
                                            <div className="certificate-section">
                                                <InteractiveCertificateBadge
                                                    certificate={generatedPassword.certificate}
                                                    size="medium"
                                                />
                                            </div>
                                        )}
                                    </>
                                ) : null}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Right Column - Activity Feed */}
                <div className="activity-section">
                    <div className="section-card activity-card">
                        <h2>📡 Live Activity</h2>
                        <div className="activity-feed">
                            {sources.map(source => (
                                <div key={source.id} className="activity-item">
                                    <span className="activity-icon">{source.icon}</span>
                                    <div className="activity-content">
                                        <div className="activity-title">{source.name}</div>
                                        <div className="activity-status" style={{ color: source.available ? '#22c55e' : '#ef4444' }}>
                                            {source.available ? 'Online' : 'Offline'}
                                        </div>
                                        {source.activity && (
                                            <div className="activity-detail">
                                                {source.id === 'lightning' && source.activity.activity?.strikes_last_hour &&
                                                    `${(source.activity.activity.strikes_last_hour / 1000).toFixed(0)}K strikes/hr`}
                                                {source.id === 'seismic' && source.activity.activity?.events_24h &&
                                                    `${source.activity.activity.events_24h} events/24h`}
                                                {source.id === 'solar' && source.activity.weather?.storm_level &&
                                                    `Storm: ${source.activity.weather.storm_level}`}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="section-card stats-card">
                        <h2>📊 Statistics</h2>
                        <div className="stats-grid">
                            <div className="stat-item">
                                <span className="stat-value">{sources.filter(s => s.available).length}</span>
                                <span className="stat-label">Active Sources</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-value">{passwordLength}</span>
                                <span className="stat-label">Password Length</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-value">
                                    {generatedPassword ? (generatedPassword.quality_score * 100).toFixed(0) : '—'}%
                                </span>
                                <span className="stat-label">Quality Score</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
