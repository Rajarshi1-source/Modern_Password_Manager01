/**
 * Ocean Wave Entropy Dashboard (TypeScript)
 * 
 * Interactive visualization of ocean wave entropy harvesting.
 * Features:
 * - Live wave animation canvas
 * - Buoy map with Leaflet
 * - Real-time entropy generation
 * - Certificate viewer
 * 
 * @author Password Manager Team
 * @created 2026-01-23
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
// @ts-ignore - Install with: npm install leaflet react-leaflet @types/leaflet
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
// @ts-ignore - Install with: npm install leaflet react-leaflet @types/leaflet
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './OceanWaveDashboard.css';

// Fix Leaflet default marker icon issue
try {
    delete (L.Icon.Default.prototype as any)._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    });
} catch (e) {
    console.warn('Leaflet not initialized:', e);
}

// Types
interface BuoyData {
    id: string;
    name: string;
    status: 'excellent' | 'good' | 'degraded' | 'offline';
    location: [number, number] | null;
    latitude: number;
    longitude: number;
    region: string;
    current_conditions: {
        wave_height: number | null;
        wave_period: number | null;
        water_temp: number | null;
        wind_speed: number | null;
    } | null;
    wave_height?: number | null;
    wave_period?: number | null;
    quality_score: number;
    last_reading: string | null;
}

interface WaveData {
    buoy_id: string;
    buoy_name: string;
    timestamp: string;
    wave_data: {
        height: number | null;
        period: number | null;
        direction: number | null;
    };
    weather_data: {
        water_temp: number | null;
        air_temp: number | null;
        wind_speed: number | null;
        wind_direction: number | null;
        pressure: number | null;
    };
    location: [number, number] | null;
    quality_score: number;
}

interface Certificate {
    certificate_id: string;
    password_hash_prefix: string;
    sources_used: string[];
    ocean: {
        buoy_id: string;
        wave_height: number | null;
    };
    quality_score: number;
    generation_timestamp: string;
}

interface GeneratedPassword {
    password: string;
    sources: string[];
    entropy_bits: number;
    quality_assessment: {
        shannon_entropy: number;
        quality: string;
    };
    mixing_algorithm: string;
    ocean_details?: {
        provider: string;
        source_id: string;
        buoy_id?: string;
        wave_height?: number;
    };
}

const API_URL = (import.meta as any).env?.VITE_API_URL || '';
const API_BASE = `${API_URL}/api/security/ocean`;

// Custom buoy marker icons
const createBuoyIcon = (status: string) => {
    const color = status === 'excellent' ? '#22c55e' :
        status === 'good' ? '#3b82f6' :
            status === 'degraded' ? '#f59e0b' : '#ef4444';

    return L.divIcon({
        className: 'buoy-marker',
        html: `
            <div style="
                width: 32px;
                height: 32px;
                background: ${color};
                border: 3px solid white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            ">🌊</div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
    });
};

// Map center controller component
const MapController: React.FC<{ center: [number, number]; zoom: number }> = ({ center, zoom }) => {
    const map = useMap();
    useEffect(() => {
        map.setView(center, zoom);
    }, [center, zoom, map]);
    return null;
};

// Buoy Map Component with Leaflet
const BuoyMap: React.FC<{
    buoys: BuoyData[];
    selectedBuoy: BuoyData | null;
    onSelectBuoy: (buoy: BuoyData) => void;
}> = ({ buoys, selectedBuoy, onSelectBuoy }) => {
    const defaultCenter: [number, number] = [35, -60]; // Atlantic Ocean
    const center: [number, number] = selectedBuoy
        ? [selectedBuoy.latitude, selectedBuoy.longitude]
        : defaultCenter;
    const zoom = selectedBuoy ? 6 : 3;

    return (
        <div className="buoy-map-container">
            <MapContainer
                center={center}
                zoom={zoom}
                style={{ height: '300px', width: '100%', borderRadius: '12px' }}
                scrollWheelZoom={true}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <MapController center={center} zoom={zoom} />

                {buoys.map((buoy) => (
                    <Marker
                        key={buoy.id}
                        position={[buoy.latitude, buoy.longitude]}
                        icon={createBuoyIcon(buoy.status)}
                        eventHandlers={{
                            click: () => onSelectBuoy(buoy),
                        }}
                    >
                        <Popup>
                            <div className="buoy-popup">
                                <h4>{buoy.name || buoy.id}</h4>
                                <p>📍 {buoy.region}</p>
                                <p>Status: <span className={`status-${buoy.status}`}>{buoy.status}</span></p>
                                {buoy.wave_height && <p>Wave: {buoy.wave_height.toFixed(1)}m</p>}
                                <p>Quality: {(buoy.quality_score * 100).toFixed(0)}%</p>
                            </div>
                        </Popup>
                    </Marker>
                ))}

                {selectedBuoy && (
                    <Circle
                        center={[selectedBuoy.latitude, selectedBuoy.longitude]}
                        radius={50000}
                        pathOptions={{
                            color: '#06b6d4',
                            fillColor: '#06b6d4',
                            fillOpacity: 0.1,
                        }}
                    />
                )}
            </MapContainer>

            <div className="map-legend">
                <span className="legend-item"><span className="dot excellent"></span> Excellent</span>
                <span className="legend-item"><span className="dot good"></span> Good</span>
                <span className="legend-item"><span className="dot degraded"></span> Degraded</span>
                <span className="legend-item"><span className="dot offline"></span> Offline</span>
            </div>
        </div>
    );
};

// Wave Visualization Component
const WaveVisualization: React.FC<{
    waveHeight: number;
    wavePeriod: number;
}> = ({ waveHeight, wavePeriod }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationId: number;
        let time = 0;

        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw multiple wave layers
            const layers = [
                { amplitude: (waveHeight || 1) * 12, frequency: 2 / (wavePeriod || 8), phase: time, color: 'rgba(6, 182, 212, 0.3)' },
                { amplitude: (waveHeight || 1) * 10, frequency: 1.5 / (wavePeriod || 8), phase: time * 0.8, color: 'rgba(34, 211, 238, 0.4)' },
                { amplitude: (waveHeight || 1) * 8, frequency: 1 / (wavePeriod || 8), phase: time * 0.6, color: 'rgba(103, 232, 249, 0.5)' },
            ];

            layers.forEach((layer) => {
                ctx.beginPath();
                ctx.moveTo(0, canvas.height / 2);

                for (let x = 0; x < canvas.width; x++) {
                    const y =
                        canvas.height / 2 +
                        Math.sin(x * 0.02 * layer.frequency + layer.phase) * layer.amplitude;
                    ctx.lineTo(x, y);
                }

                ctx.lineTo(canvas.width, canvas.height);
                ctx.lineTo(0, canvas.height);
                ctx.closePath();

                ctx.fillStyle = layer.color;
                ctx.fill();
            });

            time += 0.05;
            animationId = requestAnimationFrame(animate);
        };

        animate();

        return () => cancelAnimationFrame(animationId);
    }, [waveHeight, wavePeriod]);

    return (
        <canvas
            ref={canvasRef}
            width={600}
            height={200}
            className="wave-canvas"
        />
    );
};

// Data Card Component
const DataCard: React.FC<{
    label: string;
    value: string;
    icon: string;
}> = ({ label, value, icon }) => {
    return (
        <div className="data-card">
            <div className="data-card-icon">{icon}</div>
            <div className="data-card-content">
                <span className="data-card-label">{label}</span>
                <span className="data-card-value">{value}</span>
            </div>
        </div>
    );
};

// Main Dashboard Component
export const OceanWaveDashboard: React.FC = () => {
    const [buoys, setBuoys] = useState<BuoyData[]>([]);
    const [selectedBuoy, setSelectedBuoy] = useState<BuoyData | null>(null);
    const [liveWaveData, setLiveWaveData] = useState<WaveData | null>(null);
    const [certificates, setCertificates] = useState<Certificate[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generatedPassword, setGeneratedPassword] = useState<GeneratedPassword | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    // Fetch buoy status
    const fetchBuoyStatus = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE}/buoys/`);
            const buoysData = response.data.buoys || [];
            setBuoys(buoysData);

            // Auto-select first buoy if none selected
            if (!selectedBuoy && buoysData.length > 0) {
                setSelectedBuoy(buoysData[0]);
            }
        } catch (err) {
            console.error('Failed to fetch buoy status:', err);
            setError('Failed to load buoy data');
        } finally {
            setLoading(false);
        }
    }, [selectedBuoy]);

    // Fetch live wave data for selected buoy
    const fetchLiveWaveData = useCallback(async (buoyId: string) => {
        try {
            const response = await axios.get(`${API_BASE}/buoy/${buoyId}/live-data/`);
            setLiveWaveData(response.data);
        } catch (err) {
            console.error('Failed to fetch live wave data:', err);
        }
    }, []);

    // Generate hybrid password
    const generatePassword = async () => {
        setIsGenerating(true);
        setError(null);

        try {
            const response = await axios.post(`${API_BASE}/generate-hybrid-password/`, {
                length: 16,
                include_uppercase: true,
                include_lowercase: true,
                include_numbers: true,
                include_symbols: true,
                include_genetic: false,
            });

            setGeneratedPassword(response.data);

        } catch (err: any) {
            console.error('Failed to generate password:', err);
            setError(err.response?.data?.message || 'Failed to generate password');
        } finally {
            setIsGenerating(false);
        }
    };

    // Initial load
    useEffect(() => {
        fetchBuoyStatus();
        const interval = setInterval(fetchBuoyStatus, 60000);
        return () => clearInterval(interval);
    }, [fetchBuoyStatus]);

    // Fetch live data when buoy selected
    useEffect(() => {
        if (selectedBuoy) {
            fetchLiveWaveData(selectedBuoy.id);
            const interval = setInterval(() => fetchLiveWaveData(selectedBuoy.id), 30000);
            return () => clearInterval(interval);
        }
    }, [selectedBuoy, fetchLiveWaveData]);

    if (loading) {
        return (
            <div className="ocean-dashboard-ts loading">
                <div className="loading-spinner">
                    <span className="wave-icon">🌊</span>
                    <p>Connecting to ocean entropy sources...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="ocean-dashboard-ts">
            {/* Header */}
            <motion.header
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="dashboard-header"
            >
                <div className="header-content">
                    <h1>
                        <span className="wave-emoji">🌊</span>
                        Ocean Wave Entropy
                    </h1>
                    <p className="tagline">Passwords forged from the chaos of the ocean</p>
                </div>
            </motion.header>

            {/* Error Banner */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="error-banner"
                    >
                        ⚠️ {error}
                        <button onClick={() => setError(null)}>×</button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Buoy Map Section */}
            <motion.section
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="card map-card"
            >
                <h2>🗺️ Buoy Network Map</h2>
                <BuoyMap
                    buoys={buoys}
                    selectedBuoy={selectedBuoy}
                    onSelectBuoy={setSelectedBuoy}
                />
            </motion.section>

            {/* Main Grid */}
            <div className="main-grid">
                {/* Buoy List */}
                <motion.section
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="card buoy-list-card"
                >
                    <h2>📍 Buoy Network</h2>

                    <div className="buoy-list">
                        {buoys.map((buoy) => (
                            <button
                                key={buoy.id}
                                onClick={() => setSelectedBuoy(buoy)}
                                className={`buoy-item ${selectedBuoy?.id === buoy.id ? 'selected' : ''}`}
                            >
                                <div className="buoy-info">
                                    <span className="buoy-name">{buoy.name || buoy.id}</span>
                                    <span className="buoy-region">{buoy.region}</span>
                                </div>
                                <div className="buoy-coords">
                                    {buoy.latitude?.toFixed(2)}°, {buoy.longitude?.toFixed(2)}°
                                </div>
                            </button>
                        ))}
                    </div>
                </motion.section>

                {/* Wave Visualization */}
                <motion.section
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="card wave-viz-card"
                >
                    <h2>🌊 Live Wave Data</h2>

                    {liveWaveData ? (
                        <>
                            <WaveVisualization
                                waveHeight={liveWaveData.wave_data.height || 1}
                                wavePeriod={liveWaveData.wave_data.period || 8}
                            />

                            <div className="wave-data-grid">
                                <DataCard
                                    label="Wave Height"
                                    value={`${liveWaveData.wave_data.height?.toFixed(1) || 'N/A'} m`}
                                    icon="📏"
                                />
                                <DataCard
                                    label="Wave Period"
                                    value={`${liveWaveData.wave_data.period?.toFixed(1) || 'N/A'} s`}
                                    icon="⏱️"
                                />
                                <DataCard
                                    label="Water Temp"
                                    value={`${liveWaveData.weather_data.water_temp?.toFixed(1) || 'N/A'}°C`}
                                    icon="🌡️"
                                />
                                <DataCard
                                    label="Wind Speed"
                                    value={`${liveWaveData.weather_data.wind_speed?.toFixed(1) || 'N/A'} m/s`}
                                    icon="💨"
                                />
                            </div>

                            <div className="quality-bar">
                                <span>Entropy Quality</span>
                                <div className="quality-track">
                                    <motion.div
                                        className="quality-fill"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${(liveWaveData.quality_score || 0) * 100}%` }}
                                        transition={{ duration: 1 }}
                                    />
                                </div>
                                <span className="quality-value">
                                    {((liveWaveData.quality_score || 0) * 100).toFixed(0)}%
                                </span>
                            </div>
                        </>
                    ) : (
                        <div className="no-data">
                            Select a buoy to view live wave data
                        </div>
                    )}
                </motion.section>

                {/* Password Generator */}
                <motion.section
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="card generator-card"
                >
                    <h2>🔐 Generate Ocean-Powered Password</h2>

                    <div className="generator-controls">
                        <button
                            onClick={generatePassword}
                            disabled={isGenerating}
                            className="generate-btn"
                        >
                            {isGenerating ? (
                                <>
                                    <span className="spinner" />
                                    Harvesting Ocean Entropy...
                                </>
                            ) : (
                                <>🌊 Generate Hybrid Password</>
                            )}
                        </button>
                    </div>

                    <AnimatePresence>
                        {generatedPassword && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                className="generated-result"
                            >
                                <div className="password-display">
                                    <code>{generatedPassword.password}</code>
                                    <button
                                        onClick={() => navigator.clipboard.writeText(generatedPassword.password)}
                                        className="copy-btn"
                                        title="Copy to clipboard"
                                    >
                                        📋
                                    </button>
                                </div>

                                <div className="password-meta">
                                    <span>
                                        Sources: {generatedPassword.sources.join(' + ')}
                                    </span>
                                    <span>
                                        Entropy: {generatedPassword.entropy_bits.toFixed(0)} bits
                                    </span>
                                    <span>
                                        Quality: {generatedPassword.quality_assessment.quality}
                                    </span>
                                </div>

                                <div className="algorithm-info">
                                    🔀 {generatedPassword.mixing_algorithm}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.section>

                {/* Recent Certificates */}
                {certificates.length > 0 && (
                    <motion.section
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="card certificates-card"
                    >
                        <h2>📜 Recent Certificates</h2>

                        <div className="certificates-list">
                            {certificates.slice(0, 5).map((cert) => (
                                <div key={cert.certificate_id} className="certificate-item">
                                    <div className="cert-header">
                                        <span className="cert-id">{cert.certificate_id.slice(0, 8)}...</span>
                                        <span className="cert-time">
                                            {new Date(cert.generation_timestamp).toLocaleString()}
                                        </span>
                                    </div>

                                    <div className="cert-sources">
                                        {cert.sources_used.map((source) => (
                                            <span key={source} className="source-tag">
                                                {source}
                                            </span>
                                        ))}
                                    </div>

                                    {cert.ocean.buoy_id && (
                                        <div className="cert-ocean">
                                            Buoy: {cert.ocean.buoy_id} • Wave: {cert.ocean.wave_height?.toFixed(1)}m
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </motion.section>
                )}
            </div>

            {/* Footer */}
            <footer className="dashboard-footer">
                <p>🌊 <em>Powered by the ocean's chaos</em></p>
                <p className="footer-note">
                    Data sourced from NOAA National Data Buoy Center
                </p>
            </footer>
        </div>
    );
};

export default OceanWaveDashboard;
