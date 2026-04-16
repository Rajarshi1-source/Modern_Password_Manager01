/**
 * Ambient Biometric Fusion — service entry point.
 *
 * Combines the shared embedding helper and the HTTP client so callers
 * (the `BehavioralCaptureEngine`, `AmbientDashboard`, `SessionMonitor`)
 * only need a single import.
 */

import ambientApi from './ambientApi';
import {
  computeAmbientEmbedding,
  getOrCreateLocalSalt,
  rotateLocalSalt,
} from './ambientEmbedding';

/**
 * Build + ingest an ambient observation.
 *
 * @param {Object} args
 * @param {'web'|'extension'|'mobile'} args.surface
 * @param {string} args.deviceFp          Stable device fingerprint.
 * @param {Object} args.coarseFeatures    Bucketed features dict.
 * @param {Object} [args.sensitiveDigests] Pre-hashed hex strings for sensitive signals.
 *                                        Shape: { wifi: [...], bluetooth: [...], audio: [...] }
 * @param {number} [args.saltVersion=1]
 */
export const captureAndIngest = async ({
  surface,
  deviceFp,
  coarseFeatures = {},
  sensitiveDigests = {},
  saltVersion = 1,
}) => {
  if (!surface) throw new Error('captureAndIngest: surface required');
  if (!deviceFp) throw new Error('captureAndIngest: deviceFp required');

  const localSalt = getOrCreateLocalSalt();
  const {
    coarseFeatures: canonical,
    embeddingDigest,
    signalAvailability,
  } = await computeAmbientEmbedding({
    coarseFeatures,
    sensitiveDigests,
    localSalt,
  });

  return ambientApi.ingestObservation({
    surface,
    schema_version: 1,
    device_fp: deviceFp,
    local_salt_version: saltVersion,
    signal_availability: signalAvailability,
    coarse_features: canonical,
    embedding_digest: embeddingDigest,
  });
};

export {
  ambientApi,
  computeAmbientEmbedding,
  getOrCreateLocalSalt,
  rotateLocalSalt,
};

export default {
  ...ambientApi,
  captureAndIngest,
  computeAmbientEmbedding,
  getOrCreateLocalSalt,
  rotateLocalSalt,
};
