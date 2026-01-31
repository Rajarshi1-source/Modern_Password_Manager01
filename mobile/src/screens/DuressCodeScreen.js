/**
 * DuressCodeScreen - Mobile
 * 
 * Main screen for Military-Grade Duress Codes on mobile.
 * Shows protection status, duress codes, and navigation to sub-screens.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    RefreshControl,
    ActivityIndicator,
    Platform,
    Alert,
    TextInput,
    Modal,
} from 'react-native';
import duressCodeService from '../services/DuressCodeService';

const THREAT_LEVELS = [
    { key: 'low', label: 'Low', icon: '🟢', color: '#22c55e' },
    { key: 'medium', label: 'Medium', icon: '🟡', color: '#eab308' },
    { key: 'high', label: 'High', icon: '🟠', color: '#f97316' },
    { key: 'critical', label: 'Critical', icon: '🔴', color: '#ef4444' },
];

const DuressCodeScreen = ({ navigation }) => {
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [config, setConfig] = useState(null);
    const [codes, setCodes] = useState([]);
    const [events, setEvents] = useState([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [newCode, setNewCode] = useState({ code: '', threatLevel: 'medium', hint: '' });
    const [codeStrength, setCodeStrength] = useState({ score: 0, label: 'Weak', suggestions: [] });
    const [stats, setStats] = useState({
        totalCodes: 0,
        recentEvents: 0,
        authoritiesCount: 0,
    });

    // Fetch all data
    const fetchData = useCallback(async () => {
        try {
            // Get configuration
            const configData = await duressCodeService.getConfig();
            setConfig(configData);

            // Get codes
            const codesData = await duressCodeService.getCodes();
            setCodes(codesData.codes || []);

            // Get recent events
            const eventsData = await duressCodeService.getEvents({ limit: 3 });
            setEvents(eventsData.events || []);

            // Get authorities count
            const authData = await duressCodeService.getAuthorities();
            
            setStats({
                totalCodes: codesData.codes?.length || 0,
                recentEvents: eventsData.count || 0,
                authoritiesCount: authData.authorities?.length || 0,
            });
        } catch (error) {
            console.error('Fetch error:', error);
            Alert.alert('Error', 'Failed to load duress code data');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Toggle protection
    const handleToggleProtection = async () => {
        try {
            const newEnabled = !config?.is_enabled;
            await duressCodeService.updateConfig({ is_enabled: newEnabled });
            setConfig({ ...config, is_enabled: newEnabled });
            Alert.alert(
                newEnabled ? '✅ Protection Enabled' : '⚠️ Protection Disabled',
                newEnabled
                    ? 'Duress code protection is now active.'
                    : 'Duress code protection has been disabled.'
            );
        } catch (error) {
            Alert.alert('Error', 'Failed to update protection status');
        }
    };

    // Handle code input change
    const handleCodeChange = (text) => {
        setNewCode({ ...newCode, code: text });
        const strength = duressCodeService.calculateCodeStrength(text);
        setCodeStrength(strength);
    };

    // Add new code
    const handleAddCode = async () => {
        if (!newCode.code || newCode.code.length < 4) {
            Alert.alert('Invalid Code', 'Duress code must be at least 4 characters.');
            return;
        }

        try {
            await duressCodeService.createCode({
                code: newCode.code,
                threatLevel: newCode.threatLevel,
                codeHint: newCode.hint,
            });
            setShowAddModal(false);
            setNewCode({ code: '', threatLevel: 'medium', hint: '' });
            setCodeStrength({ score: 0, label: 'Weak', suggestions: [] });
            fetchData();
            Alert.alert('✅ Code Created', 'Your duress code has been created successfully.');
        } catch (error) {
            Alert.alert('Error', error.message || 'Failed to create duress code');
        }
    };

    // Delete code
    const handleDeleteCode = (codeId) => {
        Alert.alert(
            '⚠️ Delete Code',
            'Are you sure you want to delete this duress code?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            await duressCodeService.deleteCode(codeId);
                            fetchData();
                        } catch (error) {
                            Alert.alert('Error', 'Failed to delete code');
                        }
                    },
                },
            ]
        );
    };

    // Get threat level info
    const getThreatInfo = (level) => {
        return THREAT_LEVELS.find(t => t.key === level) || THREAT_LEVELS[1];
    };

    // Get strength bar color
    const getStrengthColor = () => {
        if (codeStrength.score >= 80) return '#22c55e';
        if (codeStrength.score >= 60) return '#eab308';
        if (codeStrength.score >= 40) return '#f97316';
        return '#ef4444';
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#dc2626" />
                <Text style={styles.loadingText}>Loading duress protection...</Text>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <ScrollView
                style={styles.scrollView}
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={() => {
                            setRefreshing(true);
                            fetchData();
                        }}
                        tintColor="#dc2626"
                    />
                }
            >
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.title}>🎖️ Duress Protection</Text>
                    <Text style={styles.subtitle}>
                        Military-grade security for coercion scenarios
                    </Text>
                </View>

                {/* Protection Status Card */}
                <View style={[
                    styles.statusCard,
                    config?.is_enabled && styles.activeCard
                ]}>
                    <View style={styles.statusHeader}>
                        <View
                            style={[
                                styles.statusIndicator,
                                { backgroundColor: config?.is_enabled ? '#22c55e' : '#ef4444' },
                            ]}
                        />
                        <Text style={styles.statusTitle}>Protection Status</Text>
                    </View>
                    
                    <Text style={styles.statusText}>
                        {config?.is_enabled ? 'Active & Protected' : 'Disabled'}
                    </Text>
                    
                    <Text style={styles.statusDescription}>
                        {config?.is_enabled
                            ? 'Your vault is protected against coercion attacks.'
                            : 'Enable protection to secure against forced access.'}
                    </Text>

                    <TouchableOpacity
                        style={[
                            styles.toggleButton,
                            config?.is_enabled && styles.disableButton
                        ]}
                        onPress={handleToggleProtection}
                    >
                        <Text style={styles.toggleButtonText}>
                            {config?.is_enabled ? '🛑 Disable Protection' : '🛡️ Enable Protection'}
                        </Text>
                    </TouchableOpacity>
                </View>

                {/* Stats Cards */}
                <View style={styles.statsRow}>
                    <View style={styles.statCard}>
                        <Text style={styles.statValue}>{stats.totalCodes}</Text>
                        <Text style={styles.statLabel}>Duress Codes</Text>
                        <Text style={styles.statIcon}>🔐</Text>
                    </View>

                    <View style={styles.statCard}>
                        <Text style={styles.statValue}>{stats.authoritiesCount}</Text>
                        <Text style={styles.statLabel}>Authorities</Text>
                        <Text style={styles.statIcon}>🚔</Text>
                    </View>

                    <View style={[
                        styles.statCard,
                        stats.recentEvents > 0 && styles.warningCard
                    ]}>
                        <Text style={styles.statValue}>{stats.recentEvents}</Text>
                        <Text style={styles.statLabel}>Events</Text>
                        <Text style={styles.statIcon}>⚠️</Text>
                    </View>
                </View>

                {/* Duress Codes List */}
                <View style={styles.section}>
                    <View style={styles.sectionHeader}>
                        <Text style={styles.sectionTitle}>🔐 Duress Codes</Text>
                        <TouchableOpacity
                            style={styles.addButton}
                            onPress={() => setShowAddModal(true)}
                        >
                            <Text style={styles.addButtonText}>+ Add</Text>
                        </TouchableOpacity>
                    </View>

                    {codes.length === 0 ? (
                        <View style={styles.emptyState}>
                            <Text style={styles.emptyIcon}>🔒</Text>
                            <Text style={styles.emptyText}>No duress codes configured</Text>
                            <Text style={styles.emptySubtext}>
                                Add a code to protect against coerced access
                            </Text>
                        </View>
                    ) : (
                        codes.map((code) => {
                            const threatInfo = getThreatInfo(code.threat_level);
                            return (
                                <View key={code.id} style={styles.codeCard}>
                                    <View style={styles.codeHeader}>
                                        <View 
                                            style={[
                                                styles.threatBadge,
                                                { backgroundColor: `${threatInfo.color}20` }
                                            ]}
                                        >
                                            <Text style={styles.threatIcon}>{threatInfo.icon}</Text>
                                            <Text style={[styles.threatLabel, { color: threatInfo.color }]}>
                                                {threatInfo.label}
                                            </Text>
                                        </View>
                                        <TouchableOpacity
                                            onPress={() => handleDeleteCode(code.id)}
                                        >
                                            <Text style={styles.deleteIcon}>🗑️</Text>
                                        </TouchableOpacity>
                                    </View>
                                    <Text style={styles.codeHint}>
                                        {code.code_hint || 'No hint provided'}
                                    </Text>
                                    <Text style={styles.codeCreated}>
                                        Created {new Date(code.created_at).toLocaleDateString()}
                                    </Text>
                                </View>
                            );
                        })
                    )}
                </View>

                {/* Recent Events */}
                {events.length > 0 && (
                    <View style={styles.section}>
                        <Text style={styles.sectionTitle}>🚨 Recent Events</Text>
                        {events.map((event) => {
                            const threatInfo = getThreatInfo(event.threat_level);
                            return (
                                <View key={event.id} style={styles.eventCard}>
                                    <View style={styles.eventHeader}>
                                        <Text style={styles.eventIcon}>{threatInfo.icon}</Text>
                                        <View style={styles.eventContent}>
                                            <Text style={styles.eventTitle}>
                                                {threatInfo.label} Alert Triggered
                                            </Text>
                                            <Text style={styles.eventTime}>
                                                {new Date(event.timestamp).toLocaleString()}
                                            </Text>
                                        </View>
                                    </View>
                                </View>
                            );
                        })}
                    </View>
                )}

                {/* Quick Actions */}
                <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Quick Actions</Text>
                    
                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('DecoyVaultPreview')}
                    >
                        <Text style={styles.actionIcon}>🎭</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Preview Decoy Vault</Text>
                            <Text style={styles.actionSubtitle}>
                                See what attackers will see
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('TrustedAuthorities')}
                    >
                        <Text style={styles.actionIcon}>🚔</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Trusted Authorities</Text>
                            <Text style={styles.actionSubtitle}>
                                Manage silent alarm contacts
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('DuressEventLog')}
                    >
                        <Text style={styles.actionIcon}>📊</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Event Log</Text>
                            <Text style={styles.actionSubtitle}>
                                View activation history
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>
                </View>

                {/* Info Box */}
                <View style={styles.infoBox}>
                    <Text style={styles.infoIcon}>⚠️</Text>
                    <Text style={styles.infoText}>
                        Duress codes are designed for life-threatening situations. 
                        When entered, they show fake data and can alert authorities silently.
                    </Text>
                </View>
            </ScrollView>

            {/* Add Code Modal */}
            <Modal
                visible={showAddModal}
                animationType="slide"
                transparent={true}
                onRequestClose={() => setShowAddModal(false)}
            >
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <Text style={styles.modalTitle}>🔐 New Duress Code</Text>
                        
                        <Text style={styles.inputLabel}>Duress Code</Text>
                        <TextInput
                            style={styles.input}
                            placeholder="Enter your duress code"
                            placeholderTextColor="#64748b"
                            secureTextEntry
                            value={newCode.code}
                            onChangeText={handleCodeChange}
                        />
                        
                        {/* Strength Indicator */}
                        <View style={styles.strengthContainer}>
                            <View style={styles.strengthBar}>
                                <View 
                                    style={[
                                        styles.strengthFill,
                                        { 
                                            width: `${codeStrength.score}%`,
                                            backgroundColor: getStrengthColor()
                                        }
                                    ]}
                                />
                            </View>
                            <Text style={[styles.strengthLabel, { color: getStrengthColor() }]}>
                                {codeStrength.label}
                            </Text>
                        </View>

                        <Text style={styles.inputLabel}>Threat Level</Text>
                        <View style={styles.threatSelector}>
                            {THREAT_LEVELS.map((level) => (
                                <TouchableOpacity
                                    key={level.key}
                                    style={[
                                        styles.threatOption,
                                        newCode.threatLevel === level.key && styles.threatOptionActive,
                                        { borderColor: level.color }
                                    ]}
                                    onPress={() => setNewCode({ ...newCode, threatLevel: level.key })}
                                >
                                    <Text style={styles.threatOptionIcon}>{level.icon}</Text>
                                    <Text style={styles.threatOptionLabel}>{level.label}</Text>
                                </TouchableOpacity>
                            ))}
                        </View>

                        <Text style={styles.inputLabel}>Hint (Optional)</Text>
                        <TextInput
                            style={styles.input}
                            placeholder="A reminder for yourself"
                            placeholderTextColor="#64748b"
                            value={newCode.hint}
                            onChangeText={(text) => setNewCode({ ...newCode, hint: text })}
                        />

                        <View style={styles.modalButtons}>
                            <TouchableOpacity
                                style={styles.cancelButton}
                                onPress={() => setShowAddModal(false)}
                            >
                                <Text style={styles.cancelButtonText}>Cancel</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={styles.saveButton}
                                onPress={handleAddCode}
                            >
                                <Text style={styles.saveButtonText}>Create Code</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#0f172a',
    },
    scrollView: {
        flex: 1,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#0f172a',
    },
    loadingText: {
        color: '#94a3b8',
        marginTop: 16,
    },
    header: {
        padding: 20,
        paddingTop: Platform.OS === 'ios' ? 60 : 20,
    },
    title: {
        fontSize: 28,
        fontWeight: '700',
        color: '#e2e8f0',
    },
    subtitle: {
        fontSize: 14,
        color: '#94a3b8',
        marginTop: 4,
    },
    statusCard: {
        marginHorizontal: 16,
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 16,
        padding: 20,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.3)',
    },
    activeCard: {
        borderColor: 'rgba(34, 197, 94, 0.4)',
        backgroundColor: 'rgba(34, 197, 94, 0.05)',
    },
    statusHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 12,
    },
    statusIndicator: {
        width: 12,
        height: 12,
        borderRadius: 6,
        marginRight: 8,
    },
    statusTitle: {
        color: '#94a3b8',
        fontSize: 14,
    },
    statusText: {
        color: '#e2e8f0',
        fontSize: 20,
        fontWeight: '600',
    },
    statusDescription: {
        color: '#94a3b8',
        fontSize: 13,
        marginTop: 8,
    },
    toggleButton: {
        backgroundColor: 'rgba(34, 197, 94, 0.2)',
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
        marginTop: 16,
        borderWidth: 1,
        borderColor: 'rgba(34, 197, 94, 0.3)',
    },
    disableButton: {
        backgroundColor: 'rgba(239, 68, 68, 0.2)',
        borderColor: 'rgba(239, 68, 68, 0.3)',
    },
    toggleButtonText: {
        color: '#e2e8f0',
        fontSize: 15,
        fontWeight: '600',
    },
    statsRow: {
        flexDirection: 'row',
        paddingHorizontal: 16,
        gap: 8,
        marginBottom: 20,
    },
    statCard: {
        flex: 1,
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 12,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    warningCard: {
        borderColor: '#f97316',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
    },
    statValue: {
        color: '#e2e8f0',
        fontSize: 24,
        fontWeight: '700',
    },
    statLabel: {
        color: '#94a3b8',
        fontSize: 11,
        marginTop: 4,
    },
    statIcon: {
        fontSize: 18,
        marginTop: 6,
    },
    section: {
        paddingHorizontal: 16,
        marginBottom: 20,
    },
    sectionHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
    },
    sectionTitle: {
        color: '#e2e8f0',
        fontSize: 16,
        fontWeight: '600',
    },
    addButton: {
        backgroundColor: 'rgba(220, 38, 38, 0.2)',
        paddingVertical: 6,
        paddingHorizontal: 14,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: 'rgba(220, 38, 38, 0.3)',
    },
    addButtonText: {
        color: '#f87171',
        fontSize: 14,
        fontWeight: '600',
    },
    emptyState: {
        alignItems: 'center',
        padding: 32,
        backgroundColor: 'rgba(30, 41, 59, 0.5)',
        borderRadius: 12,
    },
    emptyIcon: {
        fontSize: 48,
        marginBottom: 12,
    },
    emptyText: {
        color: '#e2e8f0',
        fontSize: 16,
        fontWeight: '600',
    },
    emptySubtext: {
        color: '#94a3b8',
        fontSize: 13,
        marginTop: 4,
        textAlign: 'center',
    },
    codeCard: {
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 10,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    codeHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 10,
    },
    threatBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: 4,
        paddingHorizontal: 10,
        borderRadius: 20,
    },
    threatIcon: {
        fontSize: 14,
        marginRight: 6,
    },
    threatLabel: {
        fontSize: 13,
        fontWeight: '600',
    },
    deleteIcon: {
        fontSize: 18,
    },
    codeHint: {
        color: '#e2e8f0',
        fontSize: 14,
    },
    codeCreated: {
        color: '#64748b',
        fontSize: 12,
        marginTop: 6,
    },
    eventCard: {
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 14,
        marginBottom: 8,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    eventHeader: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    eventIcon: {
        fontSize: 24,
        marginRight: 12,
    },
    eventContent: {
        flex: 1,
    },
    eventTitle: {
        color: '#e2e8f0',
        fontSize: 14,
        fontWeight: '600',
    },
    eventTime: {
        color: '#94a3b8',
        fontSize: 12,
        marginTop: 2,
    },
    actionButton: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 10,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    actionIcon: {
        fontSize: 28,
        marginRight: 14,
    },
    actionContent: {
        flex: 1,
    },
    actionTitle: {
        color: '#e2e8f0',
        fontSize: 15,
        fontWeight: '600',
    },
    actionSubtitle: {
        color: '#94a3b8',
        fontSize: 13,
        marginTop: 2,
    },
    actionArrow: {
        color: '#64748b',
        fontSize: 18,
    },
    infoBox: {
        flexDirection: 'row',
        marginHorizontal: 16,
        marginBottom: 40,
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderRadius: 12,
        padding: 14,
    },
    infoIcon: {
        fontSize: 18,
        marginRight: 10,
    },
    infoText: {
        color: '#fca5a5',
        fontSize: 13,
        flex: 1,
        lineHeight: 20,
    },
    // Modal styles
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        backgroundColor: '#1e293b',
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        padding: 24,
        paddingBottom: Platform.OS === 'ios' ? 40 : 24,
    },
    modalTitle: {
        color: '#e2e8f0',
        fontSize: 22,
        fontWeight: '700',
        marginBottom: 20,
        textAlign: 'center',
    },
    inputLabel: {
        color: '#94a3b8',
        fontSize: 14,
        marginBottom: 8,
        fontWeight: '600',
    },
    input: {
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 14,
        color: '#e2e8f0',
        fontSize: 16,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    strengthContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 20,
    },
    strengthBar: {
        flex: 1,
        height: 6,
        backgroundColor: 'rgba(100, 116, 139, 0.3)',
        borderRadius: 3,
        overflow: 'hidden',
        marginRight: 12,
    },
    strengthFill: {
        height: '100%',
        borderRadius: 3,
    },
    strengthLabel: {
        fontSize: 13,
        fontWeight: '600',
        width: 70,
        textAlign: 'right',
    },
    threatSelector: {
        flexDirection: 'row',
        gap: 8,
        marginBottom: 20,
    },
    threatOption: {
        flex: 1,
        alignItems: 'center',
        paddingVertical: 12,
        borderRadius: 10,
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderWidth: 2,
        borderColor: 'transparent',
    },
    threatOptionActive: {
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
    },
    threatOptionIcon: {
        fontSize: 20,
        marginBottom: 4,
    },
    threatOptionLabel: {
        color: '#94a3b8',
        fontSize: 11,
        fontWeight: '600',
    },
    modalButtons: {
        flexDirection: 'row',
        gap: 12,
        marginTop: 8,
    },
    cancelButton: {
        flex: 1,
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
        backgroundColor: 'rgba(100, 116, 139, 0.2)',
    },
    cancelButtonText: {
        color: '#94a3b8',
        fontSize: 16,
        fontWeight: '600',
    },
    saveButton: {
        flex: 1,
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
        backgroundColor: '#dc2626',
    },
    saveButtonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
});

export default DuressCodeScreen;
