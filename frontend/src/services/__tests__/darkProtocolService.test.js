/**
 * Tests for the dark-protocol WebSocket connect lifecycle.
 *
 * connectWebSocket() exchanges the auth token for a single-use ws-ticket and
 * returns a Promise that must settle exactly once. These tests pin the tricky
 * lifecycle edges the connect flow guards against:
 *   - the ticket lands in the URL and the socket resolves on open;
 *   - a close BEFORE open rejects (so establishSession can't hang when onerror
 *     never fires on a clean server-side close);
 *   - a socket superseded while CONNECTING closes itself and rejects instead of
 *     resolving an orphaned connection or tearing down the newer one;
 *   - a disconnect during the ticket fetch aborts to null without opening.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../wsTicket', () => ({ getWsTicket: vi.fn() }));

import { getWsTicket } from '../wsTicket';
import {
  connectWebSocket,
  disconnectWebSocket,
} from '../darkProtocolService';

// Flush the microtask + a macrotask turn so the awaited (mocked) ticket
// resolves and the socket is constructed before we drive its events.
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('darkProtocolService WebSocket connect lifecycle', () => {
  let sockets;
  let originalWebSocket;

  beforeEach(() => {
    sockets = [];
    originalWebSocket = global.WebSocket;
    class FakeWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 0; // CONNECTING
        this.onopen = null;
        this.onclose = null;
        this.onerror = null;
        this.onmessage = null;
        sockets.push(this);
      }
      send() {}
      // close() only flips readyState; tests drive onclose explicitly so a
      // single close can't double-fire the handler.
      close() {
        this.readyState = 3;
      }
      _open() {
        this.readyState = 1;
        if (this.onopen) this.onopen();
      }
    }
    FakeWebSocket.CONNECTING = 0;
    FakeWebSocket.OPEN = 1;
    FakeWebSocket.CLOSING = 2;
    FakeWebSocket.CLOSED = 3;
    global.WebSocket = FakeWebSocket;
    vi.clearAllMocks();
  });

  afterEach(() => {
    disconnectWebSocket(); // resets module-level wsConnection + clears intervals
    global.WebSocket = originalWebSocket;
  });

  it('carries the ticket in the ws URL and resolves with the socket on open', async () => {
    getWsTicket.mockResolvedValue('tkt-xyz');

    const p = connectWebSocket('sess-1');
    await flush();

    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toContain('/ws/dark-protocol/sess-1/');
    expect(sockets[0].url).toContain('ticket=tkt-xyz');

    sockets[0]._open();
    await expect(p).resolves.toBe(sockets[0]);
  });

  it('rejects (rather than hangs) when the socket closes before it opens', async () => {
    getWsTicket.mockResolvedValue('tkt');

    const p = connectWebSocket('sess-2');
    await flush();

    // Clean server-side close with no preceding onopen/onerror.
    sockets[0].onclose({ code: 4003 });
    await expect(p).rejects.toThrow(/closed before open/);
  });

  it('closes and rejects a socket superseded while CONNECTING; the newer one still resolves', async () => {
    getWsTicket.mockResolvedValue('tkt');

    const p1 = connectWebSocket('sess-3');
    await flush();
    const socketA = sockets[0];

    // Second connect() while A is still CONNECTING replaces wsConnection with B.
    const p2 = connectWebSocket('sess-3');
    await flush();
    const socketB = sockets[1];
    expect(socketB).not.toBe(socketA);

    // A opens late — it's superseded, so it must close itself and reject p1
    // without resolving an orphan or disturbing B.
    socketA._open();
    await expect(p1).rejects.toThrow(/superseded/);
    expect(socketA.readyState).toBe(3); // closed

    socketB._open();
    await expect(p2).resolves.toBe(socketB);
  });

  it('aborts to null without opening a socket when disconnect supersedes the ticket fetch', async () => {
    let resolveTicket;
    getWsTicket.mockImplementationOnce(
      () => new Promise((resolve) => { resolveTicket = resolve; })
    );

    const p = connectWebSocket('sess-4');
    // Supersede while the ticket request is still pending.
    disconnectWebSocket();
    resolveTicket('tkt-late');

    await expect(p).resolves.toBeNull();
    expect(sockets).toHaveLength(0);
  });

  it('rejects with the error when getWsTicket fails and the attempt is not superseded', async () => {
    getWsTicket.mockRejectedValue(new Error('ticket service unavailable'));

    await expect(connectWebSocket('sess-5')).rejects.toThrow('ticket service unavailable');
    expect(sockets).toHaveLength(0);
  });
});
