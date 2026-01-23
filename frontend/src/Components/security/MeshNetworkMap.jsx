/**
 * Mesh Network Map Component
 * ============================
 * 
 * Interactive map visualization showing:
 * - Current dead drop locations
 * - Nearby mesh nodes
 * - Fragment distribution status
 * - Collection radius visualization
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './MeshNetworkMap.css';

const API_BASE = '/api/mesh';

const MeshNetworkMap = ({
    deadDrop = null,
    showNodes = true,
    onNodeClick = null,
    onLocationSelect = null,
    interactive = true,
    height = '400px'
}) => {
    const mapRef = useRef(null);
    const [map, setMap] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [userLocation, setUserLocation] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedNode, setSelectedNode] = useState(null);

    // Initialize map
    useEffect(() => {
        if (!mapRef.current) return;

        // Simple canvas-based map (or integrate with Leaflet/Mapbox)
        const canvas = mapRef.current;
        const ctx = canvas.getContext('2d');

        // Set canvas size
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;

        setMap({ canvas, ctx, width: rect.width, height: rect.height });
        setLoading(false);
    }, []);

    // Fetch nearby nodes
    useEffect(() => {
        if (!showNodes || !userLocation) return;

        const fetchNodes = async () => {
            try {
                const response = await fetch(
                    `${API_BASE}/nodes/nearby/?lat=${userLocation.lat}&lon=${userLocation.lng}&radius=10`,
                    {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('token')}`
                        }
                    }
                );
                const data = await response.json();
                setNodes(data.nodes || []);
            } catch (error) {
                console.error('Failed to fetch nodes:', error);
            }
        };

        fetchNodes();
    }, [showNodes, userLocation]);

    // Get user location
    useEffect(() => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setUserLocation({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    });
                },
                (error) => console.error('Geolocation error:', error)
            );
        }
    }, []);

    // Draw map
    useEffect(() => {
        if (!map) return;

        const { ctx, width, height } = map;

        // Clear canvas
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, width, height);

        // Draw grid
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        const gridSize = 40;
        for (let x = 0; x < width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (let y = 0; y < height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        // Draw dead drop location and radius
        if (deadDrop) {
            const centerX = width / 2;
            const centerY = height / 2;
            const radiusPx = (deadDrop.radius_meters / 1000) * 100; // Scale factor

            // Draw radius circle
            ctx.beginPath();
            ctx.arc(centerX, centerY, radiusPx, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 230, 118, 0.1)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(0, 230, 118, 0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw center marker
            ctx.beginPath();
            ctx.arc(centerX, centerY, 8, 0, Math.PI * 2);
            ctx.fillStyle = '#00e676';
            ctx.fill();

            // Draw pulsing animation
            ctx.beginPath();
            ctx.arc(centerX, centerY, 20, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(0, 230, 118, 0.3)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Draw mesh nodes
        nodes.forEach((node, i) => {
            const angle = (i / nodes.length) * Math.PI * 2;
            const distance = 80 + Math.random() * 60;
            const x = width / 2 + Math.cos(angle) * distance;
            const y = height / 2 + Math.sin(angle) * distance;

            // Node circle
            ctx.beginPath();
            ctx.arc(x, y, 12, 0, Math.PI * 2);
            ctx.fillStyle = node.is_online ? 'rgba(33, 150, 243, 0.8)' : 'rgba(100, 100, 100, 0.5)';
            ctx.fill();

            // Connection line to center
            ctx.beginPath();
            ctx.moveTo(width / 2, height / 2);
            ctx.lineTo(x, y);
            ctx.strokeStyle = node.is_online ? 'rgba(33, 150, 243, 0.3)' : 'rgba(100, 100, 100, 0.2)';
            ctx.lineWidth = 1;
            ctx.setLineDash([5, 5]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Store node position for click detection
            node._mapX = x;
            node._mapY = y;
        });

        // Draw user location
        if (userLocation) {
            const userX = width / 2 + 30;
            const userY = height / 2 - 30;

            ctx.beginPath();
            ctx.arc(userX, userY, 10, 0, Math.PI * 2);
            ctx.fillStyle = '#ff5722';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

    }, [map, nodes, deadDrop, userLocation]);

    // Handle map clicks
    const handleMapClick = useCallback((e) => {
        if (!interactive || !mapRef.current) return;

        const rect = mapRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Check if clicked on a node
        for (const node of nodes) {
            if (node._mapX && node._mapY) {
                const dist = Math.sqrt((x - node._mapX) ** 2 + (y - node._mapY) ** 2);
                if (dist < 15) {
                    setSelectedNode(node);
                    if (onNodeClick) onNodeClick(node);
                    return;
                }
            }
        }

        // If not on a node and location selection enabled
        if (onLocationSelect) {
            // Convert click to lat/lng (simplified)
            const centerLat = deadDrop?.latitude || userLocation?.lat || 0;
            const centerLng = deadDrop?.longitude || userLocation?.lng || 0;
            const lat = centerLat + (mapRef.current.height / 2 - y) * 0.00001;
            const lng = centerLng + (x - mapRef.current.width / 2) * 0.00001;
            onLocationSelect({ lat, lng });
        }

        setSelectedNode(null);
    }, [interactive, nodes, deadDrop, userLocation, onNodeClick, onLocationSelect]);

    return (
        <div className="mesh-network-map" style={{ height }}>
            {loading && (
                <div className="map-loading">
                    <div className="spinner" />
                    <p>Loading map...</p>
                </div>
            )}

            <canvas
                ref={mapRef}
                className="map-canvas"
                onClick={handleMapClick}
            />

            {/* Legend */}
            <div className="map-legend">
                <div className="legend-item">
                    <span className="legend-dot" style={{ backgroundColor: '#00e676' }} />
                    <span>Dead Drop</span>
                </div>
                <div className="legend-item">
                    <span className="legend-dot" style={{ backgroundColor: '#2196f3' }} />
                    <span>Mesh Node</span>
                </div>
                <div className="legend-item">
                    <span className="legend-dot" style={{ backgroundColor: '#ff5722' }} />
                    <span>You</span>
                </div>
            </div>

            {/* Node info popup */}
            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        className="node-popup"
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                    >
                        <div className="popup-header">
                            <span className={`status-dot ${selectedNode.is_online ? 'online' : 'offline'}`} />
                            <h4>{selectedNode.device_name}</h4>
                        </div>
                        <div className="popup-info">
                            <p>Type: {selectedNode.device_type}</p>
                            <p>Trust: {Math.round(selectedNode.trust_score * 100)}%</p>
                            <p>Fragments: {selectedNode.current_fragment_count}/{selectedNode.max_fragments}</p>
                        </div>
                        <button
                            className="popup-close"
                            onClick={() => setSelectedNode(null)}
                        >
                            ×
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Stats overlay */}
            <div className="map-stats">
                <div className="stat">
                    <span className="stat-value">{nodes.filter(n => n.is_online).length}</span>
                    <span className="stat-label">Nodes Online</span>
                </div>
                {deadDrop && (
                    <div className="stat">
                        <span className="stat-value">{deadDrop.radius_meters}m</span>
                        <span className="stat-label">Radius</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MeshNetworkMap;
