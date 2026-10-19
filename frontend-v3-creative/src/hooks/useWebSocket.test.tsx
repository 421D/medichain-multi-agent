/**
 * Tests for useWebSocket — the live-streaming agent event hook.
 *
 * Covers:
 *   - opens a WebSocket to /ws/{sessionId} on mount, sets isConnected
 *   - parses incoming JSON events and assigns monotonic _seq numbers
 *   - sendMessage forwards JSON-encoded payloads when socket is OPEN
 *   - sendMessage buffers payloads when socket is not yet OPEN and clears
 *     the buffer on reconnect (M18 fix — see hook source)
 *   - non-JSON events are tolerated (warned, not crashed)
 *   - unmount sets retries to MAX so reconnect doesn't fire post-unmount
 *
 * The hook uses the global WebSocket constructor; we install a fake here
 * that exposes hooks to drive its lifecycle deterministically.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useWebSocket } from './useWebSocket';

class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = 0; // CONNECTING
  onopen: ((ev?: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev?: CloseEvent) => void) | null = null;
  onerror: ((ev?: Event) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  // Test helpers
  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }
  emit(data: unknown) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) } as MessageEvent);
  }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not open a socket when sessionId is null', () => {
    renderHook(() => useWebSocket(null));
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('opens /ws/{sessionId} and reports isConnected after onopen', () => {
    const { result } = renderHook(() => useWebSocket('sess-1'));

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toMatch(/\/ws\/sess-1$/);

    act(() => FakeWebSocket.instances[0].open());

    expect(result.current.isConnected).toBe(true);
  });

  it('parses incoming JSON and tags each event with a monotonic _seq', () => {
    const { result } = renderHook(() => useWebSocket('sess-1'));
    act(() => FakeWebSocket.instances[0].open());

    act(() => FakeWebSocket.instances[0].emit({ type: 'agent_message', content: 'hi' }));
    act(() => FakeWebSocket.instances[0].emit({ type: 'diagnosis', content: 'maybe pneumonia' }));

    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0]._seq).toBe(1);
    expect(result.current.events[1]._seq).toBe(2);
    expect(result.current.events[0].type).toBe('agent_message');
  });

  it('survives non-JSON payloads without throwing', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { result } = renderHook(() => useWebSocket('sess-1'));
    act(() => FakeWebSocket.instances[0].open());

    expect(() => act(() => FakeWebSocket.instances[0].emit('not json {['))).not.toThrow();
    expect(result.current.events).toHaveLength(0);
    expect(warn).toHaveBeenCalled();
  });

  it('sendMessage writes JSON {content} when the socket is OPEN', () => {
    const { result } = renderHook(() => useWebSocket('sess-1'));
    act(() => FakeWebSocket.instances[0].open());

    act(() => result.current.sendMessage('hello there'));

    expect(FakeWebSocket.instances[0].sent).toHaveLength(1);
    expect(JSON.parse(FakeWebSocket.instances[0].sent[0])).toEqual({ content: 'hello there' });
  });

  it('sendMessage buffers when socket is not yet OPEN; buffer is cleared on (re)connect (M18 fix)', () => {
    const { result } = renderHook(() => useWebSocket('sess-1'));
    // Send before the socket has opened — should buffer, not send.
    act(() => result.current.sendMessage('queued'));
    expect(FakeWebSocket.instances[0].sent).toHaveLength(0);

    // Open the socket — M18 fix clears the buffer rather than flushing
    // it (avoids replaying stale chat input on reconnect).
    act(() => FakeWebSocket.instances[0].open());
    expect(FakeWebSocket.instances[0].sent).toHaveLength(0);
  });

  it('clearEvents resets the events array but preserves _seq counter', () => {
    const { result } = renderHook(() => useWebSocket('sess-1'));
    act(() => FakeWebSocket.instances[0].open());
    act(() => FakeWebSocket.instances[0].emit({ type: 'agent_message', content: 'a' }));
    act(() => result.current.clearEvents());
    expect(result.current.events).toHaveLength(0);

    act(() => FakeWebSocket.instances[0].emit({ type: 'agent_message', content: 'b' }));
    // Counter is monotonic across the hook's lifetime (NOT reset by clearEvents).
    expect(result.current.events[0]._seq).toBeGreaterThan(1);
  });

  it('unmount prevents auto-reconnect by exhausting the retry budget', () => {
    const { unmount } = renderHook(() => useWebSocket('sess-1'));
    act(() => FakeWebSocket.instances[0].open());

    unmount();
    // After unmount, retriesRef is set to MAX_RETRIES so onclose's
    // reconnect path is a no-op. We can't introspect the ref directly,
    // but we can confirm no extra socket was constructed.
    const before = FakeWebSocket.instances.length;
    // Manually trigger another close (idempotent on a closed socket)
    FakeWebSocket.instances[0].onclose?.();
    expect(FakeWebSocket.instances.length).toBe(before);
  });
});
