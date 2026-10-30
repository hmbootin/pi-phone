import type { Call, CallOutcome, Contact, FeatureKind } from '../api/types';

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m === 0) return `${r}s`;
  return `${m}m ${r.toString().padStart(2, '0')}s`;
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, '0')}`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${formatDay(iso)} ${d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
}

export function isToday(iso: string): boolean {
  return new Date(iso).toDateString() === new Date().toDateString();
}

export function formatDay(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

export function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d
    .getDate()
    .toString()
    .padStart(2, '0')}`;
}

export function formatRelativeUntil(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (d.toDateString() === now.toDateString()) return `until ${time}`;
  const tomorrow = new Date();
  tomorrow.setDate(now.getDate() + 1);
  if (d.toDateString() === tomorrow.toDateString()) return `until tomorrow ${time}`;
  return `until ${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[i]}`;
}

export const FEATURE_LABELS: Record<FeatureKind, string> = {
  speed_dial: 'Speed dial',
  weather: 'Weather',
  fun_fact: 'Fun fact',
  secret_message: 'Secret message',
  mailbox: 'Mailbox',
  song: 'Song',
  none: 'Nothing',
};

export const FEATURE_HINTS: Record<FeatureKind, string> = {
  speed_dial: 'Calls a contact.',
  weather: 'Reads today’s weather for your location.',
  fun_fact: 'Tells a fun fact about a topic.',
  secret_message: 'Records a secret message and notifies a parent.',
  mailbox: 'Plays back messages left for the toddler.',
  song: 'Plays a song.',
  none: 'Plays a friendly “that button does nothing” prompt.',
};

export function contactName(contacts: Contact[] | undefined, id: number | null | undefined): string {
  if (id == null) return 'Someone';
  return contacts?.find((c) => c.id === id)?.name ?? `Contact #${id}`;
}

export function callHeadline(call: Call, contacts: Contact[] | undefined): string {
  const who = contactName(contacts, call.contact_id);
  switch (call.direction) {
    case 'outbound':
      return `Called ${who}`;
    case 'inbound':
      return call.contact_id == null ? 'Unknown caller' : `${who} called`;
    case 'feature':
      return call.feature_kind ? FEATURE_LABELS[call.feature_kind] : 'Feature';
  }
}

export function outcomeText(
  outcome: CallOutcome | null,
  call: Call,
  contacts: Contact[] | undefined,
): string {
  const who = contactName(contacts, call.contact_id);
  const they = call.direction === 'inbound' ? who : who;
  switch (outcome) {
    case null:
      return 'In progress';
    case 'completed':
      return call.direction === 'feature' ? 'Played' : `Talked for ${formatDuration(call.duration_seconds)}`;
    case 'no_answer':
      return call.direction === 'inbound' ? 'Nobody picked up at home' : `${they} didn’t pick up`;
    case 'busy':
      return `${they} was busy`;
    case 'rejected_dnd':
      return `${who} was on do-not-disturb`;
    case 'rejected_quiet_hours':
      return 'It was quiet hours';
    case 'rejected_unknown':
      return 'Unknown number, turned away';
    case 'rejected_cap':
      return 'Daily call limit reached';
    case 'time_cap':
      return `Reached the time limit after ${formatDuration(call.duration_seconds)}`;
    case 'failed':
      return 'The call failed';
  }
}

export function outcomeTone(outcome: CallOutcome | null): 'ok' | 'warn' | 'bad' | 'muted' {
  switch (outcome) {
    case null:
      return 'ok';
    case 'completed':
      return 'ok';
    case 'time_cap':
    case 'no_answer':
    case 'busy':
      return 'muted';
    case 'rejected_dnd':
    case 'rejected_quiet_hours':
    case 'rejected_cap':
    case 'rejected_unknown':
      return 'warn';
    case 'failed':
      return 'bad';
  }
}

/** "until tomorrow 7:30" quick action: next 07:30 local time strictly after now. */
export function nextMorning(hour = 7, minute = 30, now = new Date()): Date {
  const d = new Date(now);
  d.setHours(hour, minute, 0, 0);
  if (d <= now) d.setDate(d.getDate() + 1);
  return d;
}

export function isDndActive(contact: Contact, now = new Date()): boolean {
  return contact.dnd_until != null && new Date(contact.dnd_until) > now;
}
