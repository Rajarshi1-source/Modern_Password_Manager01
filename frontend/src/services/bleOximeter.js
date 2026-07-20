/**
 * BLE Pulse Oximeter (Web Bluetooth)
 *
 * Reads real SpO2 from a standard Bluetooth GATT Pulse Oximeter Service
 * (0x1822 / PLX). This is the ONLY source of SpO2 in the liveness flow -- a
 * webcam cannot measure blood oxygen, so it is never estimated from video. The
 * value read here is relayed to the backend as an explicit hardware reading; no
 * device simply means no SpO2 (the tile hides and it is excluded from scoring).
 *
 * The measurement value is an IEEE-11073 16-bit SFLOAT (little-endian on the
 * wire). The pure parsers below are unit-tested with known bytes; the device I/O
 * is a thin wrapper over the browser's Web Bluetooth API.
 */

// GATT assigned numbers (short 16-bit UUIDs).
export const PULSE_OXIMETER_SERVICE = 0x1822;
export const PLX_CONTINUOUS_MEASUREMENT = 0x2a5f;
export const PLX_SPOT_CHECK_MEASUREMENT = 0x2a5e;

// Reserved special SFLOAT mantissa values (IEEE 11073-20601) -> no real number.
const SFLOAT_NAN = 0x07ff;
const SFLOAT_NRES = 0x0800;
const SFLOAT_RESERVED = 0x0801;
const SFLOAT_POS_INF = 0x07fe;
const SFLOAT_NEG_INF = 0x0802;

/** True only when the browser exposes the Web Bluetooth API (not that a device is paired). */
export function isBleOximeterSupported() {
    return typeof navigator !== 'undefined' && Boolean(navigator.bluetooth);
}

/**
 * Parse an IEEE-11073 16-bit SFLOAT at `offset` (little-endian).
 * Returns a finite number, or null for the reserved NaN/NRes/Inf values.
 */
export function parseSFloat(view, offset) {
    const raw = view.getUint16(offset, true); // BLE is little-endian
    let mantissa = raw & 0x0fff;
    let exponent = raw >> 12;

    // Reserved special values are encoded in the mantissa field.
    if (
        mantissa === SFLOAT_NAN ||
        mantissa === SFLOAT_NRES ||
        mantissa === SFLOAT_RESERVED ||
        mantissa === SFLOAT_POS_INF ||
        mantissa === SFLOAT_NEG_INF
    ) {
        return null;
    }

    // Sign-extend the 12-bit mantissa and 4-bit exponent (two's complement).
    if (mantissa >= 0x0800) mantissa -= 0x1000;
    if (exponent >= 0x0008) exponent -= 0x0010;

    return mantissa * 10 ** exponent;
}

/**
 * Parse the SpO2 (and pulse rate) from a PLX Continuous (0x2A5F) or Spot-check
 * (0x2A5E) measurement. Both start with: flags(1) | SpO2 SFLOAT(2) | PR SFLOAT(2).
 * Returns { spo2, pulseRate } where each is a number or null.
 */
export function parsePlxMeasurement(view) {
    if (!view || view.byteLength < 5) {
        return { spo2: null, pulseRate: null };
    }
    // byte 0 is flags; the mandatory SpO2/PR SFLOATs follow.
    const spo2 = parseSFloat(view, 1);
    const pulseRate = parseSFloat(view, 3);
    return { spo2, pulseRate };
}

/**
 * Normalize a parsed measurement into a relayable reading.
 * A valid in-range SpO2 -> { spo2, quality: 1 }; anything else -> { spo2: null,
 * quality: 0 } so the backend clears rather than keeps a stale value.
 */
export function readingFromMeasurement(view) {
    const { spo2 } = parsePlxMeasurement(view);
    if (spo2 == null || !Number.isFinite(spo2) || spo2 < 0 || spo2 > 100) {
        return { spo2: null, quality: 0 };
    }
    return { spo2, quality: 1 };
}

/**
 * Manages a paired oximeter: connect, subscribe to measurement notifications,
 * and emit normalized readings. Kept small and injectable so it can be driven
 * with a mocked navigator.bluetooth in tests.
 */
export class BleOximeter {
    constructor() {
        this.device = null;
        this.characteristic = null;
        this._onValueChanged = null;
        this._onDisconnected = null;
    }

    /**
     * Prompt the user to pick an oximeter, connect, and start streaming readings.
     * @param {(reading: {spo2: number|null, quality: number}) => void} onReading
     * @param {() => void} [onDisconnect]
     */
    async connect(onReading, onDisconnect) {
        if (!isBleOximeterSupported()) {
            throw new Error('Web Bluetooth is not available in this browser');
        }
        const device = await navigator.bluetooth.requestDevice({
            filters: [{ services: [PULSE_OXIMETER_SERVICE] }],
        });
        this.device = device;

        this._onDisconnected = () => {
            // On disconnect, relay a null reading so a stale value is cleared.
            if (onReading) onReading({ spo2: null, quality: 0 });
            if (onDisconnect) onDisconnect();
        };
        device.addEventListener('gattserverdisconnected', this._onDisconnected);

        const server = await device.gatt.connect();
        const service = await server.getPrimaryService(PULSE_OXIMETER_SERVICE);
        // Prefer continuous measurement; fall back to spot-check.
        let characteristic;
        try {
            characteristic = await service.getCharacteristic(PLX_CONTINUOUS_MEASUREMENT);
        } catch {
            characteristic = await service.getCharacteristic(PLX_SPOT_CHECK_MEASUREMENT);
        }
        this.characteristic = characteristic;

        this._onValueChanged = (event) => {
            const view = event.target.value;
            if (onReading) onReading(readingFromMeasurement(view));
        };
        characteristic.addEventListener('characteristicvaluechanged', this._onValueChanged);
        await characteristic.startNotifications();
        return device;
    }

    /** Stop notifications and disconnect. Idempotent; safe to call if never connected. */
    async disconnect() {
        try {
            if (this.characteristic && this._onValueChanged) {
                this.characteristic.removeEventListener(
                    'characteristicvaluechanged', this._onValueChanged);
                await this.characteristic.stopNotifications();
            }
        } catch {
            // Device may already be gone; ignore.
        }
        if (this.device) {
            if (this._onDisconnected) {
                this.device.removeEventListener('gattserverdisconnected', this._onDisconnected);
            }
            try {
                if (this.device.gatt && this.device.gatt.connected) this.device.gatt.disconnect();
            } catch {
                // ignore
            }
        }
        this.device = null;
        this.characteristic = null;
        this._onValueChanged = null;
        this._onDisconnected = null;
    }
}
