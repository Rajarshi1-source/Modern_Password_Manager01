/**
 * Behavioral Context
 * 
 * Manages silent behavioral profile building during normal usage
 * Automatically captures behavioral data when user is logged in
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth.jsx';
import { behavioralCaptureEngine } from '../services/behavioralCapture';
import { behavioralDNAModel } from '../ml/behavioralDNA';
import { secureBehavioralStorage } from '../services/SecureBehavioralStorage';
import { kyberService } from '../services/quantum';
import axios from 'axios';

const BehavioralContext = createContext(null);

export const useBehavioral = () => {
  const context = useContext(BehavioralContext);
  if (!context) {
    throw new Error('useBehavioral must be used within BehavioralProvider');
  }
  return context;
};

export const BehavioralProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuth();

  const [isCapturing, setIsCapturing] = useState(false);
  const [profileStats, setProfileStats] = useState(null);
  const [commitmentStatus, setCommitmentStatus] = useState({
    has_commitments: false,
    ready_for_recovery: false
  });

  // Use ref to store interval ID instead of window object (prevents memory leaks)
  const statsIntervalRef = useRef(null);

  /**
   * Create behavioral commitments from current profile
   * Phase 2A: Now with quantum-resistant Kyber-768 encryption + ML embeddings
   */
  const createBehavioralCommitments = useCallback(async () => {
    try {
      console.log('Creating behavioral commitments with quantum encryption + ML...');

      // Initialize Kyber for quantum protection
      await kyberService.initialize();

      // Initialize Behavioral DNA model
      await behavioralDNAModel.initialize();

      const algoInfo = kyberService.getAlgorithmInfo();
      const dnaStatus = behavioralDNAModel.getStatus();

      console.log(`Using ${algoInfo.algorithm} (${algoInfo.status})`);
      console.log(`Behavioral DNA: ${dnaStatus.initialized ? 'Active' : 'Fallback'} (${dnaStatus.output_dimensions}D)`);

      // Get current behavioral profile
      const profile = await behavioralCaptureEngine.getCurrentProfile();

      // Generate behavioral DNA embedding (128-dimensional)
      let behavioralEmbedding = null;
      try {
        behavioralEmbedding = await behavioralDNAModel.generateEmbedding(profile);
        console.log(`Generated behavioral DNA embedding: ${behavioralEmbedding.length} dimensions`);
      } catch (error) {
        console.warn('Behavioral DNA embedding failed, continuing without ML:', error);
      }

      // Generate Kyber keypair for encryption
      let kyberPublicKey = null;
      let isQuantumProtected = false;

      try {
        const { publicKey, secretKey } = await kyberService.generateKeypair();
        kyberPublicKey = kyberService.arrayBufferToBase64(publicKey);
        isQuantumProtected = algoInfo.quantumResistant;

        console.log('Generated Kyber keypair for commitment encryption');

        // Save profile securely to IndexedDB with encryption
        try {
          await secureBehavioralStorage.saveBehavioralProfile(
            { ...profile, userId: user?.email || 'anonymous' },
            kyberService.arrayBufferToBase64(secretKey)
          );
          console.log('✅ Profile saved to secure storage (IndexedDB)');
        } catch (storageError) {
          console.warn('Failed to save to secure storage:', storageError);
        }
      } catch (error) {
        console.warn('Kyber keypair generation failed, using classical encryption:', error);
      }

      // Send to backend to create commitments
      const response = await axios.post('/api/behavioral-recovery/setup-commitments/', {
        behavioral_profile: profile,
        behavioral_embedding: behavioralEmbedding,
        kyber_public_key: kyberPublicKey,
        quantum_protected: isQuantumProtected
      });

      if (response.data.success) {
        console.log(`✅ Behavioral commitments created (${isQuantumProtected ? 'quantum-resistant' : 'classical'} + ML)`);
        setCommitmentStatus({
          has_commitments: true,
          ready_for_recovery: true,
          quantum_protected: isQuantumProtected,
          ml_enhanced: behavioralEmbedding !== null,
          creation_date: new Date().toISOString()
        });
      }
    } catch (error) {
      console.error('Error creating commitments:', error);
      throw error;
    }
  }, [user]);

  /**
   * Start silent behavioral capture
   */
  const startSilentCapture = useCallback(async () => {
    if (isCapturing) return;

    console.log('Starting silent behavioral capture...');

    try {
      // Start capture engine
      behavioralCaptureEngine.startCapture();
      setIsCapturing(true);

      // Update stats periodically
      const statsInterval = setInterval(() => {
        const stats = behavioralCaptureEngine.getProfileStatistics();
        setProfileStats(stats);

        // Auto-create commitments when profile is ready
        if (stats.isReady && !commitmentStatus?.has_commitments) {
          createBehavioralCommitments();
        }
      }, 60000); // Update every minute

      // Store interval in ref for cleanup
      statsIntervalRef.current = statsInterval;

    } catch (error) {
      console.error('Error starting behavioral capture:', error);
    }
  }, [isCapturing, commitmentStatus?.has_commitments, createBehavioralCommitments]);

  /**
   * Stop behavioral capture
   */
  const stopCapture = useCallback(() => {
    if (!isCapturing) return;

    console.log('Stopping behavioral capture...');

    behavioralCaptureEngine.stopCapture();
    setIsCapturing(false);

    // Clear stats interval using ref
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
  }, [isCapturing]);

  /**
   * Check if user has behavioral commitments set up
   */
  const checkCommitmentStatus = useCallback(async () => {
    try {
      const response = await axios.get('/api/behavioral-recovery/commitments/status/');

      if (response.data.success && response.data.data) {
        // Ensure required fields exist with defaults
        setCommitmentStatus({
          has_commitments: response.data.data.has_commitments || false,
          ready_for_recovery: response.data.data.ready_for_recovery || false,
          ...response.data.data
        });
      }
    } catch (error) {
      // Don't log 401 errors - these are expected when not authenticated
      if (error.response?.status !== 401) {
        console.error('Error checking commitment status:', error);
      }
      // Keep default state on error
    }
  }, []);

  // Start capturing when user logs in
  const performedRef = useRef(false);

  useEffect(() => {
    if (isAuthenticated && user) {
      startSilentCapture();

      // Only check once per session to avoid 429s from rapid re-renders
      if (!performedRef.current) {
        checkCommitmentStatus();
        performedRef.current = true;
      }
    } else {
      stopCapture();
      performedRef.current = false;
    }

    return () => {
      stopCapture();
    };
  }, [isAuthenticated, user, startSilentCapture, checkCommitmentStatus, stopCapture]);

  /**
   * Manually trigger commitment creation
   */
  const manuallyCreateCommitments = useCallback(async () => {
    const stats = behavioralCaptureEngine.getProfileStatistics();

    if (!stats.isReady) {
      throw new Error('Behavioral profile not ready. Need more usage data.');
    }

    await createBehavioralCommitments();
  }, [createBehavioralCommitments]);

  /**
   * Get current behavioral profile statistics
   */
  const getProfileStats = useCallback(() => {
    return behavioralCaptureEngine.getProfileStatistics();
  }, []);

  /**
   * Export behavioral profile for backup
   */
  const exportProfile = useCallback(async () => {
    try {
      // Get profile from capture engine
      const profile = await behavioralCaptureEngine.exportProfile();

      // Also include secure storage stats
      const storageStats = await secureBehavioralStorage.getStorageStats();

      return {
        ...profile,
        secureStorage: storageStats
      };
    } catch (error) {
      console.warn('Error exporting with secure storage stats:', error);
      return await behavioralCaptureEngine.exportProfile();
    }
  }, []);

  /**
   * Clear behavioral profile
   */
  const clearProfile = useCallback(async () => {
    behavioralCaptureEngine.clearProfile();

    // Also clear secure storage
    try {
      await secureBehavioralStorage.deleteAllData();
      console.log('✅ Secure storage cleared');
    } catch (error) {
      console.warn('Failed to clear secure storage:', error);
    }

    setProfileStats(null);
    setCommitmentStatus({
      has_commitments: false,
      ready_for_recovery: false
    });
  }, []);

  const value = {
    isCapturing,
    profileStats,
    commitmentStatus,
    startSilentCapture,
    stopCapture,
    createBehavioralCommitments: manuallyCreateCommitments,
    getProfileStats,
    exportProfile,
    clearProfile,
    checkCommitmentStatus
  };

  return (
    <BehavioralContext.Provider value={value}>
      {children}
    </BehavioralContext.Provider>
  );
};

