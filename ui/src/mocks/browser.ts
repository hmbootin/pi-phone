import { http, HttpResponse } from 'msw';
import { setupWorker } from 'msw/browser';
import { endActiveCall, handlers, startSimulatedCall, db } from './handlers';

type Listener = (name: string, data: unknown) => void;
const listeners = new Set<Listener>();
function emit(name: string, data: unknown) {
  for (const l of listeners) l(name, data);
}

/** `/api/events` as a long-lived SSE stream served from the service worker. */
const eventsHandler = http.get('/api/events', () => {
  const encoder = new TextEncoder();
  let listener: Listener | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(': connected\n\n'));
      listener = (name, data) => {
        controller.enqueue(encoder.encode(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`));
      };
      listeners.add(listener);
    },
    cancel() {
      if (listener) listeners.delete(listener);
    },
  });
  return new HttpResponse(stream, {
    headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
  });
});

export const worker = setupWorker(eventsHandler, ...handlers);

/** Every ~45 s, Grandma calls for 20 s so the home page has something to show. */
export function startSimulation() {
  const tick = () => {
    if (db.activeCallId == null && db.contacts.length > 0) {
      const contact = db.contacts.find((c) => c.enabled) ?? db.contacts[0]!;
      const call = startSimulatedCall(contact.id, Math.random() > 0.5 ? 'inbound' : 'outbound');
      emit('call.started', { call_id: call.id });
      setTimeout(() => {
        if (db.activeCallId !== call.id) return;
        const rec = endActiveCall();
        emit('call.ended', { call_id: call.id });
        if (rec) emit('recording.created', { recording_id: rec.id });
      }, 20_000);
    }
  };
  setTimeout(tick, 8_000);
  setInterval(tick, 45_000);
  // Expose for poking from devtools: window.tincanMock.emit('status.changed', {})
  (window as unknown as { tincanMock: unknown }).tincanMock = { db, emit, startSimulatedCall, endActiveCall };
}

/** Patch hangup so a manual hang-up also notifies SSE subscribers. */
worker.use(
  http.post('/api/calls/active/hangup', () => {
    const call = db.calls.find((c) => c.id === db.activeCallId);
    const rec = endActiveCall();
    if (call) emit('call.ended', { call_id: call.id });
    if (rec) emit('recording.created', { recording_id: rec.id });
    return new HttpResponse(null, { status: 204 });
  }),
);
