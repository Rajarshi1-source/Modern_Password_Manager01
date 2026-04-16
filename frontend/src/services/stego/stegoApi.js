/**
 * Thin axios wrapper around the ``/api/stego/`` endpoints.
 *
 * The server is treated as dumb storage + optional pixel-LSB helper:
 * the client always embeds/extracts locally when possible, and only
 * uses the server-side variants for cross-device transport.
 */

import axios from 'axios';

const BASE = '/api/stego';

function authHeaders(extra = {}) {
  const token =
    localStorage.getItem('access_token') ||
    sessionStorage.getItem('access_token') ||
    '';
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra };
}

export async function fetchStegoConfig() {
  const resp = await axios.get(`${BASE}/config/`, { headers: authHeaders() });
  return resp.data;
}

export async function listStegoVaults() {
  const resp = await axios.get(`${BASE}/`, { headers: authHeaders() });
  return resp.data;
}

export async function listStegoEvents() {
  const resp = await axios.get(`${BASE}/events/`, { headers: authHeaders() });
  return resp.data;
}

export async function downloadStegoImage(vaultId) {
  const resp = await axios.get(`${BASE}/${vaultId}/`, {
    headers: authHeaders(),
    responseType: 'arraybuffer',
  });
  return new Uint8Array(resp.data);
}

export async function deleteStegoVault(vaultId) {
  await axios.delete(`${BASE}/${vaultId}/`, { headers: authHeaders() });
}

export async function storeStegoImage({ imageBytes, label = 'Default', tier = 0, coverHash = '' }) {
  const form = new FormData();
  form.append('image', new Blob([imageBytes], { type: 'image/png' }), `${label}.png`);
  form.append('label', label);
  form.append('tier', String(tier));
  if (coverHash) form.append('cover_hash', coverHash);
  const resp = await axios.post(`${BASE}/store/`, form, {
    headers: authHeaders({ 'Content-Type': 'multipart/form-data' }),
  });
  return resp.data;
}

export async function serverEmbed({ coverBytes, blobBytes }) {
  const form = new FormData();
  form.append('cover', new Blob([coverBytes], { type: 'image/png' }), 'cover.png');
  form.append('blob', new Blob([blobBytes], { type: 'application/octet-stream' }), 'blob.bin');
  const resp = await axios.post(`${BASE}/embed/`, form, {
    headers: authHeaders({ 'Content-Type': 'multipart/form-data' }),
    responseType: 'arraybuffer',
  });
  return new Uint8Array(resp.data);
}

export async function serverExtract({ imageBytes }) {
  const form = new FormData();
  form.append('image', new Blob([imageBytes], { type: 'image/png' }), 'stego.png');
  const resp = await axios.post(`${BASE}/extract/`, form, {
    headers: authHeaders({ 'Content-Type': 'multipart/form-data' }),
    responseType: 'arraybuffer',
  });
  return new Uint8Array(resp.data);
}
