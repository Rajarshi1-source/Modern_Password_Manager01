/**
 * Duress Code Service
 * 
 * API client for Military-Grade Duress Code endpoints.
 * Provides methods for duress code management, decoy vaults,
 * trusted authorities, and evidence package handling.
 */

const BASE_URL = '/api/security';

/**
 * Get authentication headers
 */
const getHeaders = (authToken) => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authToken}`
});

// =============================================================================
// Configuration
// =============================================================================

/**
 * Get duress configuration for the current user
 * @param {string} authToken - JWT authentication token
 * @returns {Promise<Object>} Duress configuration
 */
export const getConfig = async (authToken) => {
    const response = await fetch(`${BASE_URL}/duress/config/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch duress configuration');
    }
    
    return response.json();
};

/**
 * Update duress configuration
 * @param {string} authToken - JWT authentication token
 * @param {Object} config - Configuration updates
 * @returns {Promise<Object>} Updated configuration
 */
export const updateConfig = async (authToken, config) => {
    const response = await fetch(`${BASE_URL}/duress/config/`, {
        method: 'PUT',
        headers: getHeaders(authToken),
        body: JSON.stringify(config)
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to update configuration');
    }
    
    return response.json();
};

// =============================================================================
// Duress Codes CRUD
// =============================================================================

/**
 * Get all duress codes for the current user
 * @param {string} authToken - JWT authentication token
 * @returns {Promise<Object>} List of duress codes
 */
export const getCodes = async (authToken) => {
    const response = await fetch(`${BASE_URL}/duress/codes/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch duress codes');
    }
    
    return response.json();
};

/**
 * Create a new duress code
 * @param {string} authToken - JWT authentication token
 * @param {Object} codeData - Code data { code, threat_level, code_hint, action_config }
 * @returns {Promise<Object>} Created duress code
 */
export const createCode = async (authToken, codeData) => {
    const response = await fetch(`${BASE_URL}/duress/codes/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            code: codeData.code,
            threat_level: codeData.threatLevel || 'medium',
            code_hint: codeData.codeHint || '',
            action_config: codeData.actionConfig || {}
        })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to create duress code');
    }
    
    return response.json();
};

/**
 * Get details of a specific duress code
 * @param {string} authToken - JWT authentication token
 * @param {string} codeId - Duress code UUID
 * @returns {Promise<Object>} Duress code details
 */
export const getCode = async (authToken, codeId) => {
    const response = await fetch(`${BASE_URL}/duress/codes/${codeId}/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch duress code');
    }
    
    return response.json();
};

/**
 * Update a duress code
 * @param {string} authToken - JWT authentication token
 * @param {string} codeId - Duress code UUID
 * @param {Object} codeData - Updated code data
 * @returns {Promise<Object>} Updated duress code
 */
export const updateCode = async (authToken, codeId, codeData) => {
    const response = await fetch(`${BASE_URL}/duress/codes/${codeId}/`, {
        method: 'PUT',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            new_code: codeData.code || null,
            threat_level: codeData.threatLevel || null,
            code_hint: codeData.codeHint || null,
            action_config: codeData.actionConfig || null
        })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to update duress code');
    }
    
    return response.json();
};

/**
 * Delete (deactivate) a duress code
 * @param {string} authToken - JWT authentication token
 * @param {string} codeId - Duress code UUID
 * @returns {Promise<void>}
 */
export const deleteCode = async (authToken, codeId) => {
    const response = await fetch(`${BASE_URL}/duress/codes/${codeId}/`, {
        method: 'DELETE',
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete duress code');
    }
};

// =============================================================================
// Decoy Vault
// =============================================================================

/**
 * Get decoy vault for the current user
 * @param {string} authToken - JWT authentication token
 * @param {string} threatLevel - Threat level (low, medium, high, critical)
 * @returns {Promise<Object>} Decoy vault data
 */
export const getDecoyVault = async (authToken, threatLevel = 'medium') => {
    const params = new URLSearchParams();
    params.append('threat_level', threatLevel);
    
    const response = await fetch(`${BASE_URL}/duress/decoy/?${params}`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch decoy vault');
    }
    
    return response.json();
};

/**
 * Regenerate decoy vault with new fake data
 * @param {string} authToken - JWT authentication token
 * @param {string} threatLevel - Threat level for regeneration
 * @returns {Promise<Object>} Regenerated decoy vault
 */
export const regenerateDecoyVault = async (authToken, threatLevel = 'medium') => {
    const response = await fetch(`${BASE_URL}/duress/decoy/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({ threat_level: threatLevel })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to regenerate decoy vault');
    }
    
    return response.json();
};

// =============================================================================
// Trusted Authorities
// =============================================================================

/**
 * Get all trusted authorities for silent alarms
 * @param {string} authToken - JWT authentication token
 * @returns {Promise<Object>} List of trusted authorities
 */
export const getAuthorities = async (authToken) => {
    const response = await fetch(`${BASE_URL}/duress/authorities/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch trusted authorities');
    }
    
    return response.json();
};

/**
 * Add a new trusted authority
 * @param {string} authToken - JWT authentication token
 * @param {Object} authority - Authority data
 * @returns {Promise<Object>} Created authority
 */
export const addAuthority = async (authToken, authority) => {
    const response = await fetch(`${BASE_URL}/duress/authorities/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({
            authority_type: authority.type,
            contact_method: authority.contactMethod,
            contact_details: authority.contactDetails,
            threat_levels: authority.threatLevels || ['high', 'critical'],
            name: authority.name || ''
        })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to add trusted authority');
    }
    
    return response.json();
};

/**
 * Update a trusted authority
 * @param {string} authToken - JWT authentication token
 * @param {string} authorityId - Authority UUID
 * @param {Object} authority - Updated authority data
 * @returns {Promise<Object>} Updated authority
 */
export const updateAuthority = async (authToken, authorityId, authority) => {
    const response = await fetch(`${BASE_URL}/duress/authorities/${authorityId}/`, {
        method: 'PUT',
        headers: getHeaders(authToken),
        body: JSON.stringify(authority)
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to update authority');
    }
    
    return response.json();
};

/**
 * Delete a trusted authority
 * @param {string} authToken - JWT authentication token
 * @param {string} authorityId - Authority UUID
 * @returns {Promise<void>}
 */
export const deleteAuthority = async (authToken, authorityId) => {
    const response = await fetch(`${BASE_URL}/duress/authorities/${authorityId}/`, {
        method: 'DELETE',
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete authority');
    }
};

// =============================================================================
// Duress Events
// =============================================================================

/**
 * Get duress event history
 * @param {string} authToken - JWT authentication token
 * @param {Object} options - Query options { limit, threatLevel, startDate, endDate }
 * @returns {Promise<Object>} Duress events
 */
export const getEvents = async (authToken, options = {}) => {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit);
    if (options.threatLevel) params.append('threat_level', options.threatLevel);
    if (options.startDate) params.append('start_date', options.startDate);
    if (options.endDate) params.append('end_date', options.endDate);
    
    const response = await fetch(`${BASE_URL}/duress/events/?${params}`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch duress events');
    }
    
    return response.json();
};

// =============================================================================
// Evidence Packages
// =============================================================================

/**
 * Get evidence package details
 * @param {string} authToken - JWT authentication token
 * @param {string} packageId - Evidence package UUID
 * @returns {Promise<Object>} Evidence package details
 */
export const getEvidencePackage = async (authToken, packageId) => {
    const response = await fetch(`${BASE_URL}/duress/evidence/${packageId}/`, {
        headers: getHeaders(authToken)
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch evidence package');
    }
    
    return response.json();
};

/**
 * Export evidence package for legal use
 * @param {string} authToken - JWT authentication token
 * @param {string} packageId - Evidence package UUID
 * @param {string} requestingUser - Identity of requesting user
 * @returns {Promise<Object>} Exportable evidence data
 */
export const exportEvidencePackage = async (authToken, packageId, requestingUser) => {
    const response = await fetch(`${BASE_URL}/duress/evidence/${packageId}/export/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({ requesting_user: requestingUser })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to export evidence package');
    }
    
    return response.json();
};

// =============================================================================
// Test Activation
// =============================================================================

/**
 * Test duress code activation in safe mode (no real alerts sent)
 * @param {string} authToken - JWT authentication token
 * @param {string} code - Duress code to test
 * @returns {Promise<Object>} Test activation result
 */
export const testActivation = async (authToken, code) => {
    const response = await fetch(`${BASE_URL}/duress/test/`, {
        method: 'POST',
        headers: getHeaders(authToken),
        body: JSON.stringify({ code })
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || 'Failed to test duress activation');
    }
    
    return response.json();
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Format threat level for display
 * @param {string} level - Threat level key
 * @returns {Object} { icon, label, color, description }
 */
export const formatThreatLevel = (level) => {
    const levels = {
        low: { 
            icon: '🟢', 
            label: 'Low', 
            color: '#22c55e',
            description: 'Show limited decoy vault'
        },
        medium: { 
            icon: '🟡', 
            label: 'Medium', 
            color: '#eab308',
            description: 'Full decoy + preserve evidence'
        },
        high: { 
            icon: '🟠', 
            label: 'High', 
            color: '#f97316',
            description: 'Decoy + alert authorities'
        },
        critical: { 
            icon: '🔴', 
            label: 'Critical', 
            color: '#ef4444',
            description: 'Full response + wipe real data access'
        }
    };
    return levels[level] || levels.medium;
};

/**
 * Format authority type for display
 * @param {string} type - Authority type key
 * @returns {Object} { icon, label }
 */
export const formatAuthorityType = (type) => {
    const types = {
        law_enforcement: { icon: '🚔', label: 'Law Enforcement' },
        legal_counsel: { icon: '⚖️', label: 'Legal Counsel' },
        security_team: { icon: '🛡️', label: 'Security Team' },
        family: { icon: '👨‍👩‍👧', label: 'Family Member' },
        custom: { icon: '📋', label: 'Custom Contact' }
    };
    return types[type] || types.custom;
};

/**
 * Format contact method for display
 * @param {string} method - Contact method key
 * @returns {Object} { icon, label }
 */
export const formatContactMethod = (method) => {
    const methods = {
        email: { icon: '📧', label: 'Email' },
        sms: { icon: '📱', label: 'SMS' },
        phone: { icon: '📞', label: 'Phone Call' },
        webhook: { icon: '🔗', label: 'Webhook' },
        signal: { icon: '💬', label: 'Signal' }
    };
    return methods[method] || methods.email;
};

/**
 * Calculate duress code strength
 * @param {string} code - The duress code
 * @returns {Object} { score: 0-100, label, suggestions[] }
 */
export const calculateCodeStrength = (code) => {
    let score = 0;
    const suggestions = [];
    
    // Length check
    if (code.length >= 8) score += 25;
    else if (code.length >= 6) score += 15;
    else suggestions.push('Use at least 8 characters');
    
    // Has numbers
    if (/\d/.test(code)) score += 20;
    else suggestions.push('Add numbers');
    
    // Has lowercase
    if (/[a-z]/.test(code)) score += 15;
    
    // Has uppercase
    if (/[A-Z]/.test(code)) score += 15;
    else suggestions.push('Add uppercase letters');
    
    // Has special chars
    if (/[!@#$%^&*(),.?":{}|<>]/.test(code)) score += 25;
    else suggestions.push('Add special characters');
    
    // Determine label
    let label = 'Weak';
    if (score >= 80) label = 'Strong';
    else if (score >= 60) label = 'Moderate';
    else if (score >= 40) label = 'Fair';
    
    return { score, label, suggestions };
};

export default {
    getConfig,
    updateConfig,
    getCodes,
    createCode,
    getCode,
    updateCode,
    deleteCode,
    getDecoyVault,
    regenerateDecoyVault,
    getAuthorities,
    addAuthority,
    updateAuthority,
    deleteAuthority,
    getEvents,
    getEvidencePackage,
    exportEvidencePackage,
    testActivation,
    formatThreatLevel,
    formatAuthorityType,
    formatContactMethod,
    calculateCodeStrength
};
