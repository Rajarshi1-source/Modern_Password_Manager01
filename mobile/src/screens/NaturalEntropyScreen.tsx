/**
 * NaturalEntropyScreen
 * 
 * Mobile screen for generating passwords from multiple natural entropy sources.
 * Combines Ocean Waves, Lightning, Seismic, and Solar Wind data.
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
    Alert,
    RefreshControl,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { LinearGradient } from 'expo-linear-gradient';
import oceanEntropyService from '../services/OceanEntropyService';

// =============================================================================
// Types
// =============================================================================

interface EntropySource {
    id: string;
    name: string;
    icon: string;
    color: string;
    available: boolean;
    description: string;
}

interface GeneratedPassword {
    password: string;
    sourcesUsed: string[];
    qualityScore: number;
    certificate: any;
}

interface NaturalPasswordResponse {
    success: boolean;
    password?: string;
    sourcesUsed?: string[];
    qualityScore?: number;
    certificate?: any;
    error?: string;
}

interface GlobalStatusResponse {
    success: boolean;
    sources?: Record<string, any>;
    availableSources?: number;
    totalSources?: number;
    error?: string;
}

// =============================================================================
// Components
// =============================================================================

// Source selection card
const SourceCard = ({
    source,
    selected,
    onPress
}: {
    source: EntropySource;
    selected: boolean;
    onPress: () => void;
}) => {
    // Use useRef to persist the Animated.Value across renders
    const animatedScale = useRef(new Animated.Value(1)).current;

    const handlePressIn = () => {
        Animated.spring(animatedScale, {
            toValue: 0.95,
            useNativeDriver: true,
        }).start();
    };

    const handlePressOut = () => {
        Animated.spring(animatedScale, {
            toValue: 1,
            friction: 3,
            useNativeDriver: true,
        }).start();
    };

    return (
        <TouchableOpacity
            onPress={onPress}
            onPressIn={handlePressIn}
            onPressOut={handlePressOut}
            activeOpacity={0.8}
            disabled={!source.available}
        >
            <Animated.View
                style={[
                    styles.sourceCard,
                    selected && styles.sourceCardSelected,
                    !source.available && styles.sourceCardDisabled,
                    {
                        transform: [{ scale: animatedScale }],
                        borderColor: selected ? source.color : 'transparent',
                    },
                ]}
            >
                <Text style={styles.sourceIcon}>{source.icon}</Text>
                <View style={styles.sourceInfo}>
                    <Text style={styles.sourceName}>{source.name}</Text>
                    <Text style={[
                        styles.sourceStatus,
                        { color: source.available ? '#22c55e' : '#ef4444' }
                    ]}>
                        {source.available ? '● Online' : '○ Offline'}
                    </Text>
                </View>
                <View style={[
                    styles.sourceCheckbox,
                    selected && { backgroundColor: source.color },
                ]}>
                    {selected && <Text style={styles.checkmark}>✓</Text>}
                </View>
            </Animated.View>
        </TouchableOpacity>
    );
};

// Animated quality meter
const QualityMeter = ({ score }: { score: number }) => {
    const [width] = useState(new Animated.Value(0));

    useEffect(() => {
        Animated.timing(width, {
            toValue: score * 100,
            duration: 1000,
            useNativeDriver: false,
        }).start();
    }, [score]);

    return (
        <View style={styles.qualityMeter}>
            <View style={styles.qualityLabel}>
                <Text style={styles.qualityText}>Quality Score</Text>
                <Text style={styles.qualityValue}>{(score * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.qualityBar}>
                <Animated.View
                    style={[
                        styles.qualityFill,
                        {
                            width: width.interpolate({
                                inputRange: [0, 100],
                                outputRange: ['0%', '100%'],
                            })
                        }
                    ]}
                />
            </View>
        </View>
    );
};

// Certificate badge
const CertificateBadge = ({ certificate }: { certificate: any }) => {
    const sourceIcons: Record<string, string> = {
        ocean: '🌊',
        lightning: '⚡',
        seismic: '🌍',
        solar: '☀️',
    };

    return (
        <View style={styles.certificate}>
            <View style={styles.certificateHeader}>
                <Text style={styles.certificateIcon}>🏆</Text>
                <View>
                    <Text style={styles.certificateTitle}>Natural Entropy Certificate</Text>
                    <Text style={styles.certificateId}>
                        {certificate.certificate_id?.slice(0, 12)}...
                    </Text>
                </View>
            </View>
            <View style={styles.certificateSources}>
                {certificate.sources_used?.map((source: string) => (
                    <Text key={source} style={styles.certificateSourceIcon}>
                        {sourceIcons[source] || '❓'}
                    </Text>
                ))}
            </View>
            <View style={styles.certificateStats}>
                <View style={styles.certificateStat}>
                    <Text style={styles.certificateStatValue}>
                        {certificate.total_entropy_bits}
                    </Text>
                    <Text style={styles.certificateStatLabel}>bits</Text>
                </View>
                <View style={styles.certificateStat}>
                    <Text style={styles.certificateStatValue}>
                        {certificate.password_length}
                    </Text>
                    <Text style={styles.certificateStatLabel}>chars</Text>
                </View>
            </View>
        </View>
    );
};

// =============================================================================
// Main Screen
// =============================================================================

export default function NaturalEntropyScreen() {
    // Available sources
    const sources: EntropySource[] = [
        { id: 'ocean', name: 'Ocean Waves', icon: '🌊', color: '#06b6d4', available: true, description: 'NOAA Buoys' },
        { id: 'lightning', name: 'Lightning', icon: '⚡', color: '#eab308', available: true, description: 'GOES GLM' },
        { id: 'seismic', name: 'Seismic', icon: '🌍', color: '#22c55e', available: true, description: 'USGS Network' },
        { id: 'solar', name: 'Solar Wind', icon: '☀️', color: '#f97316', available: true, description: 'DSCOVR' },
    ];

    // State
    const [selectedSources, setSelectedSources] = useState<string[]>(['ocean', 'lightning', 'seismic', 'solar']);
    const [passwordLength, setPasswordLength] = useState(24);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [generatedPassword, setGeneratedPassword] = useState<GeneratedPassword | null>(null);
    const [globalStatus, setGlobalStatus] = useState<any>(null);

    // Load status on mount
    useEffect(() => {
        loadGlobalStatus();
    }, []);

    const loadGlobalStatus = async () => {
        try {
            const status = await oceanEntropyService.getGlobalEntropyStatus() as GlobalStatusResponse;
            if (status.success) {
                setGlobalStatus(status);
                // Update source availability
                // This would update the sources array based on actual status
            }
        } catch (err) {
            console.error('Failed to load status:', err);
        }
    };

    // Toggle source selection
    const toggleSource = useCallback((sourceId: string) => {
        setSelectedSources(prev =>
            prev.includes(sourceId)
                ? prev.filter(s => s !== sourceId)
                : [...prev, sourceId]
        );
    }, []);

    // Generate password
    const handleGenerate = useCallback(async () => {
        if (selectedSources.length === 0) {
            Alert.alert('No Sources', 'Please select at least one entropy source');
            return;
        }

        setIsGenerating(true);
        setGeneratedPassword(null);

        try {
            const result = await oceanEntropyService.generateNaturalPassword(
                selectedSources,
                passwordLength,
                'standard'
            ) as NaturalPasswordResponse;

            if (result.success && result.password && result.sourcesUsed && result.qualityScore !== undefined) {
                setGeneratedPassword({
                    password: result.password,
                    sourcesUsed: result.sourcesUsed,
                    qualityScore: result.qualityScore,
                    certificate: result.certificate,
                });
            } else {
                Alert.alert('Error', result.error || 'Failed to generate password');
            }
        } catch (err) {
            Alert.alert('Error', 'An unexpected error occurred');
        } finally {
            setIsGenerating(false);
        }
    }, [selectedSources, passwordLength]);

    // Copy password
    const handleCopy = async () => {
        if (generatedPassword?.password) {
            await Clipboard.setStringAsync(generatedPassword.password);
            Alert.alert('Copied!', 'Password copied to clipboard');
        }
    };

    // Refresh
    const onRefresh = useCallback(() => {
        setIsRefreshing(true);
        loadGlobalStatus().finally(() => setIsRefreshing(false));
    }, []);

    return (
        <LinearGradient
            colors={['#0f172a', '#1e1b4b', '#0f172a']}
            style={styles.container}
        >
            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.scrollContent}
                refreshControl={
                    <RefreshControl
                        refreshing={isRefreshing}
                        onRefresh={onRefresh}
                        tintColor="#06b6d4"
                    />
                }
            >
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.headerIcon}>🌊⚡🌍☀️</Text>
                    <Text style={styles.headerTitle}>Natural Entropy</Text>
                    <Text style={styles.headerSubtitle}>
                        Harness Earth's chaos for security
                    </Text>
                </View>

                {/* Source Selection */}
                <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Select Sources</Text>
                    <View style={styles.sourcesGrid}>
                        {sources.map(source => (
                            <SourceCard
                                key={source.id}
                                source={source}
                                selected={selectedSources.includes(source.id)}
                                onPress={() => toggleSource(source.id)}
                            />
                        ))}
                    </View>
                </View>

                {/* Password Length */}
                <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Password Length: {passwordLength}</Text>
                    <View style={styles.lengthButtons}>
                        {[16, 24, 32, 48].map(len => (
                            <TouchableOpacity
                                key={len}
                                style={[
                                    styles.lengthButton,
                                    passwordLength === len && styles.lengthButtonActive,
                                ]}
                                onPress={() => setPasswordLength(len)}
                            >
                                <Text style={[
                                    styles.lengthButtonText,
                                    passwordLength === len && styles.lengthButtonTextActive,
                                ]}>
                                    {len}
                                </Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                </View>

                {/* Generate Button */}
                <TouchableOpacity
                    style={[
                        styles.generateButton,
                        (isGenerating || selectedSources.length === 0) && styles.generateButtonDisabled,
                    ]}
                    onPress={handleGenerate}
                    disabled={isGenerating || selectedSources.length === 0}
                >
                    {isGenerating ? (
                        <ActivityIndicator color="white" />
                    ) : (
                        <>
                            <Text style={styles.generateButtonIcon}>🎲</Text>
                            <Text style={styles.generateButtonText}>
                                Generate from {selectedSources.length} Source{selectedSources.length !== 1 ? 's' : ''}
                            </Text>
                        </>
                    )}
                </TouchableOpacity>

                {/* Generated Password */}
                {generatedPassword && (
                    <View style={styles.resultSection}>
                        <Text style={styles.resultTitle}>🔑 Your Password</Text>

                        <View style={styles.passwordBox}>
                            <Text style={styles.passwordText} selectable>
                                {generatedPassword.password}
                            </Text>
                            <TouchableOpacity style={styles.copyButton} onPress={handleCopy}>
                                <Text style={styles.copyButtonText}>📋</Text>
                            </TouchableOpacity>
                        </View>

                        <QualityMeter score={generatedPassword.qualityScore} />

                        <View style={styles.sourceIcons}>
                            {generatedPassword.sourcesUsed.map(sourceId => (
                                <Text key={sourceId} style={styles.resultSourceIcon}>
                                    {sources.find(s => s.id === sourceId)?.icon}
                                </Text>
                            ))}
                        </View>

                        {generatedPassword.certificate && (
                            <CertificateBadge certificate={generatedPassword.certificate} />
                        )}
                    </View>
                )}

                {/* Status Footer */}
                <View style={styles.statusFooter}>
                    <Text style={styles.statusText}>
                        {globalStatus?.availableSources ?? 0}/{globalStatus?.totalSources ?? 4} sources online
                    </Text>
                </View>
            </ScrollView>
        </LinearGradient>
    );
}

// =============================================================================
// Styles
// =============================================================================

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollView: {
        flex: 1,
    },
    scrollContent: {
        padding: 20,
        paddingBottom: 40,
    },

    // Header
    header: {
        alignItems: 'center',
        marginBottom: 32,
        marginTop: 20,
    },
    headerIcon: {
        fontSize: 36,
        marginBottom: 8,
    },
    headerTitle: {
        fontSize: 28,
        fontWeight: '700',
        color: '#f8fafc',
    },
    headerSubtitle: {
        fontSize: 14,
        color: '#94a3b8',
        marginTop: 4,
    },

    // Sections
    section: {
        marginBottom: 24,
    },
    sectionTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#e2e8f0',
        marginBottom: 12,
    },

    // Source Cards
    sourcesGrid: {
        gap: 12,
    },
    sourceCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(30, 41, 59, 0.6)',
        padding: 16,
        borderRadius: 12,
        borderWidth: 2,
        borderColor: 'transparent',
    },
    sourceCardSelected: {
        backgroundColor: 'rgba(30, 41, 59, 0.9)',
    },
    sourceCardDisabled: {
        opacity: 0.5,
    },
    sourceIcon: {
        fontSize: 28,
        marginRight: 12,
    },
    sourceInfo: {
        flex: 1,
    },
    sourceName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#f8fafc',
    },
    sourceStatus: {
        fontSize: 12,
        marginTop: 2,
    },
    sourceCheckbox: {
        width: 28,
        height: 28,
        borderRadius: 8,
        backgroundColor: '#334155',
        alignItems: 'center',
        justifyContent: 'center',
    },
    checkmark: {
        color: 'white',
        fontSize: 16,
        fontWeight: 'bold',
    },

    // Length Buttons
    lengthButtons: {
        flexDirection: 'row',
        gap: 12,
    },
    lengthButton: {
        flex: 1,
        paddingVertical: 12,
        backgroundColor: 'rgba(30, 41, 59, 0.6)',
        borderRadius: 12,
        alignItems: 'center',
    },
    lengthButtonActive: {
        backgroundColor: '#3b82f6',
    },
    lengthButtonText: {
        color: '#94a3b8',
        fontSize: 16,
        fontWeight: '600',
    },
    lengthButtonTextActive: {
        color: 'white',
    },

    // Generate Button
    generateButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#3b82f6',
        padding: 18,
        borderRadius: 16,
        marginBottom: 24,
        gap: 8,
    },
    generateButtonDisabled: {
        opacity: 0.6,
    },
    generateButtonIcon: {
        fontSize: 20,
    },
    generateButtonText: {
        color: 'white',
        fontSize: 18,
        fontWeight: '600',
    },

    // Result Section
    resultSection: {
        backgroundColor: 'rgba(30, 41, 59, 0.6)',
        borderRadius: 16,
        padding: 20,
        marginBottom: 24,
    },
    resultTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#f8fafc',
        marginBottom: 16,
        textAlign: 'center',
    },
    passwordBox: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#0f172a',
        padding: 16,
        borderRadius: 12,
        marginBottom: 16,
    },
    passwordText: {
        flex: 1,
        fontFamily: 'monospace',
        fontSize: 14,
        color: '#22c55e',
    },
    copyButton: {
        padding: 8,
    },
    copyButtonText: {
        fontSize: 20,
    },

    // Quality Meter
    qualityMeter: {
        marginBottom: 16,
    },
    qualityLabel: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: 8,
    },
    qualityText: {
        color: '#94a3b8',
        fontSize: 14,
    },
    qualityValue: {
        color: '#22c55e',
        fontSize: 14,
        fontWeight: '600',
    },
    qualityBar: {
        height: 8,
        backgroundColor: '#334155',
        borderRadius: 4,
        overflow: 'hidden',
    },
    qualityFill: {
        height: '100%',
        backgroundColor: '#22c55e',
        borderRadius: 4,
    },

    // Source Icons
    sourceIcons: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 12,
        marginBottom: 16,
    },
    resultSourceIcon: {
        fontSize: 28,
    },

    // Certificate
    certificate: {
        backgroundColor: 'rgba(15, 23, 42, 0.8)',
        borderRadius: 12,
        padding: 16,
        borderWidth: 1,
        borderColor: 'rgba(59, 130, 246, 0.3)',
    },
    certificateHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 12,
    },
    certificateIcon: {
        fontSize: 32,
        marginRight: 12,
    },
    certificateTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: '#f8fafc',
    },
    certificateId: {
        fontSize: 11,
        color: '#64748b',
        fontFamily: 'monospace',
    },
    certificateSources: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 8,
        marginBottom: 12,
    },
    certificateSourceIcon: {
        fontSize: 24,
    },
    certificateStats: {
        flexDirection: 'row',
        justifyContent: 'space-around',
    },
    certificateStat: {
        alignItems: 'center',
    },
    certificateStatValue: {
        fontSize: 20,
        fontWeight: '700',
        color: '#06b6d4',
    },
    certificateStatLabel: {
        fontSize: 11,
        color: '#64748b',
    },

    // Status Footer
    statusFooter: {
        alignItems: 'center',
        paddingTop: 16,
    },
    statusText: {
        color: '#64748b',
        fontSize: 12,
    },
});
