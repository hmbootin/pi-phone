import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { API_BASE } from './client';
import type { EventName } from './types';

export const EVENT_NAMES: EventName[] = [
  'call.started',
  'call.ended',
  'recording.created',
  'status.changed',
];

export type LiveEvent = { name: EventName | 'poll'; data: unknown };

const POLL_MS = 10_000;

/**
 * Subscribe to `/api/events` over SSE. If EventSource is unavailable or the stream
 * errors, fall back to emitting a synthetic `poll` event every few seconds until the
 * stream reconnects. Returns an unsubscribe function.
 */
export function subscribeEvents(onEvent: (e: LiveEvent) => void): () => void {
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  const startPolling = () => {
    if (pollTimer) return;
    pollTimer = setInterval(() => onEvent({ name: 'poll', data: null }), POLL_MS);
  };
  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  };

  if (typeof EventSource === 'undefined') {
    startPolling();
    return stopPolling;
  }

  const es = new EventSource(`${API_BASE}/events`, { withCredentials: true });
  for (const name of EVENT_NAMES) {
    es.addEventListener(name, (ev) => {
      let data: unknown = null;
      try {
        data = JSON.parse((ev as MessageEvent).data as string);
      } catch {
        data = (ev as MessageEvent).data;
      }
      onEvent({ name, data });
    });
  }
  es.onopen = stopPolling;
  es.onerror = startPolling;

  return () => {
    es.close();
    stopPolling();
  };
}

/** Keep react-query caches fresh from the live event stream. Mount once near the root. */
export function useLiveUpdates(enabled = true) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    const inv = (key: readonly unknown[]) => void qc.invalidateQueries({ queryKey: key });
    return subscribeEvents(({ name }) => {
      switch (name) {
        case 'call.started':
        case 'call.ended':
          inv(['calls']);
          inv(['status']);
          break;
        case 'recording.created':
          inv(['recordings']);
          inv(['status']);
          break;
        case 'status.changed':
          inv(['status']);
          break;
        case 'poll':
          inv(['calls']);
          inv(['status']);
          inv(['recordings']);
          break;
      }
    });
  }, [qc, enabled]);
}
