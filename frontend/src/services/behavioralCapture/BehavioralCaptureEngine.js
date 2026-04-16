/**
 * Behavioral Capture Engine
 * 
 * Orchestrates all behavioral capture modules to create a comprehensive
 * 247-dimensional behavioral DNA profile
 */

import { KeystrokeDynamics } from './KeystrokeDynamics';
import { MouseBiometrics } from './MouseBiometrics';
import { CognitivePatterns } from './CognitivePatterns';
import { DeviceInteraction } from './DeviceInteraction';
import { SemanticBehaviors } from './SemanticBehaviors';
import { AmbientLightCapture } from './AmbientLightCapture';
import { MotionCapture } from './MotionCapture';
import { PointerPressureCapture } from './PointerPressureCapture';
import { ScrollMomentumCapture } from './ScrollMomentumCapture';
import { BatteryCurveCapture } from './BatteryCurveCapture';
import { ConnectionCapture } from './ConnectionCapture';
import { WebBluetoothCapture } from './WebBluetoothCapture';
import ambient from '../ambient';

export class BehavioralCaptureEngine {
  constructor(options = {}) {
    // Initialize all capture modules
    this.keystrokeDynamics = new KeystrokeDynamics();
    this.mouseBiometrics = new MouseBiometrics();
    this.cognitivePatterns = new CognitivePatterns();
    this.deviceInteraction = new DeviceInteraction();
    this.semanticBehaviors = new SemanticBehaviors();

    // Ambient Biometric Fusion — passive environment signals.
    this.ambientLight = new AmbientLightCapture();
    this.motion = new MotionCapture();
    this.pointerPressure = new PointerPressureCapture();
    this.scrollMomentum = new ScrollMomentumCapture();
    this.batteryCurve = new BatteryCurveCapture();
    this.connection = new ConnectionCapture();
    this.webBluetooth = new WebBluetoothCapture();

    // Configuration
    this.config = {
      autoStart: options.autoStart !== false,
      captureInterval: options.captureInterval || 300000, // 5 minutes
      minSamplesForProfile: options.minSamplesForProfile || 100,
      enableLocalStorage: options.enableLocalStorage !== false,
      privacyMode: options.privacyMode || 'strict', // strict, balanced, permissive
      // Ambient ingest opts: if false the engine never POSTs observations.
      enableAmbientIngest: options.enableAmbientIngest !== false,
      ambientIngestInterval: options.ambientIngestInterval || 300000, // 5 min
      ambientDeviceFp: options.ambientDeviceFp || null, // caller may inject FingerprintJS visitorId
      ...options
    };
    this._lastAmbientIngestAt = 0;
    this.lastAmbientResult = null;
    
    // State
    this.isCapturing = false;
    this.samples = [];
    this.profileBuildStarted = null;
    this.lastSnapshot = null;
    
    // Storage key for local behavioral profile
    this.storageKey = 'behavioral_profile_data';
    
    // Auto-start if configured
    if (this.config.autoStart) {
      this.startCapture();
    }
  }
  
  /**
   * Start capturing behavioral data
   */
  startCapture() {
    if (this.isCapturing) {
      console.warn('BehavioralCaptureEngine: Already capturing');
      return;
    }
    
    console.log('BehavioralCaptureEngine: Starting behavioral capture');
    
    // Attach all modules
    this.keystrokeDynamics.attach();
    this.mouseBiometrics.attach();
    this.cognitivePatterns.attach();
    this.deviceInteraction.attach();
    this.semanticBehaviors.attach();
    this.ambientLight.attach();
    this.motion.attach();
    this.pointerPressure.attach();
    this.scrollMomentum.attach();
    this.batteryCurve.attach();
    this.connection.attach();
    this.webBluetooth.attach();

    this.isCapturing = true;
    this.profileBuildStarted = Date.now();
    
    // Set up periodic snapshots
    this.snapshotInterval = setInterval(() => {
      this.createSnapshot();
    }, this.config.captureInterval);
    
    // Load existing profile from local storage
    if (this.config.enableLocalStorage) {
      this.loadProfileFromStorage();
    }
  }
  
  /**
   * Stop capturing behavioral data
   */
  stopCapture() {
    if (!this.isCapturing) {
      console.warn('BehavioralCaptureEngine: Not currently capturing');
      return;
    }
    
    console.log('BehavioralCaptureEngine: Stopping behavioral capture');
    
    // Detach all modules
    this.keystrokeDynamics.detach();
    this.mouseBiometrics.detach();
    this.cognitivePatterns.detach();
    this.deviceInteraction.detach();
    this.semanticBehaviors.detach();
    this.ambientLight.detach();
    this.motion.detach();
    this.pointerPressure.detach();
    this.scrollMomentum.detach();
    this.batteryCurve.detach();
    this.connection.detach();
    this.webBluetooth.detach();
    
    this.isCapturing = false;
    
    // Clear snapshot interval
    if (this.snapshotInterval) {
      clearInterval(this.snapshotInterval);
      this.snapshotInterval = null;
    }
    
    // Save final snapshot
    if (this.config.enableLocalStorage) {
      this.createSnapshot();
      this.saveProfileToStorage();
    }
  }
  
  /**
   * Generate complete 247-dimensional behavioral vector
   */
  async generateBehavioralVector() {
    console.log('BehavioralCaptureEngine: Generating behavioral vector');
    
    // Collect features from all modules
    const [
      typingFeatures,
      mouseFeatures,
      cognitiveFeatures,
      deviceFeatures,
      semanticFeatures
    ] = await Promise.all([
      this.keystrokeDynamics.getFeatures(),
      this.mouseBiometrics.getFeatures(),
      this.cognitivePatterns.getFeatures(),
      this.deviceInteraction.getFeatures(),
      this.semanticBehaviors.getFeatures()
    ]);
    
    // Combine into comprehensive profile
    const behavioralVector = {
      // Individual module features
      typing: typingFeatures,
      mouse: mouseFeatures,
      cognitive: cognitiveFeatures,
      device: deviceFeatures,
      semantic: semanticFeatures,
      
      // Meta-features (cross-module correlations)
      meta: this._calculateMetaFeatures({
        typing: typingFeatures,
        mouse: mouseFeatures,
        cognitive: cognitiveFeatures,
        device: deviceFeatures,
        semantic: semanticFeatures
      }),
      
      // Quality assessment
      overall_quality: this._assessOverallQuality({
        typing: typingFeatures,
        mouse: mouseFeatures,
        cognitive: cognitiveFeatures,
        device: deviceFeatures,
        semantic: semanticFeatures
      }),
      
      // Timestamp
      timestamp: Date.now(),
      
      // Dimensional breakdown
      dimensions: {
        typing: Object.keys(typingFeatures).length,
        mouse: Object.keys(mouseFeatures).length,
        cognitive: Object.keys(cognitiveFeatures).length,
        device: Object.keys(deviceFeatures).length,
        semantic: Object.keys(semanticFeatures).length,
        total: this._countTotalDimensions({
          typing: typingFeatures,
          mouse: mouseFeatures,
          cognitive: cognitiveFeatures,
          device: deviceFeatures,
          semantic: semanticFeatures
        })
      }
    };
    
    console.log(`Generated behavioral vector with ${behavioralVector.dimensions.total} dimensions`);
    
    return behavioralVector;
  }
  
  /**
   * Create a snapshot of current behavioral profile
   */
  async createSnapshot() {
    try {
      const vector = await this.generateBehavioralVector();

      this.lastSnapshot = vector;
      this.samples.push(vector);

      // Opportunistically POST an ambient observation. Non-blocking;
      // failures must never disrupt behavioral capture.
      if (this.config.enableAmbientIngest) {
        this.maybeIngestAmbient().catch((err) => {
          console.warn('Ambient ingest skipped:', err?.message || err);
        });
      }
      
      // Limit stored samples to last 30 days (assuming 1 snapshot per 5 minutes)
      const maxSamples = (30 * 24 * 60) / 5; // ~8640 samples for 30 days
      if (this.samples.length > maxSamples) {
        this.samples = this.samples.slice(-maxSamples);
      }
      
      console.log(`Snapshot created. Total samples: ${this.samples.length}`);
      
      return vector;
    } catch (error) {
      console.error('Error creating snapshot:', error);
      return null;
    }
  }
  
  /**
   * Get current behavioral profile
   */
  async getCurrentProfile() {
    if (!this.isCapturing) {
      throw new Error('Capture not started. Call startCapture() first.');
    }
    
    return await this.generateBehavioralVector();
  }
  
  /**
   * Get behavioral profile statistics
   */
  getProfileStatistics() {
    return {
      samplesCollected: this.samples.length,
      profileAge: this.profileBuildStarted 
        ? Math.floor((Date.now() - this.profileBuildStarted) / 86400000) // days
        : 0,
      isReady: this.samples.length >= this.config.minSamplesForProfile,
      lastSnapshot: this.lastSnapshot ? this.lastSnapshot.timestamp : null,
      qualityScore: this.lastSnapshot ? this.lastSnapshot.overall_quality : 0,
      dimensionsCaptured: this.lastSnapshot ? this.lastSnapshot.dimensions.total : 0
    };
  }
  
  /**
   * Calculate meta-features (correlations across modules)
   */
  _calculateMetaFeatures(features) {
    const meta = {};
    
    // Typing-mouse coordination
    if (features.typing.data_quality_score && features.mouse.data_quality_score) {
      meta.typing_mouse_activity_correlation = 
        Math.abs(features.typing.data_quality_score - features.mouse.data_quality_score);
    }
    
    // Activity consistency (all modules should show similar session duration)
    const sessionDurations = [
      features.typing.session_duration_seconds,
      features.mouse.session_duration_seconds,
      features.cognitive.total_samples
    ].filter(d => d > 0);
    
    if (sessionDurations.length > 0) {
      meta.session_consistency = 1 / (1 + this._std(sessionDurations) / (this._mean(sessionDurations) + 0.001));
    }
    
    // Device-specific behavior adaptation
    meta.device_adaptation_score = features.device.device_type === 'mobile' 
      ? (features.device.touch_count > 0 ? 1 : 0)
      : (features.mouse.total_movements > 0 ? 1 : 0);
    
    return meta;
  }
  
  /**
   * Assess overall data quality across all modules
   */
  _assessOverallQuality(features) {
    const qualityScores = [
      features.typing.data_quality_score || 0,
      features.mouse.data_quality_score || 0,
      features.cognitive.data_quality_score || 0,
      features.device.data_quality_score || 0,
      features.semantic.data_quality_score || 0
    ];
    
    // Weighted average (typing and mouse are most important)
    const weights = [0.30, 0.25, 0.20, 0.15, 0.10];
    let weightedSum = 0;
    
    for (let i = 0; i < qualityScores.length; i++) {
      weightedSum += qualityScores[i] * weights[i];
    }
    
    return weightedSum;
  }
  
  /**
   * Count total dimensions captured
   */
  _countTotalDimensions(features) {
    let total = 0;
    
    Object.values(features).forEach(moduleFeatures => {
      if (typeof moduleFeatures === 'object') {
        total += Object.keys(moduleFeatures).length;
      }
    });
    
    return total;
  }
  
  /**
   * Save profile to local storage (encrypted)
   */
  async saveProfileToStorage() {
    if (!this.config.enableLocalStorage) return;
    
    try {
      const profileData = {
        samples: this.samples,
        profileBuildStarted: this.profileBuildStarted,
        lastSnapshot: this.lastSnapshot,
        version: '1.0.0'
      };
      
      // In production, encrypt this data before storing
      const encrypted = JSON.stringify(profileData); // TODO: Add encryption
      
      localStorage.setItem(this.storageKey, encrypted);
      console.log('Behavioral profile saved to local storage');
    } catch (error) {
      console.error('Error saving profile to storage:', error);
    }
  }
  
  /**
   * Load profile from local storage
   */
  async loadProfileFromStorage() {
    if (!this.config.enableLocalStorage) return;
    
    try {
      const encrypted = localStorage.getItem(this.storageKey);
      if (!encrypted) return;
      
      // TODO: Add decryption
      const profileData = JSON.parse(encrypted);
      
      if (profileData.samples) {
        this.samples = profileData.samples;
        this.profileBuildStarted = profileData.profileBuildStarted;
        this.lastSnapshot = profileData.lastSnapshot;
        
        console.log(`Loaded ${this.samples.length} behavioral samples from storage`);
      }
    } catch (error) {
      console.error('Error loading profile from storage:', error);
      // Clear corrupted data
      localStorage.removeItem(this.storageKey);
    }
  }
  
  /**
   * Clear all captured data
   */
  clearProfile() {
    this.samples = [];
    this.lastSnapshot = null;
    this.profileBuildStarted = null;
    
    // Clear module data
    this.keystrokeDynamics.reset();
    this.mouseBiometrics.reset();
    this.cognitivePatterns.reset();
    this.deviceInteraction.reset();
    this.semanticBehaviors.reset();
    this.ambientLight.reset();
    this.motion.reset();
    this.pointerPressure.reset();
    this.scrollMomentum.reset();
    this.batteryCurve.reset();
    this.connection.reset();
    this.webBluetooth.reset();
    this.lastAmbientResult = null;
    
    // Clear storage
    if (this.config.enableLocalStorage) {
      localStorage.removeItem(this.storageKey);
    }
    
    console.log('Behavioral profile cleared');
  }
  
  /**
   * Export profile for backup/transfer
   */
  async exportProfile() {
    const profile = {
      version: '1.0.0',
      exportDate: new Date().toISOString(),
      statistics: this.getProfileStatistics(),
      samples: this.samples,
      currentVector: await this.generateBehavioralVector()
    };
    
    return profile;
  }
  
  /**
   * Import profile from backup
   */
  importProfile(profileData) {
    if (profileData.version !== '1.0.0') {
      throw new Error('Incompatible profile version');
    }
    
    this.samples = profileData.samples || [];
    this.lastSnapshot = profileData.currentVector;
    this.profileBuildStarted = Date.now();
    
    console.log(`Imported ${this.samples.length} samples`);
  }
  
  // ============================================================================
  // AMBIENT BIOMETRIC FUSION
  // ============================================================================

  /**
   * Snapshot the ambient collectors into the protocol-level coarse
   * features dict. No timestamps, no IP, no raw signals.
   */
  async buildAmbientCoarseFeatures() {
    const [light, motion, pointer, scroll, battery, conn] = await Promise.all([
      this.ambientLight.getFeatures(),
      this.motion.getFeatures(),
      this.pointerPressure.getFeatures(),
      this.scrollMomentum.getFeatures(),
      this.batteryCurve.getFeatures(),
      this.connection.getFeatures(),
    ]);
    const typingFeatures = this.lastSnapshot?.typing || {};
    const tz = new Date().getTimezoneOffset() * -1; // minutes east of UTC
    const hour = new Date().getHours();
    const coarse = {
      light_bucket: light.light_bucket || 'unknown',
      motion_class: motion.motion_class || 'unknown',
      pointer_pressure_mean_bucket: pointer.pointer_pressure_mean_bucket || 'unknown',
      scroll_momentum_bucket: scroll.scroll_momentum_bucket || 'unknown',
      battery_drain_slope_bucket: battery.battery_drain_slope_bucket || 'unknown',
      connection_class: conn.connection_class || 'unknown',
      effective_type: conn.effective_type || 'unknown',
      typing_cadence_stats: {
        dwell_time_mean: typingFeatures.dwell_time_mean ?? null,
        flight_time_mean: typingFeatures.flight_time_mean ?? null,
        typing_speed_wpm: typingFeatures.typing_speed_wpm ?? null,
      },
      tz_offset_min: tz,
      is_business_hours: hour >= 8 && hour < 19,
    };
    const sensitiveDigests = {
      bluetooth: this.webBluetooth.getDigestSet(),
    };
    return { coarse, sensitiveDigests };
  }

  /**
   * Compose + POST an ambient observation, honoring the ingest interval.
   */
  async maybeIngestAmbient() {
    const now = Date.now();
    if (now - this._lastAmbientIngestAt < this.config.ambientIngestInterval) {
      return null;
    }
    this._lastAmbientIngestAt = now;

    const deviceFp = this.config.ambientDeviceFp || this._resolveDeviceFp();
    if (!deviceFp) {
      // Without a stable device fp we cannot build a per-device baseline;
      // silently skip rather than polluting the server's profile table.
      return null;
    }

    const { coarse, sensitiveDigests } = await this.buildAmbientCoarseFeatures();
    try {
      const result = await ambient.captureAndIngest({
        surface: 'web',
        deviceFp,
        coarseFeatures: coarse,
        sensitiveDigests,
      });
      this.lastAmbientResult = result;
      return result;
    } catch (err) {
      console.warn('Ambient ingest failed:', err?.message || err);
      return null;
    }
  }

  _resolveDeviceFp() {
    try {
      const cached = this.lastSnapshot?.device?.device_fingerprint
        || this.lastSnapshot?.device?.fingerprint;
      if (cached) return String(cached);
    } catch { /* ignore */ }
    // Fallback: lightweight, stable-per-device synthetic id held in localStorage.
    try {
      const k = 'ambient_device_fp';
      const v = typeof localStorage !== 'undefined' ? localStorage.getItem(k) : null;
      if (v) return v;
      const rand = new Uint8Array(16);
      if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(rand);
      const hex = Array.from(rand, (b) => b.toString(16).padStart(2, '0')).join('');
      if (typeof localStorage !== 'undefined') localStorage.setItem(k, hex);
      return hex;
    } catch {
      return null;
    }
  }

  /**
   * Return the last ambient ingest result (score + matched context).
   */
  getLastAmbientResult() {
    return this.lastAmbientResult;
  }

  // ============================================================================
  // UTILITY FUNCTIONS
  // ============================================================================
  
  _mean(arr) {
    if (!arr || arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }
  
  _std(arr) {
    if (!arr || arr.length === 0) return 0;
    const mean = this._mean(arr);
    const squaredDiffs = arr.map(x => Math.pow(x - mean, 2));
    return Math.sqrt(this._mean(squaredDiffs));
  }
}

// Export singleton instance
export const behavioralCaptureEngine = new BehavioralCaptureEngine({ autoStart: false });

