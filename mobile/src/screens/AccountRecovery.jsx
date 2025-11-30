import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import axios from 'axios';
import { API_URL } from '../config';

const AccountRecovery = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (!email) {
      Alert.alert('Error', 'Please enter your email address');
      return;
    }

    setLoading(true);
    
    try {
      await axios.post(`${API_URL}/api/auth/request_password_reset/`, {
        email,
      });
      
      setSubmitted(true);
    } catch (error) {
      Alert.alert(
        'Error',
        'An error occurred while sending the recovery email. Please try again later.'
      );
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Check Your Email</Text>
        <Text style={styles.description}>
          If an account exists with the email {email}, we've sent you instructions on how to reset your password.
        </Text>
        <Text style={styles.subtext}>
          Don't see the email? Check your spam folder.
        </Text>
        
        <TouchableOpacity
          style={styles.button}
          onPress={() => navigation.navigate('Login')}
        >
          <Text style={styles.buttonText}>Return to Login</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <Text style={styles.title}>Recover Your Account</Text>
      
      <Text style={styles.description}>
        Enter your email address and we'll send you a link to reset your master password.
      </Text>
      
      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        editable={!loading}
      />
      
      <TouchableOpacity
        style={styles.button}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>Send Reset Link</Text>
        )}
      </TouchableOpacity>
      
      <TouchableOpacity
        style={styles.textButton}
        onPress={() => navigation.navigate('Login')}
        disabled={loading}
      >
        <Text style={styles.textButtonText}>Back to Login</Text>
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    padding: 24,
    justifyContent: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  description: {
    fontSize: 16,
    color: '#4B5563',
    marginBottom: 24,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  button: {
    backgroundColor: '#4A6CF7',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 16,
  },
  textButton: {
    padding: 16,
    alignItems: 'center',
  },
  textButtonText: {
    color: '#4A6CF7',
    fontWeight: '500',
  },
  subtext: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 24,
    fontStyle: 'italic',
  },
});

export default AccountRecovery;
