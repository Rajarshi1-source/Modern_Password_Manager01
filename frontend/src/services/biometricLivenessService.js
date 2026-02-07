/**
 * Biometric Liveness Service
 * 
 * Frontend service for deepfake-resistant biometric verification.
 * Handles API calls, WebSocket streaming, and camera capture utilities.
 */

const API_BASE = '/api/liveness';

class BiometricLivenessService {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.onFrameResult = null;
    this.onSessionComplete = null;
  }

  /**
   * Get auth headers for API requests
   */
  getHeaders() {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    };
  }

  /**
   * Start a new liveness verification session
   */
  async startSession(context = 'login', deviceFingerprint = '') {
    const response = await fetch(`${API_BASE}/session/start/`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ context, device_fingerprint: deviceFingerprint }),
    });

    if (!response.ok) {
      throw new Error('Failed to start liveness session');
    }

    const data = await response.json();
    this.sessionId = data.session_id;
    return data;
  }

  /**
   * Connect WebSocket for real-time frame processing
   */
  connectWebSocket(sessionId, onFrameResult, onComplete, onError) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/liveness/${sessionId}/`;
    
    this.ws = new WebSocket(wsUrl);
    this.onFrameResult = onFrameResult;
    this.onSessionComplete = onComplete;

    this.ws.onopen = () => {
      console.log('Liveness WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'frame_result' && this.onFrameResult) {
        this.onFrameResult(data);
      } else if (data.type === 'session_complete' && this.onSessionComplete) {
        this.onSessionComplete(data);
      } else if (data.type === 'error' && onError) {
        onError(data.message);
      }
    };

    this.ws.onerror = (error) => {
      console.error('Liveness WebSocket error:', error);
      if (onError) onError('WebSocket connection error');
    };

    this.ws.onclose = () => {
      console.log('Liveness WebSocket closed');
    };
  }

  /**
   * Send a video frame via WebSocket
   */
  sendFrame(frameBase64, width, height, timestampMs) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'frame',
        frame: frameBase64,
        width,
        height,
        timestamp_ms: timestampMs,
      }));
    }
  }

  /**
   * Submit challenge response via WebSocket
   */
  submitChallengeResponse(response) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'challenge_response',
        response,
      }));
    }
  }

  /**
   * Complete session via WebSocket
   */
  completeSession() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'complete' }));
    }
  }

  /**
   * Get current challenge via REST API
   */
  async getChallenge(sessionId) {
    const response = await fetch(`${API_BASE}/challenge/?session_id=${sessionId}`, {
      headers: this.getHeaders(),
    });
    return response.json();
  }

  /**
   * Get user's liveness profile
   */
  async getProfile() {
    const response = await fetch(`${API_BASE}/profile/`, {
      headers: this.getHeaders(),
    });
    return response.json();
  }

  /**
   * Get/update liveness settings
   */
  async getSettings() {
    const response = await fetch(`${API_BASE}/settings/`, {
      headers: this.getHeaders(),
    });
    return response.json();
  }

  async updateSettings(settings) {
    const response = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(settings),
    });
    return response.json();
  }

  /**
   * Get verification history
   */
  async getHistory(limit = 10) {
    const response = await fetch(`${API_BASE}/history/?limit=${limit}`, {
      headers: this.getHeaders(),
    });
    return response.json();
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.sessionId = null;
  }
}

// Camera capture utilities
export const CameraUtils = {
  /**
   * Start camera stream
   */
  async startCamera(videoElement, facingMode = 'user') {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode,
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
      });
      videoElement.srcObject = stream;
      await videoElement.play();
      return stream;
    } catch (error) {
      console.error('Camera access error:', error);
      throw error;
    }
  },

  /**
   * Stop camera stream
   */
  stopCamera(stream) {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }
  },

  /**
   * Capture frame from video as base64
   */
  captureFrame(videoElement, canvas) {
    const ctx = canvas.getContext('2d');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    ctx.drawImage(videoElement, 0, 0);
    
    // Get raw pixel data as base64
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const base64 = btoa(String.fromCharCode.apply(null, new Uint8Array(imageData.data.buffer)));
    
    return {
      base64,
      width: canvas.width,
      height: canvas.height,
    };
  },
};

// Timing utilities for reaction time measurement
export const TimingUtils = {
  getHighResTime: () => performance.now(),
  
  measureReactionTime: (startTime) => {
    return performance.now() - startTime;
  },
};

export default new BiometricLivenessService();
