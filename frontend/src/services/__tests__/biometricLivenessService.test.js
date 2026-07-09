/**
 * Tests for the biometric-liveness WebSocket ticket auth migration.
 *
 * The liveness socket previously connected with no credential, so the consumer
 * immediately close(4001)'d. It now exchanges the auth token for a short-lived,
 * single-use ws-ticket (kept out of the URL) — mirroring the neuro/adversarial
 * migration. These tests pin that behaviour: the ticket lands in the URL, and a
 * ticket failure fails closed (no socket, onError fired) rather than opening an
 * anonymous socket.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../wsTicket', () => ({ getWsTicket: vi.fn() }));

import { getWsTicket } from '../wsTicket';
import livenessService from '../biometricLivenessService';

describe('biometricLivenessService WebSocket ticket auth', () => {
  let sockets;
  let originalWebSocket;

  beforeEach(() => {
    sockets = [];
    originalWebSocket = global.WebSocket;
    class FakeWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 0;
        sockets.push(this);
      }
      close() {
        this.readyState = 3;
      }
      send() {}
    }
    FakeWebSocket.OPEN = 1;
    global.WebSocket = FakeWebSocket;
    vi.clearAllMocks();
  });

  afterEach(() => {
    livenessService.disconnect();
    global.WebSocket = originalWebSocket;
  });

  it('fetches a single-use ticket and carries it in the ws URL (not the token)', async () => {
    getWsTicket.mockResolvedValueOnce('tkt-123');

    await livenessService.connectWebSocket('sess-1', vi.fn(), vi.fn(), vi.fn());

    expect(getWsTicket).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toContain('/ws/liveness/sess-1/');
    expect(sockets[0].url).toContain('ticket=tkt-123');
  });

  it('fails closed (no socket, onError fired) when the ticket fetch fails', async () => {
    const onError = vi.fn();
    getWsTicket.mockRejectedValueOnce(new Error('no ticket'));

    await livenessService.connectWebSocket('sess-2', vi.fn(), vi.fn(), onError);

    expect(sockets).toHaveLength(0);
    expect(onError).toHaveBeenCalledWith('WebSocket authentication failed');
  });

  it('does not open a socket when a disconnect supersedes the in-flight ticket', async () => {
    let resolveTicket;
    getWsTicket.mockImplementationOnce(
      () => new Promise((resolve) => { resolveTicket = resolve; })
    );

    const connectPromise = livenessService.connectWebSocket('sess-3', vi.fn(), vi.fn(), vi.fn());
    // Supersede the attempt while the ticket request is still pending.
    livenessService.disconnect();
    resolveTicket('tkt-late');
    await connectPromise;

    expect(sockets).toHaveLength(0);
  });
});
