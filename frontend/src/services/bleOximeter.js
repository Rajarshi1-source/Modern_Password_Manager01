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

// PLX Measurement Status bits (uint16) the device may report about a reading.
const MS_MEASUREMENT_UNAVAILABLE = 1 << 13;
const MS_QUESTIONABLE = 1 << 14;
const MS_INVALID = 1 << 15;

/**
 * Byte offset of the optional Measurement Status uint16, or -1 if the flags say
 * it is absent. Both characteristics start flags(1)|SpO2(2)|PR(2) = 5 bytes, but
 * the optional fields BEFORE Measurement Status differ:
 *   - Continuous (0x2A5F): bit0 SpO2PR-Fast(+4), bit1 SpO2PR-Slow(+4), bit2 = status.
 *   - Spot-check (0x2A5E): bit0 Timestamp(+7), bit1 = status.
 */
function measurementStatusOffset(flags, spotCheck) {
    if (spotCheck) {
        if (!(flags & 0x02)) return -1;
        return 5 + ((flags & 0x01) ? 7 : 0);
    }
    if (!(flags & 0x04)) return -1;
    return 5 + ((flags & 0x01) ? 4 : 0) + ((flags & 0x02) ? 4 : 0);
}

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
 * `status` is the optional Measurement Status uint16 when the flags advertise it,
 * else null. Pass `spotCheck` true for the 0x2A5E characteristic (different flag
 * layout). Returns { spo2, pulseRate, status } (each number, or null).
 */
export function parsePlxMeasurement(view, spotCheck = false) {
    if (!view || view.byteLength < 5) {
        return { spo2: null, pulseRate: null, status: null };
    }
    const flags = view.getUint8(0);
    const spo2 = parseSFloat(view, 1);
    const pulseRate = parseSFloat(view, 3);
    let status = null;
    const off = measurementStatusOffset(flags, spotCheck);
    if (off >= 0 && off + 2 <= view.byteLength) {
        status = view.getUint16(off, true);
    }
    return { spo2, pulseRate, status };
}

/**
 * Normalize a parsed measurement into a relayable reading.
 * A valid in-range SpO2 -> { spo2, quality: 1 }; anything else -> { spo2: null,
 * quality: 0 } so the backend clears rather than keeps a stale value. When the
 * device reports Measurement Status, a reading it flags invalid/unavailable is
 * cleared, and a "questionable" one is relayed at reduced quality rather than
 * treated as fully trustworthy -- never surface an untrustworthy signal at full
 * confidence.
 */
export function readingFromMeasurement(view, spotCheck = false) {
    const { spo2, status } = parsePlxMeasurement(view, spotCheck);
    if (spo2 == null || !Number.isFinite(spo2) || spo2 < 0 || spo2 > 100) {
        return { spo2: null, quality: 0 };
    }
    if (status != null && (status & (MS_INVALID | MS_MEASUREMENT_UNAVAILABLE))) {
        return { spo2: null, quality: 0 };
    }
    const quality = (status != null && (status & MS_QUESTIONABLE)) ? 0.5 : 1;
    return { spo2, quality };
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
        try {
            this.device = device;

            this._onDisconnected = () => {
                // On disconnect, relay a null reading so a stale value is cleared.
                if (onReading) onReading({ spo2: null, quality: 0 });
                if (onDisconnect) onDisconnect();
            };
            device.addEventListener('gattserverdisconnected', this._onDisconnected);

            const server = await device.gatt.connect();
            const service = await server.getPrimaryService(PULSE_OXIMETER_SERVICE);
            // Prefer continuous measurement; fall back to spot-check (which has a
            // different optional-field layout, so track which one we subscribed to
            // for correct Measurement Status decoding).
            let characteristic;
            let spotCheck = false;
            try {
                characteristic = await service.getCharacteristic(PLX_CONTINUOUS_MEASUREMENT);
            } catch {
                characteristic = await service.getCharacteristic(PLX_SPOT_CHECK_MEASUREMENT);
                spotCheck = true;
            }
            this.characteristic = characteristic;

            this._onValueChanged = (event) => {
                const view = event.target.value;
                if (onReading) onReading(readingFromMeasurement(view, spotCheck));
            };
            characteristic.addEventListener('characteristicvaluechanged', this._onValueChanged);
            await characteristic.startNotifications();
            return device;
        } catch (err) {
            // A post-connect step failed (service/characteristic/notify): tear
            // down the half-open GATT connection + listeners before rethrowing,
            // so we never leave the radio connected to a device we can't use.
            await this.disconnect();
            throw err;
        }
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
