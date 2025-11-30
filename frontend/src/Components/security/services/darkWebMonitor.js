import axios from 'axios';
import hibpService from './hibpService';

class DarkWebMonitor {
  constructor() {
    this.apiClient = axios.create({
      baseURL: '/api/security/dark-web',
      headers: {'Content-Type': 'application/json'}
    });
  }

  /**
   * Get all breach alerts for the current user
   * @returns {Promise<Array>} - List of breach alerts
   */
  async getBreachAlerts() {
    try {
      const response = await this.apiClient.get('/get_breaches/');
      return response.data;
    } catch (error) {
      console.error('Error fetching breach alerts:', error);
      throw error;
    }
  }

  /**
   * Mark a breach alert as resolved
   * @param {number} alertId - ID of the alert to resolve
   * @returns {Promise<Object>} - Response from the server
   */
  async markBreachResolved(alertId) {
    try {
      const response = await this.apiClient.post('/mark_resolved/', {
        alert_id: alertId
      });
      return response.data;
    } catch (error) {
      console.error('Error resolving breach alert:', error);
      throw error;
    }
  }

  /**
   * Start a server-side scan of the user's vault
   * @returns {Promise<Object>} - Response with task_id
   */
  async startVaultScan() {
    try {
      const response = await this.apiClient.post('/scan_vault/');
      return response.data;
    } catch (error) {
      console.error('Error starting vault scan:', error);
      throw error;
    }
  }

  /**
   * Check the status of a vault scan task
   * @param {string} taskId - ID of the scan task
   * @returns {Promise<Object>} - Task status
   */
  async checkScanStatus(taskId) {
    try {
      const response = await this.apiClient.get('/scan_status/', {
        params: { task_id: taskId }
      });
      return response.data;
    } catch (error) {
      console.error('Error checking scan status:', error);
      throw error;
    }
  }

  /**
   * Check all passwords in the vault for breaches
   * This runs client-side to protect password privacy
   * @param {Array} vaultItems - List of vault items
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>} - Scan results
   */
  async scanVaultPasswords(vaultItems, progressCallback) {
    const passwordItems = vaultItems.filter(item => 
      item.type === 'password' || 
      (item.item_type === 'password')
    );
    
    const results = {
      total: passwordItems.length,
      breached: 0,
      items: []
    };

    for (let i = 0; i < passwordItems.length; i++) {
      const item = passwordItems[i];
      
      try {
        // Get the actual password from the item
        // In a real app, this would be decrypted from item.encrypted_data
        let password;
        if (item.data && item.data.password) {
          password = item.data.password;
        } else if (item.encrypted_data) {
          // Example: This would normally decrypt the password
          const data = JSON.parse(item.encrypted_data);
          password = data.password;
        }

        if (password) {
          // Check if password is breached
          const breachCount = await hibpService.checkPasswordThroughBackend(password);
          
          if (breachCount > 0) {
            results.breached++;
            results.items.push({
              id: item.id || item.item_id,
              name: item.data?.name || JSON.parse(item.encrypted_data || '{}').name || 'Unknown',
              count: breachCount
            });
          }
        }
      } catch (err) {
        console.error('Error checking password:', err);
      }

      // Update progress
      if (progressCallback) {
        progressCallback({
          current: i + 1,
          total: passwordItems.length
        });
      }
    }

    return results;
  }

  /**
   * Check if a specific password is breached
   * @param {string} password - Password to check
   * @returns {Promise<number>} - Number of breach occurrences
   */
  async checkPassword(password) {
    return await hibpService.checkPasswordThroughBackend(password);
  }
}

// Export as singleton
export default new DarkWebMonitor();
