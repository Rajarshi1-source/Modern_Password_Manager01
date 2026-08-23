import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

vi.mock('./darkProtocolService', () => ({
    default: {
        getCapabilities: vi.fn(),
        proxyVaultOperation: vi.fn(),
    },
}));

import darkProtocolService from './darkProtocolService';
import onionSyncService, {
    SYNC_PRIVACY_MODES,
    getSyncPrivacyMode,
    setSyncPrivacyMode,
    isOnionSyncAvailable,
    syncVault,
    OnionSyncUnavailableError,
} from './onionSyncService';

const SYNC_DATA = { last_sync: '2026-01-01T00:00:00Z', items: [] };

let vaultService;

const capabilities = (vaultProxyAvailable) => ({
    anonymity: { available: true },
    vault_proxy: { available: vaultProxyAvailable },
});

beforeEach(() => {
    localStorage.clear();
    vaultService = { syncVault: vi.fn().mockResolvedValue({ items: ['clearnet'] }) };
    darkProtocolService.getCapabilities.mockReset();
    darkProtocolService.proxyVaultOperation.mockReset();
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('privacy mode preference', () => {
    test('defaults to off so the module is inert until enabled', () => {
        expect(getSyncPrivacyMode()).toBe(SYNC_PRIVACY_MODES.OFF);
    });

    test('round-trips a valid mode', () => {
        setSyncPrivacyMode(SYNC_PRIVACY_MODES.REQUIRE_ONION);

        expect(getSyncPrivacyMode()).toBe(SYNC_PRIVACY_MODES.REQUIRE_ONION);
    });

    test('rejects an unknown mode', () => {
        expect(() => setSyncPrivacyMode('sort_of_private')).toThrow();
    });

    test('falls back to off if storage holds a bogus value', () => {
        localStorage.setItem('vault.sync.privacyMode', 'nonsense');

        expect(getSyncPrivacyMode()).toBe(SYNC_PRIVACY_MODES.OFF);
    });
});

describe('isOnionSyncAvailable', () => {
    test('gates on vault_proxy.available, not anonymity.available', async () => {
        // The daemon being up is not enough -- the request must have arrived
        // over the onion ingress or the proxy will refuse it.
        darkProtocolService.getCapabilities.mockResolvedValue({
            anonymity: { available: true },
            vault_proxy: { available: false },
        });

        expect(await isOnionSyncAvailable()).toBe(false);
    });

    test('returns true when the proxy reports available', async () => {
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(true));

        expect(await isOnionSyncAvailable()).toBe(true);
    });

    test('treats a failed capability fetch as unavailable', async () => {
        // Never default to "available": that is exactly how a user gets told
        // their sync was anonymous when it was not.
        darkProtocolService.getCapabilities.mockRejectedValue(new Error('down'));

        expect(await isOnionSyncAvailable()).toBe(false);
    });
});

describe('syncVault — off', () => {
    test('goes straight to clearnet without probing capabilities', async () => {
        const result = await syncVault(SYNC_DATA, { vaultService });

        expect(vaultService.syncVault).toHaveBeenCalledWith(SYNC_DATA);
        expect(darkProtocolService.getCapabilities).not.toHaveBeenCalled();
        expect(result).toEqual({
            data: { items: ['clearnet'] },
            transport: 'clearnet',
            degraded: false,
        });
    });
});

describe('syncVault — prefer_onion', () => {
    test('routes through the vault proxy when available', async () => {
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(true));
        darkProtocolService.proxyVaultOperation.mockResolvedValue({
            success: true,
            data: { items: ['onion'] },
        });

        const result = await syncVault(SYNC_DATA, {
            vaultService,
            mode: SYNC_PRIVACY_MODES.PREFER_ONION,
        });

        expect(darkProtocolService.proxyVaultOperation).toHaveBeenCalledWith(
            'vault_sync',
            SYNC_DATA,
        );
        expect(vaultService.syncVault).not.toHaveBeenCalled();
        expect(result.transport).toBe('onion');
        expect(result.degraded).toBe(false);
        expect(result.data).toEqual({ items: ['onion'] });
    });

    test('falls back to clearnet BUT flags the downgrade', async () => {
        // The flag is the point. A silent fallback is a false privacy promise.
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(false));

        const result = await syncVault(SYNC_DATA, {
            vaultService,
            mode: SYNC_PRIVACY_MODES.PREFER_ONION,
        });

        expect(vaultService.syncVault).toHaveBeenCalledWith(SYNC_DATA);
        expect(result.transport).toBe('clearnet');
        expect(result.degraded).toBe(true);
    });
});

describe('syncVault — require_onion', () => {
    test('fails closed rather than downgrading', async () => {
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(false));

        await expect(
            syncVault(SYNC_DATA, {
                vaultService,
                mode: SYNC_PRIVACY_MODES.REQUIRE_ONION,
            }),
        ).rejects.toBeInstanceOf(OnionSyncUnavailableError);

        // The critical assertion: no clearnet request was made at all.
        expect(vaultService.syncVault).not.toHaveBeenCalled();
    });

    test('fails closed when the capability endpoint is unreachable', async () => {
        darkProtocolService.getCapabilities.mockRejectedValue(new Error('down'));

        await expect(
            syncVault(SYNC_DATA, {
                vaultService,
                mode: SYNC_PRIVACY_MODES.REQUIRE_ONION,
            }),
        ).rejects.toBeInstanceOf(OnionSyncUnavailableError);
        expect(vaultService.syncVault).not.toHaveBeenCalled();
    });

    test('succeeds over onion when available', async () => {
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(true));
        darkProtocolService.proxyVaultOperation.mockResolvedValue({
            data: { items: ['onion'] },
        });

        const result = await syncVault(SYNC_DATA, {
            vaultService,
            mode: SYNC_PRIVACY_MODES.REQUIRE_ONION,
        });

        expect(result.transport).toBe('onion');
        expect(result.degraded).toBe(false);
    });
});

describe('syncVault — contract', () => {
    test('uses the stored preference when no mode is passed', async () => {
        setSyncPrivacyMode(SYNC_PRIVACY_MODES.REQUIRE_ONION);
        darkProtocolService.getCapabilities.mockResolvedValue(capabilities(false));

        await expect(syncVault(SYNC_DATA, { vaultService })).rejects.toBeInstanceOf(
            OnionSyncUnavailableError,
        );
    });

    test('requires a vaultService dependency', async () => {
        await expect(syncVault(SYNC_DATA, {})).rejects.toThrow(/vaultService/);
    });

    test('rejects an explicit but invalid mode instead of silently downgrading', async () => {
        // A typo'd override must fail loudly -- falling through to the
        // degraded-clearnet branch would report `degraded: true` for a mode
        // that was never a real onion request, the same false-privacy-promise
        // the REQUIRE_ONION fail-closed behaviour above exists to prevent.
        await expect(
            syncVault(SYNC_DATA, { vaultService, mode: 'sort_of_private' }),
        ).rejects.toThrow(/Unknown sync privacy mode/);
        expect(darkProtocolService.getCapabilities).not.toHaveBeenCalled();
        expect(vaultService.syncVault).not.toHaveBeenCalled();
    });

    test('default export exposes the documented surface', () => {
        expect(Object.keys(onionSyncService).sort()).toEqual([
            'OnionSyncUnavailableError',
            'SYNC_PRIVACY_MODES',
            'getSyncPrivacyMode',
            'isOnionSyncAvailable',
            'setSyncPrivacyMode',
            'syncVault',
        ]);
    });
});
