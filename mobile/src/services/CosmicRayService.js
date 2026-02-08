/**
 * Cosmic Ray Service - Mobile
 * 
 * API client for cosmic ray entropy endpoints.
 */

import apiClient from './apiClient';

const BASE_URL = '/api/security/cosmic';

/**
 * Get cosmic ray detector status
 */
export const getDetectorStatus = async () => {
    const response = await apiClient.get(`${BASE_URL}/status/`);
    return response.data;
};

/**
 * Generate password using cosmic ray entropy
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
 */
export const getRecentEvents = async (limit = 20) => {
    const response = await apiClient.get(`${BASE_URL}/events/`, {
        params: {limit},
    });
    return response.data;
};

/**
 * Update cosmic ray collection settings
 */
export const updateCollectionSettings = async (settings = {}) => {
    const response = await apiClient.post(`${BASE_URL}/settings/`, {
        continuous_collection: settings.continuousCollection || false,
    });
    return response.data;
};

/**
 * Generate raw entropy bytes
 */
export const generateEntropyBatch = async (count = 32) => {
    const response = await apiClient.post(`${BASE_URL}/entropy-batch/`, {count});
    return response.data;
};

export default {
    getDetectorStatus,
    generateCosmicPassword,
    getRecentEvents,
    updateCollectionSettings,
    generateEntropyBatch,
};
