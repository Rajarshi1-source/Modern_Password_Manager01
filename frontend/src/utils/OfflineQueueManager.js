/**
 * Offline Queue Manager
 * 
 * Manages a queue of breach alerts received while offline.
 * Stores alerts in localStorage and syncs them when connection is restored.
 */

class OfflineQueueManager {
  constructor() {
    this.queue = this.loadQueue();
    this.maxQueueSize = 100;
    this.storageKey = 'breach_alert_queue';
  }

  /**
   * Load queue from localStorage
   * @returns {Array} Queued alerts
   */
  loadQueue() {
    try {
      const stored = localStorage.getItem(this.storageKey);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('[OfflineQueue] Failed to load queue:', error);
      return [];
    }
  }

  /**
   * Save queue to localStorage
   */
  saveQueue() {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.queue));
    } catch (error) {
      console.error('[OfflineQueue] Failed to save queue:', error);
    }
  }

  /**
   * Add an alert to the queue
   * @param {Object} alert - Alert object
   * @returns {Object} Queued alert with metadata
   */
  enqueue(alert) {
    if (this.queue.length >= this.maxQueueSize) {
      console.warn('[OfflineQueue] Queue full, removing oldest alert');
      this.queue.shift(); // Remove oldest
    }
    
    const queuedAlert = {
      ...alert,
      queuedAt: new Date().toISOString(),
      id: `queued_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    };
    
    this.queue.push(queuedAlert);
    this.saveQueue();
    
    console.log(`[OfflineQueue] Alert queued. Queue size: ${this.queue.length}`);
    return queuedAlert;
  }

  /**
   * Remove and return all queued alerts
   * @returns {Array} All queued alerts
   */
  dequeueAll() {
    const alerts = [...this.queue];
    this.queue = [];
    this.saveQueue();
    
    console.log(`[OfflineQueue] Dequeued ${alerts.length} alerts`);
    return alerts;
  }

  /**
   * Get current queue size
   * @returns {number} Number of queued alerts
   */
  getQueueSize() {
    return this.queue.length;
  }

  /**
   * Get all queued alerts without removing them
   * @returns {Array} Queued alerts
   */
  peek() {
    return [...this.queue];
  }

  /**
   * Remove a specific alert from the queue
   * @param {string} alertId - ID of the alert to remove
   * @returns {boolean} True if alert was found and removed
   */
  remove(alertId) {
    const initialLength = this.queue.length;
    this.queue = this.queue.filter(alert => alert.id !== alertId);
    
    if (this.queue.length < initialLength) {
      this.saveQueue();
      return true;
    }
    return false;
  }

  /**
   * Clear all queued alerts
   */
  clear() {
    this.queue = [];
    this.saveQueue();
    console.log('[OfflineQueue] Queue cleared');
  }

  /**
   * Get oldest alert timestamp
   * @returns {string|null} ISO timestamp or null if queue is empty
   */
  getOldestTimestamp() {
    if (this.queue.length === 0) return null;
    return this.queue[0].queuedAt;
  }

  /**
   * Check if queue is full
   * @returns {boolean}
   */
  isFull() {
    return this.queue.length >= this.maxQueueSize;
  }

  /**
   * Get queue statistics
   * @returns {Object} Queue statistics
   */
  getStats() {
    return {
      size: this.queue.length,
      maxSize: this.maxQueueSize,
      isFull: this.isFull(),
      oldestTimestamp: this.getOldestTimestamp(),
      utilizationPercent: (this.queue.length / this.maxQueueSize) * 100
    };
  }
}

export default OfflineQueueManager;

