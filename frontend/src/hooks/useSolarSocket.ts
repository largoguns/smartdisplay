import { useEffect, useState } from 'react';
import type { SolarData } from '../types/dashboard';

export interface SolarSocketState {
  data: SolarData | null;
  connected: boolean;
}

const PING_MS = 25_000;
const FALLBACK_POLL_MS = 10_000;
const MAX_BACKOFF_MS = 30_000;

/**
 * Lecturas del inversor en tiempo real por WebSocket con reconexión
 * exponencial; mientras el socket está caído se usa el endpoint REST.
 */
export function useSolarSocket(): SolarSocketState {
  const [data, setData] = useState<SolarData | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let disposed = false;
    let ws: WebSocket | null = null;
    let backoff = 1_000;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let pollTimer: number | undefined;

    const poll = async () => {
      try {
        const res = await fetch('/api/solar/current', { cache: 'no-store' });
        if (res.ok && !disposed) setData((await res.json()) as SolarData);
      } catch {
        // seguimos esperando al socket
      }
    };

    const startFallback = () => {
      if (pollTimer === undefined) {
        void poll();
        pollTimer = window.setInterval(poll, FALLBACK_POLL_MS);
      }
    };

    const stopFallback = () => {
      window.clearInterval(pollTimer);
      pollTimer = undefined;
    };

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${window.location.host}/ws/solar`);

      ws.onopen = () => {
        backoff = 1_000;
        setConnected(true);
        stopFallback();
        pingTimer = window.setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('ping'), PING_MS);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          setData(JSON.parse(event.data) as SolarData);
        } catch {
          // mensaje no válido: se ignora
        }
      };

      ws.onclose = () => {
        window.clearInterval(pingTimer);
        if (disposed) return;
        setConnected(false);
        startFallback();
        reconnectTimer = window.setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
      };

      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(reconnectTimer);
      window.clearInterval(pingTimer);
      stopFallback();
      ws?.close();
    };
  }, []);

  return { data, connected };
}
