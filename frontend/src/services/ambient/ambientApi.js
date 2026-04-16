/**
 * Thin axios client for the `/api/ambient/` endpoints.
 *
 * The embedding is already computed client-side (digest + coarse
 * features). This module only shuttles JSON.
 */

import api from '../api';

const BASE = '/api/ambient';

export const ingestObservation = async (payload) => {
  const response = await api.post(`${BASE}/ingest/`, payload);
  return response.data;
};

export const listContexts = async () => {
  const response = await api.get(`${BASE}/contexts/`);
  return response.data;
};

export const promoteContext = async ({ observationId, label }) => {
  const response = await api.post(`${BASE}/contexts/promote/`, {
    observation_id: observationId,
    label,
  });
  return response.data;
};

export const renameContext = async ({ contextId, label }) => {
  const response = await api.patch(`${BASE}/contexts/${contextId}/`, { label });
  return response.data;
};

export const deleteContext = async ({ contextId }) => {
  const response = await api.delete(`${BASE}/contexts/${contextId}/`);
  return response.data;
};

export const listObservations = async (limit = 50) => {
  const response = await api.get(`${BASE}/observations/`, { params: { limit } });
  return response.data;
};

export const getProfile = async () => {
  const response = await api.get(`${BASE}/profile/`);
  return response.data;
};

export const getSignalConfig = async () => {
  const response = await api.get(`${BASE}/settings/`);
  return response.data;
};

export const patchSignalConfig = async (updates) => {
  const response = await api.patch(`${BASE}/settings/`, updates);
  return response.data;
};

export const resetBaseline = async () => {
  const response = await api.post(`${BASE}/baseline/reset/`);
  return response.data;
};

export const getConfig = async () => {
  const response = await api.get(`${BASE}/config/`);
  return response.data;
};

export default {
  ingestObservation,
  listContexts,
  promoteContext,
  renameContext,
  deleteContext,
  listObservations,
  getProfile,
  getSignalConfig,
  patchSignalConfig,
  resetBaseline,
  getConfig,
};
