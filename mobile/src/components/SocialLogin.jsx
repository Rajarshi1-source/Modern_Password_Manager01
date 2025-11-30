import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import * as AuthSession from 'expo-auth-session';
import { API_URL } from '../config';

// Initialize WebBrowser for OAuth
WebBrowser.maybeCompleteAuthSession();

const SocialLogin = ({ onLoginSuccess }) => {
  const handleGoogleLogin = async () => {
    try {
      // Get discovery document for Google
      const discovery = await AuthSession.fetchDiscoveryAsync(
        'https://accounts.google.com'
      );
      
      // Create a request
      const request = new AuthSession.AuthRequest({
        clientId: 'YOUR_GOOGLE_CLIENT_ID',
        redirectUri: AuthSession.makeRedirectUri({
          scheme: 'passwordmanager',
          path: '/oauth-callback'
        }),
        scopes: ['profile', 'email'],
        usePKCE: true,
        codeChallenge: AuthSession.CodeChallenge.S256
      });
      
      // Prompt for authorization
      const result = await request.promptAsync(discovery);
      
      if (result.type === 'success') {
        // Exchange the authorization code for a token
        const tokenResult = await fetch(`${API_URL}/api/auth/social/google/complete/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: result.params.code,
            redirectUri: AuthSession.makeRedirectUri({
              scheme: 'passwordmanager',
              path: '/oauth-callback'
            }),
          }),
        }).then(res => res.json());
        
        if (tokenResult.token) {
          onLoginSuccess(tokenResult.token);
        }
      }
    } catch (error) {
      console.error('Google OAuth error:', error);
    }
  };

  const handleAppleLogin = async () => {
    // Similar implementation for Apple
  };

  return (
    <View style={styles.container}>
      <View style={styles.divider}>
        <View style={styles.line} />
        <Text style={styles.dividerText}>OR CONTINUE WITH</Text>
        <View style={styles.line} />
      </View>
      
      <TouchableOpacity style={[styles.button, styles.googleButton]} onPress={handleGoogleLogin}>
        <Ionicons name="logo-google" size={20} color="#FFF" />
        <Text style={styles.buttonText}>Continue with Google</Text>
      </TouchableOpacity>
      
      <TouchableOpacity style={[styles.button, styles.appleButton]} onPress={handleAppleLogin}>
        <Ionicons name="logo-apple" size={20} color="#FFF" />
        <Text style={styles.buttonText}>Continue with Apple</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    marginVertical: 20,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 20,
  },
  line: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5E7EB',
  },
  dividerText: {
    marginHorizontal: 10,
    color: '#6B7280',
    fontSize: 12,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  googleButton: {
    backgroundColor: '#DB4437',
  },
  appleButton: {
    backgroundColor: '#000',
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default SocialLogin;
