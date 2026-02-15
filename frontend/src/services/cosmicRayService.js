import { api as apiClient } from './api';

/**
 * Cosmic Ray Entropy Service
 * ===========================
 * 
 * Client for cosmic ray-based true random number generation.
 * Uses USB cosmic ray detectors or simulation fallback.
 */

const BASE_URL = '/api/security/cosmic';

/**
 * Get cosmic ray detector status
 * @returns {Promise<Object>} Detector status including mode, availability, config
 */
export const getDetectorStatus = async () => {
    const response = await apiClient.get(`${BASE_URL}/status/`);
    return response.data;
};

/**
 * Generate password using cosmic ray entropy
 * @param {Object} options Password generation options
 * @param {number} options.length Password length (8-128, default: 16)
 * @param {boolean} options.includeUppercase Include uppercase letters
 * @param {boolean} options.includeLowercase Include lowercase letters
 * @param {boolean} options.includeDigits Include numbers
 * @param {boolean} options.includeSymbols Include symbols
 * @param {string} options.customCharset Optional custom character set
 * @returns {Promise<Object>} Generated password with source info
 */
export const generateCosmicPassword = async (options = {}) => {
    const payload = {
        length: options.length || 16,
        include_uppercase: options.includeUppercase !== false,
        include_lowercase: options.includeLowercase !== false,
        include_digits: options.includeDigits !== false,
        include_symbols: options.includeSymbols !== false,
    };
    
    if (options.customCharset) {
        payload.custom_charset = options.customCharset;
    }
    
    const response = await apiClient.post(`${BASE_URL}/generate-password/`, payload);
    return response.data;
};

/**
 * Get recent cosmic ray detection events
 * @param {number} limit Maximum events to return (default: 20)
 * @returns {Promise<Object>} List of recent events
 */
export const getRecentEvents = async (limit = 20) => {
    const response = await apiClient.get(`${BASE_URL}/events/`, {
        params: { limit }
    });
    return response.data;
};

/**
 * Update cosmic ray collection settings
 * @param {Object} settings Collection settings
 * @param {boolean} settings.continuousCollection Enable/disable continuous collection
 * @returns {Promise<Object>} Updated settings confirmation
 */
export const updateCollectionSettings = async (settings = {}) => {
    const response = await apiClient.post(`${BASE_URL}/settings/`, {
        continuous_collection: settings.continuousCollection || false
    });
    return response.data;
};

/**
 * Generate raw entropy bytes from cosmic rays
 * @param {number} count Number of bytes to generate (1-1024, default: 32)
 * @returns {Promise<Object>} Entropy bytes in hex and base64 formats
 */
export const generateEntropyBatch = async (count = 32) => {
    const response = await apiClient.post(`${BASE_URL}/entropy-batch/`, { count });
    return response.data;
};

export default {
    getDetectorStatus,
    generateCosmicPassword,
    getRecentEvents,
    updateCollectionSettings,
    generateEntropyBatch,
};
