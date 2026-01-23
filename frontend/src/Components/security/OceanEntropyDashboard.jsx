/**
 * Ocean Entropy Dashboard
 * ========================
 * 
 * Dashboard component for ocean wave entropy harvesting.
 * Shows live buoy data, entropy generation, and wave visualizations.
 * 
 * "Powered by the ocean's chaos" 🌊
 * 
 * @author Password Manager Team
 * @created 2026-01-23
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './OceanEntropyDashboard.css';

const API_URL = import.meta.env.VITE_API_URL || '';
const API_BASE = `${API_URL}/api/security/ocean`;

/**
 * Ocean Entropy Dashboard Component
 */
const OceanEntropyDashboard = () => {
    // State
    const [status, setStatus] = useState(null);
    const [buoys, setBuoys] = useState([]);
    const [readings, setReadings] = useState([]);
    const [generatedEntropy, setGeneratedEntropy] = useState(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState(null);
    const [selectedRegion, setSelectedRegion] = useState('all');

    // Fetch status
    const fetchStatus = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE}/status/`);
            setStatus(response.data);
        } catch (err) {
            console.error('Failed to fetch ocean status:', err);
            setError('Failed to connect to ocean entropy service');
        }
    }, []);

    // Fetch buoys
    const fetchBuoys = useCallback(async () => {
        try {
            const params = selectedRegion !== 'all' ? { region: selectedRegion } : {};
            const response = await axios.get(`${API_BASE}/buoys/`, { params });
            setBuoys(response.data.buoys || []);
        } catch (err) {
            console.error('Failed to fetch buoys:', err);
        }
    }, [selectedRegion]);

    // Fetch readings
    const fetchReadings = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE}/readings/`, {
                params: { limit: 5 }
            });
            setReadings(response.data.readings || []);
        } catch (err) {
            console.error('Failed to fetch readings:', err);
        }
    }, []);

    // Generate entropy
    const generateEntropy = async (byteCount = 32) => {
        setGenerating(true);
        setError(null);

        try {
            const response = await axios.post(`${API_BASE}/generate/`, {
                count: byteCount,
                format: 'hex'
            });

            setGeneratedEntropy(response.data);
            fetchStatus(); // Refresh status
        } catch (err) {
            console.error('Failed to generate entropy:', err);
            setError('Failed to generate ocean entropy');
        } finally {
            setGenerating(false);
        }
    };

    // Initial load
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            await Promise.all([fetchStatus(), fetchBuoys(), fetchReadings()]);
            setLoading(false);
        };

        loadData();

        // Auto-refresh every 30 seconds
        const interval = setInterval(() => {
            fetchStatus();
            fetchReadings();
        }, 30000);

        return () => clearInterval(interval);
    }, [fetchStatus, fetchBuoys, fetchReadings]);

    // Reload buoys when region changes
    useEffect(() => {
        fetchBuoys();
    }, [selectedRegion, fetchBuoys]);

    if (loading) {
        return (
            <div className="ocean-dashboard loading">
                <div className="wave-loader">
                    <div className="wave"></div>
                    <div className="wave"></div>
                    <div className="wave"></div>
                </div>
                <p>Connecting to ocean entropy sources...</p>
            </div>
        );
    }

    return (
        <div className="ocean-dashboard">
            {/* Header */}
            <header className="ocean-header">
                <div className="header-content">
                    <div className="title-area">
                        <span className="ocean-icon">🌊</span>
                        <div>
                            <h1>Ocean Wave Entropy</h1>
                            <p className="tagline">Powered by the ocean's chaos</p>
                        </div>
                    </div>

                    <div className="status-badge" data-status={status?.status || 'unknown'}>
                        {status?.status === 'available' ? '● Active' : '○ Degraded'}
                    </div>
                </div>
            </header>

            {/* Error Banner */}
            {error && (
                <div className="error-banner">
                    <span>⚠️</span> {error}
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Stats Cards */}
            <section className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">📡</div>
                    <div className="stat-content">
                        <span className="stat-value">{status?.buoys?.healthy || 0}</span>
                        <span className="stat-label">Active Buoys</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon">🌍</div>
                    <div className="stat-content">
                        <span className="stat-value">{status?.config?.pool_contribution_percent || 0}%</span>
                        <span className="stat-label">Pool Contribution</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon">⚡</div>
                    <div className="stat-content">
                        <span className="stat-value">{status?.config?.min_entropy_bits || 0}</span>
                        <span className="stat-label">Min Entropy (bits/byte)</span>
                    </div>
                </div>

                <div className="stat-card generated">
                    <div className="stat-icon">🎲</div>
                    <div className="stat-content">
                        <span className="stat-value">{generatedEntropy ? generatedEntropy.bytes_count : '-'}</span>
                        <span className="stat-label">Bytes Generated</span>
                    </div>
                </div>
            </section>

            {/* Main Content Grid */}
            <div className="main-grid">
                {/* Wave Visualizer */}
                <section className="card wave-visualizer">
                    <h2>🌊 Live Wave Data</h2>
                    <div className="wave-animation">
                        <svg viewBox="0 0 400 100" preserveAspectRatio="none">
                            <path
                                className="wave-path primary"
                                d="M0,50 C100,30 200,70 300,50 C350,40 400,60 400,50 L400,100 L0,100 Z"
                            />
                            <path
                                className="wave-path secondary"
                                d="M0,60 C80,40 160,80 240,55 C320,35 400,65 400,50 L400,100 L0,100 Z"
                            />
                        </svg>
                    </div>

                    {readings.length > 0 && (
                        <div className="current-readings">
                            {readings.slice(0, 3).map((reading, idx) => (
                                <div key={idx} className="reading-item">
                                    <span className="buoy-id">🔵 {reading.buoy_id}</span>
                                    <div className="reading-values">
                                        {reading.wave_height_m && (
                                            <span>Height: {reading.wave_height_m}m</span>
                                        )}
                                        {reading.wave_period_sec && (
                                            <span>Period: {reading.wave_period_sec}s</span>
                                        )}
                                        {reading.sea_temp_c && (
                                            <span>Temp: {reading.sea_temp_c}°C</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                {/* Entropy Generator */}
                <section className="card entropy-generator">
                    <h2>⚡ Generate Entropy</h2>

                    <p className="description">
                        Generate cryptographically secure random bytes from real-time
                        ocean wave data collected from NOAA buoys.
                    </p>

                    <div className="generate-controls">
                        <button
                            className="generate-btn"
                            onClick={() => generateEntropy(32)}
                            disabled={generating}
                        >
                            {generating ? (
                                <>
                                    <span className="spinner"></span>
                                    Harvesting waves...
                                </>
                            ) : (
                                <>🌊 Generate 32 Bytes</>
                            )}
                        </button>

                        <button
                            className="generate-btn secondary"
                            onClick={() => generateEntropy(64)}
                            disabled={generating}
                        >
                            🌊 Generate 64 Bytes
                        </button>
                    </div>

                    {generatedEntropy && (
                        <div className="entropy-result">
                            <h3>Generated Entropy</h3>
                            <code className="entropy-hex">{generatedEntropy.entropy}</code>

                            <div className="entropy-meta">
                                <span>🔵 Source: {generatedEntropy.source_buoys?.join(', ')}</span>
                                <span>📊 Provider: {generatedEntropy.provider}</span>
                                <span>⏰ {new Date(generatedEntropy.generated_at).toLocaleTimeString()}</span>
                            </div>

                            <p className="ocean-message">{generatedEntropy.message}</p>
                        </div>
                    )}
                </section>

                {/* Buoy Map */}
                <section className="card buoy-map">
                    <div className="card-header">
                        <h2>📡 Active Buoys</h2>

                        <select
                            value={selectedRegion}
                            onChange={(e) => setSelectedRegion(e.target.value)}
                            className="region-select"
                        >
                            <option value="all">All Regions</option>
                            <option value="atlantic">Atlantic</option>
                            <option value="pacific">Pacific</option>
                            <option value="gulf">Gulf of Mexico</option>
                            <option value="caribbean">Caribbean</option>
                        </select>
                    </div>

                    <div className="buoy-list">
                        {buoys.map((buoy) => (
                            <div key={buoy.id} className="buoy-item">
                                <div className="buoy-icon">📍</div>
                                <div className="buoy-info">
                                    <span className="buoy-name">{buoy.name}</span>
                                    <span className="buoy-details">
                                        {buoy.id} • {buoy.region}
                                    </span>
                                    <span className="buoy-coords">
                                        {buoy.latitude.toFixed(3)}°, {buoy.longitude.toFixed(3)}°
                                    </span>
                                </div>
                            </div>
                        ))}

                        {buoys.length === 0 && (
                            <p className="no-buoys">No buoys found in this region</p>
                        )}
                    </div>
                </section>

                {/* Provider Info */}
                <section className="card provider-info">
                    <h2>ℹ️ About Ocean Entropy</h2>

                    <div className="info-content">
                        <p>
                            <strong>NOAA Ocean Wave Entropy</strong> harvests randomness from
                            real-time oceanographic data collected by the National Data Buoy Center.
                        </p>

                        <h3>Entropy Sources</h3>
                        <ul>
                            <li>🌊 <strong>Wave Height & Period</strong> - Highly chaotic, unpredictable</li>
                            <li>🌡️ <strong>Sea Temperature</strong> - Continuous fluctuations</li>
                            <li>💨 <strong>Wind Speed & Gusts</strong> - Rapid, random changes</li>
                            <li>🔄 <strong>Wave Direction</strong> - Multi-directional patterns</li>
                        </ul>

                        <h3>Security Features</h3>
                        <ul>
                            <li>✅ Von Neumann debiasing to ensure uniform distribution</li>
                            <li>✅ BLAKE3 hash conditioning for cryptographic quality</li>
                            <li>✅ Multiple geographically distributed sources</li>
                            <li>✅ Min-entropy validation (&gt;4 bits/byte)</li>
                        </ul>

                        <p className="tagline-footer">
                            🌊 <em>Powered by the ocean's chaos</em>
                        </p>
                    </div>
                </section>
            </div>
        </div>
    );
};

export default OceanEntropyDashboard;
