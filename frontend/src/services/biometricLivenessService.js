/**
 * Biometric Liveness Service
 *
 * Frontend service for experimental biometric liveness verification.
 * Handles API calls, WebSocket streaming, and camera capture utilities.
 *
 * NOTE: the liveness checks are experimental signal-processing heuristics
 * (rPPG pulse, face-mesh landmarks), NOT a proven anti-deepfake guarantee —
 * there are no trained detection models behind them. Do not present the result
 * as definitive spoof resistance.
 */

import { authHeader } from '../utils/authHeader';
import { getWsTicket } from './wsTicket';

const API_BASE = '/api/liveness';

class BiometricLivenessService {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.onFrameResult = null;
    this.onSessionComplete = null;
    this.onChallengeResult = null;
    // Optional: transient (retryable) server conflicts. Left null by default so
    // they degrade to a console warning rather than the terminal error screen.
    this.onRetryableError = null;
    // Bumped by every connect/disconnect so an in-flight ticket fetch that has
    // been superseded doesn't open a stale socket.
    this.wsConnectGeneration = 0;
  }

  /**
   * Get auth headers for API requests
   */
  getHeaders() {
    return {
      'Content-Type': 'application/json',
      ...authHeader(),
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
   * Connect WebSocket for real-time frame processing.
   *
   * Exchanges the long-lived auth token for a short-lived, single-use ticket so
   * it never lands in the ws:// URL (access logs / browser history); the ticket
   * is consumed by the same TokenAuthMiddleware that authenticates the WS route,
   * so no consumer change is needed. Without it the socket connected as
   * AnonymousUser and the consumer immediately close(4001)'d. This is demo
   * enablement only — connecting the socket does NOT make the anti-spoofing
   * claims real.
   *
   * @param {function} [onChallengeResult] optional handler for the server's
   *   per-challenge outcome (challenge_result envelope): whether the challenge
   *   was scored/consumed and, once a real gaze estimator lands, whether it
   *   passed. Optional so existing callers keep working.
   * @returns {Promise<boolean>} true once the socket was created and handlers
   *   attached; false if the ticket fetch or socket construction failed, or the
   *   attempt was superseded. Callers must abort their "connected" flow on false.
   */
  async connectWebSocket(sessionId, onFrameResult, onComplete, onError, onChallengeResult) {
    const generation = ++this.wsConnectGeneration;
    this.onFrameResult = onFrameResult;
    this.onSessionComplete = onComplete;
    this.onChallengeResult = onChallengeResult;

    let ticket;
    try {
      ticket = await getWsTicket();
    } catch (error) {
      // Superseded by a disconnect()/newer connect() while the ticket was in
      // flight — stay silent for a dead attempt.
      if (generation !== this.wsConnectGeneration) return false;
      console.error('Error fetching liveness WebSocket ticket:', error);
      if (onError) onError('WebSocket authentication failed');
      return false;
    }
    // Superseded while the ticket was in flight — don't open a stale socket.
    if (generation !== this.wsConnectGeneration) return false;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/liveness/${sessionId}/?ticket=${encodeURIComponent(ticket)}`;

    try {
      this.ws = new WebSocket(wsUrl);
    } catch (error) {
      console.error('Error creating liveness WebSocket:', error);
      if (onError) onError('WebSocket connection error');
      return false;
    }

    this.ws.onopen = () => {
      console.log('Liveness WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        // A malformed frame must not throw out of the handler and kill the
        // session's message loop; drop it (matches darkProtocolService).
        console.error('Failed to parse liveness WebSocket message:', e);
        return;
      }

      if (data.type === 'frame_result' && this.onFrameResult) {
        this.onFrameResult(data);
      } else if (data.type === 'challenge_result' && this.onChallengeResult) {
        this.onChallengeResult(data);
      } else if (data.type === 'session_complete' && this.onSessionComplete) {
        this.onSessionComplete(data);
      } else if (data.type === 'error') {
        // `retryable` marks a TRANSIENT conflict (session_busy: another worker
        // briefly holds this session's cross-process lock). Routing it to
        // onError would halt capture and drop the user into the terminal error
        // screen over a collision that resolves in milliseconds, so it is
        // reported separately and the session simply keeps streaming.
        if (data.retryable) {
          if (this.onRetryableError) this.onRetryableError(data.message);
          else console.warn('Liveness transient error (retrying):', data.message);
        } else if (onError) {
          onError(data.message);
        }
      }
    };

    this.ws.onerror = (error) => {
      console.error('Liveness WebSocket error:', error);
      if (onError) onError('WebSocket connection error');
    };

    this.ws.onclose = () => {
      console.log('Liveness WebSocket closed');
    };

    return true;
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
   * Relay a real SpO2 reading from a paired BLE pulse oximeter over the same
   * session WebSocket. SpO2 is never derived from the webcam; this is the only
   * path it enters scoring. The backend stamps it on the server clock and
   * validates range/quality, so a bad reading is simply dropped (no SpO2).
   */
  submitHardwareSpo2(spo2, quality = 1.0) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'hardware_spo2', spo2, quality }));
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
   * Get server-side liveness capabilities: which modalities are genuinely
   * operational (e.g. deepfake model loaded, thermal source configured). SpO2
   * is always server-unavailable because it requires client oximeter hardware.
   */
  async getCapabilities() {
    const response = await fetch(`${API_BASE}/capabilities/`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      throw new Error('Failed to load liveness capabilities');
    }
    return response.json();
  }

  /**
   * Detect capabilities available on THIS device. SpO2 and thermal are
   * hardware-gated and never fabricated: SpO2 needs a Bluetooth pulse oximeter,
   * thermal needs an IR camera (no standard web API exposes one). If the
   * hardware isn't present, the modality stays off.
   */
  detectClientCapabilities() {
    const nav = typeof navigator !== 'undefined' ? navigator : {};
    const hasCamera = !!(nav.mediaDevices && nav.mediaDevices.getUserMedia);
    // Only detects whether the browser ships the Web Bluetooth API -- NOT that a
    // pulse oximeter is paired or reachable. A real SpO2 reading additionally
    // requires the user to pair a BLE oximeter, so spo2Hardware stays false here
    // and is only upgraded after a device is actually connected.
    const bluetoothApiSupported = 'bluetooth' in nav;
    return {
      camera: hasCamera,
      bluetoothApiSupported,
      spo2Hardware: false,
      // No standard web API exposes a thermal/IR camera stream in the browser.
      thermalHardware: false,
    };
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
    // Invalidate any connect() whose ticket request is still in flight.
    this.wsConnectGeneration++;
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
