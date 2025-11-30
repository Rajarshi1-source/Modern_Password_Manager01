import React, { useState, useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import Constants from 'expo-constants';
import { Route } from 'react-router-dom';

// Import our custom AppNavigator
import AppNavigator from './src/navigation/AppNavigator';
import EmergencyAccess from './src/screens/EmergencyAccess';
import EmergencyVaultAccess from './src/screens/EmergencyVaultAccess';

// This variable determines which navigation system to use
// Set to false if you want to use Expo Router screens instead
const USE_CUSTOM_NAVIGATOR = true;

export default function App() {
  // If we're not using our custom navigator, we should load the expo-router entry
  if (!USE_CUSTOM_NAVIGATOR) {
    // This will dynamically import the Expo Router entry
    const ExpoRouter = require('expo-router/entry');
    return <ExpoRouter />;
  }

  // Use our custom AppNavigator
  return (
    <SafeAreaProvider>
      <View style={styles.container}>
        <StatusBar style="auto" />
        <AppNavigator />
        <Route path="/emergency-access" element={<EmergencyAccess />} />
        <Route path="/emergency-vault/:requestId" element={<EmergencyVaultAccess />} />
      </View>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
