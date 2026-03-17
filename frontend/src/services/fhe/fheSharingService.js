/**
 * FHE Sharing Service
 *
 * Frontend service for Homomorphic Password Sharing API.
 * Handles creating shares, using autofill tokens, managing groups,
 * and viewing access logs.
 *
 * The core concept: passwords are shared as FHE-encrypted "autofill tokens"
 * that can fill form fields but CANNOT be decrypted to reveal the password.
 */

import api from '../api';

const API_BASE = '/api/fhe-sharing';

/**
 * Create a new homomorphic share.
 *
 * @param {string} vaultItemId - UUID of the vault item to share
 * @param {string} recipientUsername - Username of the recipient
 * @param {Object} options - Additional options
 * @param {string[]} options.domainConstraints - Domains where autofill is allowed
 * @param {string|null} options.expiresAt - Expiration datetime (ISO 8601)
 * @param {number|null} options.maxUses - Maximum autofill uses
 * @param {string|null} options.groupId - Optional share group ID
 * @returns {Promise<Object>} Created share data
 */
export const createShare = async (vaultItemId, recipientUsername, options = {}) => {
  try {
    const response = await api.post(`${API_BASE}/shares/`, {
      vault_item_id: vaultItemId,
      recipient_username: recipientUsername,
      domain_constraints: options.domainConstraints || [],
      expires_at: options.expiresAt || null,
      max_uses: options.maxUses || null,
      group_id: options.groupId || null,
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Create share error:', error);
    throw error.response?.data || { error: 'Failed to create share' };
  }
};

/**
 * List shares created by the current user.
 *
 * @param {boolean} includeInactive - Include revoked/expired shares
 * @returns {Promise<Object>} List of shares
 */
export const listMyShares = async (includeInactive = false) => {
  try {
    const response = await api.get(`${API_BASE}/shares/list/`, {
      params: { include_inactive: includeInactive },
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] List shares error:', error);
    throw error.response?.data || { error: 'Failed to list shares' };
  }
};

/**
 * List shares received by the current user (available for autofill).
 *
 * @returns {Promise<Object>} List of received shares
 */
export const listReceivedShares = async () => {
  try {
    const response = await api.get(`${API_BASE}/received/`);
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] List received shares error:', error);
    throw error.response?.data || { error: 'Failed to list received shares' };
  }
};

/**
 * Get details of a specific share.
 *
 * @param {string} shareId - UUID of the share
 * @returns {Promise<Object>} Share details
 */
export const getShareDetail = async (shareId) => {
  try {
    const response = await api.get(`${API_BASE}/shares/${shareId}/`);
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Get share detail error:', error);
    throw error.response?.data || { error: 'Failed to get share details' };
  }
};

/**
 * Use an autofill token to fill a password form field.
 *
 * @param {string} shareId - UUID of the share
 * @param {string} domain - Domain where autofill is being attempted
 * @param {string} formFieldSelector - CSS selector for the target field
 * @returns {Promise<Object>} Autofill payload data
 */
export const useAutofillToken = async (
  shareId,
  domain,
  formFieldSelector = 'input[type="password"]'
) => {
  try {
    const response = await api.post(`${API_BASE}/shares/${shareId}/use/`, {
      domain,
      form_field_selector: formFieldSelector,
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Use autofill error:', error);
    throw error.response?.data || { error: 'Failed to use autofill' };
  }
};

/**
 * Revoke a share (owner only).
 *
 * @param {string} shareId - UUID of the share
 * @param {string} reason - Optional revocation reason
 * @returns {Promise<Object>} Updated share data
 */
export const revokeShare = async (shareId, reason = '') => {
  try {
    const response = await api.delete(`${API_BASE}/shares/${shareId}/revoke/`, {
      data: { reason },
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Revoke share error:', error);
    throw error.response?.data || { error: 'Failed to revoke share' };
  }
};

/**
 * Get access logs for a share (owner only).
 *
 * @param {string} shareId - UUID of the share
 * @param {number} page - Page number
 * @param {number} pageSize - Items per page
 * @returns {Promise<Object>} Paginated access logs
 */
export const getShareLogs = async (shareId, page = 1, pageSize = 50) => {
  try {
    const response = await api.get(`${API_BASE}/shares/${shareId}/logs/`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Get share logs error:', error);
    throw error.response?.data || { error: 'Failed to get share logs' };
  }
};

/**
 * Create a new share group.
 *
 * @param {string} name - Group name
 * @param {string} vaultItemId - UUID of the vault item
 * @param {string} description - Optional description
 * @returns {Promise<Object>} Created group data
 */
export const createShareGroup = async (name, vaultItemId, description = '') => {
  try {
    const response = await api.post(`${API_BASE}/groups/`, {
      name,
      vault_item_id: vaultItemId,
      description,
    });
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Create group error:', error);
    throw error.response?.data || { error: 'Failed to create group' };
  }
};

/**
 * List share groups owned by the current user.
 *
 * @returns {Promise<Object>} List of share groups
 */
export const listShareGroups = async () => {
  try {
    const response = await api.get(`${API_BASE}/groups/list/`);
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] List groups error:', error);
    throw error.response?.data || { error: 'Failed to list groups' };
  }
};

/**
 * Get FHE sharing service status.
 *
 * @returns {Promise<Object>} Service status data
 */
export const getShareStatus = async () => {
  try {
    const response = await api.get(`${API_BASE}/status/`);
    return response.data;
  } catch (error) {
    console.error('[FHE Sharing] Status error:', error);
    throw error.response?.data || { error: 'Failed to get status' };
  }
};

// Default export for convenience
const fheSharingService = {
  createShare,
  listMyShares,
  listReceivedShares,
  getShareDetail,
  useAutofillToken,
  revokeShare,
  getShareLogs,
  createShareGroup,
  listShareGroups,
  getShareStatus,
};

export default fheSharingService;
