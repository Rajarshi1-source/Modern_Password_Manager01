/**
 * Tests for the BLE pulse-oximeter helper.
 *
 * Covers the pure IEEE-11073 SFLOAT / PLX-measurement parsers (with known bytes)
 * and the pairing/relay flow over a mocked navigator.bluetooth. SpO2 is only
 * ever a real hardware reading -- these lock the parse + relay path.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import {
    parseSFloat,
    parsePlxMeasurement,
    readingFromMeasurement,
    isBleOximeterSupported,
    BleOximeter,
    PULSE_OXIMETER_SERVICE,
} from '../bleOximeter';

const viewOf = (bytes) => new DataView(new Uint8Array(bytes).buffer);

describe('SFLOAT / PLX parsing', () => {
    it('parses an integer SFLOAT (exponent 0)', () => {
        // 98 -> mantissa 0x062, exponent 0 -> raw 0x0062, little-endian [0x62,0x00]
        expect(parseSFloat(viewOf([0x62, 0x00]), 0)).toBe(98);
    });

    it('parses a fractional SFLOAT (negative exponent)', () => {
        // 97.5 -> mantissa 975 (0x3CF), exponent -1 (0xF) -> raw 0xF3CF -> [0xCF,0xF3]
        expect(parseSFloat(viewOf([0xcf, 0xf3]), 0)).toBeCloseTo(97.5, 5);
    });

    it('returns null for the reserved NaN value', () => {
        // mantissa 0x07FF -> raw 0x07FF -> [0xFF,0x07]
        expect(parseSFloat(viewOf([0xff, 0x07]), 0)).toBeNull();
    });

    it('extracts SpO2 and pulse rate from a PLX measurement', () => {
        // flags 0x00 | SpO2 98 [0x62,0x00] | PR 72 [0x48,0x00]
        const m = parsePlxMeasurement(viewOf([0x00, 0x62, 0x00, 0x48, 0x00]));
        expect(m.spo2).toBe(98);
        expect(m.pulseRate).toBe(72);
    });

    it('returns nulls for a too-short measurement', () => {
        expect(parsePlxMeasurement(viewOf([0x00, 0x01]))).toEqual({ spo2: null, pulseRate: null });
    });

    it('normalizes a valid reading to quality 1, and NaN/out-of-range to cleared', () => {
        expect(readingFromMeasurement(viewOf([0x00, 0x62, 0x00, 0x48, 0x00])))
            .toEqual({ spo2: 98, quality: 1 });
        // NaN SpO2 -> cleared
        expect(readingFromMeasurement(viewOf([0x00, 0xff, 0x07, 0x48, 0x00])))
            .toEqual({ spo2: null, quality: 0 });
    });
});

describe('BleOximeter pairing + relay', () => {
    const originalBluetooth = navigator.bluetooth;

    afterEach(() => {
        Object.defineProperty(navigator, 'bluetooth', {
            value: originalBluetooth,
            configurable: true,
        });
    });

    const mockBluetooth = () => {
        const charListeners = {};
        const deviceListeners = {};
        const characteristic = {
            addEventListener: vi.fn((type, cb) => { charListeners[type] = cb; }),
            removeEventListener: vi.fn(),
            startNotifications: vi.fn().mockResolvedValue(undefined),
            stopNotifications: vi.fn().mockResolvedValue(undefined),
        };
        const service = { getCharacteristic: vi.fn().mockResolvedValue(characteristic) };
        const gatt = {
            connected: true,
            connect: vi.fn(function () { return Promise.resolve(gatt); }),
            disconnect: vi.fn(),
            getPrimaryService: vi.fn().mockResolvedValue(service),
        };
        const device = {
            gatt,
            addEventListener: vi.fn((type, cb) => { deviceListeners[type] = cb; }),
            removeEventListener: vi.fn(),
        };
        const bluetooth = { requestDevice: vi.fn().mockResolvedValue(device) };
        Object.defineProperty(navigator, 'bluetooth', { value: bluetooth, configurable: true });
        return { bluetooth, device, service, gatt, characteristic, charListeners, deviceListeners };
    };

    it('reports support based on the Web Bluetooth API presence', () => {
        mockBluetooth();
        expect(isBleOximeterSupported()).toBe(true);
        Object.defineProperty(navigator, 'bluetooth', { value: undefined, configurable: true });
        expect(isBleOximeterSupported()).toBe(false);
    });

    it('connects filtering on the Pulse Oximeter Service and relays parsed readings', async () => {
        const { bluetooth, service, characteristic, charListeners } = mockBluetooth();
        const onReading = vi.fn();
        const oximeter = new BleOximeter();

        await oximeter.connect(onReading);

        expect(bluetooth.requestDevice).toHaveBeenCalledWith({
            filters: [{ services: [PULSE_OXIMETER_SERVICE] }],
        });
        expect(service.getCharacteristic).toHaveBeenCalled();
        expect(characteristic.startNotifications).toHaveBeenCalled();

        // Simulate a device notification: SpO2 98%.
        charListeners.characteristicvaluechanged({
            target: { value: viewOf([0x00, 0x62, 0x00, 0x48, 0x00]) },
        });
        expect(onReading).toHaveBeenCalledWith({ spo2: 98, quality: 1 });

        await oximeter.disconnect();
        expect(characteristic.stopNotifications).toHaveBeenCalled();
    });

    it('relays a cleared reading and notifies on a device-initiated disconnect', async () => {
        const { deviceListeners } = mockBluetooth();
        const onReading = vi.fn();
        const onDisconnect = vi.fn();
        const oximeter = new BleOximeter();
        await oximeter.connect(onReading, onDisconnect);

        // The device drops (gattserverdisconnected). SpO2 must clear + notify.
        deviceListeners.gattserverdisconnected();
        expect(onReading).toHaveBeenCalledWith({ spo2: null, quality: 0 });
        expect(onDisconnect).toHaveBeenCalled();
    });

    it('tears down the GATT connection if a post-connect step fails', async () => {
        const { gatt } = mockBluetooth();
        gatt.getPrimaryService.mockRejectedValueOnce(new Error('no service'));
        const oximeter = new BleOximeter();

        await expect(oximeter.connect(vi.fn())).rejects.toThrow('no service');
        // The half-open GATT connection is torn down rather than left dangling.
        expect(gatt.disconnect).toHaveBeenCalled();
    });

    it('throws when Web Bluetooth is unavailable', async () => {
        Object.defineProperty(navigator, 'bluetooth', { value: undefined, configurable: true });
        const oximeter = new BleOximeter();
        await expect(oximeter.connect(vi.fn())).rejects.toThrow();
    });
});
