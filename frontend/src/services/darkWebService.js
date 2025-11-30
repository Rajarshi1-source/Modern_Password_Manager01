import axios from 'axios';
import { CryptoService } from './cryptoService';

export class DarkWebService {
  constructor(apiClient) {
    this.api = apiClient || axios.create({
      baseURL: '/api',
      headers: {'Content-Type': 'application/json'}
    });
    this.crypto = new CryptoService();
  }
  
  /**
   * Check if a password has been exposed in data breaches
   * Uses k-anonymity technique to protect password
   */
  async checkPassword(password) {
    // Generate SHA-1 hash of password
    const hash = await this.crypto.sha1Hash(password);
    const prefix = hash.substring(0, 5);
    const suffix = hash.substring(5).toUpperCase();
    
    // Send only prefix to server (k-anonymity)
    const response = await this.api.post('/security/dark-web/check_password/', {
      hash_prefix: prefix
    });
    
    // Check if our suffix exists in the returned list
    return response.data[suffix] || 0;
  }
  
  /**
   * Check all vault passwords for breaches
   * Runs entirely client-side to preserve privacy
   */
  async checkVaultPasswords(vaultItems, progressCallback) {
    const results = {
      total: 0,
      breached: 0,
      items: []
    };
    
    // Filter for password items
    const passwordItems = vaultItems.filter(i => i.type === 'password');
    results.total = passwordItems.length;
    
    // Process 5 passwords at a time to avoid rate limiting
    for (let i = 0; i < passwordItems.length; i += 5) {
      const batch = passwordItems.slice(i, i + 5);
      
      // Process batch in parallel
      const promises = batch.map(async (item) => {
        try {
          const occurrences = await this.checkPassword(item.data.password);
          
          if (occurrences > 0) {
            results.breached++;
            results.items.push({
              id: item.id,
              name: item.data.name,
              username: item.data.username,
              url: item.data.url,
              occurrences
            });
          }
          
          // Update progress
          if (progressCallback) {
            progressCallback({
              current: i + batch.indexOf(item) + 1,
              total: passwordItems.length
            });
          }
          
        } catch (error) {
          console.error('Error checking password:', error);
        }
      });
      
      await Promise.all(promises);
      
      // Add slight delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    return results;
  }
  
  /**
   * Get breach alerts from server
   */
  async getBreachAlerts() {
    const response = await this.api.get('/security/dark-web/get_breaches/');
    return response.data;
  }
  
  /**
   * Mark breach alert as resolved
   */
  async markBreachResolved(alertId) {
    const response = await this.api.post('/security/dark-web/mark_resolved/', {
      alert_id: alertId
    });
    return response.data;
  }
  
  /**
   * Start a full vault scan
   */
  async startVaultScan() {
    const response = await this.api.post('/security/dark-web/scan_vault/');
    return response.data;
  }
}
