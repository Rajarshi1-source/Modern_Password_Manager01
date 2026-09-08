/**
 * The one derivation of "which account does this device-local vault state
 * belong to".
 *
 * Every hidden-vault artefact is keyed by this value and by nothing else:
 * `vaultUnlockEnvelope:<id>` (unlockEnvelopeStore), `vaultWrappedDEK:<id>`
 * (sessionVaultCrypto), and `vaultLocalCache:<id>` (decoyVaultStore). They are
 * only usable together if every caller computes the id the same way.
 *
 * It had been written out longhand at each call site instead, and adding a
 * fourth consumer is what exposed the cost: the decoy store was first written
 * against a bare `user.id`, so for any account whose `id` is absent it would
 * have written under `undefined` while the envelope it must open lived under
 * the email. Seeding would report success and the decoy would open empty --
 * a silent, account-shaped failure with nothing in the logs.
 *
 * `id` first because it is stable across an email change; `email` as the
 * fallback for identity shapes that carry no numeric id; `null` when neither
 * exists, which every consumer already treats as "no vault state available"
 * rather than as a usable key.
 */
export const vaultUserId = (user) => user?.id ?? user?.email ?? null;

export default vaultUserId;
