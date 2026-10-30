import type { Call, Contact, Feature, Recording, Ringtone, Settings, SystemStatus } from '../api/types';

export interface MockDb {
  contacts: Contact[];
  features: Feature[];
  settings: Settings;
  ringtones: Ringtone[];
  calls: Call[];
  recordings: Recording[];
  status: SystemStatus;
  activeCallId: number | null;
  loggedIn: boolean;
  nextId: number;
}

const hoursAgo = (h: number, now: Date) => new Date(now.getTime() - h * 3600_000).toISOString();
const minutesFrom = (iso: string, m: number) => new Date(new Date(iso).getTime() + m * 60_000).toISOString();

export function seedDb(now = new Date()): MockDb {
  const contacts: Contact[] = [
    {
      id: 1,
      name: 'Grandma',
      spoken_name: 'Grandma Jo',
      number: '+15555550123',
      speed_dial: 2,
      enabled: true,
      inbound_allowed: true,
      dnd_until: null,
      max_call_minutes: null,
      created_at: hoursAgo(24 * 30, now),
    },
    {
      id: 2,
      name: 'Grandpa',
      spoken_name: 'Grandpa Lou',
      number: '+15555550124',
      speed_dial: 3,
      enabled: true,
      inbound_allowed: true,
      dnd_until: null,
      max_call_minutes: 5,
      created_at: hoursAgo(24 * 30, now),
    },
    {
      id: 3,
      name: 'Auntie May',
      spoken_name: 'Auntie May',
      number: '+15555550125',
      speed_dial: 4,
      enabled: true,
      inbound_allowed: false,
      dnd_until: new Date(now.getTime() + 90 * 60_000).toISOString(),
      max_call_minutes: null,
      created_at: hoursAgo(24 * 12, now),
    },
    {
      id: 4,
      name: 'Dad at work',
      spoken_name: 'Daddy',
      number: '+15555550126',
      speed_dial: 5,
      enabled: false,
      inbound_allowed: true,
      dnd_until: null,
      max_call_minutes: 3,
      created_at: hoursAgo(24 * 5, now),
    },
  ];

  const features: Feature[] = [
    { digit: 0, kind: 'none', config: {}, enabled: true },
    { digit: 1, kind: 'weather', config: {}, enabled: true },
    { digit: 6, kind: 'song', config: { title: 'Twinkle Twinkle' }, enabled: true },
    { digit: 7, kind: 'fun_fact', config: { topic: 'dinosaurs' }, enabled: true },
    { digit: 8, kind: 'secret_message', config: { recipient: 'Mom', notify: 'ntfy' }, enabled: true },
    { digit: 9, kind: 'mailbox', config: {}, enabled: true },
  ];

  const settings: Settings = {
    max_call_minutes: 10,
    warning_seconds_before_end: 60,
    quiet_hours: { start: '19:30', end: '07:30', tz: 'America/Chicago' },
    daily_call_cap: 10,
    ring_timeout_seconds: 25,
    unknown_caller_policy: 'reject',
    notifications: { ntfy_topic: 'tincan-home', email: null },
    trunk_caller_id: '+15555550100',
    weather_location: { lat: 30.27, lon: -97.74, name: 'home' },
    ringtone: 'classic',
    ringer_volume: 80,
  };

  const ringtone = (name: string, builtin: boolean, duration_seconds = 2): Ringtone => ({
    name,
    builtin,
    duration_seconds,
    audio_url: `/api/ringtones/${name}/audio`,
  });
  const ringtones: Ringtone[] = [
    ringtone('classic', true),
    ringtone('chime', true),
    ringtone('birds', true),
    ringtone('grandmas-doorbell', false, 1.4),
  ];

  const recordings: Recording[] = [];
  const calls: Call[] = [];
  let id = 1;
  let recId = 1;

  const addCall = (c: Omit<Call, 'id' | 'recording_id'> & { record?: boolean; kind?: Recording['kind'] }) => {
    const callId = id++;
    let recording_id: number | null = null;
    if (c.record && c.duration_seconds) {
      recording_id = recId++;
      recordings.push({
        id: recording_id,
        kind: c.kind ?? 'call',
        call_id: callId,
        contact_id: c.contact_id,
        created_at: c.ended_at ?? c.started_at,
        duration_seconds: c.duration_seconds,
        size_bytes: c.duration_seconds * 16_000,
        backed_up_at: recId % 3 === 0 ? null : minutesFrom(c.ended_at ?? c.started_at, 15),
        listened: recId % 2 === 0,
        audio_url: `/api/recordings/${recording_id}/audio`,
      });
    }
    calls.push({
      id: callId,
      direction: c.direction,
      contact_id: c.contact_id,
      feature_kind: c.feature_kind,
      started_at: c.started_at,
      answered_at: c.answered_at,
      ended_at: c.ended_at,
      duration_seconds: c.duration_seconds,
      outcome: c.outcome,
      recording_id,
    });
  };

  const mk = (hAgo: number, durationSec: number | null) => {
    const started_at = hoursAgo(hAgo, now);
    const answered_at = durationSec ? minutesFrom(started_at, 0.2) : null;
    const ended_at = minutesFrom(started_at, durationSec ? durationSec / 60 + 0.2 : 0.4);
    return { started_at, answered_at, ended_at, duration_seconds: durationSec };
  };

  addCall({ direction: 'outbound', contact_id: 1, feature_kind: null, outcome: 'completed', ...mk(100, 412), record: true });
  addCall({ direction: 'feature', contact_id: null, feature_kind: 'fun_fact', outcome: 'completed', ...mk(76, 22) });
  addCall({ direction: 'inbound', contact_id: 2, feature_kind: null, outcome: 'no_answer', ...mk(70, null) });
  addCall({ direction: 'outbound', contact_id: 2, feature_kind: null, outcome: 'time_cap', ...mk(52, 300), record: true });
  addCall({ direction: 'inbound', contact_id: null, feature_kind: null, outcome: 'rejected_unknown', ...mk(49, null) });
  addCall({ direction: 'feature', contact_id: null, feature_kind: 'secret_message', outcome: 'completed', ...mk(30, 18), record: true, kind: 'secret' });
  addCall({ direction: 'outbound', contact_id: 3, feature_kind: null, outcome: 'rejected_dnd', ...mk(27, null) });
  addCall({ direction: 'inbound', contact_id: 1, feature_kind: null, outcome: 'rejected_quiet_hours', ...mk(13, null) });
  addCall({ direction: 'feature', contact_id: null, feature_kind: 'weather', outcome: 'completed', ...mk(5, 14) });
  addCall({ direction: 'outbound', contact_id: 1, feature_kind: null, outcome: 'completed', ...mk(3, 255), record: true });
  addCall({ direction: 'outbound', contact_id: 4, feature_kind: null, outcome: 'failed', ...mk(2, null) });
  addCall({ direction: 'inbound', contact_id: 2, feature_kind: null, outcome: 'completed', ...mk(1, 96), record: true });

  calls.sort((a, b) => b.id - a.id);

  const status: SystemStatus = {
    asterisk: 'connected',
    phone: 'registered',
    trunk: 'registered',
    version: '0.1.0-mock',
    disk_free_bytes: 23.4 * 1024 ** 3,
    backup: {
      last_ok_at: hoursAgo(2, now),
      pending: recordings.filter((r) => !r.backed_up_at).length,
    },
  };

  return {
    contacts,
    features,
    settings,
    ringtones,
    calls,
    recordings,
    status,
    activeCallId: null,
    loggedIn: true,
    nextId: 1000,
  };
}

export const MOCK_PASSWORD = 'tincan';
