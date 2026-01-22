/**
 * GeofenceScreen - Mobile
 * 
 * Main screen for geofencing features on mobile.
 * Shows current location status, travel alerts, and navigation to sub-screens.
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
} from 'react-native';
import geolocationService from '../services/GeolocationService';
import TravelAlert from '../components/TravelAlert';

const GeofenceScreen = ({ navigation }) => {
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [currentLocation, setCurrentLocation] = useState(null);
    const [geofenceStatus, setGeofenceStatus] = useState(null);
    const [travelEvents, setTravelEvents] = useState([]);
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [stats, setStats] = useState({
        zones: 0,
        pendingEvents: 0,
        lastCheck: null,
    });

    // Fetch all data
    const fetchData = useCallback(async () => {
        try {
            // Get zones count
            const zonesData = await geolocationService.getGeofenceZones();
            
            // Get pending events
            const eventsData = await geolocationService.getTravelEvents({
                resolved: false,
                limit: 5,
            });

            // Get current location and check geofence
            const hasPermission = await geolocationService.checkPermissions();
            if (hasPermission) {
                try {
                    const position = await geolocationService.getCurrentPosition({
                        enableHighAccuracy: true,
                        timeout: 10000,
                    });
                    
                    setCurrentLocation({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                    });

                    // Check if in trusted zone
                    const geoCheck = await geolocationService.checkGeofence(
                        position.coords.latitude,
                        position.coords.longitude
                    );
                    setGeofenceStatus(geoCheck);
                } catch (locError) {
                    console.log('Location error:', locError);
                }
            }

            setStats({
                zones: zonesData.zones?.length || 0,
                pendingEvents: eventsData.count || 0,
                lastCheck: new Date().toISOString(),
            });
            setTravelEvents(eventsData.events || []);
        } catch (error) {
            console.error('Fetch error:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Handle location capture
    const handleCaptureLocation = async () => {
        try {
            Alert.alert('Capturing...', 'Getting your location');
            
            const result = await geolocationService.captureAndAnalyze();
            
            if (result.analysis && !result.analysis.is_plausible) {
                setSelectedEvent(result.analysis.event);
            } else {
                Alert.alert(
                    '✅ Location Recorded',
                    'Your location has been captured and analyzed.'
                );
            }
            fetchData();
        } catch (error) {
            Alert.alert('Error', 'Failed to capture location');
        }
    };

    // Get status color
    const getStatusColor = () => {
        if (!geofenceStatus) return '#64748b';
        return geofenceStatus.is_in_trusted_zone ? '#22c55e' : '#f97316';
    };

    // Get status text
    const getStatusText = () => {
        if (!geofenceStatus) return 'Unknown';
        return geofenceStatus.is_in_trusted_zone
            ? `In "${geofenceStatus.zone_name}"`
            : 'Outside Trusted Zones';
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#3b82f6" />
                <Text style={styles.loadingText}>Loading geofence data...</Text>
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
                        tintColor="#3b82f6"
                    />
                }
            >
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.title}>🌍 Geofencing</Text>
                    <Text style={styles.subtitle}>
                        Physics-based location security
                    </Text>
                </View>

                {/* Current Status Card */}
                <View style={styles.statusCard}>
                    <View style={styles.statusHeader}>
                        <View
                            style={[
                                styles.statusIndicator,
                                { backgroundColor: getStatusColor() },
                            ]}
                        />
                        <Text style={styles.statusTitle}>Current Status</Text>
                    </View>
                    
                    <Text style={styles.statusText}>{getStatusText()}</Text>
                    
                    {currentLocation && (
                        <Text style={styles.coordsText}>
                            📍 {currentLocation.latitude.toFixed(4)}, {currentLocation.longitude.toFixed(4)}
                            {currentLocation.accuracy && ` (±${Math.round(currentLocation.accuracy)}m)`}
                        </Text>
                    )}

                    <TouchableOpacity
                        style={styles.captureButton}
                        onPress={handleCaptureLocation}
                    >
                        <Text style={styles.captureButtonText}>
                            📍 Capture Current Location
                        </Text>
                    </TouchableOpacity>
                </View>

                {/* Stats Cards */}
                <View style={styles.statsRow}>
                    <TouchableOpacity
                        style={styles.statCard}
                        onPress={() => navigation.navigate('TrustedZones')}
                    >
                        <Text style={styles.statValue}>{stats.zones}</Text>
                        <Text style={styles.statLabel}>Trusted Zones</Text>
                        <Text style={styles.statIcon}>🛡️</Text>
                    </TouchableOpacity>

                    <View
                        style={[
                            styles.statCard,
                            stats.pendingEvents > 0 && styles.warningCard,
                        ]}
                    >
                        <Text style={styles.statValue}>{stats.pendingEvents}</Text>
                        <Text style={styles.statLabel}>Active Alerts</Text>
                        <Text style={styles.statIcon}>⚠️</Text>
                    </View>
                </View>

                {/* Travel Alerts */}
                {travelEvents.length > 0 && (
                    <View style={styles.alertsSection}>
                        <Text style={styles.sectionTitle}>🚨 Recent Alerts</Text>
                        {travelEvents.map((event) => (
                            <TouchableOpacity
                                key={event.id}
                                style={[
                                    styles.alertItem,
                                    event.severity === 'critical' && styles.criticalAlert,
                                ]}
                                onPress={() => setSelectedEvent(event)}
                            >
                                <View style={styles.alertContent}>
                                    <Text style={styles.alertTitle}>
                                        {event.severity === 'critical'
                                            ? '🚀 Impossible Travel'
                                            : '⚠️ Unusual Pattern'}
                                    </Text>
                                    <Text style={styles.alertMeta}>
                                        {event.distance_km?.toFixed(0)} km • 
                                        {Math.round(event.required_speed_kmh)} km/h
                                    </Text>
                                </View>
                                <Text style={styles.alertArrow}>→</Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                )}

                {/* Quick Actions */}
                <View style={styles.actionsSection}>
                    <Text style={styles.sectionTitle}>Quick Actions</Text>
                    
                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('TrustedZones')}
                    >
                        <Text style={styles.actionIcon}>🏠</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Manage Trusted Zones</Text>
                            <Text style={styles.actionSubtitle}>
                                Add home, office, or other locations
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('TravelItinerary')}
                    >
                        <Text style={styles.actionIcon}>✈️</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Travel Itineraries</Text>
                            <Text style={styles.actionSubtitle}>
                                Pre-register upcoming trips
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => navigation.navigate('LocationHistory')}
                    >
                        <Text style={styles.actionIcon}>📊</Text>
                        <View style={styles.actionContent}>
                            <Text style={styles.actionTitle}>Location History</Text>
                            <Text style={styles.actionSubtitle}>
                                View recorded locations
                            </Text>
                        </View>
                        <Text style={styles.actionArrow}>→</Text>
                    </TouchableOpacity>
                </View>

                {/* Info Box */}
                <View style={styles.infoBox}>
                    <Text style={styles.infoIcon}>ℹ️</Text>
                    <Text style={styles.infoText}>
                        Geofencing uses physics to detect impossible travel. 
                        Location data is encrypted and automatically deleted after 90 days.
                    </Text>
                </View>
            </ScrollView>

            {/* Travel Alert Modal */}
            <TravelAlert
                event={selectedEvent}
                visible={!!selectedEvent}
                onDismiss={() => setSelectedEvent(null)}
                onResolved={() => {
                    setSelectedEvent(null);
                    fetchData();
                }}
            />
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
        borderColor: 'rgba(255, 255, 255, 0.1)',
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
    coordsText: {
        color: '#64748b',
        fontSize: 12,
        marginTop: 8,
    },
    captureButton: {
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
        marginTop: 16,
        borderWidth: 1,
        borderColor: 'rgba(59, 130, 246, 0.3)',
    },
    captureButtonText: {
        color: '#93c5fd',
        fontSize: 15,
        fontWeight: '600',
    },
    statsRow: {
        flexDirection: 'row',
        paddingHorizontal: 16,
        gap: 12,
        marginBottom: 20,
    },
    statCard: {
        flex: 1,
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 16,
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
        fontSize: 28,
        fontWeight: '700',
    },
    statLabel: {
        color: '#94a3b8',
        fontSize: 12,
        marginTop: 4,
    },
    statIcon: {
        fontSize: 24,
        marginTop: 8,
    },
    alertsSection: {
        paddingHorizontal: 16,
        marginBottom: 20,
    },
    sectionTitle: {
        color: '#e2e8f0',
        fontSize: 16,
        fontWeight: '600',
        marginBottom: 12,
    },
    alertItem: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        borderRadius: 12,
        padding: 16,
        marginBottom: 8,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    criticalAlert: {
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
    },
    alertContent: {
        flex: 1,
    },
    alertTitle: {
        color: '#e2e8f0',
        fontSize: 15,
        fontWeight: '600',
    },
    alertMeta: {
        color: '#94a3b8',
        fontSize: 13,
        marginTop: 4,
    },
    alertArrow: {
        color: '#64748b',
        fontSize: 18,
    },
    actionsSection: {
        paddingHorizontal: 16,
        marginBottom: 20,
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
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderRadius: 12,
        padding: 14,
    },
    infoIcon: {
        fontSize: 18,
        marginRight: 10,
    },
    infoText: {
        color: '#93c5fd',
        fontSize: 13,
        flex: 1,
        lineHeight: 20,
    },
});

export default GeofenceScreen;
