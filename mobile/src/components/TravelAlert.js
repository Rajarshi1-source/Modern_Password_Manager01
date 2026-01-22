/**
 * TravelAlert Component - Mobile
 * 
 * Displays impossible travel alerts as push notification-style cards.
 * Allows users to verify legitimate travel or report unauthorized access.
 */

import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    Modal,
    TextInput,
    ActivityIndicator,
    Alert,
    Animated,
    Dimensions,
} from 'react-native';
import geolocationService from '../services/GeolocationService';

const { width } = Dimensions.get('window');

const TravelAlert = ({
    event,
    visible,
    onDismiss,
    onResolved,
}) => {
    const [resolving, setResolving] = useState(false);
    const [showVerifyModal, setShowVerifyModal] = useState(false);
    const [bookingRef, setBookingRef] = useState('');
    const [lastName, setLastName] = useState('');
    const [verifying, setVerifying] = useState(false);

    if (!event) return null;

    // Format speed for display
    const formatSpeed = (speed) => {
        if (speed > 1000) {
            return `${(speed / 1000).toFixed(1)}k`;
        }
        return Math.round(speed);
    };

    // Format time difference
    const formatTimeDiff = (seconds) => {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${(seconds / 3600).toFixed(1)}h`;
    };

    // Get severity color
    const getSeverityColor = (severity) => {
        const colors = {
            low: '#84cc16',
            medium: '#eab308',
            high: '#f97316',
            critical: '#ef4444',
        };
        return colors[severity] || colors.medium;
    };

    // Get travel mode icon
    const getTravelModeIcon = (mode) => {
        const icons = {
            walking: '🚶',
            driving: '🚗',
            train: '🚄',
            flight: '✈️',
            supersonic: '🚀',
            unknown: '❓',
        };
        return icons[mode] || icons.unknown;
    };

    // Handle "This was me" action
    const handleConfirmLegitimate = async () => {
        setResolving(true);
        try {
            await geolocationService.resolveTravelEvent(
                event.id,
                true,
                'User confirmed as legitimate travel'
            );
            Alert.alert('Confirmed', 'Travel marked as legitimate');
            onResolved?.();
            onDismiss?.();
        } catch (error) {
            Alert.alert('Error', 'Failed to confirm travel');
        } finally {
            setResolving(false);
        }
    };

    // Handle "Block" action
    const handleReportUnauthorized = async () => {
        Alert.alert(
            'Report Unauthorized Access',
            'This will block the session and log out all devices. Continue?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Block',
                    style: 'destructive',
                    onPress: async () => {
                        setResolving(true);
                        try {
                            await geolocationService.resolveTravelEvent(
                                event.id,
                                false,
                                'User reported as unauthorized access'
                            );
                            Alert.alert(
                                'Session Blocked',
                                'All sessions have been terminated. Please change your password.'
                            );
                            onResolved?.();
                            onDismiss?.();
                        } catch (error) {
                            Alert.alert('Error', 'Failed to block session');
                        } finally {
                            setResolving(false);
                        }
                    },
                },
            ]
        );
    };

    // Handle booking verification
    const handleVerifyBooking = async () => {
        if (!bookingRef || !lastName) {
            Alert.alert('Error', 'Please enter booking reference and last name');
            return;
        }

        setVerifying(true);
        try {
            const result = await geolocationService.verifyBooking(bookingRef, lastName);
            
            if (result.verified) {
                Alert.alert(
                    '✅ Travel Verified',
                    'Your booking has been verified successfully!'
                );
                setShowVerifyModal(false);
                onResolved?.();
                onDismiss?.();
            } else {
                Alert.alert(
                    'Verification Failed',
                    result.message || 'Could not verify booking'
                );
            }
        } catch (error) {
            Alert.alert('Error', 'Failed to verify booking');
        } finally {
            setVerifying(false);
        }
    };

    return (
        <Modal
            visible={visible}
            animationType="slide"
            transparent={true}
            onRequestClose={onDismiss}
        >
            <View style={styles.overlay}>
                <View style={styles.alertCard}>
                    {/* Header */}
                    <View style={[
                        styles.header,
                        { backgroundColor: getSeverityColor(event.severity) }
                    ]}>
                        <Text style={styles.headerIcon}>
                            {getTravelModeIcon(event.inferred_travel_mode)}
                        </Text>
                        <Text style={styles.headerTitle}>
                            {event.severity === 'critical'
                                ? 'Impossible Travel Detected'
                                : 'Unusual Travel Pattern'}
                        </Text>
                    </View>

                    {/* Content */}
                    <View style={styles.content}>
                        {/* Travel Details */}
                        <View style={styles.detailsSection}>
                            <View style={styles.locationRow}>
                                <View style={styles.location}>
                                    <Text style={styles.locationLabel}>From</Text>
                                    <Text style={styles.locationValue}>
                                        {event.source_city || 'Unknown Location'}
                                    </Text>
                                </View>
                                <Text style={styles.arrow}>→</Text>
                                <View style={styles.location}>
                                    <Text style={styles.locationLabel}>To</Text>
                                    <Text style={styles.locationValue}>
                                        {event.destination_city || 'Current Location'}
                                    </Text>
                                </View>
                            </View>

                            <View style={styles.statsRow}>
                                <View style={styles.stat}>
                                    <Text style={styles.statValue}>
                                        {event.distance_km?.toFixed(0)} km
                                    </Text>
                                    <Text style={styles.statLabel}>Distance</Text>
                                </View>
                                <View style={styles.stat}>
                                    <Text style={styles.statValue}>
                                        {formatTimeDiff(event.time_difference_seconds)}
                                    </Text>
                                    <Text style={styles.statLabel}>Time Gap</Text>
                                </View>
                                <View style={styles.stat}>
                                    <Text style={[
                                        styles.statValue,
                                        event.required_speed_kmh > 920 && styles.criticalText
                                    ]}>
                                        {formatSpeed(event.required_speed_kmh)} km/h
                                    </Text>
                                    <Text style={styles.statLabel}>Required Speed</Text>
                                </View>
                            </View>
                        </View>

                        {/* Warning Message */}
                        {event.severity === 'critical' && (
                            <View style={styles.warningBox}>
                                <Text style={styles.warningIcon}>⚠️</Text>
                                <Text style={styles.warningText}>
                                    This travel speed exceeds commercial flight limits.
                                    This could indicate a compromised account.
                                </Text>
                            </View>
                        )}

                        {/* Actions */}
                        <View style={styles.actions}>
                            <TouchableOpacity
                                style={styles.verifyButton}
                                onPress={() => setShowVerifyModal(true)}
                                disabled={resolving}
                            >
                                <Text style={styles.verifyButtonText}>
                                    ✈️ Verify with Booking
                                </Text>
                            </TouchableOpacity>

                            <View style={styles.buttonRow}>
                                <TouchableOpacity
                                    style={[styles.button, styles.confirmButton]}
                                    onPress={handleConfirmLegitimate}
                                    disabled={resolving}
                                >
                                    {resolving ? (
                                        <ActivityIndicator color="#fff" size="small" />
                                    ) : (
                                        <Text style={styles.buttonText}>✓ This was me</Text>
                                    )}
                                </TouchableOpacity>

                                <TouchableOpacity
                                    style={[styles.button, styles.blockButton]}
                                    onPress={handleReportUnauthorized}
                                    disabled={resolving}
                                >
                                    <Text style={styles.buttonText}>🚫 Block</Text>
                                </TouchableOpacity>
                            </View>

                            <TouchableOpacity
                                style={styles.dismissButton}
                                onPress={onDismiss}
                            >
                                <Text style={styles.dismissText}>Dismiss</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </View>

            {/* Booking Verification Modal */}
            <Modal
                visible={showVerifyModal}
                animationType="fade"
                transparent={true}
                onRequestClose={() => setShowVerifyModal(false)}
            >
                <View style={styles.overlay}>
                    <View style={styles.verifyModalContent}>
                        <Text style={styles.verifyTitle}>Verify Your Booking</Text>
                        <Text style={styles.verifySubtitle}>
                            Enter your flight booking details to verify legitimate travel
                        </Text>

                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Booking Reference (PNR)</Text>
                            <TextInput
                                style={styles.input}
                                placeholder="e.g., ABC123"
                                placeholderTextColor="#64748b"
                                value={bookingRef}
                                onChangeText={setBookingRef}
                                autoCapitalize="characters"
                            />
                        </View>

                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Last Name</Text>
                            <TextInput
                                style={styles.input}
                                placeholder="As it appears on booking"
                                placeholderTextColor="#64748b"
                                value={lastName}
                                onChangeText={setLastName}
                                autoCapitalize="characters"
                            />
                        </View>

                        <TouchableOpacity
                            style={styles.verifySubmitButton}
                            onPress={handleVerifyBooking}
                            disabled={verifying}
                        >
                            {verifying ? (
                                <ActivityIndicator color="#fff" />
                            ) : (
                                <Text style={styles.verifySubmitText}>
                                    Verify Booking
                                </Text>
                            )}
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.verifyCancelButton}
                            onPress={() => setShowVerifyModal(false)}
                        >
                            <Text style={styles.verifyCancelText}>Cancel</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
        </Modal>
    );
};

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20,
    },
    alertCard: {
        width: width - 40,
        backgroundColor: '#1e293b',
        borderRadius: 16,
        overflow: 'hidden',
        maxHeight: '90%',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 16,
        gap: 12,
    },
    headerIcon: {
        fontSize: 28,
    },
    headerTitle: {
        color: '#fff',
        fontSize: 18,
        fontWeight: '700',
        flex: 1,
    },
    content: {
        padding: 20,
    },
    detailsSection: {
        marginBottom: 20,
    },
    locationRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 20,
    },
    location: {
        flex: 1,
    },
    locationLabel: {
        color: '#94a3b8',
        fontSize: 12,
        marginBottom: 4,
    },
    locationValue: {
        color: '#e2e8f0',
        fontSize: 16,
        fontWeight: '600',
    },
    arrow: {
        color: '#64748b',
        fontSize: 24,
        marginHorizontal: 12,
    },
    statsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        backgroundColor: 'rgba(15, 23, 42, 0.5)',
        borderRadius: 12,
        padding: 16,
    },
    stat: {
        alignItems: 'center',
    },
    statValue: {
        color: '#e2e8f0',
        fontSize: 18,
        fontWeight: '700',
    },
    statLabel: {
        color: '#94a3b8',
        fontSize: 12,
        marginTop: 4,
    },
    criticalText: {
        color: '#ef4444',
    },
    warningBox: {
        flexDirection: 'row',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderRadius: 12,
        padding: 14,
        marginBottom: 20,
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.3)',
    },
    warningIcon: {
        fontSize: 20,
        marginRight: 12,
    },
    warningText: {
        color: '#fca5a5',
        fontSize: 14,
        flex: 1,
        lineHeight: 20,
    },
    actions: {
        gap: 12,
    },
    verifyButton: {
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: 'rgba(59, 130, 246, 0.3)',
    },
    verifyButtonText: {
        color: '#93c5fd',
        fontSize: 16,
        fontWeight: '600',
    },
    buttonRow: {
        flexDirection: 'row',
        gap: 12,
    },
    button: {
        flex: 1,
        padding: 14,
        borderRadius: 12,
        alignItems: 'center',
    },
    confirmButton: {
        backgroundColor: '#22c55e',
    },
    blockButton: {
        backgroundColor: '#ef4444',
    },
    buttonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    dismissButton: {
        padding: 12,
        alignItems: 'center',
    },
    dismissText: {
        color: '#94a3b8',
        fontSize: 14,
    },
    verifyModalContent: {
        width: width - 40,
        backgroundColor: '#1e293b',
        borderRadius: 16,
        padding: 24,
    },
    verifyTitle: {
        color: '#e2e8f0',
        fontSize: 20,
        fontWeight: '700',
        textAlign: 'center',
        marginBottom: 8,
    },
    verifySubtitle: {
        color: '#94a3b8',
        fontSize: 14,
        textAlign: 'center',
        marginBottom: 24,
    },
    inputGroup: {
        marginBottom: 16,
    },
    inputLabel: {
        color: '#94a3b8',
        fontSize: 14,
        marginBottom: 8,
    },
    input: {
        backgroundColor: 'rgba(15, 23, 42, 0.8)',
        borderRadius: 8,
        padding: 14,
        color: '#e2e8f0',
        fontSize: 16,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    verifySubmitButton: {
        backgroundColor: '#3b82f6',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginTop: 8,
    },
    verifySubmitText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    verifyCancelButton: {
        padding: 16,
        alignItems: 'center',
    },
    verifyCancelText: {
        color: '#94a3b8',
        fontSize: 14,
    },
});

export default TravelAlert;
