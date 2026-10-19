import { useState, useEffect, useRef, useCallback } from 'react';
import type { WebSocketEvent } from '@/types/medichain';

const MAX_RETRIES = 5;
// When the event buffer grows this large, trim down to ~EVENT_BUFFER_KEEP
// (prevents unbounded memory). Consumers should track `_seq` — not array
// indices — so they don't skip a whole batch when the buffer trims.
const EVENT_BUFFER_TRIM_AT = 500;
const EVENT_BUFFER_KEEP = 400;

/** WebSocketEvent with a monotonic sequence id. `_seq` strictly increases for
 * the lifetime of the hook and survives buffer trimming, so "last processed"
 * trackers should use this value rather than array indices. */
export interface SeqEvent extends WebSocketEvent {
  _seq: number;
}

export function useWebSocket(sessionId: string | null) {
  const [events, setEvents] = useState<SeqEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const bufferRef = useRef<string[]>([]);
  const seqCounter = useRef(0);

  const clearEvents = useCallback(() => setEvents([]), []);

  const sendMessage = useCallback((content: string) => {
    const payload = JSON.stringify({ content });
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(payload);
    } else {
      bufferRef.current.push(payload);
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/${sessionId}`;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        retriesRef.current = 0;
        // M18 fix: clear stale buffered messages on reconnect instead of flushing
        bufferRef.current = [];
      };

      ws.onmessage = (e) => {
        try {
          const raw: WebSocketEvent = JSON.parse(e.data);
          const seq = ++seqCounter.current;
          const withSeq: SeqEvent = { ...raw, _seq: seq };
          setEvents(prev => {
            if (prev.length >= EVENT_BUFFER_TRIM_AT) {
              // Keep the most recent (EVENT_BUFFER_KEEP - 1) + new event.
              return [...prev.slice(prev.length - EVENT_BUFFER_KEEP + 1), withSeq];
            }
            return [...prev, withSeq];
          });
        } catch (err) { console.warn('WS parse error:', err); }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (retriesRef.current < MAX_RETRIES) {
          // M17 fix: add jitter to exponential backoff
          const delay = Math.min(1000 * 2 ** retriesRef.current, 30000) * (0.5 + Math.random() * 0.5);
          retriesRef.current++;
          setTimeout(connect, delay);
        }
      };

      // M16 fix: log WebSocket errors before closing
      ws.onerror = (err) => { console.warn('WebSocket error:', err); ws.close(); };
    }

    connect();
    return () => {
      retriesRef.current = MAX_RETRIES; // prevent reconnect
      wsRef.current?.close();
    };
  }, [sessionId]);

  return { events, isConnected, sendMessage, clearEvents };
}
