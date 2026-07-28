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

// Bounded retry for one-shot control ops conflicted by session_busy. The server
// holds a session lock only for a single fast operation, so 150/300/600/1200ms
// covers ordinary contention; past that it is not transient and the caller is
// told rather than left waiting.
const ONE_SHOT_RETRY_LIMIT = 4;
const ONE_SHOT_RETRY_BASE_MS = 150;

// A server `error` frame's `message` arrives in one of two shapes: a snake_case
// WIRE CODE minted by the consumer for something the user must not read
// verbatim ('internal_error', 'invalid_session_state'), or already-human prose
// from the service/decode layer ('Session expired', 'Invalid frame encoding',
// 'Missing frame data'). LivenessVerification renders whatever reaches onError
// straight into its error screen, so codes MUST be translated -- and prose must
// NOT be, or a specific, actionable message would be flattened into a vague one.
const ERROR_COPY = {
  session_busy: 'Verification is busy; please try again',
  internal_error: 'Verification failed unexpectedly; please try again',
  invalid_session_state:
    'This verification session is no longer active; please start again',
};
const GENERIC_ERROR = 'Verification failed; please try again';
// Every wire code is a bare lowercase identifier; every prose message the server
// sends carries spaces and a capital. Shape-testing the UNMAPPED ones is the
// point of this guard, more than the map itself: a code added server-side after
// this client shipped (say 'session_revoked') would otherwise print raw on the
// error screen, which is exactly the bug being fixed.
const WIRE_CODE_RE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;

function humanizeError(message) {
  if (typeof message !== 'string' || !message) return GENERIC_ERROR;
  // hasOwnProperty, not truthiness: a message of 'constructor' would otherwise
  // resolve off the prototype and hand a function to the error screen.
  if (Object.prototype.hasOwnProperty.call(ERROR_COPY, message)) {
    return ERROR_COPY[message];
  }
  return WIRE_CODE_RE.test(message) ? GENERIC_ERROR : message;
}

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
    // The last one-shot control op awaiting an answer, kept so a session_busy
    // can re-send it (see _sendOneShot).
    this._pendingOneShot = null;
    this._onError = null;
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
    // Kept so a one-shot op that stays conflicted after every retry can still
    // escalate to the terminal error path instead of hanging.
    this._onError = onError;
    this._pendingOneShot = null;

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

      // An answer retires the outstanding op so a later session_busy cannot
      // resurrect it -- but ONLY if it answers THAT op. Clearing on any answer
      // breaks the eviction case: after `complete` supersedes an unanswered
      // challenge_response, the server's late challenge_result for the
      // abandoned one would untrack the complete, and its own session_busy
      // would then find nothing pending and merely log, stranding the UI.
      // Null-prototype: data.type is server input, and a plain literal would
      // resolve 'toString' (and friends) to an inherited function, making
      // `answered` truthy for a type that maps to nothing. Same reason
      // humanizeError looks its map up with hasOwnProperty.
      const ANSWERS = { __proto__: null, challenge_result: 'challenge_response', session_complete: 'complete' };
      const answered = ANSWERS[data.type];
      if (answered && this._pendingOneShot
          && this._pendingOneShot.payload.type === answered) {
        this._pendingOneShot = null;
      }

      if (data.type === 'frame_result' && this.onFrameResult) {
        this.onFrameResult(data);
      } else if (data.type === 'challenge_result' && this.onChallengeResult) {
        this.onChallengeResult(data);
      } else if (data.type === 'session_complete' && this.onSessionComplete) {
        this.onSessionComplete(data);
      } else if (data.type === 'error') {
        // `retryable` marks a non-terminal error: the session is still usable,
        // so routing it to onError would halt capture and drop the user into
        // the error screen over something recoverable.
        //
        // But retryable does NOT mean "re-send this now". Only session_busy is
        // the server saying it never processed the request. The other retryable
        // error, required_challenge_incomplete, means the USER still has to
        // answer a challenge -- auto-resending `complete` there just burns the
        // retry budget on four identical refusals and then reports a terminal
        // failure, when the correct behaviour is to wait for the user.
        if (data.retryable) {
          // Raw code by design: onRetryableError is a programmatic hook (null
          // by default, never wired to the error screen), so a caller can
          // switch on the code. Only onError feeds rendered copy.
          if (this.onRetryableError) this.onRetryableError(data.message);
          if (data.message === 'session_busy') {
            this._retryPendingOneShot(data);
          }
        } else if (onError) {
          onError(humanizeError(data.message));
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
   * Send a ONE-SHOT control op, remembering it so a session_busy can re-send it.
   *
   * Unlike a frame (another follows in ~33ms), nothing re-drives a conflicted
   * `complete` or `challenge_response`: the UI would sit waiting for a result
   * the server never produced. Re-sending is safe because session_busy means
   * the request was NOT processed -- either the lock was never acquired, or the
   * lease was lost and the save discarded. The server is idempotent for both
   * anyway (re-completion returns the frozen verdict; answered_challenges
   * rejects a replay), so a redundant retry cannot double-score.
   */
  _sendOneShot(payload) {
    if (!(this.ws && this.ws.readyState === WebSocket.OPEN)) {
      // Returning quietly would leave the caller waiting on a result that can
      // never arrive -- onclose only logs, so a `complete` sent after the
      // socket dropped would strand the UI in 'processing'. Same hang shape the
      // retry path exists to prevent, just from a closed socket instead of a
      // conflict.
      if (this._onError) this._onError('WebSocket connection error');
      return;
    }
    // Only one op is tracked at a time, so sending a second while the first is
    // still unanswered abandons it: its retry timer will find _pendingOneShot
    // changed and stop. That is acceptable ONLY because the replacement is
    // itself tracked and escalates on failure -- in practice `complete`
    // superseding an answered-and-conflicted `challenge_response`, which is the
    // user moving on. Do NOT send a one-shot AFTER `complete`: evicting the
    // complete would leave the UI in 'processing' with nothing to re-drive it.
    if (this._pendingOneShot) {
      console.warn('Liveness: abandoning unanswered',
                   this._pendingOneShot.payload.type, 'for', payload.type);
    }
    this._pendingOneShot = { payload, attempts: 0 };
    this.ws.send(JSON.stringify(payload));
  }

  /** Re-send the pending one-shot op with bounded backoff, or give up loudly. */
  _retryPendingOneShot(data) {
    const pending = this._pendingOneShot;
    if (!pending) {
      // A conflicted frame with nothing outstanding: lossy by design, the next
      // one is milliseconds away.
      console.warn('Liveness transient error (ignored):', data.message);
      return;
    }
    // A socket multiplexes frames and control ops, so a session_busy is only
    // ours if the server says which message lost the race. `op` is absent only
    // when talking to a server older than this field; retrying then is still
    // safe (the ops are idempotent) so we fall back rather than stall.
    if (data.op !== undefined && data.op !== pending.payload.type) {
      console.warn('Liveness transient error for', data.op, '(ignored)');
      return;
    }
    if (pending.attempts >= ONE_SHOT_RETRY_LIMIT) {
      // Sustained contention is no longer transient; surfacing it is better
      // than leaving the caller waiting on a result that will never arrive.
      // Through humanizeError, like every other rendered error: only
      // session_busy reaches this branch, so passing data.message straight
      // through would put the wire code on the user's error screen.
      this._pendingOneShot = null;
      if (this._onError) this._onError(humanizeError(data.message));
      return;
    }
    pending.attempts += 1;
    const delay = ONE_SHOT_RETRY_BASE_MS * 2 ** (pending.attempts - 1);
    setTimeout(() => {
      // No longer the tracked op: answered, disconnected, or replaced by a
      // later one-shot (which _sendOneShot logs and which is itself tracked).
      // Nothing to re-drive in any of those cases.
      if (this._pendingOneShot !== pending) return;
      if (!(this.ws && this.ws.readyState === WebSocket.OPEN)) {
        // Socket died during the backoff. Same reasoning as _sendOneShot:
        // onclose only logs, so returning quietly here would strand the caller
        // in 'processing' on a verdict that can never arrive.
        this._pendingOneShot = null;
        if (this._onError) this._onError('WebSocket connection error');
        return;
      }
      this.ws.send(JSON.stringify(pending.payload));
    }, delay);
  }

  /**
   * Submit challenge response via WebSocket
   */
  submitChallengeResponse(response) {
    this._sendOneShot({ type: 'challenge_response', response });
  }

  /**
   * Relay a real SpO2 reading from a paired BLE pulse oximeter over the same
   * session WebSocket. SpO2 is never derived from the webcam; this is the only
   * path it enters scoring. The backend stamps it on the server clock and
   * validates range/quality, so a bad reading is simply dropped (no SpO2).
   *
   * LOSSY ON CONFLICT, deliberately -- do NOT route this through _sendOneShot,
   * despite the server sending a correlated session_busy for it:
   *
   *  - This is a STREAM, not a one-shot. It is called from the oximeter's GATT
   *    notification callback, so a superseding reading follows within about a
   *    second, exactly like frames. _sendOneShot has a single pending slot, so a
   *    reading arriving while `complete` awaits its verdict would evict that
   *    complete and it would never be retried -- reinstating the silent hang the
   *    retry path exists to prevent.
   *  - A retry would also re-stamp a stale sample. submit_hardware_spo2 stamps
   *    on the SERVER clock at ingest, and the pulse service drops readings older
   *    than MAX_SPO2_AGE_MS; resending seconds later would present an old
   *    measurement as current, which is the one thing SpO2 handling must not do.
   *
   * A conflicted reading still logs via _retryPendingOneShot's no-pending path.
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
    this._sendOneShot({ type: 'complete' });
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
    // Drop any queued retry so it cannot fire against the next session.
    this._pendingOneShot = null;
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
