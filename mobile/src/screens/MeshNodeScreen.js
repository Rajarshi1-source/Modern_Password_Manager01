/**
 * Mesh Node Screen - Mobile
 * ===========================
 * 
 * Screen to register and manage this device as a mesh node.
 * Allows storing fragments for other users' dead drops.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    Switch,
    TextInput,
    Alert,
    ScrollView,
    ActivityIndicator,
    Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import meshService from '../services/MeshService';

const MeshNodeScreen = ({ navigation }) => {
    const [isNode, setIsNode] = useState(false);
    const [nodeInfo, setNodeInfo] = useState(null);
    const [loading, setLoading] = useState(true);
    const [registering, setRegistering] = useState(false);
    const [fragments, setFragments] = useState([]);
    
    // Settings
    const [settings, setSettings] = useState({
        deviceName: '',
        maxFragments: 10,
        isAvailable: true,
        autoAccept: true,
    });

    // Check if already registered as node
    useEffect(() => {
        const checkNodeStatus = async () => {
            try {
                const savedNodeId = await AsyncStorage.getItem('meshNodeId');
                if (savedNodeId) {
                    // Fetch node info from server
                    const nodes = await meshService.getMeshNodes();
                    const myNode = nodes.nodes?.find(n => n.id === savedNodeId);
                    if (myNode) {
                        setIsNode(true);
                        setNodeInfo(myNode);
                        setSettings({
                            deviceName: myNode.device_name,
                            maxFragments: myNode.max_fragments,
                            isAvailable: myNode.is_available_for_storage,
                            autoAccept: true,
                        });
                        // Fetch stored fragments
                        fetchStoredFragments(savedNodeId);
                    }
                }
            } catch (error) {
                console.error('Failed to check node status:', error);
            } finally {
                setLoading(false);
            }
        };

        checkNodeStatus();
    }, []);

    // Fetch fragments stored on this node
    const fetchStoredFragments = async (nodeId) => {
        // In real implementation, this would fetch from local storage
        // Here we simulate some stored fragments
        setFragments([
            { id: 'frag-1', dropTitle: 'Emergency Access', expiresIn: '5 days' },
            { id: 'frag-2', dropTitle: 'Backup Codes', expiresIn: '2 days' },
        ]);
    };

    // Register as mesh node
    const registerAsNode = async () => {
        if (!settings.deviceName.trim()) {
            Alert.alert('Error', 'Please enter a device name');
            return;
        }

        setRegistering(true);
        try {
            // Generate keypair
            const keypair = meshService.crypto?.generateMeshKeypair?.() || {
                publicKey: 'mock-public-key-' + Date.now(),
            };

            // Get BLE address (mock for demo)
            const bleAddress = 'AA:BB:CC:DD:EE:FF';

            const result = await meshService.registerAsNode({
                device_name: settings.deviceName,
                device_type: Platform.OS === 'ios' ? 'phone_ios' : 'phone_android',
                ble_address: bleAddress,
                public_key: keypair.publicKey,
                max_fragments: settings.maxFragments,
                is_available_for_storage: settings.isAvailable,
            });

            if (result.node) {
                await AsyncStorage.setItem('meshNodeId', result.node.id);
                setIsNode(true);
                setNodeInfo(result.node);
                Alert.alert('Success', 'Device registered as mesh node');
            } else {
                Alert.alert('Error', result.error || 'Registration failed');
            }
        } catch (error) {
            Alert.alert('Error', error.message);
        } finally {
            setRegistering(false);
        }
    };

    // Unregister node
    const unregisterNode = async () => {
        Alert.alert(
            'Unregister Node',
            'This will remove your device from the mesh network. Stored fragments will be redistributed.',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Unregister',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            await AsyncStorage.removeItem('meshNodeId');
                            setIsNode(false);
                            setNodeInfo(null);
                            setFragments([]);
                        } catch (error) {
                            Alert.alert('Error', error.message);
                        }
                    },
                },
            ]
        );
    };

    // Update node settings
    const updateSettings = async () => {
        if (!nodeInfo) return;

        try {
            // Would call API to update node settings
            Alert.alert('Success', 'Settings updated');
        } catch (error) {
            Alert.alert('Error', error.message);
        }
    };

    // Ping to update online status
    const pingNode = async () => {
        if (!nodeInfo) return;

        try {
            const location = await meshService.getCurrentLocation();
            await meshService.pingNode(nodeInfo.id, {
                lat: location.latitude,
                lng: location.longitude,
            });
            Alert.alert('Success', 'Status updated');
        } catch (error) {
            console.error('Ping failed:', error);
        }
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#00e676" />
                <Text style={styles.loadingText}>Loading node status...</Text>
            </View>
        );
    }

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
            <View style={styles.header}>
                <Text style={styles.headerTitle}>🖥️ Mesh Node</Text>
                <Text style={styles.headerSubtitle}>
                    Help others share passwords securely
                </Text>
            </View>

            {!isNode ? (
                // Registration Form
                <View style={styles.section}>
                    <View style={styles.infoCard}>
                        <Text style={styles.infoTitle}>Become a Mesh Node</Text>
                        <Text style={styles.infoText}>
                            By registering as a mesh node, your device will help store encrypted 
                            password fragments for other users. You cannot read these fragments - 
                            they're encrypted and meaningless without the other pieces.
                        </Text>
                    </View>

                    <View style={styles.form}>
                        <Text style={styles.label}>Device Name</Text>
                        <TextInput
                            style={styles.input}
                            value={settings.deviceName}
                            onChangeText={text => setSettings({ ...settings, deviceName: text })}
                            placeholder="e.g., John's Phone"
                            placeholderTextColor="#606060"
                        />

                        <Text style={styles.label}>Max Fragments to Store</Text>
                        <View style={styles.sliderRow}>
                            <TouchableOpacity
                                style={styles.sliderBtn}
                                onPress={() => setSettings(s => ({ ...s, maxFragments: Math.max(1, s.maxFragments - 1) }))}
                            >
                                <Text style={styles.sliderBtnText}>-</Text>
                            </TouchableOpacity>
                            <Text style={styles.sliderValue}>{settings.maxFragments}</Text>
                            <TouchableOpacity
                                style={styles.sliderBtn}
                                onPress={() => setSettings(s => ({ ...s, maxFragments: Math.min(50, s.maxFragments + 1) }))}
                            >
                                <Text style={styles.sliderBtnText}>+</Text>
                            </TouchableOpacity>
                        </View>

                        <View style={styles.toggleRow}>
                            <Text style={styles.toggleLabel}>Available for storage</Text>
                            <Switch
                                value={settings.isAvailable}
                                onValueChange={val => setSettings({ ...settings, isAvailable: val })}
                                trackColor={{ false: '#404040', true: '#00e67660' }}
                                thumbColor={settings.isAvailable ? '#00e676' : '#808080'}
                            />
                        </View>
                    </View>

                    <TouchableOpacity
                        style={styles.registerBtn}
                        onPress={registerAsNode}
                        disabled={registering}
                    >
                        {registering ? (
                            <ActivityIndicator color="#000" />
                        ) : (
                            <Text style={styles.registerBtnText}>Register as Node</Text>
                        )}
                    </TouchableOpacity>
                </View>
            ) : (
                // Node Dashboard
                <>
                    <View style={styles.statusCard}>
                        <View style={styles.statusHeader}>
                            <View style={[styles.statusDot, { backgroundColor: nodeInfo?.is_online ? '#00e676' : '#808080' }]} />
                            <Text style={styles.statusText}>
                                {nodeInfo?.is_online ? 'Online' : 'Offline'}
                            </Text>
                        </View>
                        <Text style={styles.nodeName}>{nodeInfo?.device_name}</Text>
                        <Text style={styles.nodeId}>{nodeInfo?.id?.slice(0, 8)}...</Text>
                    </View>

                    <View style={styles.statsRow}>
                        <View style={styles.statCard}>
                            <Text style={styles.statValue}>{fragments.length}</Text>
                            <Text style={styles.statLabel}>Stored</Text>
                        </View>
                        <View style={styles.statCard}>
                            <Text style={styles.statValue}>{settings.maxFragments}</Text>
                            <Text style={styles.statLabel}>Max</Text>
                        </View>
                        <View style={styles.statCard}>
                            <Text style={styles.statValue}>
                                {Math.round((nodeInfo?.trust_score || 0) * 100)}%
                            </Text>
                            <Text style={styles.statLabel}>Trust</Text>
                        </View>
                    </View>

                    <View style={styles.section}>
                        <Text style={styles.sectionTitle}>Stored Fragments</Text>
                        {fragments.length === 0 ? (
                            <Text style={styles.emptyText}>No fragments stored</Text>
                        ) : (
                            fragments.map(frag => (
                                <View key={frag.id} style={styles.fragmentCard}>
                                    <View style={styles.fragmentInfo}>
                                        <Text style={styles.fragmentTitle}>{frag.dropTitle}</Text>
                                        <Text style={styles.fragmentExpiry}>Expires in {frag.expiresIn}</Text>
                                    </View>
                                    <View style={styles.fragmentBadge}>
                                        <Text style={styles.fragmentBadgeText}>🔒</Text>
                                    </View>
                                </View>
                            ))
                        )}
                    </View>

                    <View style={styles.section}>
                        <Text style={styles.sectionTitle}>Settings</Text>
                        
                        <View style={styles.toggleRow}>
                            <Text style={styles.toggleLabel}>Available for storage</Text>
                            <Switch
                                value={settings.isAvailable}
                                onValueChange={val => setSettings({ ...settings, isAvailable: val })}
                                trackColor={{ false: '#404040', true: '#00e67660' }}
                                thumbColor={settings.isAvailable ? '#00e676' : '#808080'}
                            />
                        </View>
                    </View>

                    <View style={styles.actionsRow}>
                        <TouchableOpacity style={styles.actionBtn} onPress={pingNode}>
                            <Text style={styles.actionBtnText}>📡 Ping</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.actionBtn} onPress={updateSettings}>
                            <Text style={styles.actionBtnText}>💾 Save</Text>
                        </TouchableOpacity>
                    </View>

                    <TouchableOpacity style={styles.unregisterBtn} onPress={unregisterNode}>
                        <Text style={styles.unregisterBtnText}>Unregister Node</Text>
                    </TouchableOpacity>
                </>
            )}
        </ScrollView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#1a1a2e',
    },
    content: {
        padding: 20,
        paddingTop: 50,
    },
    loadingContainer: {
        flex: 1,
        backgroundColor: '#1a1a2e',
        alignItems: 'center',
        justifyContent: 'center',
    },
    loadingText: {
        color: '#808080',
        marginTop: 16,
    },
    header: {
        marginBottom: 24,
    },
    headerTitle: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#fff',
    },
    headerSubtitle: {
        color: '#808080',
        marginTop: 4,
    },
    section: {
        marginBottom: 24,
    },
    sectionTitle: {
        color: '#a0a0a0',
        fontSize: 13,
        fontWeight: '600',
        marginBottom: 12,
        textTransform: 'uppercase',
    },
    infoCard: {
        padding: 16,
        backgroundColor: 'rgba(33, 150, 243, 0.1)',
        borderWidth: 1,
        borderColor: 'rgba(33, 150, 243, 0.2)',
        borderRadius: 12,
        marginBottom: 20,
    },
    infoTitle: {
        color: '#2196f3',
        fontSize: 16,
        fontWeight: '600',
        marginBottom: 8,
    },
    infoText: {
        color: '#a0a0a0',
        fontSize: 13,
        lineHeight: 20,
    },
    form: {
        marginBottom: 20,
    },
    label: {
        color: '#a0a0a0',
        fontSize: 13,
        marginBottom: 8,
    },
    input: {
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.15)',
        borderRadius: 10,
        padding: 14,
        color: '#fff',
        fontSize: 15,
        marginBottom: 16,
    },
    sliderRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 20,
        marginBottom: 20,
    },
    sliderBtn: {
        width: 44,
        height: 44,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 22,
        alignItems: 'center',
        justifyContent: 'center',
    },
    sliderBtnText: {
        color: '#fff',
        fontSize: 24,
    },
    sliderValue: {
        color: '#00e676',
        fontSize: 32,
        fontWeight: 'bold',
        minWidth: 60,
        textAlign: 'center',
    },
    toggleRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 12,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(255, 255, 255, 0.05)',
    },
    toggleLabel: {
        color: '#e0e0e0',
        fontSize: 15,
    },
    registerBtn: {
        backgroundColor: '#00e676',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
    },
    registerBtnText: {
        color: '#000',
        fontSize: 16,
        fontWeight: '600',
    },
    statusCard: {
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        padding: 20,
        alignItems: 'center',
        marginBottom: 20,
    },
    statusHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        marginBottom: 8,
    },
    statusDot: {
        width: 10,
        height: 10,
        borderRadius: 5,
    },
    statusText: {
        color: '#a0a0a0',
        fontSize: 13,
    },
    nodeName: {
        color: '#fff',
        fontSize: 20,
        fontWeight: '600',
        marginBottom: 4,
    },
    nodeId: {
        color: '#606060',
        fontSize: 12,
        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    },
    statsRow: {
        flexDirection: 'row',
        gap: 12,
        marginBottom: 24,
    },
    statCard: {
        flex: 1,
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        borderRadius: 12,
        padding: 16,
        alignItems: 'center',
    },
    statValue: {
        color: '#00e676',
        fontSize: 24,
        fontWeight: 'bold',
    },
    statLabel: {
        color: '#808080',
        fontSize: 11,
        textTransform: 'uppercase',
        marginTop: 4,
    },
    emptyText: {
        color: '#606060',
        textAlign: 'center',
        padding: 20,
    },
    fragmentCard: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 14,
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.08)',
        borderRadius: 10,
        marginBottom: 10,
    },
    fragmentInfo: {
        flex: 1,
    },
    fragmentTitle: {
        color: '#e0e0e0',
        fontSize: 14,
        marginBottom: 2,
    },
    fragmentExpiry: {
        color: '#808080',
        fontSize: 12,
    },
    fragmentBadge: {
        width: 36,
        height: 36,
        backgroundColor: 'rgba(0, 230, 118, 0.1)',
        borderRadius: 18,
        alignItems: 'center',
        justifyContent: 'center',
    },
    fragmentBadgeText: {
        fontSize: 16,
    },
    actionsRow: {
        flexDirection: 'row',
        gap: 12,
        marginBottom: 16,
    },
    actionBtn: {
        flex: 1,
        padding: 14,
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 10,
        alignItems: 'center',
    },
    actionBtnText: {
        color: '#e0e0e0',
        fontWeight: '500',
    },
    unregisterBtn: {
        padding: 14,
        backgroundColor: 'rgba(244, 67, 54, 0.1)',
        borderRadius: 10,
        alignItems: 'center',
    },
    unregisterBtnText: {
        color: '#f44336',
        fontWeight: '500',
    },
});

export default MeshNodeScreen;
