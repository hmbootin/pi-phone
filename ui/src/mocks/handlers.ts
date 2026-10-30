import { HttpResponse, http, delay } from 'msw';
import type {
  Call,
  Contact,
  ContactInput,
  ContactPatch,
  DndRequest,
  Feature,
  FeatureInput,
  FeatureKind,
  Recording,
  RecordingKind,
  Ringtone,
  SettingsPatch,
} from '../api/types';
import { MOCK_PASSWORD, seedDb, type MockDb } from './data';
import { makeToneWav } from './wav';

export let db: MockDb = seedDb();

export function resetDb(now?: Date) {
  db = seedDb(now);
}

const ALL_DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

function error(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status });
}

function requireAuth() {
  if (!db.loggedIn) return error(401, 'unauthorized', 'Please sign in.');
  return null;
}

function allFeatures(): Feature[] {
  return ALL_DIGITS.map((digit) => {
    const contact = db.contacts.find((c) => c.speed_dial === digit);
    if (contact) {
      return { digit, kind: 'speed_dial' as FeatureKind, config: { contact_id: contact.id }, enabled: contact.enabled };
    }
    return db.features.find((f) => f.digit === digit) ?? { digit, kind: 'none', config: {}, enabled: true };
  });
}

function previewText(f: Feature): string {
  switch (f.kind) {
    case 'weather':
      return `Good morning! Today at ${db.settings.weather_location.name} it is sunny and 72 degrees.`;
    case 'fun_fact':
      return `Here is a fun fact about ${f.config.topic ?? 'animals'}: some dinosaurs were as small as chickens!`;
    case 'secret_message':
      return `Tell ${f.config.recipient ?? 'Mom'} your secret after the beep, then hang up.`;
    case 'mailbox':
      return 'You have one new message. Here it is!';
    case 'song':
      return `Here comes ${f.config.title ?? 'a song'}!`;
    case 'speed_dial':
      return 'Calling...';
    case 'none':
      return 'That button does nothing. Try another one!';
  }
}

/** Mirrors the backend: file stem, lower-cased, non [a-z0-9_-] runs become '-', max 32 chars. */
function ringtoneSlug(filename: string): string {
  const stem = filename.replace(/\.[^.]*$/, '').toLowerCase();
  return stem
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
    .slice(0, 32)
    .replace(/[-_]+$/, '');
}

const audioResponse = () =>
  HttpResponse.arrayBuffer(makeToneWav(), { headers: { 'Content-Type': 'audio/wav' } });

export const handlers = [
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { password?: string };
    if (body.password !== MOCK_PASSWORD) return error(401, 'bad_password', 'Wrong password.');
    db.loggedIn = true;
    return HttpResponse.json({ ok: true });
  }),

  // Contacts
  http.get('/api/contacts', () => requireAuth() ?? HttpResponse.json(db.contacts)),
  http.post('/api/contacts', async ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const input = (await request.json()) as ContactInput;
    if (db.contacts.some((c) => c.speed_dial === input.speed_dial)) {
      return error(409, 'speed_dial_taken', `Speed dial ${input.speed_dial} is already used by another contact.`);
    }
    const contact: Contact = { ...input, id: db.nextId++, created_at: new Date().toISOString() };
    db.contacts.push(contact);
    db.features = db.features.filter((f) => f.digit !== contact.speed_dial);
    return HttpResponse.json(contact, { status: 201 });
  }),
  http.patch('/api/contacts/:id', async ({ request, params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const id = Number(params.id);
    const contact = db.contacts.find((c) => c.id === id);
    if (!contact) return error(404, 'not_found', 'No such contact.');
    const patch = (await request.json()) as ContactPatch;
    if (patch.speed_dial !== undefined && db.contacts.some((c) => c.id !== id && c.speed_dial === patch.speed_dial)) {
      return error(409, 'speed_dial_taken', `Speed dial ${patch.speed_dial} is already used by another contact.`);
    }
    Object.assign(contact, patch);
    return HttpResponse.json(contact);
  }),
  http.delete('/api/contacts/:id', ({ params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    db.contacts = db.contacts.filter((c) => c.id !== Number(params.id));
    return new HttpResponse(null, { status: 204 });
  }),
  http.post('/api/contacts/:id/dnd', async ({ request, params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const contact = db.contacts.find((c) => c.id === Number(params.id));
    if (!contact) return error(404, 'not_found', 'No such contact.');
    const body = (await request.json()) as DndRequest;
    if ('clear' in body) contact.dnd_until = null;
    else if ('minutes' in body) contact.dnd_until = new Date(Date.now() + body.minutes * 60_000).toISOString();
    else contact.dnd_until = body.until;
    return HttpResponse.json(contact);
  }),

  // Features
  http.get('/api/features', () => requireAuth() ?? HttpResponse.json(allFeatures())),
  http.put('/api/features/:digit', async ({ request, params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const digit = Number(params.digit);
    if (db.contacts.some((c) => c.speed_dial === digit)) {
      return error(409, 'digit_is_speed_dial', `Digit ${digit} is a contact's speed dial.`);
    }
    const input = (await request.json()) as FeatureInput;
    const feature: Feature = { digit, ...input };
    db.features = [...db.features.filter((f) => f.digit !== digit), feature];
    return HttpResponse.json(feature);
  }),
  http.post('/api/features/:digit/preview', async ({ params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const digit = Number(params.digit);
    const f = allFeatures().find((x) => x.digit === digit)!;
    await delay(300);
    return HttpResponse.json({ text: previewText(f), audio_url: `/api/audio/prompts/preview-${digit}.wav` });
  }),
  http.get('/api/audio/prompts/:file', () => audioResponse()),

  // Settings
  http.get('/api/settings', () => requireAuth() ?? HttpResponse.json(db.settings)),
  http.patch('/api/settings', async ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const patch = (await request.json()) as SettingsPatch;
    if (patch.ringtone !== undefined && !db.ringtones.some((r) => r.name === patch.ringtone)) {
      return error(422, 'unknown_ringtone', `No ringtone named '${patch.ringtone}'.`);
    }
    db.settings = {
      ...db.settings,
      ...patch,
      quiet_hours: { ...db.settings.quiet_hours, ...(patch.quiet_hours ?? {}) },
      notifications: { ...db.settings.notifications, ...(patch.notifications ?? {}) },
      weather_location: { ...db.settings.weather_location, ...(patch.weather_location ?? {}) },
    };
    return HttpResponse.json(db.settings);
  }),

  // Ringtones
  http.get('/api/ringtones', () => requireAuth() ?? HttpResponse.json(db.ringtones)),
  http.post('/api/ringtones', async ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const form = await request.formData();
    const file = form.get('file') as File | string | null;
    // Not instanceof File: under vitest the parsed File comes from Node's realm, not jsdom's.
    if (file === null || typeof file === 'string') return error(400, 'invalid_wav', 'Only WAV files (16-bit PCM) are accepted');
    const name = ringtoneSlug(file.name);
    if (!name) return error(400, 'bad_name', 'The file name must contain a letter or digit');
    if (db.ringtones.some((r) => r.name === name && r.builtin)) {
      return error(409, 'ringtone_builtin', `'${name}' is a built-in ringtone; rename the file`);
    }
    if (!/\.wav$/i.test(file.name)) return error(400, 'invalid_wav', 'Only WAV files (16-bit PCM) are accepted');
    if (file.size > 2 * 1024 * 1024) return error(413, 'too_large', 'Ringtones must be under 2048 KB');
    const seconds = Math.min(10, Math.max(0.5, Math.round((file.size / 32_000) * 10) / 10)); // pretend 16 kHz mono
    const entry: Ringtone = { name, builtin: false, duration_seconds: seconds, audio_url: `/api/ringtones/${name}/audio` };
    db.ringtones = [...db.ringtones.filter((r) => r.name !== name), entry];
    await delay(200);
    return HttpResponse.json(entry, { status: 201 });
  }),
  http.delete('/api/ringtones/:name', ({ params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const name = String(params.name);
    const existing = db.ringtones.find((r) => r.name === name);
    if (!existing) return error(404, 'not_found', `No ringtone named '${name}'.`);
    if (existing.builtin) return error(409, 'ringtone_builtin', 'Built-in ringtones cannot be deleted');
    db.ringtones = db.ringtones.filter((r) => r.name !== name);
    if (db.settings.ringtone === name) db.settings = { ...db.settings, ringtone: 'classic' };
    return new HttpResponse(null, { status: 204 });
  }),
  http.get('/api/ringtones/:name/audio', ({ params }) => {
    const tone = db.ringtones.find((r) => r.name === String(params.name));
    if (!tone) return error(404, 'not_found', 'No such ringtone.');
    return HttpResponse.arrayBuffer(makeToneWav(tone.duration_seconds, tone.builtin ? 880 : 660), {
      headers: { 'Content-Type': 'audio/wav' },
    });
  }),

  // Calls
  http.get('/api/calls/active', () => {
    const denied = requireAuth();
    if (denied) return denied;
    const active = db.calls.find((c) => c.id === db.activeCallId) ?? null;
    return HttpResponse.json(active);
  }),
  http.post('/api/calls/active/hangup', () => {
    const denied = requireAuth();
    if (denied) return denied;
    endActiveCall();
    return new HttpResponse(null, { status: 204 });
  }),
  http.get('/api/calls', ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get('limit') ?? 50);
    const before = url.searchParams.get('before');
    let list = db.calls;
    if (before) list = list.filter((c) => c.id < Number(before));
    return HttpResponse.json(list.slice(0, limit));
  }),

  // Recordings
  http.get('/api/recordings/:id/audio', () => audioResponse()),
  http.get('/api/recordings', ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const url = new URL(request.url);
    const kind = url.searchParams.get('kind') as RecordingKind | null;
    const contactId = url.searchParams.get('contact_id');
    const limit = Number(url.searchParams.get('limit') ?? 100);
    let list = [...db.recordings].sort((a, b) => b.id - a.id);
    if (kind) list = list.filter((r) => r.kind === kind);
    if (contactId) list = list.filter((r) => r.contact_id === Number(contactId));
    return HttpResponse.json(list.slice(0, limit));
  }),
  http.patch('/api/recordings/:id', async ({ request, params }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const rec = db.recordings.find((r) => r.id === Number(params.id));
    if (!rec) return error(404, 'not_found', 'No such recording.');
    const body = (await request.json()) as Partial<Recording>;
    if (typeof body.listened === 'boolean') rec.listened = body.listened;
    return HttpResponse.json(rec);
  }),

  // System
  http.get('/api/system/status', () => {
    const denied = requireAuth();
    if (denied) return denied;
    db.status.backup.pending = db.recordings.filter((r) => !r.backed_up_at).length;
    return HttpResponse.json(db.status);
  }),
  http.post('/api/system/test-call', async ({ request }) => {
    const denied = requireAuth();
    if (denied) return denied;
    const body = (await request.json()) as { contact_id?: number };
    if (!db.contacts.some((c) => c.id === body.contact_id)) return error(404, 'not_found', 'No such contact.');
    await delay(400);
    return HttpResponse.json({ ok: true });
  }),
];

/** Simulation helpers used by the browser mock to make the home page feel alive. */
export function startSimulatedCall(contactId: number, direction: Call['direction'] = 'outbound'): Call {
  const now = new Date().toISOString();
  const call: Call = {
    id: db.nextId++,
    direction,
    contact_id: contactId,
    feature_kind: null,
    started_at: now,
    answered_at: now,
    ended_at: null,
    duration_seconds: null,
    outcome: null,
    recording_id: null,
  };
  db.calls.unshift(call);
  db.activeCallId = call.id;
  return call;
}

export function endActiveCall(): Recording | null {
  const call = db.calls.find((c) => c.id === db.activeCallId);
  db.activeCallId = null;
  if (!call || call.ended_at) return null;
  const ended = new Date();
  call.ended_at = ended.toISOString();
  call.duration_seconds = Math.round((ended.getTime() - new Date(call.started_at).getTime()) / 1000);
  call.outcome = 'completed';
  const rec: Recording = {
    id: db.nextId++,
    kind: 'call',
    call_id: call.id,
    contact_id: call.contact_id,
    created_at: call.ended_at,
    duration_seconds: call.duration_seconds,
    size_bytes: call.duration_seconds * 16_000,
    backed_up_at: null,
    listened: false,
    audio_url: '',
  };
  rec.audio_url = `/api/recordings/${rec.id}/audio`;
  call.recording_id = rec.id;
  db.recordings.push(rec);
  return rec;
}
