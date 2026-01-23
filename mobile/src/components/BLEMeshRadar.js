/**
 * BLE Mesh Radar Component - Mobile
 * ===================================
 * 
 * Visual radar display for nearby mesh nodes.
 * Shows real-time BLE scanning with animated visualization.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Animated,
    Easing,
    Dimensions,
} from 'react-native';
import meshService from '../services/MeshService';

const { width } = Dimensions.get('window');
const RADAR_SIZE = Math.min(width - 80, 300);

const BLEMeshRadar = ({ 
    isScanning = false,
    nodes = [],
    onNodePress,
    showLabels = true 
}) => {
    const sweepAnim = useRef(new Animated.Value(0)).current;
    const pulseAnim = useRef(new Animated.Value(0)).current;

    // Sweep animation
    useEffect(() => {
        if (isScanning) {
            const sweep = Animated.loop(
                Animated.timing(sweepAnim, {
                    toValue: 1,
                    duration: 2000,
                    easing: Easing.linear,
                    useNativeDriver: true,
                })
            );
            sweep.start();
            return () => sweep.stop();
        } else {
            sweepAnim.setValue(0);
        }
    }, [isScanning, sweepAnim]);

    // Pulse animation for center
    useEffect(() => {
        const pulse = Animated.loop(
            Animated.sequence([
                Animated.timing(pulseAnim, {
                    toValue: 1,
                    duration: 1500,
                    easing: Easing.out(Easing.ease),
                    useNativeDriver: true,
                }),
                Animated.timing(pulseAnim, {
                    toValue: 0,
                    duration: 0,
                    useNativeDriver: true,
                }),
            ])
        );
        pulse.start();
        return () => pulse.stop();
    }, [pulseAnim]);

    // Calculate node position based on RSSI
    const getNodePosition = (node, index, total) => {
        // Distribute nodes around the radar
        const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
        
        // Distance based on RSSI (closer = stronger signal)
        const maxRssi = -30;
        const minRssi = -100;
        const normalizedRssi = Math.max(0, Math.min(1, (node.rssi - minRssi) / (maxRssi - minRssi)));
        const distancePercent = 0.2 + (1 - normalizedRssi) * 0.6; // 20% to 80% from center
        
        const radius = (RADAR_SIZE / 2) * distancePercent;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        
        return { x, y, angle, distancePercent };
    };

    // Get signal color based on RSSI
    const getSignalColor = (rssi) => {
        if (rssi >= -50) return '#00e676';
        if (rssi >= -65) return '#8bc34a';
        if (rssi >= -80) return '#ffc107';
        return '#f44336';
    };

    const sweepRotation = sweepAnim.interpolate({
        inputRange: [0, 1],
        outputRange: ['0deg', '360deg'],
    });

    const pulseScale = pulseAnim.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 2],
    });

    const pulseOpacity = pulseAnim.interpolate({
        inputRange: [0, 1],
        outputRange: [0.5, 0],
    });

    return (
        <View style={styles.container}>
            <View style={[styles.radar, { width: RADAR_SIZE, height: RADAR_SIZE }]}>
                {/* Radar rings */}
                <View style={[styles.ring, styles.ring1, { width: RADAR_SIZE * 0.33, height: RADAR_SIZE * 0.33 }]} />
                <View style={[styles.ring, styles.ring2, { width: RADAR_SIZE * 0.66, height: RADAR_SIZE * 0.66 }]} />
                <View style={[styles.ring, styles.ring3, { width: RADAR_SIZE, height: RADAR_SIZE }]} />

                {/* Cross lines */}
                <View style={styles.crossLine} />
                <View style={[styles.crossLine, styles.crossLineVertical]} />

                {/* Sweep animation */}
                {isScanning && (
                    <Animated.View
                        style={[
                            styles.sweep,
                            {
                                width: RADAR_SIZE,
                                height: RADAR_SIZE,
                                transform: [{ rotate: sweepRotation }],
                            },
                        ]}
                    />
                )}

                {/* Center dot with pulse */}
                <View style={styles.centerContainer}>
                    <Animated.View
                        style={[
                            styles.centerPulse,
                            {
                                transform: [{ scale: pulseScale }],
                                opacity: pulseOpacity,
                            },
                        ]}
                    />
                    <View style={styles.centerDot} />
                </View>

                {/* Node dots */}
                {nodes.map((node, index) => {
                    const position = getNodePosition(node, index, nodes.length);
                    const color = getSignalColor(node.rssi);
                    
                    return (
                        <Animated.View
                            key={node.id}
                            style={[
                                styles.nodeDot,
                                {
                                    backgroundColor: color,
                                    left: RADAR_SIZE / 2 + position.x - 8,
                                    top: RADAR_SIZE / 2 + position.y - 8,
                                    shadowColor: color,
                                },
                            ]}
                        >
                            {showLabels && (
                                <View style={styles.nodeLabel}>
                                    <Text style={styles.nodeLabelText} numberOfLines={1}>
                                        {node.name?.split('-')[1] || node.name}
                                    </Text>
                                </View>
                            )}
                        </Animated.View>
                    );
                })}
            </View>

            {/* Legend */}
            <View style={styles.legend}>
                <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: '#00e676' }]} />
                    <Text style={styles.legendText}>Excellent</Text>
                </View>
                <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: '#8bc34a' }]} />
                    <Text style={styles.legendText}>Good</Text>
                </View>
                <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: '#ffc107' }]} />
                    <Text style={styles.legendText}>Fair</Text>
                </View>
                <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: '#f44336' }]} />
                    <Text style={styles.legendText}>Weak</Text>
                </View>
            </View>

            {/* Status */}
            <View style={styles.statusBar}>
                <Text style={styles.statusText}>
                    {isScanning ? 'Scanning...' : `${nodes.length} node${nodes.length !== 1 ? 's' : ''} found`}
                </Text>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        alignItems: 'center',
        padding: 16,
    },
    radar: {
        position: 'relative',
        alignItems: 'center',
        justifyContent: 'center',
    },
    ring: {
        position: 'absolute',
        borderWidth: 1,
        borderColor: 'rgba(0, 230, 118, 0.2)',
        borderRadius: 1000,
    },
    ring1: {},
    ring2: {},
    ring3: {},
    crossLine: {
        position: 'absolute',
        width: '100%',
        height: 1,
        backgroundColor: 'rgba(0, 230, 118, 0.1)',
    },
    crossLineVertical: {
        width: 1,
        height: '100%',
    },
    sweep: {
        position: 'absolute',
        backgroundColor: 'transparent',
        borderRadius: 1000,
        overflow: 'hidden',
    },
    centerContainer: {
        position: 'absolute',
        alignItems: 'center',
        justifyContent: 'center',
    },
    centerPulse: {
        position: 'absolute',
        width: 20,
        height: 20,
        backgroundColor: 'rgba(0, 230, 118, 0.3)',
        borderRadius: 10,
    },
    centerDot: {
        width: 12,
        height: 12,
        backgroundColor: '#00e676',
        borderRadius: 6,
        borderWidth: 2,
        borderColor: '#1a1a2e',
    },
    nodeDot: {
        position: 'absolute',
        width: 16,
        height: 16,
        borderRadius: 8,
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 0.8,
        shadowRadius: 8,
        elevation: 5,
    },
    nodeLabel: {
        position: 'absolute',
        top: -20,
        left: -20,
        width: 56,
        alignItems: 'center',
    },
    nodeLabelText: {
        color: '#a0a0a0',
        fontSize: 9,
        textAlign: 'center',
    },
    legend: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 16,
        marginTop: 24,
        marginBottom: 12,
    },
    legendItem: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    legendDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
    },
    legendText: {
        color: '#808080',
        fontSize: 11,
    },
    statusBar: {
        paddingVertical: 8,
        paddingHorizontal: 16,
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderRadius: 16,
    },
    statusText: {
        color: '#a0a0a0',
        fontSize: 13,
    },
});

export default BLEMeshRadar;
