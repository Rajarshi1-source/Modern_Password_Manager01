/**
 * TrustedZonesScreen - Mobile
 * 
 * Screen for managing trusted geofence zones.
 * Users can add, edit, and delete trusted locations like home and office.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    FlatList,
    TouchableOpacity,
    TextInput,
    Modal,
    Alert,
    ActivityIndicator,
    RefreshControl,
    Dimensions,
    Platform,
} from 'react-native';
import MapView, { Marker, Circle } from 'react-native-maps';
import Slider from '@react-native-community/slider';
import geolocationService from '../services/GeolocationService';

const { width } = Dimensions.get('window');

const TrustedZonesScreen = ({ navigation }) => {
    const [zones, setZones] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [editingZone, setEditingZone] = useState(null);
    const [currentLocation, setCurrentLocation] = useState(null);
    
    // Form state
    const [formData, setFormData] = useState({
        name: '',
        latitude: '',
        longitude: '',
        radius_meters: 500,
        is_always_trusted: true,
        require_mfa_outside: true,
    });

    // Fetch zones
    const fetchZones = useCallback(async () => {
        try {
            const data = await geolocationService.getGeofenceZones();
            setZones(data.zones || []);
        } catch (error) {
            console.error('Failed to fetch zones:', error);
            Alert.alert('Error', 'Failed to load trusted zones');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    // Get current location
    const getCurrentLocation = useCallback(async () => {
        try {
            const hasPermission = await geolocationService.checkPermissions();
            if (!hasPermission) {
                await geolocationService.requestPermissions();
            }
            
            const position = await geolocationService.getCurrentPosition({
                enableHighAccuracy: true,
            });
            
            setCurrentLocation({
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
            });
        } catch (error) {
            console.error('Location error:', error);
        }
    }, []);

    useEffect(() => {
        fetchZones();
        getCurrentLocation();
    }, [fetchZones, getCurrentLocation]);

    // Use current location
    const useCurrentLocationForZone = () => {
        if (currentLocation) {
            setFormData({
                ...formData,
                latitude: currentLocation.latitude.toFixed(7),
                longitude: currentLocation.longitude.toFixed(7),
            });
        } else {
            Alert.alert('Error', 'Current location not available');
        }
    };

    // Create zone
    const handleCreateZone = async () => {
        if (!formData.name || !formData.latitude || !formData.longitude) {
            Alert.alert('Error', 'Please fill in all required fields');
            return;
        }

        try {
            await geolocationService.createZone({
                ...formData,
                latitude: parseFloat(formData.latitude),
                longitude: parseFloat(formData.longitude),
            });
            
            Alert.alert('Success', 'Trusted zone created');
            resetForm();
            fetchZones();
        } catch (error) {
            console.error('Create failed:', error);
            Alert.alert('Error', 'Failed to create zone');
        }
    };

    // Delete zone
    const handleDeleteZone = (zoneId, zoneName) => {
        Alert.alert(
            'Delete Zone',
            `Are you sure you want to delete "${zoneName}"?`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            await geolocationService.deleteZone(zoneId);
                            fetchZones();
                        } catch (error) {
                            Alert.alert('Error', 'Failed to delete zone');
                        }
                    },
                },
            ]
        );
    };

    // Reset form
    const resetForm = () => {
        setModalVisible(false);
        setEditingZone(null);
        setFormData({
            name: '',
            latitude: '',
            longitude: '',
            radius_meters: 500,
            is_always_trusted: true,
            require_mfa_outside: true,
        });
    };

    // Get zone icon
    const getZoneIcon = (name) => {
        const lower = name.toLowerCase();
        if (lower.includes('home')) return '🏠';
        if (lower.includes('office') || lower.includes('work')) return '🏢';
        if (lower.includes('gym')) return '🏋️';
        if (lower.includes('school') || lower.includes('university')) return '🎓';
        return '📍';
    };

    // Render zone item
    const renderZoneItem = ({ item }) => (
        <View style={styles.zoneCard}>
            <View style={styles.zoneIcon}>
                <Text style={styles.zoneEmoji}>{getZoneIcon(item.name)}</Text>
            </View>
            <View style={styles.zoneInfo}>
                <Text style={styles.zoneName}>{item.name}</Text>
                <Text style={styles.zoneCoords}>
                    {parseFloat(item.latitude).toFixed(4)}, {parseFloat(item.longitude).toFixed(4)}
                </Text>
                <View style={styles.zoneBadges}>
                    <View style={styles.radiusBadge}>
                        <Text style={styles.badgeText}>{item.radius_meters}m</Text>
                    </View>
                    {item.is_always_trusted && (
                        <View style={[styles.badge, styles.trustedBadge]}>
                            <Text style={styles.badgeText}>🔓 No MFA</Text>
                        </View>
                    )}
                </View>
            </View>
            <TouchableOpacity
                style={styles.deleteButton}
                onPress={() => handleDeleteZone(item.id, item.name)}
            >
                <Text style={styles.deleteButtonText}>🗑️</Text>
            </TouchableOpacity>
        </View>
    );

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#3b82f6" />
                <Text style={styles.loadingText}>Loading trusted zones...</Text>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={styles.header}>
                <Text style={styles.title}>🛡️ Trusted Zones</Text>
                <Text style={styles.subtitle}>
                    Define locations where MFA is not required
                </Text>
            </View>

            {/* Map Preview */}
            {currentLocation && (
                <View style={styles.mapContainer}>
                    <MapView
                        style={styles.map}
                        initialRegion={{
                            ...currentLocation,
                            latitudeDelta: 0.05,
                            longitudeDelta: 0.05,
                        }}
                    >
                        <Marker
                            coordinate={currentLocation}
                            title="You are here"
                            pinColor="#3b82f6"
                        />
                        {zones.map((zone) => (
                            <React.Fragment key={zone.id}>
                                <Marker
                                    coordinate={{
                                        latitude: parseFloat(zone.latitude),
                                        longitude: parseFloat(zone.longitude),
                                    }}
                                    title={zone.name}
                                    pinColor="#22c55e"
                                />
                                <Circle
                                    center={{
                                        latitude: parseFloat(zone.latitude),
                                        longitude: parseFloat(zone.longitude),
                                    }}
                                    radius={zone.radius_meters}
                                    fillColor="rgba(34, 197, 94, 0.2)"
                                    strokeColor="rgba(34, 197, 94, 0.8)"
                                    strokeWidth={2}
                                />
                            </React.Fragment>
                        ))}
                    </MapView>
                </View>
            )}

            {/* Zones List */}
            <FlatList
                data={zones}
                keyExtractor={(item) => item.id}
                renderItem={renderZoneItem}
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={() => {
                            setRefreshing(true);
                            fetchZones();
                        }}
                        tintColor="#3b82f6"
                    />
                }
                ListEmptyComponent={
                    <View style={styles.emptyContainer}>
                        <Text style={styles.emptyIcon}>📍</Text>
                        <Text style={styles.emptyText}>No trusted zones defined</Text>
                        <Text style={styles.emptyHint}>
                            Add your home or office to skip MFA when logging in
                        </Text>
                    </View>
                }
                contentContainerStyle={styles.listContent}
            />

            {/* Add Button */}
            <TouchableOpacity
                style={styles.addButton}
                onPress={() => setModalVisible(true)}
            >
                <Text style={styles.addButtonText}>+ Add Zone</Text>
            </TouchableOpacity>

            {/* Add Zone Modal */}
            <Modal
                visible={modalVisible}
                animationType="slide"
                presentationStyle="pageSheet"
                onRequestClose={resetForm}
            >
                <View style={styles.modalContainer}>
                    <View style={styles.modalHeader}>
                        <TouchableOpacity onPress={resetForm}>
                            <Text style={styles.cancelText}>Cancel</Text>
                        </TouchableOpacity>
                        <Text style={styles.modalTitle}>Add Trusted Zone</Text>
                        <TouchableOpacity onPress={handleCreateZone}>
                            <Text style={styles.saveText}>Save</Text>
                        </TouchableOpacity>
                    </View>

                    <View style={styles.modalContent}>
                        <View style={styles.formGroup}>
                            <Text style={styles.label}>Zone Name *</Text>
                            <TextInput
                                style={styles.input}
                                placeholder="e.g., Home, Office"
                                placeholderTextColor="#64748b"
                                value={formData.name}
                                onChangeText={(text) =>
                                    setFormData({ ...formData, name: text })
                                }
                            />
                        </View>

                        <View style={styles.formRow}>
                            <View style={[styles.formGroup, { flex: 1, marginRight: 8 }]}>
                                <Text style={styles.label}>Latitude</Text>
                                <TextInput
                                    style={styles.input}
                                    placeholder="28.6139"
                                    placeholderTextColor="#64748b"
                                    keyboardType="numeric"
                                    value={formData.latitude}
                                    onChangeText={(text) =>
                                        setFormData({ ...formData, latitude: text })
                                    }
                                />
                            </View>
                            <View style={[styles.formGroup, { flex: 1, marginLeft: 8 }]}>
                                <Text style={styles.label}>Longitude</Text>
                                <TextInput
                                    style={styles.input}
                                    placeholder="77.2090"
                                    placeholderTextColor="#64748b"
                                    keyboardType="numeric"
                                    value={formData.longitude}
                                    onChangeText={(text) =>
                                        setFormData({ ...formData, longitude: text })
                                    }
                                />
                            </View>
                        </View>

                        <TouchableOpacity
                            style={styles.locationButton}
                            onPress={useCurrentLocationForZone}
                        >
                            <Text style={styles.locationButtonText}>
                                📍 Use Current Location
                            </Text>
                        </TouchableOpacity>

                        <View style={styles.formGroup}>
                            <Text style={styles.label}>
                                Radius: {formData.radius_meters}m
                            </Text>
                            <Slider
                                style={styles.slider}
                                minimumValue={50}
                                maximumValue={5000}
                                step={50}
                                value={formData.radius_meters}
                                onValueChange={(value) =>
                                    setFormData({ ...formData, radius_meters: value })
                                }
                                minimumTrackTintColor="#3b82f6"
                                maximumTrackTintColor="#1e293b"
                                thumbTintColor="#3b82f6"
                            />
                            <View style={styles.sliderLabels}>
                                <Text style={styles.sliderLabel}>50m</Text>
                                <Text style={styles.sliderLabel}>5km</Text>
                            </View>
                        </View>

                        <TouchableOpacity
                            style={styles.checkboxRow}
                            onPress={() =>
                                setFormData({
                                    ...formData,
                                    is_always_trusted: !formData.is_always_trusted,
                                })
                            }
                        >
                            <View
                                style={[
                                    styles.checkbox,
                                    formData.is_always_trusted && styles.checkboxChecked,
                                ]}
                            >
                                {formData.is_always_trusted && (
                                    <Text style={styles.checkmark}>✓</Text>
                                )}
                            </View>
                            <Text style={styles.checkboxLabel}>
                                Skip MFA in this zone
                            </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.checkboxRow}
                            onPress={() =>
                                setFormData({
                                    ...formData,
                                    require_mfa_outside: !formData.require_mfa_outside,
                                })
                            }
                        >
                            <View
                                style={[
                                    styles.checkbox,
                                    formData.require_mfa_outside && styles.checkboxChecked,
                                ]}
                            >
                                {formData.require_mfa_outside && (
                                    <Text style={styles.checkmark}>✓</Text>
                                )}
                            </View>
                            <Text style={styles.checkboxLabel}>
                                Require MFA outside all zones
                            </Text>
                        </TouchableOpacity>
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
    mapContainer: {
        height: 200,
        marginHorizontal: 16,
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 16,
    },
    map: {
        flex: 1,
    },
    listContent: {
        padding: 16,
        paddingBottom: 100,
    },
    zoneCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 12,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    zoneIcon: {
        width: 48,
        height: 48,
        borderRadius: 24,
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    zoneEmoji: {
        fontSize: 24,
    },
    zoneInfo: {
        flex: 1,
        marginLeft: 12,
    },
    zoneName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#e2e8f0',
    },
    zoneCoords: {
        fontSize: 12,
        color: '#94a3b8',
        marginTop: 2,
    },
    zoneBadges: {
        flexDirection: 'row',
        marginTop: 8,
        gap: 8,
    },
    radiusBadge: {
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 12,
    },
    badge: {
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 12,
    },
    trustedBadge: {
        backgroundColor: 'rgba(34, 197, 94, 0.2)',
    },
    badgeText: {
        fontSize: 12,
        color: '#e2e8f0',
    },
    deleteButton: {
        padding: 8,
    },
    deleteButtonText: {
        fontSize: 20,
    },
    emptyContainer: {
        alignItems: 'center',
        padding: 40,
    },
    emptyIcon: {
        fontSize: 48,
        marginBottom: 16,
    },
    emptyText: {
        fontSize: 16,
        color: '#e2e8f0',
    },
    emptyHint: {
        fontSize: 14,
        color: '#94a3b8',
        textAlign: 'center',
        marginTop: 8,
    },
    addButton: {
        position: 'absolute',
        bottom: 32,
        left: 16,
        right: 16,
        backgroundColor: '#3b82f6',
        paddingVertical: 16,
        borderRadius: 12,
        alignItems: 'center',
    },
    addButtonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    modalContainer: {
        flex: 1,
        backgroundColor: '#0f172a',
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: 16,
        paddingTop: Platform.OS === 'ios' ? 60 : 16,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(255, 255, 255, 0.1)',
    },
    cancelText: {
        color: '#94a3b8',
        fontSize: 16,
    },
    modalTitle: {
        color: '#e2e8f0',
        fontSize: 18,
        fontWeight: '600',
    },
    saveText: {
        color: '#3b82f6',
        fontSize: 16,
        fontWeight: '600',
    },
    modalContent: {
        padding: 20,
    },
    formGroup: {
        marginBottom: 20,
    },
    formRow: {
        flexDirection: 'row',
        marginBottom: 12,
    },
    label: {
        color: '#94a3b8',
        fontSize: 14,
        marginBottom: 8,
    },
    input: {
        backgroundColor: 'rgba(15, 23, 42, 0.8)',
        borderRadius: 8,
        padding: 14,
        color: '#e2e8f0',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    locationButton: {
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        padding: 14,
        borderRadius: 8,
        alignItems: 'center',
        marginBottom: 20,
    },
    locationButtonText: {
        color: '#93c5fd',
        fontSize: 14,
        fontWeight: '500',
    },
    slider: {
        width: '100%',
        height: 40,
    },
    sliderLabels: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    sliderLabel: {
        color: '#64748b',
        fontSize: 12,
    },
    checkboxRow: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: 12,
    },
    checkbox: {
        width: 24,
        height: 24,
        borderRadius: 6,
        borderWidth: 2,
        borderColor: '#64748b',
        marginRight: 12,
        justifyContent: 'center',
        alignItems: 'center',
    },
    checkboxChecked: {
        backgroundColor: '#3b82f6',
        borderColor: '#3b82f6',
    },
    checkmark: {
        color: '#fff',
        fontWeight: '700',
    },
    checkboxLabel: {
        color: '#e2e8f0',
        fontSize: 14,
    },
});

export default TrustedZonesScreen;
