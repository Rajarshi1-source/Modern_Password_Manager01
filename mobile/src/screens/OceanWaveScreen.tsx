/**
 * Ocean Wave Entropy Screen
 * ==========================
 * 
 * Mobile screen for ocean wave entropy visualization and password generation.
 * Features:
 * - Interactive map with NOAA buoy markers
 * - Live wave data visualization
 * - Hybrid password generation
 * - Certificate viewer
 * 
 * "Powered by the ocean's chaos" 🌊
 * 
 * @author Password Manager Team
 * @created 2026-01-25
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    ActivityIndicator,
    Animated,
    Dimensions,
    RefreshControl,
    Alert,
    Platform,
} from 'react-native';
// @ts-ignore - Install with: npx expo install expo-clipboard
import * as Clipboard from 'expo-clipboard';
// @ts-ignore - Install with: npx expo install react-native-maps
import MapView, { Marker, Circle, PROVIDER_GOOGLE } from 'react-native-maps';
// @ts-ignore - Install with: npx expo install expo-linear-gradient
import { LinearGradient } from 'expo-linear-gradient';
// @ts-ignore - Install with: npx expo install expo-blur
import { BlurView } from 'expo-blur';
// @ts-ignore - Install with: npx expo install react-native-svg
import Svg, { Path, Defs, LinearGradient as SvgGradient, Stop } from 'react-native-svg';
import oceanEntropyService from '../services/OceanEntropyService';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Types
interface BuoyData {
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    region: string;
    status: 'excellent' | 'good' | 'degraded' | 'offline';
    wave_height: number | null;
    wave_period: number | null;
    water_temp: number | null;
    wind_speed: number | null;
    quality_score: number;
    last_reading: string | null;
}

interface GeneratedPassword {
    password: string;
    sources: string[];
    entropy_bits: number;
    quality_score: number;
    ocean_details: {
        buoy_id: string;
        wave_height: number | null;
    };
    certificate_id: string;
}

interface HybridPasswordResult {
    success: boolean;
    password?: string;
    sources?: string[];
    entropyBits?: number;
    qualityScore?: number;
    oceanDetails?: {
        buoy_id?: string;
        wave_height?: number | null;
    };
    certificateId?: string;
    error?: string;
}

interface BuoyApiResponse {
    buoys: BuoyData[];
}

// Wave Animation Component
const WaveAnimation: React.FC<{ waveHeight: number; wavePeriod: number }> = ({
    waveHeight,
    wavePeriod,
}) => {
    const animatedValue = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        animatedValue.setValue(0);
        const animation = Animated.loop(
            Animated.timing(animatedValue, {
                toValue: 1,
                duration: (wavePeriod || 8) * 1000,
                useNativeDriver: true,
            })
        );
        animation.start();
        return () => animation.stop();
    }, [wavePeriod, animatedValue]);

    const translateX = animatedValue.interpolate({
        inputRange: [0, 1],
        outputRange: [0, -SCREEN_WIDTH],
    });

    const amplitude = Math.min((waveHeight || 1) * 15, 50);

    return (
        <View style={styles.waveContainer}>
            <Animated.View style={{ transform: [{ translateX }] }}>
                <Svg height={100} width={SCREEN_WIDTH * 2} viewBox={`0 0 ${SCREEN_WIDTH * 2} 100`}>
                    <Defs>
                        <SvgGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                            <Stop offset="0%" stopColor="#06b6d4" stopOpacity="0.8" />
                            <Stop offset="100%" stopColor="#0284c7" stopOpacity="0.3" />
                        </SvgGradient>
                    </Defs>
                    <Path
                        d={generateWavePath(SCREEN_WIDTH * 2, 100, amplitude, 3)}
                        fill="url(#waveGradient)"
                    />
                </Svg>
            </Animated.View>
        </View>
    );
};

// Generate SVG wave path
const generateWavePath = (
    width: number,
    height: number,
    amplitude: number,
    waves: number
): string => {
    const wavelength = width / waves;
    let path = `M0,${height / 2}`;

    for (let x = 0; x <= width; x += 10) {
        const y = height / 2 + Math.sin((x / wavelength) * Math.PI * 2) * amplitude;
        path += ` L${x},${y}`;
    }

    path += ` L${width},${height} L0,${height} Z`;
    return path;
};

// Buoy Marker Component
const BuoyMarker: React.FC<{
    buoy: BuoyData;
    isSelected: boolean;
    onPress: () => void;
}> = ({ buoy, isSelected, onPress }) => {
    const getStatusColor = () => {
        switch (buoy.status) {
            case 'excellent': return '#22c55e';
            case 'good': return '#3b82f6';
            case 'degraded': return '#f59e0b';
            case 'offline': return '#ef4444';
            default: return '#6b7280';
        }
    };

    return (
        <Marker
            coordinate={{ latitude: buoy.latitude, longitude: buoy.longitude }}
            onPress={onPress}
            anchor={{ x: 0.5, y: 0.5 }}
        >
            <View style={[styles.markerContainer, isSelected && styles.markerSelected]}>
                <View style={[styles.markerDot, { backgroundColor: getStatusColor() }]}>
                    <Text style={styles.markerEmoji}>🌊</Text>
                </View>
                {isSelected && (
                    <View style={styles.markerLabel}>
                        <Text style={styles.markerLabelText}>{buoy.name || buoy.id}</Text>
                    </View>
                )}
            </View>
        </Marker>
    );
};

// Data Card Component
const DataCard: React.FC<{
    icon: string;
    label: string;
    value: string;
    color?: string;
}> = ({ icon, label, value, color = '#06b6d4' }) => (
    <View style={styles.dataCard}>
        <Text style={styles.dataCardIcon}>{icon}</Text>
        <Text style={styles.dataCardLabel}>{label}</Text>
        <Text style={[styles.dataCardValue, { color }]}>{value}</Text>
    </View>
);

// Main Screen Component
const OceanWaveScreen: React.FC = () => {
    const [buoys, setBuoys] = useState<BuoyData[]>([]);
    const [selectedBuoy, setSelectedBuoy] = useState<BuoyData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generatedPassword, setGeneratedPassword] = useState<GeneratedPassword | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [stormStatus, setStormStatus] = useState<any>(null);

    const mapRef = useRef<MapView>(null);

    // Initial map region (Atlantic Ocean)
    const [region, setRegion] = useState({
        latitude: 35.0,
        longitude: -60.0,
        latitudeDelta: 40,
        longitudeDelta: 60,
    });

    // Fetch buoy data
    const fetchBuoys = useCallback(async () => {
        try {
            const response = await oceanEntropyService.getBuoys() as BuoyApiResponse;
            const buoyList = response.buoys || [];
            setBuoys(buoyList);

            if (buoyList.length > 0 && !selectedBuoy) {
                setSelectedBuoy(buoyList[0]);
            }

            setError(null);
        } catch (err) {
            console.error('Failed to fetch buoys:', err);
            setError('Failed to load buoy data');
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, [selectedBuoy]);

    useEffect(() => {
        fetchBuoys();
        const interval = setInterval(fetchBuoys, 60000); // Refresh every minute
        return () => clearInterval(interval);
    }, [fetchBuoys]);

    // Fetch storm status
    const fetchStormStatus = useCallback(async () => {
        try {
            const status = await oceanEntropyService.getStormStatus();
            setStormStatus(status);
        } catch (err) {
            console.error('Failed to fetch storm status:', err);
        }
    }, []);

    useEffect(() => {
        fetchStormStatus();
        const stormInterval = setInterval(fetchStormStatus, 60000);
        return () => clearInterval(stormInterval);
    }, [fetchStormStatus]);

    // Handle refresh
    const onRefresh = useCallback(() => {
        setIsRefreshing(true);
        fetchBuoys();
        fetchStormStatus();
    }, [fetchBuoys, fetchStormStatus]);

    // Select buoy and center map
    const handleSelectBuoy = useCallback((buoy: BuoyData) => {
        setSelectedBuoy(buoy);
        mapRef.current?.animateToRegion({
            latitude: buoy.latitude,
            longitude: buoy.longitude,
            latitudeDelta: 5,
            longitudeDelta: 5,
        }, 500);
    }, []);

    // Generate hybrid password
    const handleGeneratePassword = useCallback(async () => {
        setIsGenerating(true);
        setError(null);

        try {
            const result = await oceanEntropyService.generateHybridPassword({
                length: 16,
                includeUppercase: true,
                includeLowercase: true,
                includeNumbers: true,
                includeSymbols: true,
            }) as HybridPasswordResult;

            if (!result.success) {
                throw new Error(result.error || 'Generation failed');
            }

            setGeneratedPassword({
                password: result.password || '',
                sources: result.sources || [],
                entropy_bits: result.entropyBits || 0,
                quality_score: result.qualityScore || 0,
                ocean_details: {
                    buoy_id: result.oceanDetails?.buoy_id || '',
                    wave_height: result.oceanDetails?.wave_height ?? null,
                },
                certificate_id: result.certificateId || '',
            });
        } catch (err) {
            console.error('Password generation failed:', err);
            setError('Failed to generate password');
        } finally {
            setIsGenerating(false);
        }
    }, []);

    // Copy password to clipboard
    const handleCopyPassword = useCallback(async () => {
        if (generatedPassword?.password) {
            await Clipboard.setStringAsync(generatedPassword.password);
            Alert.alert('Copied!', 'Password copied to clipboard');
        }
    }, [generatedPassword]);

    if (isLoading) {
        return (
            <LinearGradient colors={['#0f172a', '#1e3a5f', '#0f172a']} style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#06b6d4" />
                <Text style={styles.loadingText}>🌊 Connecting to ocean entropy sources...</Text>
            </LinearGradient>
        );
    }

    return (
        <LinearGradient colors={['#0f172a', '#1e3a5f', '#0f172a']} style={styles.container}>
            <ScrollView
                style={styles.scrollView}
                refreshControl={
                    <RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} tintColor="#06b6d4" />
                }
            >
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.headerTitle}>🌊 Ocean Entropy</Text>
                    <Text style={styles.headerSubtitle}>Powered by the ocean's chaos</Text>
                </View>

                {/* Error Banner */}
                {error && (
                    <View style={styles.errorBanner}>
                        <Text style={styles.errorText}>⚠️ {error}</Text>
                    </View>
                )}

                {/* Storm Chase Mode Banner */}
                {stormStatus?.isActive && (
                    <View style={styles.stormBanner}>
                        <Text style={styles.stormBannerIcon}>
                            {stormStatus.mostSevere === 'extreme' ? '🌀' : '⚠️'}
                        </Text>
                        <View style={styles.stormBannerContent}>
                            <Text style={styles.stormBannerTitle}>
                                STORM CHASE MODE ACTIVE
                            </Text>
                            <Text style={styles.stormBannerSubtitle}>
                                {stormStatus.activeStormsCount} storm(s) • +{((stormStatus.maxEntropyBonus || 0) * 100).toFixed(0)}% entropy
                            </Text>
                        </View>
                    </View>
                )}

                {/* Map View */}
                <View style={styles.mapContainer}>
                    <MapView
                        ref={mapRef}
                        style={styles.map}
                        provider={PROVIDER_GOOGLE}
                        initialRegion={region}
                        mapType="hybrid"
                    >
                        {buoys.map((buoy) => (
                            <BuoyMarker
                                key={buoy.id}
                                buoy={buoy}
                                isSelected={selectedBuoy?.id === buoy.id}
                                onPress={() => handleSelectBuoy(buoy)}
                            />
                        ))}

                        {selectedBuoy && (
                            <Circle
                                center={{ latitude: selectedBuoy.latitude, longitude: selectedBuoy.longitude }}
                                radius={50000}
                                strokeColor="rgba(6, 182, 212, 0.5)"
                                fillColor="rgba(6, 182, 212, 0.1)"
                            />
                        )}
                    </MapView>

                    {/* Buoy count badge */}
                    <View style={styles.buoyCountBadge}>
                        <Text style={styles.buoyCountText}>{buoys.length} buoys</Text>
                    </View>
                </View>

                {/* Selected Buoy Details */}
                {selectedBuoy && (
                    <BlurView intensity={20} style={styles.buoyDetailsCard}>
                        <View style={styles.buoyDetailsHeader}>
                            <Text style={styles.buoyName}>{selectedBuoy.name || selectedBuoy.id}</Text>
                            <View style={[
                                styles.statusBadge,
                                { backgroundColor: selectedBuoy.status === 'excellent' ? '#22c55e' : '#3b82f6' }
                            ]}>
                                <Text style={styles.statusText}>{selectedBuoy.status}</Text>
                            </View>
                        </View>

                        <Text style={styles.buoyRegion}>📍 {selectedBuoy.region}</Text>

                        {/* Wave Animation */}
                        <WaveAnimation
                            waveHeight={selectedBuoy.wave_height || 1}
                            wavePeriod={selectedBuoy.wave_period || 8}
                        />

                        {/* Data Cards */}
                        <View style={styles.dataCardsRow}>
                            <DataCard
                                icon="📏"
                                label="Wave Height"
                                value={`${selectedBuoy.wave_height?.toFixed(1) || 'N/A'} m`}
                            />
                            <DataCard
                                icon="⏱️"
                                label="Period"
                                value={`${selectedBuoy.wave_period?.toFixed(1) || 'N/A'} s`}
                            />
                            <DataCard
                                icon="🌡️"
                                label="Water Temp"
                                value={`${selectedBuoy.water_temp?.toFixed(1) || 'N/A'}°C`}
                            />
                            <DataCard
                                icon="💨"
                                label="Wind"
                                value={`${selectedBuoy.wind_speed?.toFixed(1) || 'N/A'} m/s`}
                            />
                        </View>

                        {/* Quality Score */}
                        <View style={styles.qualityContainer}>
                            <Text style={styles.qualityLabel}>Entropy Quality</Text>
                            <View style={styles.qualityBar}>
                                <View style={[
                                    styles.qualityFill,
                                    { width: `${(selectedBuoy.quality_score || 0) * 100}%` }
                                ]} />
                            </View>
                            <Text style={styles.qualityValue}>
                                {((selectedBuoy.quality_score || 0) * 100).toFixed(0)}%
                            </Text>
                        </View>
                    </BlurView>
                )}

                {/* Password Generator */}
                <View style={styles.generatorCard}>
                    <Text style={styles.generatorTitle}>🔐 Generate Ocean-Powered Password</Text>

                    <TouchableOpacity
                        style={[styles.generateButton, isGenerating && styles.generateButtonDisabled]}
                        onPress={handleGeneratePassword}
                        disabled={isGenerating}
                    >
                        {isGenerating ? (
                            <ActivityIndicator color="#ffffff" />
                        ) : (
                            <Text style={styles.generateButtonText}>🌊 Generate Hybrid Password</Text>
                        )}
                    </TouchableOpacity>

                    {/* Generated Password Display */}
                    {generatedPassword && (
                        <View style={styles.passwordResult}>
                            <TouchableOpacity onPress={handleCopyPassword} style={styles.passwordDisplay}>
                                <Text style={styles.passwordText}>{generatedPassword.password}</Text>
                                <Text style={styles.copyHint}>Tap to copy</Text>
                            </TouchableOpacity>

                            <View style={styles.passwordMeta}>
                                <Text style={styles.metaText}>
                                    Sources: {generatedPassword.sources.join(' + ')}
                                </Text>
                                <Text style={styles.metaText}>
                                    Entropy: {generatedPassword.entropy_bits.toFixed(0)} bits
                                </Text>
                                {generatedPassword.ocean_details?.buoy_id && (
                                    <Text style={styles.metaText}>
                                        Buoy: {generatedPassword.ocean_details.buoy_id}
                                    </Text>
                                )}
                            </View>
                        </View>
                    )}
                </View>

                {/* Buoy List */}
                <View style={styles.buoyListCard}>
                    <Text style={styles.buoyListTitle}>📍 Active Buoys</Text>

                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                        {buoys.slice(0, 10).map((buoy) => (
                            <TouchableOpacity
                                key={buoy.id}
                                style={[
                                    styles.buoyListItem,
                                    selectedBuoy?.id === buoy.id && styles.buoyListItemSelected,
                                ]}
                                onPress={() => handleSelectBuoy(buoy)}
                            >
                                <Text style={styles.buoyListEmoji}>🌊</Text>
                                <Text style={styles.buoyListName}>{buoy.name || buoy.id}</Text>
                                <Text style={styles.buoyListRegion}>{buoy.region}</Text>
                            </TouchableOpacity>
                        ))}
                    </ScrollView>
                </View>

                {/* Footer */}
                <View style={styles.footer}>
                    <Text style={styles.footerText}>🌊 Data from NOAA National Data Buoy Center</Text>
                </View>
            </ScrollView>
        </LinearGradient>
    );
};

// Styles
const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollView: {
        flex: 1,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        color: '#94a3b8',
        marginTop: 16,
        fontSize: 16,
    },
    header: {
        padding: 20,
        paddingTop: 60,
        alignItems: 'center',
    },
    headerTitle: {
        fontSize: 32,
        fontWeight: 'bold',
        color: '#ffffff',
    },
    headerSubtitle: {
        fontSize: 14,
        color: '#94a3b8',
        marginTop: 4,
        fontStyle: 'italic',
    },
    errorBanner: {
        backgroundColor: 'rgba(239, 68, 68, 0.2)',
        padding: 12,
        marginHorizontal: 16,
        borderRadius: 8,
        marginBottom: 16,
    },
    errorText: {
        color: '#fca5a5',
        textAlign: 'center',
    },
    mapContainer: {
        height: 300,
        marginHorizontal: 16,
        borderRadius: 16,
        overflow: 'hidden',
        marginBottom: 16,
    },
    map: {
        flex: 1,
    },
    buoyCountBadge: {
        position: 'absolute',
        top: 10,
        right: 10,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: 20,
    },
    buoyCountText: {
        color: '#06b6d4',
        fontWeight: 'bold',
    },
    markerContainer: {
        alignItems: 'center',
    },
    markerSelected: {
        transform: [{ scale: 1.2 }],
    },
    markerDot: {
        width: 36,
        height: 36,
        borderRadius: 18,
        justifyContent: 'center',
        alignItems: 'center',
        borderWidth: 2,
        borderColor: '#ffffff',
    },
    markerEmoji: {
        fontSize: 18,
    },
    markerLabel: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 4,
        marginTop: 4,
    },
    markerLabelText: {
        color: '#ffffff',
        fontSize: 10,
    },
    buoyDetailsCard: {
        marginHorizontal: 16,
        borderRadius: 16,
        padding: 16,
        marginBottom: 16,
        backgroundColor: 'rgba(30, 58, 95, 0.8)',
        overflow: 'hidden',
    },
    buoyDetailsHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 8,
    },
    buoyName: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#ffffff',
        flex: 1,
    },
    statusBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 12,
    },
    statusText: {
        color: '#ffffff',
        fontSize: 12,
        fontWeight: 'bold',
        textTransform: 'uppercase',
    },
    buoyRegion: {
        color: '#94a3b8',
        marginBottom: 12,
    },
    waveContainer: {
        height: 100,
        overflow: 'hidden',
        marginVertical: 12,
        borderRadius: 8,
    },
    dataCardsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginTop: 12,
    },
    dataCard: {
        flex: 1,
        alignItems: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        padding: 10,
        borderRadius: 8,
        marginHorizontal: 4,
    },
    dataCardIcon: {
        fontSize: 20,
        marginBottom: 4,
    },
    dataCardLabel: {
        color: '#94a3b8',
        fontSize: 10,
        marginBottom: 2,
    },
    dataCardValue: {
        color: '#06b6d4',
        fontSize: 14,
        fontWeight: 'bold',
    },
    qualityContainer: {
        marginTop: 16,
        flexDirection: 'row',
        alignItems: 'center',
    },
    qualityLabel: {
        color: '#94a3b8',
        fontSize: 12,
        marginRight: 12,
    },
    qualityBar: {
        flex: 1,
        height: 8,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 4,
        overflow: 'hidden',
    },
    qualityFill: {
        height: '100%',
        backgroundColor: '#22c55e',
        borderRadius: 4,
    },
    qualityValue: {
        color: '#22c55e',
        marginLeft: 12,
        fontWeight: 'bold',
    },
    generatorCard: {
        marginHorizontal: 16,
        backgroundColor: 'rgba(30, 58, 95, 0.6)',
        borderRadius: 16,
        padding: 16,
        marginBottom: 16,
    },
    generatorTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#ffffff',
        textAlign: 'center',
        marginBottom: 16,
    },
    generateButton: {
        backgroundColor: '#0891b2',
        paddingVertical: 16,
        borderRadius: 12,
        alignItems: 'center',
    },
    generateButtonDisabled: {
        opacity: 0.6,
    },
    generateButtonText: {
        color: '#ffffff',
        fontSize: 16,
        fontWeight: 'bold',
    },
    passwordResult: {
        marginTop: 16,
    },
    passwordDisplay: {
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        padding: 16,
        borderRadius: 8,
        alignItems: 'center',
    },
    passwordText: {
        color: '#22d3ee',
        fontSize: 18,
        fontFamily: 'monospace',
        letterSpacing: 2,
    },
    copyHint: {
        color: '#64748b',
        fontSize: 12,
        marginTop: 8,
    },
    passwordMeta: {
        marginTop: 12,
        padding: 12,
        backgroundColor: 'rgba(0, 0, 0, 0.2)',
        borderRadius: 8,
    },
    metaText: {
        color: '#94a3b8',
        fontSize: 12,
        marginBottom: 4,
    },
    buoyListCard: {
        marginHorizontal: 16,
        marginBottom: 16,
    },
    buoyListTitle: {
        fontSize: 16,
        fontWeight: 'bold',
        color: '#ffffff',
        marginBottom: 12,
    },
    buoyListItem: {
        backgroundColor: 'rgba(30, 58, 95, 0.6)',
        padding: 12,
        borderRadius: 12,
        marginRight: 12,
        alignItems: 'center',
        minWidth: 100,
    },
    buoyListItemSelected: {
        backgroundColor: '#0891b2',
    },
    buoyListEmoji: {
        fontSize: 24,
        marginBottom: 4,
    },
    buoyListName: {
        color: '#ffffff',
        fontSize: 12,
        fontWeight: 'bold',
        textAlign: 'center',
    },
    buoyListRegion: {
        color: '#94a3b8',
        fontSize: 10,
        textAlign: 'center',
        marginTop: 2,
    },
    footer: {
        padding: 20,
        alignItems: 'center',
    },
    footerText: {
        color: '#64748b',
        fontSize: 12,
        fontStyle: 'italic',
    },
    // Storm Chase Mode Banner Styles
    stormBanner: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(239, 68, 68, 0.2)',
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.5)',
        marginHorizontal: 16,
        marginBottom: 16,
        padding: 12,
        borderRadius: 12,
    },
    stormBannerIcon: {
        fontSize: 28,
        marginRight: 12,
    },
    stormBannerContent: {
        flex: 1,
    },
    stormBannerTitle: {
        color: '#fca5a5',
        fontSize: 14,
        fontWeight: 'bold',
    },
    stormBannerSubtitle: {
        color: '#f87171',
        fontSize: 12,
        marginTop: 2,
    },
});

export default OceanWaveScreen;
