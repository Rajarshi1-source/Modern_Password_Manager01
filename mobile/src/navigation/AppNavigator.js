import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { MenuItem } from 'react-native-elements';
import { FaUserShield } from 'react-icons/fa';

// Import screens
import Login from '../screens/Login';
import Settings from '../screens/Settings';
// Assuming Vault screen exists based on navigation in Login.jsx
import Vault from '../screens/Vault';
import AccountRecovery from '../screens/AccountRecovery';

// Import geofencing screens
import GeofenceScreen from '../screens/GeofenceScreen';
import TrustedZonesScreen from '../screens/TrustedZonesScreen';

// Import natural entropy screen
import NaturalEntropyScreen from '../screens/NaturalEntropyScreen';

// Import duress code screen
import DuressCodeScreen from '../screens/DuressCodeScreen';

// Import auth service
import { authService } from '../services/authService';

const AuthStack = createStackNavigator();
const MainStack = createStackNavigator();
const Tab = createBottomTabNavigator();

// Authentication stack - shown when user is not logged in
const AuthNavigator = () => (
  <AuthStack.Navigator screenOptions={{ headerShown: false }}>
    <AuthStack.Screen name="Login" component={Login} />
    <AuthStack.Screen name="AccountRecovery" component={AccountRecovery} />
  </AuthStack.Navigator>
);

// Main tab navigator - shown after authentication
const MainTabNavigator = () => {
  const navigation = useNavigation();

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName;

          if (route.name === 'Vault') {
            iconName = focused ? 'ios-lock-closed' : 'ios-lock-closed-outline';
          } else if (route.name === 'SettingsStack') {
            iconName = focused ? 'ios-settings' : 'ios-settings-outline';
          } else if (route.name === 'Geofence') {
            iconName = focused ? 'ios-location' : 'ios-location-outline';
          }

          return <Ionicons name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#4A6CF7',
        tabBarInactiveTintColor: 'gray',
      })}
    >
      <Tab.Screen 
        name="Vault" 
        component={Vault} 
        options={{ headerTitle: 'Password Vault' }}
      />
      <Tab.Screen 
        name="Geofence" 
        component={GeofenceNavigator} 
        options={{ 
          headerShown: false, 
          tabBarLabel: 'Location',
          tabBarBadge: undefined // Can show alert count here
        }}
      />
      <Tab.Screen 
        name="SettingsStack" 
        component={SettingsNavigator} 
        options={{ headerShown: false, tabBarLabel: 'Settings' }}
      />
      <Tab.Screen 
        name="EmergencyAccess" 
        component={EmergencyAccess} 
        options={{ headerTitle: 'Emergency Access' }}
      />
    </Tab.Navigator>
  );
};

// Geofence navigation stack
const GeofenceNavigator = () => (
  <MainStack.Navigator>
    <MainStack.Screen 
      name="GeofenceMain" 
      component={GeofenceScreen}
      options={{ headerShown: false }}
    />
    <MainStack.Screen 
      name="TrustedZones" 
      component={TrustedZonesScreen}
      options={{ headerTitle: 'Trusted Zones' }}
    />
  </MainStack.Navigator>
);

// Settings stack
const SettingsNavigator = () => (
  <MainStack.Navigator>
    <MainStack.Screen 
      name="Settings" 
      component={Settings}
      options={{ headerTitle: 'Settings' }}
    />
    <MainStack.Screen 
      name="NaturalEntropy" 
      component={NaturalEntropyScreen}
      options={{ headerTitle: 'Natural Entropy' }}
    />
    <MainStack.Screen 
      name="DuressCode" 
      component={DuressCodeScreen}
      options={{ headerTitle: 'Duress Protection', headerShown: false }}
    />
  </MainStack.Navigator>
);

// Root navigator - switches between auth and main flows
const AppNavigator = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check authentication status on app load
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const authenticated = await authService.isAuthenticated();
      setIsAuthenticated(authenticated);
    } catch (error) {
      console.error('Error checking authentication status:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    // You could return a loading screen component here
    return null;
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <MainTabNavigator /> : <AuthNavigator />}
    </NavigationContainer>
  );
};

export default AppNavigator;
