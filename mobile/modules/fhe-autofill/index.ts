/**
 * fhe-autofill — Expo native module bridge.
 *
 * The JavaScript layer in `mobile/src/services/fhe/preClient.js`
 * imports the module through `NativeModules.FheAutofill` so that it
 * remains callable even in the pure-JS fallback.  This file exports
 * typed helpers for consumers who want a friendlier API.
 */

import { requireNativeModule } from 'expo-modules-core';

export type UmbralPublicKeys = {
  umbralPublicKey: string;
  umbralVerifyingKey: string;
  umbralSignerPublicKey: string;
};

export type UmbralSecretKeys = {
  sk: string;
  signerSk: string;
};

export type UmbralIdentity = {
  public: UmbralPublicKeys;
  secret: UmbralSecretKeys;
};

export type PrePayload = {
  recipientSk: string;
  delegatingPk: string;
  verifyingPk: string;
  capsule: string;
  cfrag: string;
  ciphertext: string;
};

export type DecryptOptions = {
  sealedAutofill?: boolean;
  domain?: string;
  packageName?: string;
};

export type DecryptResult =
  | { plaintext: string; autofilled?: false }
  | { autofilled: true; domain: string };

type FheAutofillModuleShape = {
  isUmbralAvailable(): Promise<boolean>;
  generateKeyPair(): Promise<UmbralIdentity>;
  decryptReencrypted(payload: PrePayload, options: DecryptOptions): Promise<DecryptResult>;
  isSystemAutofillEnabled(): Promise<boolean>;
  openSystemAutofillSettings(): Promise<void>;
  storePendingFill(payload: PrePayload, packageHint: string): Promise<{ id: string }>;
  clearPendingFills(): Promise<void>;
};

const FheAutofillModule = requireNativeModule<FheAutofillModuleShape>('FheAutofill');
export default FheAutofillModule;
