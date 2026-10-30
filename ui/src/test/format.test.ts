import { describe, expect, it } from 'vitest';
import type { Call } from '../api/types';
import { formatDuration, nextMorning, outcomeText } from '../lib/format';

const contacts = [{ id: 1, name: 'Grandma' }] as never;
const base: Call = {
  id: 1,
  direction: 'outbound',
  contact_id: 1,
  feature_kind: null,
  started_at: '2026-10-29T10:00:00Z',
  answered_at: null,
  ended_at: null,
  duration_seconds: 125,
  outcome: null,
  recording_id: null,
};

describe('format helpers', () => {
  it('describes outcomes in plain words', () => {
    expect(outcomeText('rejected_dnd', base, contacts)).toBe('Grandma was on do-not-disturb');
    expect(outcomeText('completed', base, contacts)).toBe('Talked for 2m 05s');
    expect(outcomeText('no_answer', { ...base, direction: 'inbound' }, contacts)).toBe('Nobody picked up at home');
    expect(outcomeText('rejected_quiet_hours', base, contacts)).toBe('It was quiet hours');
  });

  it('formats durations', () => {
    expect(formatDuration(0)).toBe('0s');
    expect(formatDuration(59)).toBe('59s');
    expect(formatDuration(61)).toBe('1m 01s');
    expect(formatDuration(null)).toBe('—');
  });

  it('nextMorning picks the next 07:30 strictly after now', () => {
    const early = new Date(2026, 9, 29, 6, 0);
    const late = new Date(2026, 9, 29, 8, 0);
    expect(nextMorning(7, 30, early).getDate()).toBe(29);
    expect(nextMorning(7, 30, late).getDate()).toBe(30);
    expect(nextMorning(7, 30, late).getHours()).toBe(7);
  });
});
