/**
 * Smoke + byte-layout tests for the browser HiddenVaultBlob implementation.
 *
 * The heavy "argon2 + WebCrypto end-to-end round-trip" is exercised in
 * Phase 8 (see ``phase8-tests``) under a dedicated jsdom+subtle setup.
 * Here we stick to exported invariants that do not touch Argon2 so the
 * suite runs fast and does not depend on the WASM build.
 */

import { describe, expect, test } from 'vitest';

import {
  TIERS,
  tierBytes,
  slotPayloadLen,
  HiddenVaultError,
  WrongPasswordError,
  MalformedBlobError,
  PayloadTooLargeError,
} from '../hiddenVaultEnvelope';

describe('hiddenVaultEnvelope tier invariants', () => {
  test('tier byte sizes are fixed per spec', () => {
    expect(tierBytes(TIERS.TIER0_32K)).toBe(32 * 1024);
    expect(tierBytes(TIERS.TIER1_128K)).toBe(128 * 1024);
    expect(tierBytes(TIERS.TIER2_1M)).toBe(1024 * 1024);
  });

  test('slot payload lengths match Python envelope', () => {
    // These numbers must agree with TIER_SLOT_PAYLOAD_LEN in envelope.py.
    expect(slotPayloadLen(TIERS.TIER0_32K)).toBe(16000);
    expect(slotPayloadLen(TIERS.TIER1_128K)).toBe(60000);
    expect(slotPayloadLen(TIERS.TIER2_1M)).toBe(490000);
  });

  test('unknown tier throws', () => {
    expect(() => tierBytes(999)).toThrow();
    expect(() => slotPayloadLen(999)).toThrow();
  });
});

describe('hiddenVaultEnvelope error hierarchy', () => {
  test('specialised errors descend from HiddenVaultError', () => {
    expect(new WrongPasswordError()).toBeInstanceOf(HiddenVaultError);
    expect(new MalformedBlobError()).toBeInstanceOf(HiddenVaultError);
    expect(new PayloadTooLargeError()).toBeInstanceOf(HiddenVaultError);
  });
});
