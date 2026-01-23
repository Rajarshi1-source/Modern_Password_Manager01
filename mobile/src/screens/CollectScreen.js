/**
 * Collect Screen - Mobile
 * ========================
 * 
 * GPS + BLE fragment collection screen for dead drops.
 * Guides user to location and collects fragments when verified.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ActivityIndicator,
    Alert,
    Vibration,
    Platform,
} from 'react-native';
import meshService from '../services/MeshService';

const CollectScreen = ({ route, navigation }) => {
    const { dropId } = route.params;
    
    const [step, setStep] = useState('loading'); // loading, location, scanning, collecting, success, error
    const [deadDrop, setDeadDrop] = useState(null);
    const [userLocation, setUserLocation] = useState(null);
    const [distance, setDistance] = useState(null);
    const [bleNodes, setBleNodes] = useState([]);
    const [progress, setProgress] = useState(0);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    // Fetch dead drop details
    useEffect(() => {
        const fetchDetails = async () => {
            try {
                const data = await meshService.getDeadDropDetail(dropId);
                setDeadDrop(data);
                setStep('location');
            } catch (err) {
                setError('Failed to load dead drop details');
                setStep('error');
            }
        };
        fetchDetails();
    }, [dropId]);

    // Watch user location
    useEffect(() => {
        let watchId;

        const startWatching = async () => {
            try {
                const location = await meshService.getCurrentLocation();
                updateDistance(location);

                // In React Native, you'd use watchPosition
                // Simulating with interval for this example
                watchId = setInterval(async () => {
                    try {
                        const loc = await meshService.getCurrentLocation();
                        updateDistance(loc);
                    } catch (e) {
                        console.log('Location update failed');
                    }
                }, 5000);
            } catch (err) {
                console.error('Location error:', err);
            }
        };

        if (step === 'location') {
            startWatching();
        }

        return () => {
            if (watchId) clearInterval(watchId);
        };
    }, [step, deadDrop]);

    // Calculate distance
    const updateDistance = (location) => {
        if (!deadDrop) return;
        
        setUserLocation(location);
        
        const dist = calculateDistance(
            location.latitude,
            location.longitude,
            parseFloat(deadDrop.latitude),
            parseFloat(deadDrop.longitude)
        );
        setDistance(Math.round(dist));
    };

    // Haversine distance
    const calculateDistance = (lat1, lon1, lat2, lon2) => {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    };

    // Start BLE scan
    const startBLEScan = async () => {
        setStep('scanning');
        setBleNodes([]);
        
        try {
            const nodes = await meshService.startScanningForNodes(
                (node) => {
                    setBleNodes(prev => [...prev, node]);
                    Vibration.vibrate(50);
                },
                8000
            );

            if (nodes.length === 0) {
                setError('No mesh nodes found nearby');
                setStep('error');
            } else {
                setStep('collecting');
            }
        } catch (err) {
            setError(err.message);
            setStep('error');
        }
    };

    // Collect fragments
    const collectFragments = async () => {
        setProgress(0);
        
        try {
            // Update progress
            const interval = setInterval(() => {
                setProgress(p => Math.min(p + 10, 90));
            }, 300);

            const result = await meshService.attemptCollection(
                dropId,
                (status) => console.log('Collection status:', status)
            );

            clearInterval(interval);

            if (result.secret) {
                setProgress(100);
                setResult(result);
                setStep('success');
                Vibration.vibrate([0, 100, 100, 100]);
            } else {
                setError(result.error || 'Collection failed');
                setStep('error');
            }
        } catch (err) {
            setError(err.message);
            setStep('error');
        }
    };

    // Check if in range
    const inRange = distance !== null && deadDrop && distance <= deadDrop.radius_meters;

    // Render based on step
    const renderContent = () => {
        switch (step) {
            case 'loading':
                return (
                    <View style={styles.centerContent}>
                        <ActivityIndicator size="large" color="#00e676" />
                        <Text style={styles.loadingText}>Loading dead drop...</Text>
                    </View>
                );

            case 'location':
                return (
                    <View style={styles.stepContent}>
                        <View style={styles.compass}>
                            <View style={styles.compassRing}>
                                <View style={styles.compassInner}>
                                    <Text style={styles.distanceValue}>
                                        {distance !== null 
                                            ? (distance > 1000 ? `${(distance/1000).toFixed(1)}km` : `${distance}m`)
                                            : '...'
                                        }
                                    </Text>
                                    <Text style={styles.distanceLabel}>to target</Text>
                                </View>
                            </View>
                        </View>

                        {deadDrop?.location_hint && (
                            <View style={styles.hintCard}>
                                <Text style={styles.hintIcon}>💡</Text>
                                <Text style={styles.hintText}>{deadDrop.location_hint}</Text>
                            </View>
                        )}

                        <View style={[styles.rangeStatus, inRange ? styles.inRange : styles.outOfRange]}>
                            <Text style={styles.rangeIcon}>{inRange ? '✓' : '↗'}</Text>
                            <Text style={styles.rangeText}>
                                {inRange ? 'You are within range' : 'Move closer to the target'}
                            </Text>
                        </View>

                        <TouchableOpacity
                            style={[styles.actionBtn, !inRange && styles.actionBtnDisabled]}
                            onPress={startBLEScan}
                            disabled={!inRange}
                        >
                            <Text style={styles.actionBtnText}>
                                {inRange ? '📶 Scan for Mesh Nodes' : 'Get Closer to Collect'}
                            </Text>
                        </TouchableOpacity>
                    </View>
                );

            case 'scanning':
                return (
                    <View style={styles.stepContent}>
                        <View style={styles.radarContainer}>
                            <View style={styles.radar}>
                                <View style={styles.radarSweep} />
                                {bleNodes.map((node, i) => (
                                    <View
                                        key={node.id}
                                        style={[
                                            styles.radarDot,
                                            { left: `${30 + i * 20}%`, top: `${40 + (i % 2) * 20}%` }
                                        ]}
                                    />
                                ))}
                            </View>
                        </View>

                        <Text style={styles.stepTitle}>Scanning for Nodes...</Text>
                        <Text style={styles.stepSubtitle}>Found {bleNodes.length} node(s)</Text>

                        {bleNodes.map(node => (
                            <View key={node.id} style={styles.nodeItem}>
                                <Text style={styles.nodeName}>{node.name}</Text>
                                <Text style={styles.nodeRssi}>{node.rssi}dBm</Text>
                            </View>
                        ))}
                    </View>
                );

            case 'collecting':
                return (
                    <View style={styles.stepContent}>
                        <View style={styles.progressCircle}>
                            <Text style={styles.progressText}>{progress}%</Text>
                        </View>

                        <Text style={styles.stepTitle}>Ready to Collect</Text>
                        <Text style={styles.stepSubtitle}>
                            Found {bleNodes.length} nodes. Need {deadDrop?.required_fragments || 3} fragments.
                        </Text>

                        <TouchableOpacity
                            style={styles.collectBtn}
                            onPress={collectFragments}
                            disabled={progress > 0 && progress < 100}
                        >
                            <Text style={styles.collectBtnText}>
                                {progress > 0 ? 'Collecting...' : '🔓 Collect & Reconstruct'}
                            </Text>
                        </TouchableOpacity>
                    </View>
                );

            case 'success':
                return (
                    <View style={styles.stepContent}>
                        <View style={styles.successIcon}>
                            <Text style={styles.successEmoji}>🎉</Text>
                        </View>

                        <Text style={styles.successTitle}>Secret Recovered!</Text>
                        <Text style={styles.successSubtitle}>
                            Collected {result?.fragments_collected} fragments
                        </Text>

                        <View style={styles.secretBox}>
                            <Text style={styles.secretLabel}>Your Secret:</Text>
                            <Text style={styles.secretValue}>{result?.secret}</Text>
                        </View>

                        <TouchableOpacity
                            style={styles.copyBtn}
                            onPress={() => {
                                // Copy to clipboard
                                Alert.alert('Copied', 'Secret copied to clipboard');
                            }}
                        >
                            <Text style={styles.copyBtnText}>📋 Copy to Clipboard</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.doneBtn}
                            onPress={() => navigation.goBack()}
                        >
                            <Text style={styles.doneBtnText}>Done</Text>
                        </TouchableOpacity>
                    </View>
                );

            case 'error':
                return (
                    <View style={styles.stepContent}>
                        <View style={styles.errorIcon}>
                            <Text style={styles.errorEmoji}>❌</Text>
                        </View>

                        <Text style={styles.errorTitle}>Collection Failed</Text>
                        <Text style={styles.errorMessage}>{error}</Text>

                        <TouchableOpacity
                            style={styles.retryBtn}
                            onPress={() => {
                                setStep('location');
                                setError(null);
                                setProgress(0);
                            }}
                        >
                            <Text style={styles.retryBtnText}>Try Again</Text>
                        </TouchableOpacity>
                    </View>
                );

            default:
                return null;
        }
    };

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()}>
                    <Text style={styles.backBtn}>← Back</Text>
                </TouchableOpacity>
                <Text style={styles.headerTitle}>📥 Collect Fragments</Text>
            </View>

            {renderContent()}
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#1a1a2e',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 20,
        paddingTop: 50,
        paddingBottom: 20,
        gap: 16,
    },
    backBtn: {
        color: '#a0a0a0',
        fontSize: 16,
    },
    headerTitle: {
        color: '#fff',
        fontSize: 20,
        fontWeight: 'bold',
    },
    centerContent: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    loadingText: {
        color: '#808080',
        marginTop: 16,
    },
    stepContent: {
        flex: 1,
        padding: 20,
        alignItems: 'center',
    },
    compass: {
        width: 200,
        height: 200,
        marginBottom: 24,
    },
    compassRing: {
        width: '100%',
        height: '100%',
        borderWidth: 3,
        borderColor: 'rgba(0, 230, 118, 0.3)',
        borderRadius: 100,
        alignItems: 'center',
        justifyContent: 'center',
    },
    compassInner: {
        alignItems: 'center',
    },
    distanceValue: {
        fontSize: 40,
        fontWeight: 'bold',
        color: '#fff',
    },
    distanceLabel: {
        color: '#808080',
        fontSize: 14,
    },
    hintCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
        padding: 16,
        backgroundColor: 'rgba(255, 193, 7, 0.1)',
        borderWidth: 1,
        borderColor: 'rgba(255, 193, 7, 0.2)',
        borderRadius: 12,
        marginBottom: 16,
        width: '100%',
    },
    hintIcon: {
        fontSize: 24,
    },
    hintText: {
        flex: 1,
        color: '#ffc107',
        fontSize: 14,
    },
    rangeStatus: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
        paddingHorizontal: 20,
        paddingVertical: 14,
        borderRadius: 25,
        marginBottom: 24,
    },
    inRange: {
        backgroundColor: 'rgba(0, 230, 118, 0.15)',
    },
    outOfRange: {
        backgroundColor: 'rgba(255, 152, 0, 0.15)',
    },
    rangeIcon: {
        fontSize: 18,
    },
    rangeText: {
        fontSize: 14,
        color: '#e0e0e0',
    },
    actionBtn: {
        width: '100%',
        padding: 16,
        backgroundColor: '#00e676',
        borderRadius: 12,
        alignItems: 'center',
    },
    actionBtnDisabled: {
        backgroundColor: 'rgba(0, 230, 118, 0.3)',
    },
    actionBtnText: {
        color: '#000',
        fontSize: 16,
        fontWeight: '600',
    },
    radarContainer: {
        width: 200,
        height: 200,
        marginBottom: 24,
    },
    radar: {
        width: '100%',
        height: '100%',
        borderRadius: 100,
        borderWidth: 2,
        borderColor: 'rgba(0, 230, 118, 0.3)',
        backgroundColor: 'rgba(0, 230, 118, 0.05)',
    },
    radarSweep: {
        position: 'absolute',
        width: '100%',
        height: '100%',
    },
    radarDot: {
        position: 'absolute',
        width: 12,
        height: 12,
        backgroundColor: '#00e676',
        borderRadius: 6,
    },
    stepTitle: {
        fontSize: 20,
        fontWeight: '600',
        color: '#fff',
        marginBottom: 8,
    },
    stepSubtitle: {
        color: '#a0a0a0',
        marginBottom: 16,
    },
    nodeItem: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        width: '100%',
        padding: 12,
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        borderRadius: 8,
        marginBottom: 8,
    },
    nodeName: {
        color: '#e0e0e0',
    },
    nodeRssi: {
        color: '#00e676',
        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    },
    progressCircle: {
        width: 150,
        height: 150,
        borderRadius: 75,
        borderWidth: 8,
        borderColor: '#00e676',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 24,
    },
    progressText: {
        fontSize: 36,
        fontWeight: 'bold',
        color: '#00e676',
    },
    collectBtn: {
        width: '100%',
        padding: 18,
        backgroundColor: '#00e676',
        borderRadius: 12,
        alignItems: 'center',
        marginTop: 24,
    },
    collectBtnText: {
        color: '#000',
        fontSize: 17,
        fontWeight: '600',
    },
    successIcon: {
        width: 100,
        height: 100,
        backgroundColor: 'rgba(0, 230, 118, 0.2)',
        borderRadius: 50,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
    },
    successEmoji: {
        fontSize: 50,
    },
    successTitle: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#00e676',
        marginBottom: 8,
    },
    successSubtitle: {
        color: '#a0a0a0',
        marginBottom: 24,
    },
    secretBox: {
        width: '100%',
        padding: 16,
        backgroundColor: 'rgba(0, 230, 118, 0.1)',
        borderWidth: 1,
        borderColor: 'rgba(0, 230, 118, 0.3)',
        borderRadius: 12,
        marginBottom: 16,
    },
    secretLabel: {
        color: '#808080',
        fontSize: 12,
        marginBottom: 8,
    },
    secretValue: {
        color: '#00e676',
        fontSize: 16,
        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    },
    copyBtn: {
        padding: 12,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
        marginBottom: 12,
    },
    copyBtnText: {
        color: '#e0e0e0',
    },
    doneBtn: {
        padding: 14,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
        width: '100%',
        alignItems: 'center',
    },
    doneBtnText: {
        color: '#e0e0e0',
        fontWeight: '600',
    },
    errorIcon: {
        width: 100,
        height: 100,
        backgroundColor: 'rgba(244, 67, 54, 0.2)',
        borderRadius: 50,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
    },
    errorEmoji: {
        fontSize: 50,
    },
    errorTitle: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#f44336',
        marginBottom: 8,
    },
    errorMessage: {
        color: '#f44336',
        textAlign: 'center',
        marginBottom: 24,
    },
    retryBtn: {
        padding: 14,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
    },
    retryBtnText: {
        color: '#e0e0e0',
        fontWeight: '600',
    },
});

export default CollectScreen;
