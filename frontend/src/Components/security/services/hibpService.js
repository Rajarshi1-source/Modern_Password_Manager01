import axios from 'axios';

class HibpService {
  constructor() {
    this.apiUrl = 'https://api.pwnedpasswords.com/range/';
    this.userAgent = 'PasswordManagerApp';
  }

  /**
   * Get the SHA-1 hash of a string
   * @param {string} text - Text to hash
   * @returns {Promise<string>} - SHA-1 hash
   */
  async sha1Hash(text) {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-1', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Check if a password has been exposed in data breaches using k-anonymity
   * @param {string} password - Password to check
   * @returns {Promise<number>} - Number of times the password has been exposed
   */
  async checkPassword(password) {
    try {
      // Generate SHA-1 hash of password
      const hash = await this.sha1Hash(password);
      const prefix = hash.substring(0, 5).toUpperCase();
      const suffix = hash.substring(5).toUpperCase();

      // Get hash suffixes from API using k-anonymity
      const response = await axios.get(`${this.apiUrl}${prefix}`, {
        headers: { 'User-Agent': this.userAgent }
      });

      // Search for our suffix in the response
      const lines = response.data.split('\n');
      for (const line of lines) {
        const [foundSuffix, count] = line.split(':');
        if (foundSuffix.trim() === suffix) {
          return parseInt(count.trim());
        }
      }

      return 0; // Password not found in breaches
    } catch (error) {
      console.error('Error checking password breach:', error);
      throw error;
    }
  }

  /**
   * Check password against HIBP using our backend proxy
   * Use this method instead of direct API calls to avoid CORS issues
   * @param {string} password - Password to check
   * @returns {Promise<number>} - Number of times the password has been exposed
   */
  async checkPasswordThroughBackend(password) {
    try {
      // Generate SHA-1 hash of password
      const hash = await this.sha1Hash(password);
      const prefix = hash.substring(0, 5).toUpperCase();
      const suffix = hash.substring(5).toUpperCase();

      // Call our backend API that proxies to HIBP
      const response = await axios.post('/api/security/dark-web/check_password/', {
        hash_prefix: prefix
      });

      // Our backend returns a map of suffixes to counts
      return response.data[suffix] || 0;
    } catch (error) {
      console.error('Error checking password breach via backend:', error);
      throw error;
    }
  }

  /**
   * Check if an email has been in a data breach
   * NOTE: This must be proxied through the backend to use an API key
   * @param {string} email - Email to check
   * @returns {Promise<Array>} - List of breaches
   */
  async checkEmailThroughBackend(email) {
    try {
      const response = await axios.post('/api/security/dark-web/check_email/', {
        email: email
      });
      return response.data;
    } catch (error) {
      console.error('Error checking email breach:', error);
      throw error;
    }
  }
}

// Export as singleton
export default new HibpService();
