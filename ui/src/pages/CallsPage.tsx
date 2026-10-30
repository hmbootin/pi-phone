import { useState } from 'react';
import { Link } from 'react-router';
import { useQueries } from '@tanstack/react-query';
import { api } from '../api/client';
import { keys, useContacts } from '../api/hooks';
import type { Call } from '../api/types';
import { ErrorText } from '../components/ErrorText';
import { callHeadline, dayKey, formatDay, formatDuration, formatTime, outcomeText, outcomeTone } from '../lib/format';

const PAGE = 50;

export function CallsPage() {
  const contacts = useContacts();
  // Cursor pagination: each page is keyed by the `before` cursor so react-query
  // (and the SSE invalidation) can refresh all loaded pages.
  const [cursors, setCursors] = useState<(number | undefined)[]>([undefined]);
  const pages = useQueries({
    queries: cursors.map((before) => ({
      queryKey: keys.calls({ limit: PAGE, before }),
      queryFn: () => api.calls.list({ limit: PAGE, before }),
    })),
  });

  const calls: Call[] = pages.flatMap((p) => p.data ?? []);
  const last = pages[pages.length - 1];
  const canLoadMore = last?.data && last.data.length === PAGE;
  const error = pages.find((p) => p.error)?.error;

  const groups: [string, Call[]][] = [];
  for (const c of calls) {
    const k = dayKey(c.started_at);
    const g = groups[groups.length - 1];
    if (g && g[0] === k) g[1].push(c);
    else groups.push([k, [c]]);
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Calls</h1>
      </header>
      <ErrorText error={error} />
      {pages[0]?.isLoading && <div className="muted">Loading&hellip;</div>}
      {calls.length === 0 && !pages[0]?.isLoading && <div className="empty">No calls yet.</div>}
      {groups.map(([day, list]) => (
        <section key={day}>
          <h2>{formatDay(list[0]!.started_at)}</h2>
          <div className="card">
            <ul className="list">
              {list.map((c) => (
                <li key={c.id} className="row between" aria-label={callHeadline(c, contacts.data)}>
                  <div className="grow">
                    <div className="strong">{callHeadline(c, contacts.data)}</div>
                    <div className={`small tone-${outcomeTone(c.outcome)}`}>{outcomeText(c.outcome, c, contacts.data)}</div>
                    {c.recording_id != null && (
                      <Link to="/memories" className="small">
                        Listen
                      </Link>
                    )}
                  </div>
                  <div className="small muted" style={{ textAlign: 'right' }}>
                    <div>{formatTime(c.started_at)}</div>
                    {c.duration_seconds != null && <div>{formatDuration(c.duration_seconds)}</div>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ))}
      {canLoadMore && (
        <button
          className="btn block"
          onClick={() => setCursors((cs) => [...cs, last.data![last.data!.length - 1]!.id])}
          disabled={last?.isFetching}
        >
          Load older calls
        </button>
      )}
    </div>
  );
}
