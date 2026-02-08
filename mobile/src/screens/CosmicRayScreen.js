/**
 * Cosmic Ray Screen - Mobile
 * 
 * Mobile screen for cosmic ray-based password generation.
 */

import React, {useState, useEffect, useCallback} from 'react';
import {
    View,
    Text,
    ScrollView,
    TouchableOpacity,
    ActivityIndicator,
    StyleSheet,
    Alert,
    Clipboard,
} from 'react-native';
import LinearGradient from 'react-native-linear-gradient';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import cosmicRayService from '../services/CosmicRayService';

const CosmicRayScreen = ({navigation}) => {
    const [status, setStatus] = useState(null);
    const [password, setPassword] = useState('');
    const [passwordInfo, setPasswordInfo] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState(null);
    const [copied, setCopied] = useState(false);

    // Password options
    const [passwordLength, setPasswordLength] = useState(20);
    const [includeUppercase, setIncludeUppercase] = useState(true);
    const [includeLowercase, setIncludeLowercase] = useState(true);
    const [includeDigits, setIncludeDigits] = useState(true);
    const [includeSymbols, setIncludeSymbols] = useState(true);

    // Load detector status
    const loadStatus = useCallback(async () => {
        try {
            setIsLoading(true);
            const data = await cosmicRayService.getDetectorStatus();
            setStatus(data);
        } catch (err) {
            console.error('Failed to load status:', err);
            setError(err.message || 'Failed to load detector status');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadStatus();
    }, [loadStatus]);

    // Generate password
    const handleGenerate = async () => {
        try {
            setIsGenerating(true);
            setError(null);

            const result = await cosmicRayService.generateCosmicPassword({
                length: passwordLength,
                includeUppercase,
                includeLowercase,
                includeDigits,
                includeSymbols,
            });

            if (result.success) {
                setPassword(result.password);
                setPasswordInfo(result);
            } else {
                throw new Error(result.error || 'Generation failed');
            }
        } catch (err) {
            console.error('Generation error:', err);
            setError(err.message || 'Failed to generate password');
        } finally {
            setIsGenerating(false);
        }
    };

    // Copy password
    const handleCopy = () => {
        if (password) {
            Clipboard.setString(password);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    // Get mode display
    const getModeInfo = (mode) => {
        switch (mode) {
            case 'hardware':
                return {label: 'Hardware', icon: 'satellite-variant', color: '#10b981'};
            case 'simulation':
                return {label: 'Simulation', icon: 'laptop', color: '#a78bfa'};
            default:
                return {label: 'Unknown', icon: 'help-circle', color: '#9ca3af'};
        }
    };

    const modeInfo = status?.status
        ? getModeInfo(status.status.mode)
        : getModeInfo('unknown');

    if (isLoading && !status) {
        return (
            <LinearGradient
                colors={['#0a0f1e', '#1a1f3e', '#0a0f1e']}
                style={styles.container}>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color="#64c8ff" />
                    <Text style={styles.loadingText}>
                        Initializing Cosmic Ray Detector...
                    </Text>
                </View>
            </LinearGradient>
        );
    }

    return (
        <LinearGradient
            colors={['#0a0f1e', '#1a1f3e', '#0a0f1e']}
            style={styles.container}>
            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}>
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.title}>🌌 Cosmic Ray Entropy</Text>
                    <Text style={styles.subtitle}>
                        True randomness from muon detection
                    </Text>

                    <View style={styles.modeBadge}>
                        <Icon name={modeInfo.icon} size={16} color={modeInfo.color} />
                        <Text style={[styles.modeText, {color: modeInfo.color}]}>
                            {modeInfo.label}
                        </Text>
                    </View>
                </View>

                {/* Error Banner */}
                {error && (
                    <View style={styles.errorBanner}>
                        <Icon name="alert-circle" size={20} color="#f87171" />
                        <Text style={styles.errorText}>{error}</Text>
                    </View>
                )}

                {/* Password Options */}
                <View style={styles.card}>
                    <Text style={styles.cardTitle}>⚙️ Password Options</Text>

                    <View style={styles.lengthControl}>
                        <Text style={styles.lengthLabel}>
                            Length: <Text style={styles.lengthValue}>{passwordLength}</Text>
                        </Text>
                        <View style={styles.lengthButtons}>
                            <TouchableOpacity
                                style={styles.lengthBtn}
                                onPress={() =>
                                    setPasswordLength(Math.max(8, passwordLength - 4))
                                }>
                                <Text style={styles.lengthBtnText}>−</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={styles.lengthBtn}
                                onPress={() =>
                                    setPasswordLength(Math.min(64, passwordLength + 4))
                                }>
                                <Text style={styles.lengthBtnText}>+</Text>
                            </TouchableOpacity>
                        </View>
                    </View>

                    <View style={styles.checkboxRow}>
                        <TouchableOpacity
                            style={[
                                styles.checkbox,
                                includeUppercase && styles.checkboxActive,
                            ]}
                            onPress={() => setIncludeUppercase(!includeUppercase)}>
                            <Text style={styles.checkboxText}>ABC</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[
                                styles.checkbox,
                                includeLowercase && styles.checkboxActive,
                            ]}
                            onPress={() => setIncludeLowercase(!includeLowercase)}>
                            <Text style={styles.checkboxText}>abc</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.checkbox, includeDigits && styles.checkboxActive]}
                            onPress={() => setIncludeDigits(!includeDigits)}>
                            <Text style={styles.checkboxText}>123</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[
                                styles.checkbox,
                                includeSymbols && styles.checkboxActive,
                            ]}
                            onPress={() => setIncludeSymbols(!includeSymbols)}>
                            <Text style={styles.checkboxText}>!@#</Text>
                        </TouchableOpacity>
                    </View>
                </View>

                {/* Generate Button */}
                <TouchableOpacity
                    style={[styles.generateBtn, isGenerating && styles.generating]}
                    onPress={handleGenerate}
                    disabled={isGenerating}>
                    {isGenerating ? (
                        <View style={styles.generatingContent}>
                            <ActivityIndicator size="small" color="#fff" />
                            <Text style={styles.generateBtnText}>
                                Harvesting Cosmic Rays...
                            </Text>
                        </View>
                    ) : (
                        <Text style={styles.generateBtnText}>
                            ✨ Generate Cosmic Password
                        </Text>
                    )}
                </TouchableOpacity>

                {/* Password Result */}
                {password && (
                    <View style={styles.resultCard}>
                        <Text style={styles.passwordDisplay}>{password}</Text>

                        <TouchableOpacity
                            style={[styles.copyBtn, copied && styles.copiedBtn]}
                            onPress={handleCopy}>
                            <Icon
                                name={copied ? 'check' : 'content-copy'}
                                size={18}
                                color={copied ? '#34d399' : '#64c8ff'}
                            />
                            <Text
                                style={[
                                    styles.copyBtnText,
                                    copied && styles.copiedBtnText,
                                ]}>
                                {copied ? 'Copied!' : 'Copy'}
                            </Text>
                        </TouchableOpacity>

                        {passwordInfo && (
                            <View style={styles.passwordMeta}>
                                <Text style={styles.metaItem}>
                                    🎲 {passwordInfo.source}
                                </Text>
                                <Text style={styles.metaItem}>
                                    ⚡ {passwordInfo.entropy_bits} bits
                                </Text>
                                <Text style={styles.metaItem}>
                                    🔬 {passwordInfo.events_used} events
                                </Text>
                            </View>
                        )}
                    </View>
                )}

                {/* Info Section */}
                <View style={styles.infoCard}>
                    <Text style={styles.cardTitle}>ℹ️ How It Works</Text>
                    <Text style={styles.infoText}>
                        Cosmic rays from deep space create unpredictable muon arrivals.
                        We harvest the precise timing to generate true random numbers.
                    </Text>
                </View>
            </ScrollView>
        </LinearGradient>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollContent: {
        padding: 20,
        paddingBottom: 40,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        marginTop: 16,
        color: '#a0b4d0',
        fontSize: 16,
    },
    header: {
        alignItems: 'center',
        marginBottom: 24,
    },
    title: {
        fontSize: 28,
        fontWeight: '700',
        color: '#fff',
        marginBottom: 8,
    },
    subtitle: {
        fontSize: 14,
        color: '#a0b4d0',
        marginBottom: 12,
    },
    modeBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
        paddingHorizontal: 12,
        paddingVertical: 6,
        backgroundColor: 'rgba(100, 200, 255, 0.1)',
        borderRadius: 16,
    },
    modeText: {
        fontSize: 12,
        fontWeight: '600',
        textTransform: 'uppercase',
    },
    errorBanner: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
        padding: 12,
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        borderRadius: 8,
        marginBottom: 16,
    },
    errorText: {
        flex: 1,
        color: '#fca5a5',
        fontSize: 14,
    },
    card: {
        backgroundColor: 'rgba(20, 30, 60, 0.7)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: 'rgba(100, 200, 255, 0.15)',
    },
    cardTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#a0c4ff',
        marginBottom: 16,
    },
    lengthControl: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
    },
    lengthLabel: {
        color: '#a0b4d0',
        fontSize: 14,
    },
    lengthValue: {
        color: '#64c8ff',
        fontWeight: '700',
    },
    lengthButtons: {
        flexDirection: 'row',
        gap: 8,
    },
    lengthBtn: {
        width: 40,
        height: 40,
        borderRadius: 8,
        backgroundColor: 'rgba(100, 200, 255, 0.15)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    lengthBtnText: {
        color: '#64c8ff',
        fontSize: 20,
        fontWeight: '600',
    },
    checkboxRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 8,
    },
    checkbox: {
        paddingHorizontal: 16,
        paddingVertical: 10,
        backgroundColor: 'rgba(100, 200, 255, 0.1)',
        borderRadius: 8,
        borderWidth: 1,
        borderColor: 'rgba(100, 200, 255, 0.2)',
    },
    checkboxActive: {
        backgroundColor: 'rgba(100, 200, 255, 0.25)',
        borderColor: '#64c8ff',
    },
    checkboxText: {
        color: '#e0e8ff',
        fontSize: 14,
        fontWeight: '500',
    },
    generateBtn: {
        backgroundColor: '#2563eb',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginBottom: 16,
    },
    generating: {
        backgroundColor: '#7c3aed',
    },
    generatingContent: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
    },
    generateBtnText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    resultCard: {
        backgroundColor: 'rgba(10, 15, 30, 0.8)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: 'rgba(100, 200, 255, 0.2)',
    },
    passwordDisplay: {
        fontFamily: 'monospace',
        fontSize: 16,
        color: '#64ffb4',
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        padding: 12,
        borderRadius: 8,
        marginBottom: 12,
    },
    copyBtn: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        padding: 12,
        backgroundColor: 'rgba(100, 200, 255, 0.15)',
        borderRadius: 8,
    },
    copiedBtn: {
        backgroundColor: 'rgba(16, 185, 129, 0.2)',
    },
    copyBtnText: {
        color: '#64c8ff',
        fontSize: 14,
        fontWeight: '600',
    },
    copiedBtnText: {
        color: '#34d399',
    },
    passwordMeta: {
        marginTop: 12,
        paddingTop: 12,
        borderTopWidth: 1,
        borderTopColor: 'rgba(100, 200, 255, 0.1)',
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 12,
    },
    metaItem: {
        color: '#8899bb',
        fontSize: 12,
    },
    infoCard: {
        backgroundColor: 'rgba(20, 30, 60, 0.7)',
        borderRadius: 12,
        padding: 16,
        borderWidth: 1,
        borderColor: 'rgba(100, 200, 255, 0.15)',
    },
    infoText: {
        color: '#a0b4d0',
        fontSize: 14,
        lineHeight: 22,
    },
});

export default CosmicRayScreen;
