/**
 * Determinism + privacy tests for the shared ambient embedding helper.
 *
 * The embedding MUST be:
 *   - Deterministic for the same (coarseFeatures, sensitiveDigests, salt).
 *   - Stable under key reordering in coarseFeatures.
 *   - Different when the local salt changes.
 *   - Different when a coarse feature changes.
 *   - A 128-bit hex string (32 hex chars).
 *
 * The helper NEVER echoes sensitive values back; it only returns the
 * canonicalized coarse features, the opaque digest, and an availability
 * bitmap.
 */

import { describe, expect, test } from 'vitest';

import { computeAmbientEmbedding } from '../ambientEmbedding';

const baseInput = () => ({
  coarseFeatures: {
    light_bucket: 'indoor',
    motion_class: 'still',
    connection_class: 'wifi',
    battery_drain_slope_bucket: 'idle',
    is_business_hours: true,
  },
  sensitiveDigests: {
    wifi: ['a'.repeat(64)],
    bluetooth: ['b'.repeat(64)],
    audio: ['c'.repeat(64)],
  },
  localSalt: 'salt-v1-0123456789abcdef0123456789abcdef',
});

describe('computeAmbientEmbedding', () => {
  test('is deterministic for identical inputs', async () => {
    const a = await computeAmbientEmbedding(baseInput());
    const b = await computeAmbientEmbedding(baseInput());
    expect(a.embeddingDigest).toBe(b.embeddingDigest);
  });

  test('is stable under coarse key reordering', async () => {
    const input = baseInput();
    const reordered = {
      ...input,
      coarseFeatures: {
        is_business_hours: input.coarseFeatures.is_business_hours,
        connection_class: input.coarseFeatures.connection_class,
        battery_drain_slope_bucket: input.coarseFeatures.battery_drain_slope_bucket,
        motion_class: input.coarseFeatures.motion_class,
        light_bucket: input.coarseFeatures.light_bucket,
      },
    };
    const a = await computeAmbientEmbedding(input);
    const b = await computeAmbientEmbedding(reordered);
    expect(a.embeddingDigest).toBe(b.embeddingDigest);
  });

  test('salt rotation changes the digest', async () => {
    const a = await computeAmbientEmbedding(baseInput());
    const b = await computeAmbientEmbedding({ ...baseInput(), localSalt: 'salt-v2-differentbytes' });
    expect(a.embeddingDigest).not.toBe(b.embeddingDigest);
  });

  test('changing a coarse feature changes the digest', async () => {
    const a = await computeAmbientEmbedding(baseInput());
    const bInput = baseInput();
    bInput.coarseFeatures.light_bucket = 'sunlight';
    const b = await computeAmbientEmbedding(bInput);
    expect(a.embeddingDigest).not.toBe(b.embeddingDigest);
  });

  test('is a 128-bit (32 hex) digest', async () => {
    const r = await computeAmbientEmbedding(baseInput());
    expect(r.embeddingDigest).toMatch(/^[0-9a-f]{32}$/);
  });

  test('availability reflects present/absent coarse signals', async () => {
    const input = baseInput();
    delete input.coarseFeatures.light_bucket;
    input.sensitiveDigests = { wifi: [], bluetooth: [], audio: [] };
    const r = await computeAmbientEmbedding(input);
    expect(r.signalAvailability.ambient_light).toBe(false);
    expect(r.signalAvailability.wifi_signature).toBe(false);
    expect(r.signalAvailability.bluetooth_devices).toBe(false);
    expect(r.signalAvailability.ambient_audio).toBe(false);
    expect(r.signalAvailability.network_class).toBe(true);
  });

  test('output does not echo sensitive digests back', async () => {
    const r = await computeAmbientEmbedding(baseInput());
    const serialized = JSON.stringify(r);
    expect(serialized).not.toContain('a'.repeat(64));
    expect(serialized).not.toContain('b'.repeat(64));
    expect(serialized).not.toContain('c'.repeat(64));
  });

  test('empty input returns empty digest', async () => {
    const r = await computeAmbientEmbedding({ coarseFeatures: {}, sensitiveDigests: {}, localSalt: 's' });
    expect(r.embeddingDigest).toBe('');
  });
});
