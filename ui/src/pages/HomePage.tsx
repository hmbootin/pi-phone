import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useActiveCall, useCalls, useContacts, useHangup, useRecordings, useStatus } from '../api/hooks';
import type { Call, Contact } from '../api/types';
import { ErrorText } from '../components/ErrorText';
import { StatusPill } from '../components/StatusPill';
import {
  callHeadline,
  formatBytes,
  formatClock,
  formatDateTime,
  formatTime,
  isToday,
  outcomeText,
  outcomeTone,
} from '../lib/format';

function useElapsed(since: string | null | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!since) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [since]);
  if (!since) return 0;
  return (now - new Date(since).getTime()) / 1000;
}

function ActiveCallCard({ call, contacts }: { call: Call; contacts: Contact[] | undefined }) {
  const elapsed = useElapsed(call.answered_at ?? call.started_at);
  const hangup = useHangup();
  return (
    <section className="card accent" aria-label="Active call">
      <div className="row between">
        <div>
          <div className="small muted">{call.answered_at ? 'On a call' : 'Ringing'}</div>
          <div className="strong" style={{ fontSize: '1.2rem' }}>
            {callHeadline(call, contacts)}
          </div>
          <div className="muted">{formatClock(elapsed)}</div>
        </div>
        <button className="btn danger" onClick={() => hangup.mutate()} disabled={hangup.isPending}>
          Hang up
        </button>
      </div>
      <ErrorText error={hangup.error} />
    </section>
  );
}

export function HomePage() {
  const status = useStatus();
  const active = useActiveCall();
  const calls = useCalls({ limit: 50 });
  const contacts = useContacts();
  const recordings = useRecordings();

  const todays = (calls.data ?? []).filter((c) => isToday(c.started_at));
  const unlistened = (recordings.data ?? []).filter((r) => !r.listened).length;
  const s = status.data;

  return (
    <div className="page">
      <header className="page-header">
        <h1>Tin Can</h1>
        {s && <span className="muted small">v{s.version}</span>}
      </header>

      <div className="row wrap" style={{ marginBottom: 12 }}>
        {s ? (
          <>
            <StatusPill label="Asterisk" state={s.asterisk} />
            <StatusPill label="Phone" state={s.phone} />
            <StatusPill label="Trunk" state={s.trunk} />
          </>
        ) : status.isError ? (
          <span className="tone-bad small">Can&apos;t reach the backend.</span>
        ) : (
          <span className="muted small">Checking the line&hellip;</span>
        )}
      </div>

      {active.data && <ActiveCallCard call={active.data} contacts={contacts.data} />}

      <div className="stat-grid">
        <Link to="/memories" className="stat">
          <div className="value">{unlistened}</div>
          <div className="label">{unlistened === 1 ? 'memory to listen to' : 'memories to listen to'}</div>
        </Link>
        <div className="stat">
          <div className="value">{todays.length}</div>
          <div className="label">{todays.length === 1 ? 'call today' : 'calls today'}</div>
        </div>
      </div>

      <h2>Today</h2>
      <section className="card">
        {calls.isLoading ? (
          <div className="muted">Loading&hellip;</div>
        ) : todays.length === 0 ? (
          <div className="empty">No calls yet today.</div>
        ) : (
          <ul className="list">
            {todays.map((c) => (
              <li key={c.id} className="row between">
                <div className="grow">
                  <div className="strong">{callHeadline(c, contacts.data)}</div>
                  <div className={`small tone-${outcomeTone(c.outcome)}`}>{outcomeText(c.outcome, c, contacts.data)}</div>
                </div>
                <div className="small muted">{formatTime(c.started_at)}</div>
              </li>
            ))}
          </ul>
        )}
        {todays.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <Link to="/calls" className="small">
              All calls
            </Link>
          </div>
        )}
      </section>

      <h2>Backup</h2>
      <section className="card">
        {s ? (
          <div className="stack">
            <div className="row between">
              <span>Last successful backup</span>
              <span className={s.backup.last_ok_at ? '' : 'tone-warn'}>{formatDateTime(s.backup.last_ok_at)}</span>
            </div>
            <div className="row between">
              <span>Waiting to upload</span>
              <span className={s.backup.pending > 0 ? 'tone-warn' : 'tone-ok'}>{s.backup.pending}</span>
            </div>
            <div className="row between">
              <span>Disk free</span>
              <span>{formatBytes(s.disk_free_bytes)}</span>
            </div>
          </div>
        ) : (
          <div className="muted">&hellip;</div>
        )}
      </section>
    </div>
  );
}
