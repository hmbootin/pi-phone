import { useEffect, useState } from 'react';
import { useContacts, useSettings, useSettingsMutation, useTestCall } from '../api/hooks';
import type { Settings } from '../api/types';
import { ErrorText } from '../components/ErrorText';
import { RingtonePicker } from '../components/RingtonePicker';

function timezones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (k: string) => string[] };
  const list = intl.supportedValuesOf?.('timeZone') ?? [];
  const common = ['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'Europe/London', 'UTC'];
  return list.length ? list : common;
}

export function SettingsPage() {
  const settings = useSettings();
  const save = useSettingsMutation();
  const contacts = useContacts();
  const testCall = useTestCall();
  const [form, setForm] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);
  const [testContact, setTestContact] = useState<number | ''>('');

  useEffect(() => {
    if (settings.data && !form) setForm(settings.data);
  }, [settings.data, form]);

  if (!form) {
    return (
      <div className="page">
        <h1>Settings</h1>
        <ErrorText error={settings.error} />
        <div className="muted">Loading&hellip;</div>
      </div>
    );
  }

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => {
    setSaved(false);
    setForm((f) => (f ? { ...f, [k]: v } : f));
  };
  const num = (e: React.ChangeEvent<HTMLInputElement>) => Number(e.target.value);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await save.mutateAsync(form);
      setForm(result);
      setSaved(true);
    } catch {
      // surfaced via save.error
    }
  };

  const tzs = timezones();

  return (
    <div className="page">
      <header className="page-header">
        <h1>Settings</h1>
      </header>
      <form onSubmit={submit}>
        <h2>Calls</h2>
        <div className="card">
          <div className="field-row">
            <div className="field">
              <label htmlFor="s-max">Max minutes per call</label>
              <input id="s-max" type="number" min={1} max={120} value={form.max_call_minutes} onChange={(e) => set('max_call_minutes', num(e))} />
            </div>
            <div className="field">
              <label htmlFor="s-warn">Warning beep (seconds before end)</label>
              <input id="s-warn" type="number" min={0} max={600} value={form.warning_seconds_before_end} onChange={(e) => set('warning_seconds_before_end', num(e))} />
            </div>
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="s-cap">Daily call cap</label>
              <input id="s-cap" type="number" min={0} max={100} value={form.daily_call_cap} onChange={(e) => set('daily_call_cap', num(e))} />
            </div>
            <div className="field">
              <label htmlFor="s-ring">Ring timeout (seconds)</label>
              <input id="s-ring" type="number" min={5} max={120} value={form.ring_timeout_seconds} onChange={(e) => set('ring_timeout_seconds', num(e))} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="s-unknown">Unknown callers</label>
            <select id="s-unknown" value={form.unknown_caller_policy} onChange={(e) => set('unknown_caller_policy', e.target.value as Settings['unknown_caller_policy'])}>
              <option value="reject">Politely turn away</option>
              <option value="voicemail">Send to voicemail for parents</option>
            </select>
          </div>
        </div>

        <h2>Quiet hours</h2>
        <div className="card">
          <div className="field-row">
            <div className="field">
              <label htmlFor="s-qstart">Start</label>
              <input id="s-qstart" type="time" value={form.quiet_hours.start} onChange={(e) => set('quiet_hours', { ...form.quiet_hours, start: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="s-qend">End</label>
              <input id="s-qend" type="time" value={form.quiet_hours.end} onChange={(e) => set('quiet_hours', { ...form.quiet_hours, end: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="s-tz">Time zone</label>
            <select id="s-tz" value={form.quiet_hours.tz} onChange={(e) => set('quiet_hours', { ...form.quiet_hours, tz: e.target.value })}>
              {!tzs.includes(form.quiet_hours.tz) && <option value={form.quiet_hours.tz}>{form.quiet_hours.tz}</option>}
              {tzs.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
        </div>

        <h2>Ringtone</h2>
        <RingtonePicker value={form.ringtone} volume={form.ringer_volume} onChange={(name) => set('ringtone', name)} onVolume={(v) => set('ringer_volume', v)} />

        <h2>Notifications</h2>
        <div className="card">
          <div className="field">
            <label htmlFor="s-ntfy">ntfy topic</label>
            <input id="s-ntfy" type="text" placeholder="tincan-home" value={form.notifications.ntfy_topic ?? ''} onChange={(e) => set('notifications', { ...form.notifications, ntfy_topic: e.target.value || null })} />
            <span className="hint">Install the ntfy app and subscribe to this topic for push notifications.</span>
          </div>
          <div className="field">
            <label htmlFor="s-email">Email</label>
            <input id="s-email" type="email" placeholder="you@example.com" value={form.notifications.email ?? ''} onChange={(e) => set('notifications', { ...form.notifications, email: e.target.value || null })} />
          </div>
        </div>

        <h2>Line</h2>
        <div className="card">
          <div className="field">
            <label htmlFor="s-cid">Caller ID (our number)</label>
            <input id="s-cid" type="tel" value={form.trunk_caller_id} onChange={(e) => set('trunk_caller_id', e.target.value)} />
          </div>
        </div>

        <h2>Weather location</h2>
        <div className="card">
          <div className="field">
            <label htmlFor="s-wname">Name</label>
            <input id="s-wname" type="text" value={form.weather_location.name} onChange={(e) => set('weather_location', { ...form.weather_location, name: e.target.value })} />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="s-lat">Latitude</label>
              <input id="s-lat" type="number" step="any" value={form.weather_location.lat} onChange={(e) => set('weather_location', { ...form.weather_location, lat: num(e) })} />
            </div>
            <div className="field">
              <label htmlFor="s-lon">Longitude</label>
              <input id="s-lon" type="number" step="any" value={form.weather_location.lon} onChange={(e) => set('weather_location', { ...form.weather_location, lon: num(e) })} />
            </div>
          </div>
        </div>

        <ErrorText error={save.error} />
        {saved && <div className="notice">Settings saved.</div>}
        <button type="submit" className="btn primary block" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save settings'}
        </button>
      </form>

      <h2>Test the line</h2>
      <div className="card">
        <p className="small muted" style={{ marginTop: 0 }}>
          Rings the toddler&apos;s phone with a test prompt so you can check it works end to end.
        </p>
        <div className="field">
          <label htmlFor="s-test">Contact to use</label>
          <select id="s-test" value={testContact} onChange={(e) => setTestContact(e.target.value === '' ? '' : Number(e.target.value))}>
            <option value="">Pick a contact</option>
            {contacts.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <ErrorText error={testCall.error} />
        {testCall.isSuccess && <div className="notice">Test call started. The phone should ring.</div>}
        <button className="btn block" disabled={testContact === '' || testCall.isPending} onClick={() => testContact !== '' && testCall.mutate(testContact)}>
          {testCall.isPending ? 'Calling…' : 'Test call'}
        </button>
      </div>
    </div>
  );
}
