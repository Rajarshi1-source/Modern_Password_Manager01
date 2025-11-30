import FingerprintJS from '@fingerprintjs/fingerprintjs';

/**
 * Utility class for generating and managing device fingerprints
 * to aid in identifying suspicious login attempts
 */
class DeviceFingerprint {
  constructor() {
    this.fpPromise = FingerprintJS.load();
  }

  /**
   * Generate a device fingerprint
   * @returns {Promise<string>} A unique device ID
   */
  async generate() {
    // Get the existing fingerprint from local storage if available
    const existingFingerprint = localStorage.getItem('device_fingerprint');
    if (existingFingerprint) {
      return existingFingerprint;
    }
    
    try {
      // Create a new fingerprint if one doesn't exist
      const fp = await this.fpPromise;
      const result = await fp.get();
      
      // The visitorId is the fingerprint we'll use
      const fingerprint = result.visitorId;
      
      // Store the fingerprint for future use
      localStorage.setItem('device_fingerprint', fingerprint);
      
      return fingerprint;
    } catch (error) {
      console.error('Error generating device fingerprint:', error);
      // Fallback to generating a UUID if fingerprinting fails
      return this._generateUUID();
    }
  }
  
  /**
   * Generate a UUID (fallback method)
   * @returns {string} A randomly generated UUID
   * @private
   */
  _generateUUID() {
    // Simple UUID generator as fallback
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : ((r & 0x3) | 0x8);
      return v.toString(16);
    });
  }
  
  /**
   * Clear the stored fingerprint
   * Used when logging out
   */
  clear() {
    localStorage.removeItem('device_fingerprint');
  }
  
  /**
   * Check if this device is registered with the backend
   * @returns {Promise<boolean>} Whether the device is registered
   */
  async isRegistered() {
    const fingerprint = await this.generate();
    
    try {
      const response = await fetch('/api/devices/check/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        },
        body: JSON.stringify({ device_id: fingerprint })
      });
      
      if (!response.ok) {
        return false;
      }
      
      const data = await response.json();
      return data.registered === true;
    } catch (error) {
      console.error('Error checking device registration:', error);
      return false;
    }
  }
}

// Export as singleton
const deviceFingerprint = new DeviceFingerprint();
export default deviceFingerprint; 