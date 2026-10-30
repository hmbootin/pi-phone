// Hand-written from docs/api.md. Keep in sync with the contract.

export const MEMORY_KEYS = ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'sos'] as const;
export type MemoryKey = (typeof MEMORY_KEYS)[number];

export interface Contact {
  id: number;
  name: string;
  spoken_name: string;
  number: string;
  /** 0-9, or null when the contact is only on a memory key. */
  speed_dial: number | null;
  /** 'm1'..'m9' or 'sos': the phone's dedicated keys. */
  memory_key: MemoryKey | null;
  enabled: boolean;
  inbound_allowed: boolean;
  dnd_until: string | null;
  max_call_minutes: number | null;
  created_at: string;
}

export type ContactInput = Omit<Contact, 'id' | 'created_at'>;
export type ContactPatch = Partial<ContactInput>;

export type DndRequest = { minutes: number } | { until: string } | { clear: true };

export type FeatureKind =
  | 'speed_dial'
  | 'weather'
  | 'fun_fact'
  | 'secret_message'
  | 'mailbox'
  | 'song'
  | 'none';

/** Free-form per-kind config. Known keys are typed; the backend may add more. */
export interface FeatureConfig {
  topic?: string;
  recipient?: string;
  notify?: 'ntfy' | 'email' | 'both';
  title?: string;
  [key: string]: unknown;
}

export interface Feature {
  digit: number;
  kind: FeatureKind;
  config: FeatureConfig;
  enabled: boolean;
}

export type FeatureInput = Omit<Feature, 'digit'>;

export interface FeaturePreview {
  text: string;
  audio_url: string;
}

export type UnknownCallerPolicy = 'reject' | 'voicemail';

export interface QuietHours {
  start: string; // "HH:MM"
  end: string; // "HH:MM"
  tz: string; // IANA zone
}

export interface Notifications {
  ntfy_topic: string | null;
  email: string | null;
}

export interface WeatherLocation {
  lat: number;
  lon: number;
  name: string;
}

export interface Settings {
  max_call_minutes: number;
  warning_seconds_before_end: number;
  quiet_hours: QuietHours;
  daily_call_cap: number;
  ring_timeout_seconds: number;
  unknown_caller_policy: UnknownCallerPolicy;
  notifications: Notifications;
  trunk_caller_id: string;
  weather_location: WeatherLocation;
}

export type SettingsPatch = Partial<Settings>;

export type CallDirection = 'outbound' | 'inbound' | 'feature';

export type CallOutcome =
  | 'completed'
  | 'no_answer'
  | 'busy'
  | 'rejected_dnd'
  | 'rejected_quiet_hours'
  | 'rejected_unknown'
  | 'rejected_cap'
  | 'time_cap'
  | 'failed';

export interface Call {
  id: number;
  direction: CallDirection;
  contact_id: number | null;
  feature_kind: FeatureKind | null;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  outcome: CallOutcome | null;
  recording_id: number | null;
}

export type RecordingKind = 'call' | 'secret' | 'voicemail';

export interface Recording {
  id: number;
  kind: RecordingKind;
  call_id: number | null;
  contact_id: number | null;
  created_at: string;
  duration_seconds: number;
  size_bytes: number;
  backed_up_at: string | null;
  listened: boolean;
  audio_url: string;
}

export interface RecordingsQuery {
  kind?: RecordingKind;
  contact_id?: number;
  limit?: number;
}

export interface CallsQuery {
  limit?: number;
  before?: number;
}

export type LinkState = 'connected' | 'disconnected';
export type RegistrationState = 'registered' | 'unregistered';
export type TrunkState = RegistrationState | 'unconfigured';

export interface SystemStatus {
  asterisk: LinkState;
  phone: RegistrationState;
  trunk: TrunkState;
  version: string;
  disk_free_bytes: number;
  backup: {
    last_ok_at: string | null;
    pending: number;
  };
}

export type EventName = 'call.started' | 'call.ended' | 'recording.created' | 'status.changed';

export interface ApiErrorBody {
  error: { code: string; message: string };
}
