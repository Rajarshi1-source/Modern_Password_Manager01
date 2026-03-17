/**
 * FHE Sharing Service - Mobile
 *
 * Mobile service for Homomorphic Password Sharing API.
 * Mirrors the frontend fheSharingService.js for React Native.
 */

import axios from 'axios';
import { API_URL } from '../config';
import { authService } from './authService';

const API_BASE = `${API_URL}/api/fhe-sharing`;

const getHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Token ${authService.getToken()}`,
});

/**
 * Create a new homomorphic share.
 */
export const createShare = async (vaultItemId, recipientUsername, options = {}) => {
  const response = await axios.post(`${API_BASE}/shares/`, {
    vault_item_id: vaultItemId,
    recipient_username: recipientUsername,
    domain_constraints: options.domainConstraints || [],
    expires_at: options.expiresAt || null,
    max_uses: options.maxUses || null,
    group_id: options.groupId || null,
  }, { headers: getHeaders() });
  return response.data;
};

/**
 * List shares created by the current user.
 */
export const listMyShares = async (includeInactive = false) => {
  const response = await axios.get(`${API_BASE}/shares/list/`, {
    params: { include_inactive: includeInactive },
    headers: getHeaders(),
  });
  return response.data;
};

/**
 * List shares received by the current user.
 */
export const listReceivedShares = async () => {
  const response = await axios.get(`${API_BASE}/received/`, {
    headers: getHeaders(),
  });
  return response.data;
};

/**
 * Get details of a specific share.
 */
export const getShareDetail = async (shareId) => {
  const response = await axios.get(`${API_BASE}/shares/${shareId}/`, {
    headers: getHeaders(),
  });
  return response.data;
};

/**
 * Use an autofill token.
 */
export const useAutofillToken = async (shareId, domain, formFieldSelector = 'input[type="password"]') => {
  const response = await axios.post(`${API_BASE}/shares/${shareId}/use/`, {
    domain,
    form_field_selector: formFieldSelector,
  }, { headers: getHeaders() });
  return response.data;
};

/**
 * Revoke a share.
 */
export const revokeShare = async (shareId, reason = '') => {
  const response = await axios.delete(`${API_BASE}/shares/${shareId}/revoke/`, {
    data: { reason },
    headers: getHeaders(),
  });
  return response.data;
};

/**
 * Get access logs for a share.
 */
export const getShareLogs = async (shareId, page = 1, pageSize = 50) => {
  const response = await axios.get(`${API_BASE}/shares/${shareId}/logs/`, {
    params: { page, page_size: pageSize },
    headers: getHeaders(),
  });
  return response.data;
};

/**
 * Get FHE sharing service status.
 */
export const getShareStatus = async () => {
  const response = await axios.get(`${API_BASE}/status/`, {
    headers: getHeaders(),
  });
  return response.data;
};

const FHESharingService = {
  createShare,
  listMyShares,
  listReceivedShares,
  getShareDetail,
  useAutofillToken,
  revokeShare,
  getShareLogs,
  getShareStatus,
};

export default FHESharingService;
