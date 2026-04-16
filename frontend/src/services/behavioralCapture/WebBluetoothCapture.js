/**
 * Web Bluetooth calibration-only capture.
 *
 * Web Bluetooth requires a user gesture and an explicit device selection
 * dialog — it is NOT a background signal. This module is used only by
 * the "Teach me this place" flow in the Ambient dashboard and hashes
 * the selected device's id + name into the LSH bit pool. Raw GATT or
 * address info never leaves the device.
 */

export class WebBluetoothCapture {
  constructor() {
    this.attached = false;
    this.deviceDigests = new Set(); // hex strings
    this.available = false;
  }

  attach() {
    if (this.attached) return;
    this.attached = true;
    try {
      this.available = Boolean(navigator && navigator.bluetooth);
    } catch {
      this.available = false;
    }
  }

  detach() {
    this.attached = false;
  }

  /**
   * Must be called from a user-gesture handler. Opens the browser device
   * chooser; the user picks one device at a time. We hash the opaque
   * `device.id` (and fallback name) and keep only the digest.
   *
   * Returns the hex digest string on success, null on cancel.
   */
  async addDeviceFromUserGesture() {
    if (!this.available || typeof navigator.bluetooth === 'undefined') return null;
    try {
      const device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
      });
      if (!device) return null;
      const text = `${device.id || ''}:${device.name || ''}`;
      const enc = new TextEncoder().encode(text);
      const hashBuf = await crypto.subtle.digest('SHA-256', enc);
      const hex = Array.from(new Uint8Array(hashBuf))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
      this.deviceDigests.add(hex);
      return hex;
    } catch {
      return null;
    }
  }

  async getFeatures() {
    return {
      bluetooth_device_count: this.deviceDigests.size,
      available: this.available,
    };
  }

  reset() {
    this.deviceDigests.clear();
  }

  /**
   * Expose the current digest set so `ambientEmbedding.js` can fold it
   * into the LSH digest.
   */
  getDigestSet() {
    return Array.from(this.deviceDigests);
  }
}
