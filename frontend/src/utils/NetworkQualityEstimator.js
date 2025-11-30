/**
 * Network Quality Estimator
 * 
 * Tracks connection latency and estimates network quality based on recent samples.
 * Used to provide real-time feedback on WebSocket connection health.
 */

class NetworkQualityEstimator {
  constructor() {
    this.latencies = [];
    this.maxSamples = 20;
  }

  /**
   * Add a new latency measurement
   * @param {number} latency - Latency in milliseconds
   */
  addLatency(latency) {
    this.latencies.push(latency);
    if (this.latencies.length > this.maxSamples) {
      this.latencies.shift();
    }
  }

  /**
   * Calculate average latency from recent samples
   * @returns {number} Average latency in milliseconds
   */
  getAverageLatency() {
    if (this.latencies.length === 0) return 0;
    const sum = this.latencies.reduce((a, b) => a + b, 0);
    return sum / this.latencies.length;
  }

  /**
   * Determine network quality based on average latency
   * @returns {Object} Quality level, text, and color
   */
  getQuality() {
    const avg = this.getAverageLatency();
    if (avg === 0) return { level: 'unknown', text: 'Unknown', color: 'gray' };
    if (avg < 100) return { level: 'excellent', text: 'Excellent', color: 'green' };
    if (avg < 300) return { level: 'good', text: 'Good', color: 'blue' };
    if (avg < 600) return { level: 'fair', text: 'Fair', color: 'yellow' };
    return { level: 'poor', text: 'Poor', color: 'red' };
  }

  /**
   * Calculate jitter (variance in latency)
   * @returns {number} Jitter in milliseconds
   */
  getJitter() {
    if (this.latencies.length < 2) return 0;
    let sum = 0;
    for (let i = 1; i < this.latencies.length; i++) {
      sum += Math.abs(this.latencies[i] - this.latencies[i - 1]);
    }
    return sum / (this.latencies.length - 1);
  }

  /**
   * Get packet loss estimate (based on missing pongs)
   * @returns {number} Estimated packet loss percentage
   */
  getPacketLoss() {
    // This would need actual missing pong tracking
    // Placeholder implementation
    return 0;
  }

  /**
   * Get detailed metrics
   * @returns {Object} All quality metrics
   */
  getMetrics() {
    return {
      averageLatency: this.getAverageLatency(),
      jitter: this.getJitter(),
      quality: this.getQuality(),
      sampleCount: this.latencies.length,
      minLatency: this.latencies.length > 0 ? Math.min(...this.latencies) : 0,
      maxLatency: this.latencies.length > 0 ? Math.max(...this.latencies) : 0
    };
  }

  /**
   * Reset all measurements
   */
  reset() {
    this.latencies = [];
  }
}

export default NetworkQualityEstimator;

