/**
 * Device-local storage for recovery key pairs and sealed shares.
 *
 * - The guardian key pair lives on the guardian's device for as long as they
 *   are a guardian; its public key is what they give the account owner.
 * - A requester key pair is one-time, made per recovery request, and deleted
 *   once the seed is recovered.
 * - A guardian keeps a copy of its sealed share (opaque without its key) so it
 *   can re-seal it to a requester when approving.
 *
 * Nothing here is sent to the server except public keys and sealed values.
 */
import { newHolderKeyPair } from './sealedShareRecovery';

const GUARDIAN_KEY = 'pwm.recovery.guardianKeyPair.v1';
const requesterKey = (requestId) => `pwm.recovery.requesterKeyPair.v1.${requestId}`;
const sealedShareKey = (voucherId) => `pwm.recovery.sealedShare.v1.${voucherId}`;

function read(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function write(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

/** This device's guardian key pair, created on first use. */
export async function getOrCreateGuardianKeyPair() {
  const existing = read(GUARDIAN_KEY);
  if (existing?.publicKey && existing?.secretKey) return existing;
  const keyPair = await newHolderKeyPair();
  write(GUARDIAN_KEY, keyPair);
  return keyPair;
}

export function getGuardianKeyPair() {
  return read(GUARDIAN_KEY);
}

export async function newRequesterKeyPair() {
  return newHolderKeyPair();
}

export function saveRequesterKeyPair(requestId, keyPair) {
  write(requesterKey(requestId), keyPair);
}

export function getRequesterKeyPair(requestId) {
  return read(requesterKey(requestId));
}

export function forgetRequesterKeyPair(requestId) {
  try {
    window.localStorage.removeItem(requesterKey(requestId));
  } catch {
    /* storage unavailable: nothing to forget */
  }
}

export function saveSealedShare(voucherId, sealedShare) {
  write(sealedShareKey(voucherId), sealedShare);
}

export function getSealedShare(voucherId) {
  return read(sealedShareKey(voucherId));
}
