/**
 * Onion Sync Service
 *
 * Routes vault sync over the Tor onion service when the user asks for it.
 *
 * WHAT THIS FIXES
 * ---------------
 * The Tor infrastructure ("Dark Protocol") already existed and worked: a v3
 * onion service, a dedicated onion ingress listener, an ingress-verifying
 * `/vault-proxy/` endpoint that refuses clearnet outright, and `vault_sync`
 * already registered in the backend's VAULT_OPERATION_ROUTES. What was missing
 * was any client that used it -- `darkProtocolService.proxyVaultOperation` had
 * zero callers, and the real sync path went straight out over clearnet via
 * `vaultService.syncVault`. The rails were built; nothing rode them.
 *
 * WHAT IT DOES AND DOES NOT PROTECT
 * ---------------------------------
 * Onion routing here hides the client's **IP address** from the server, and
 * the existing cover-traffic generator raises the cost of timing analysis.
 *
 * It does NOT make the sync anonymous in the sense of unlinking it from the
 * user: `/vault-proxy/` is `IsAuthenticated`, so the JWT still names the
 * account. Claiming otherwise in the UI would be a lie the architecture cannot
 * back. True unlinkability needs anonymous credentials (blind-signed tokens
 * issued over clearnet, redeemed over onion) and is deliberately out of scope
 * here -- see docs/privacy-features-gap-remediation-plan.md §4.1 Phase 4.
 * Callers rendering privacy copy must say "hides your IP", not "the server
 * cannot identify you".
 *
 * Vault contents are unaffected either way: the payload is already encrypted
 * client-side before it reaches any transport. This module adds metadata
 * privacy only and changes no crypto, so it is orthogonal to -- and cannot
 * weaken -- the zero-knowledge invariant.
 *
 * TRANSPORT REALITY
 * -----------------
 * A page served over clearnet HTTPS cannot open a .onion connection; only a
 * process that can reach a SOCKS5 proxy can. So `prefer_onion` genuinely
 * upgrades the transport only when the app is being served FROM the onion
 * address (e.g. Tor Browser) or by a client that owns a Tor process. That is
 * why `syncVault` reports which transport it actually used instead of assuming
 * -- and why it gates on the server's own `vault_proxy.available`, which is
 * computed from whether THIS request arrived over the onion ingress, a network
 * fact the client cannot fake or wishfully assert.
 */

import darkProtocolService from './darkProtocolService';

export const SYNC_PRIVACY_MODES = {
    /** Today's behaviour: straight to the clearnet endpoint. */
    OFF: 'off',
    /** Use the onion route when genuinely available; fall back and say so. */
    PREFER_ONION: 'prefer_onion',
    /** Onion or nothing. Never silently downgrades. */
    REQUIRE_ONION: 'require_onion',
};

const STORAGE_KEY = 'vault.sync.privacyMode';

const VALID_MODES = new Set(Object.values(SYNC_PRIVACY_MODES));

/**
 * Read the user's sync privacy preference.
 *
 * Defaults to OFF so this module is inert until explicitly enabled -- shipping
 * a transport change that silently alters everyone's sync path would be a
 * surprising default for a security product.
 */
export const getSyncPrivacyMode = () => {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        return VALID_MODES.has(stored) ? stored : SYNC_PRIVACY_MODES.OFF;
    } catch {
        // Storage can throw in private-browsing / disabled-cookie contexts.
        return SYNC_PRIVACY_MODES.OFF;
    }
};

export const setSyncPrivacyMode = (mode) => {
    if (!VALID_MODES.has(mode)) {
        throw new Error(`Unknown sync privacy mode: ${mode}`);
    }
    localStorage.setItem(STORAGE_KEY, mode);
};

/**
 * Ask the server whether an onion-routed vault operation would actually work
 * right now.
 *
 * Gates on `vault_proxy.available`, which the backend computes as
 * `anonymity_active AND request arrived over the onion ingress` -- not on
 * `anonymity.available` alone, which only says the daemon is up. Using the
 * weaker signal would let us route a sync into a guaranteed
 * `clearnet_ingress_refused`.
 *
 * A failed capability fetch resolves to false. Treating an unreachable
 * capability endpoint as "available" would be the one failure mode this whole
 * feature exists to prevent: telling a user their sync was anonymous when it
 * was not.
 */
export const isOnionSyncAvailable = async () => {
    try {
        const capabilities = await darkProtocolService.getCapabilities();
        return Boolean(capabilities?.vault_proxy?.available);
    } catch {
        return false;
    }
};

/**
 * Error thrown when REQUIRE_ONION cannot be satisfied.
 *
 * Deliberately a hard failure. The alternative -- quietly syncing over
 * clearnet -- is precisely the "letting the client believe it was anonymous"
 * behaviour the backend's vault proxy refuses to do, and the client must not
 * undo that refusal from this side.
 */
export class OnionSyncUnavailableError extends Error {
    constructor(message = 'Onion-routed sync is unavailable and privacy mode is set to require it.') {
        super(message);
        this.name = 'OnionSyncUnavailableError';
        this.code = 'onion_required_unavailable';
    }
}

/**
 * Synchronise the vault, honouring the user's privacy mode.
 *
 * @param {Object} syncData - the same payload `vaultService.syncVault` takes
 * @param {Object} deps
 * @param {Object} deps.vaultService - injected for testability; must expose
 *   `syncVault(syncData)`
 * @param {string} [deps.mode] - override the stored preference
 * @returns {Promise<{data: Object, transport: 'onion'|'clearnet', degraded: boolean}>}
 *   `degraded` is true only when the user ASKED for onion and did not get it.
 *   Callers must surface that rather than swallowing it -- a silent downgrade
 *   is a false privacy promise.
 */
export const syncVault = async (syncData, { vaultService, mode = null } = {}) => {
    if (!vaultService || typeof vaultService.syncVault !== 'function') {
        throw new Error('onionSyncService.syncVault requires a vaultService dependency');
    }

    const effectiveMode = mode || getSyncPrivacyMode();

    if (effectiveMode === SYNC_PRIVACY_MODES.OFF) {
        // Byte-identical to the pre-existing path. No capability probe, so an
        // opted-out user pays nothing for this module existing.
        return {
            data: await vaultService.syncVault(syncData),
            transport: 'clearnet',
            degraded: false,
        };
    }

    const available = await isOnionSyncAvailable();

    if (available) {
        // `vault_sync` is already a registered operation on the backend's
        // route table; this is the call that was missing.
        const result = await darkProtocolService.proxyVaultOperation('vault_sync', syncData);
        return {
            // The proxy wraps the vault's own response in an envelope.
            data: result?.data ?? result,
            transport: 'onion',
            degraded: false,
        };
    }

    if (effectiveMode === SYNC_PRIVACY_MODES.REQUIRE_ONION) {
        throw new OnionSyncUnavailableError();
    }

    return {
        data: await vaultService.syncVault(syncData),
        transport: 'clearnet',
        degraded: true,
    };
};

export default {
    SYNC_PRIVACY_MODES,
    getSyncPrivacyMode,
    setSyncPrivacyMode,
    isOnionSyncAvailable,
    syncVault,
    OnionSyncUnavailableError,
};
