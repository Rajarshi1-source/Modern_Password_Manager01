/**
 * ML Security Service
 * 
 * Provides client-side interface to ML security endpoints:
 * - Password strength prediction
 * - Anomaly detection
 * - Threat analysis
 */

import axios from 'axios';

// Use relative paths in development to leverage Vite proxy
const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');
const ML_API_BASE = `${API_URL}/api/ml-security`;

class MLSecurityService {
    /**
     * ============================================================================
     * PASSWORD STRENGTH PREDICTION
     * ============================================================================
     */
    
    /**
     * Predict password strength using LSTM model
     * @param {string} password - Password to analyze
     * @param {boolean} save - Whether to save prediction to database
     * @returns {Promise} Prediction results
     */
    async predictPasswordStrength(password, save = false) {
        try {
            const response = await axios.post(`${ML_API_BASE}/password-strength/predict/`, {
                password,
                save_prediction: save
            });
            return response.data;
        } catch (error) {
            console.error('Password strength prediction error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get user's password strength history
     * @returns {Promise} History of predictions
     */
    async getPasswordStrengthHistory() {
        try {
            const response = await axios.get(`${ML_API_BASE}/password-strength/history/`);
            return response.data;
        } catch (error) {
            console.error('Error fetching password history:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * ============================================================================
     * ANOMALY DETECTION
     * ============================================================================
     */
    
    /**
     * Detect anomalies in current session
     * @param {Object} sessionData - Current session information
     * @returns {Promise} Anomaly detection results
     */
    async detectSessionAnomaly(sessionData) {
        try {
            const response = await axios.post(`${ML_API_BASE}/anomaly/detect/`, {
                session_data: sessionData
            });
            return response.data;
        } catch (error) {
            console.error('Anomaly detection error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get user behavior profile
     * @returns {Promise} User behavior profile
     */
    async getUserBehaviorProfile() {
        try {
            const response = await axios.get(`${ML_API_BASE}/behavior/profile/`);
            return response.data;
        } catch (error) {
            console.error('Error fetching behavior profile:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Update user behavior profile with new session data
     * @param {Object} sessionData - Session data to add to profile
     * @returns {Promise} Update result
     */
    async updateBehaviorProfile(sessionData) {
        try {
            const response = await axios.post(`${ML_API_BASE}/behavior/profile/update/`, {
                session_data: sessionData
            });
            return response.data;
        } catch (error) {
            console.error('Error updating behavior profile:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * ============================================================================
     * THREAT ANALYSIS
     * ============================================================================
     */
    
    /**
     * Analyze session for threats using hybrid CNN-LSTM model
     * @param {Object} sessionData - Session context data
     * @param {Object} behaviorData - User behavior data
     * @returns {Promise} Threat analysis results
     */
    async analyzeThreat(sessionData, behaviorData) {
        try {
            const response = await axios.post(`${ML_API_BASE}/threat/analyze/`, {
                session_data: sessionData,
                behavior_data: behaviorData
            });
            return response.data;
        } catch (error) {
            console.error('Threat analysis error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get threat prediction history
     * @param {number} limit - Number of records to fetch
     * @returns {Promise} Threat history
     */
    async getThreatHistory(limit = 50) {
        try {
            const response = await axios.get(`${ML_API_BASE}/threat/history/`, {
                params: { limit }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching threat history:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * ============================================================================
     * BATCH OPERATIONS
     * ============================================================================
     */
    
    /**
     * Perform all ML analyses on current session
     * @param {Object} data - Combined data for all analyses
     * @returns {Promise} Complete analysis results
     */
    async batchAnalyzeSession(data) {
        try {
            const response = await axios.post(`${ML_API_BASE}/session/analyze/`, data);
            return response.data;
        } catch (error) {
            console.error('Batch analysis error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * ============================================================================
     * ML MODEL INFORMATION
     * ============================================================================
     */
    
    /**
     * Get information about active ML models
     * @returns {Promise} ML model information
     */
    async getMLModelInfo() {
        try {
            const response = await axios.get(`${ML_API_BASE}/models/info/`);
            return response.data;
        } catch (error) {
            console.error('Error fetching ML model info:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * ============================================================================
     * SESSION MONITORING (Client-side)
     * ============================================================================
     */
    
    /**
     * Collect current session data for analysis
     * @returns {Object} Session data
     */
    collectSessionData() {
        const now = new Date();
        
        return {
            // Device information
            device_trust_score: this._calculateDeviceTrustScore(),
            device_known: localStorage.getItem('device_id') !== null,
            device_fingerprint_similarity: 1.0,
            os_trust_score: 0.8,
            
            // Network information (estimated)
            ip_trust_score: 0.8,
            ip_reputation: 0.8,
            vpn_detected: false,
            tor_detected: false,
            ip_consistency: 0.9,
            
            // Location (if available)
            location_distance_km: 0,
            location_consistency: 0.9,
            timezone_consistency: 1.0,
            
            // Temporal
            login_hour: now.getHours(),
            login_day: now.getDay(),
            time_consistency_score: 0.85,
            
            // Session metrics
            session_duration: this._getSessionDuration(),
            failed_attempts: parseInt(localStorage.getItem('failed_attempts') || '0'),
            api_request_rate: this._calculateAPIRequestRate(),
            suspicious_actions_count: 0,
            
            // Behavioral
            device_consistency: 0.95,
            location_consistency: 0.9,
            time_since_last_login: this._getTimeSinceLastLogin(),
            vault_access_frequency: this._getVaultAccessFrequency(),
        };
    }
    
    /**
     * Collect current behavior data for analysis
     * @returns {Object} Behavior data
     */
    collectBehaviorData() {
        return {
            typing_speed: this._getTypingSpeed(),
            mouse_speed: this._getMouseSpeed(),
            click_frequency: this._getClickFrequency(),
            vault_access_count: parseInt(sessionStorage.getItem('vault_access_count') || '0'),
            password_view_count: parseInt(sessionStorage.getItem('password_view_count') || '0'),
            password_copy_count: parseInt(sessionStorage.getItem('password_copy_count') || '0'),
            page_navigation_speed: this._getNavigationSpeed(),
            idle_time: this._getIdleTime(),
            error_rate: 0.0,
            api_error_rate: 0.0,
            suspicious_clipboard_activity: false,
            rapid_data_access: false,
            session_anomaly_score: 0.0,
            behavior_deviation_score: 0.0,
        };
    }
    
    /**
     * ============================================================================
     * PRIVATE HELPER METHODS
     * ============================================================================
     */
    
    _calculateDeviceTrustScore() {
        // Check if device has been seen before
        const deviceId = localStorage.getItem('device_id');
        const deviceTrustHistory = JSON.parse(localStorage.getItem('device_trust_history') || '[]');
        
        if (deviceId && deviceTrustHistory.length > 0) {
            return 0.9; // Known device
        }
        return 0.5; // Unknown device
    }
    
    _getSessionDuration() {
        const sessionStart = sessionStorage.getItem('session_start');
        if (!sessionStart) {
            const now = Date.now();
            sessionStorage.setItem('session_start', now);
            return 0;
        }
        return (Date.now() - parseInt(sessionStart)) / 1000; // seconds
    }
    
    _getTimeSinceLastLogin() {
        const lastLogin = localStorage.getItem('last_login');
        if (!lastLogin) return 0;
        return (Date.now() - parseInt(lastLogin)) / 1000 / 3600; // hours
    }
    
    _getVaultAccessFrequency() {
        const count = parseInt(sessionStorage.getItem('vault_access_count') || '0');
        const duration = this._getSessionDuration() / 60; // minutes
        return duration > 0 ? count / duration : 0;
    }
    
    _calculateAPIRequestRate() {
        const count = parseInt(sessionStorage.getItem('api_request_count') || '0');
        const duration = this._getSessionDuration() / 60; // minutes
        return duration > 0 ? count / duration : 0;
    }
    
    _getTypingSpeed() {
        // Get stored typing speed or default
        return parseFloat(sessionStorage.getItem('typing_speed') || '50');
    }
    
    _getMouseSpeed() {
        // Get stored mouse speed or default
        return parseFloat(sessionStorage.getItem('mouse_speed') || '30');
    }
    
    _getClickFrequency() {
        const clicks = parseInt(sessionStorage.getItem('click_count') || '0');
        const duration = this._getSessionDuration() / 60; // minutes
        return duration > 0 ? clicks / duration : 0;
    }
    
    _getNavigationSpeed() {
        const navigations = parseInt(sessionStorage.getItem('navigation_count') || '0');
        const duration = this._getSessionDuration() / 60; // minutes
        return duration > 0 ? navigations / duration : 0;
    }
    
    _getIdleTime() {
        const lastActivity = sessionStorage.getItem('last_activity');
        if (!lastActivity) return 0;
        return (Date.now() - parseInt(lastActivity)) / 1000; // seconds
    }
    
    /**
     * ============================================================================
     * FHE-ENHANCED PASSWORD STRENGTH (PRIVACY-PRESERVING)
     * ============================================================================
     */
    
    /**
     * Check password strength using FHE (Fully Homomorphic Encryption)
     * Password is encrypted client-side and strength is computed on encrypted data
     * @param {string} password - Password to analyze
     * @param {Object} options - FHE options (maxLatency, minAccuracy)
     * @returns {Promise} FHE strength check results
     */
    async checkPasswordStrengthFHE(password, options = {}) {
        try {
            // Dynamically import FHE service to avoid loading it unnecessarily
            const { fheService } = await import('./fhe/fheService');
            
            // Use FHE service to check strength
            const result = await fheService.checkPasswordStrength(password, {
                maxLatency: options.maxLatency || 1000,
                minAccuracy: options.minAccuracy || 0.9,
            });
            
            return {
                success: true,
                ...result,
                fheEnabled: true,
            };
        } catch (error) {
            console.warn('FHE strength check failed, falling back to standard:', error);
            
            // Fallback to regular strength check
            const fallbackResult = await this.predictPasswordStrength(password, false);
            return {
                ...fallbackResult,
                fheEnabled: false,
                fallbackReason: error.message,
            };
        }
    }
    
    /**
     * Batch check password strength for multiple passwords using FHE
     * @param {string[]} passwords - Array of passwords to check
     * @param {Object} options - Batch options
     * @returns {Promise} Batch strength results
     */
    async batchCheckPasswordStrengthFHE(passwords, options = {}) {
        try {
            const { fheService } = await import('./fhe/fheService');
            
            const results = await fheService.batchCheckStrength(passwords, {
                rules: options.rules,
            });
            
            return {
                success: true,
                results,
                fheEnabled: true,
                batchSize: passwords.length,
            };
        } catch (error) {
            console.warn('FHE batch check failed:', error);
            
            // Fallback to individual checks
            const results = await Promise.all(
                passwords.map(pwd => this.predictPasswordStrength(pwd, false))
            );
            
            return {
                success: true,
                results,
                fheEnabled: false,
                fallbackReason: error.message,
            };
        }
    }
    
    /**
     * Get FHE service status and metrics
     * @returns {Promise} FHE service status
     */
    async getFHEStatus() {
        try {
            const { fheService } = await import('./fhe/fheService');
            return await fheService.getStatus();
        } catch (error) {
            return {
                available: false,
                error: error.message,
            };
        }
    }
    
    /**
     * Get FHE service metrics
     * @returns {Promise} FHE metrics
     */
    async getFHEMetrics() {
        try {
            const { fheService } = await import('./fhe/fheService');
            return fheService.getMetrics();
        } catch (error) {
            return {
                available: false,
                error: error.message,
            };
        }
    }
    
    /**
     * ============================================================================
     * ADVERSARIAL AI INTEGRATION
     * ============================================================================
     */
    
    /**
     * Analyze password using adversarial AI
     * @param {string} password - Password to analyze
     * @param {boolean} runFullBattle - Whether to run full battle simulation
     * @returns {Promise} Adversarial analysis results
     */
    async analyzePasswordAdversarial(password, runFullBattle = false) {
        try {
            const adversarialService = (await import('./adversarialService')).default;
            
            if (runFullBattle) {
                return await adversarialService.analyzePassword(
                    adversarialService.extractFeatures(password),
                    true
                );
            } else {
                return await adversarialService.getQuickAssessment(
                    adversarialService.extractFeatures(password)
                );
            }
        } catch (error) {
            console.error('Adversarial analysis error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get combined password analysis (ML + Adversarial)
     * @param {string} password - Password to analyze
     * @returns {Promise} Combined analysis results
     */
    async getComprehensivePasswordAnalysis(password) {
        try {
            // Run both analyses in parallel
            const [mlResult, adversarialResult] = await Promise.all([
                this.predictPasswordStrength(password, false),
                this.analyzePasswordAdversarial(password, false)
            ]);
            
            return {
                success: true,
                ml_analysis: mlResult,
                adversarial_analysis: adversarialResult,
                combined_score: this._calculateCombinedScore(mlResult, adversarialResult),
                recommendations: this._mergeRecommendations(mlResult, adversarialResult)
            };
        } catch (error) {
            console.error('Comprehensive analysis error:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get adversarial defense recommendations
     * @param {Object} options - Query options
     * @returns {Promise} Defense recommendations
     */
    async getAdversarialRecommendations(options = {}) {
        try {
            const adversarialService = (await import('./adversarialService')).default;
            return await adversarialService.getRecommendations(options);
        } catch (error) {
            console.error('Error fetching adversarial recommendations:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get user's adversarial defense profile
     * @returns {Promise} Defense profile
     */
    async getAdversarialDefenseProfile() {
        try {
            const adversarialService = (await import('./adversarialService')).default;
            return await adversarialService.getDefenseProfile();
        } catch (error) {
            console.error('Error fetching defense profile:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Get trending attack patterns
     * @param {number} limit - Number of trends to fetch
     * @returns {Promise} Trending attacks
     */
    async getTrendingAttacks(limit = 5) {
        try {
            const adversarialService = (await import('./adversarialService')).default;
            return await adversarialService.getTrendingAttacks(limit);
        } catch (error) {
            console.error('Error fetching trending attacks:', error);
            throw this._handleError(error);
        }
    }
    
    /**
     * Calculate combined score from ML and adversarial analysis
     * @private
     */
    _calculateCombinedScore(mlResult, adversarialResult) {
        const mlScore = this._strengthToScore(mlResult?.prediction?.strength);
        const advScore = adversarialResult?.analysis?.defense_score || 0.5;
        
        // Weighted average: 40% ML, 60% Adversarial (adversarial is more attack-aware)
        return (mlScore * 0.4) + (advScore * 0.6);
    }
    
    /**
     * Convert strength label to numeric score
     * @private
     */
    _strengthToScore(strength) {
        const scores = {
            'very_weak': 0.1,
            'weak': 0.3,
            'moderate': 0.5,
            'strong': 0.75,
            'very_strong': 0.95
        };
        return scores[strength] || 0.5;
    }
    
    /**
     * Merge recommendations from both analysis types
     * @private
     */
    _mergeRecommendations(mlResult, adversarialResult) {
        const mlRecs = mlResult?.prediction?.recommendations || [];
        const advRecs = adversarialResult?.analysis?.recommendations || [];
        
        // Combine and deduplicate
        const allRecs = [...advRecs, ...mlRecs.map(r => ({ 
            title: r, 
            priority: 'medium',
            source: 'ml' 
        }))];
        
        return allRecs.slice(0, 5); // Return top 5
    }
    
    _handleError(error) {
        if (error.response) {
            // Server responded with error
            return {
                message: error.response.data.message || 'ML service error',
                status: error.response.status,
                data: error.response.data
            };
        } else if (error.request) {
            // Request made but no response
            return {
                message: 'No response from ML service',
                status: 0,
                data: null
            };
        } else {
            // Error setting up request
            return {
                message: error.message || 'ML service error',
                status: 0,
                data: null
            };
        }
    }
}

// Export singleton instance
const mlSecurityService = new MLSecurityService();
export default mlSecurityService;

