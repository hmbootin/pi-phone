import { useMemo, useState } from 'react';
import { useContacts, useMarkListened, useRecordings } from '../api/hooks';
import type { Recording, RecordingKind } from '../api/types';
import { AudioPlayer } from '../components/AudioPlayer';
import { ErrorText } from '../components/ErrorText';
import { contactName, dayKey, formatBytes, formatDay, formatDuration, formatTime } from '../lib/format';


function RecordingRow({ rec, who }: { rec: Recording; who: string }) {
  const mark = useMarkListened();
  const title =
    rec.kind === 'call' ? `Call with ${who}` : rec.kind === 'secret' ? 'Secret message' : `Voicemail from ${who}`;
  return (
    <li aria-label={title}>
      <div className="row">
        {!rec.listened && <span className="unread-dot" aria-label="Not listened yet" />}
        <div className="grow">
          <div className="strong">{title}</div>
          <div className="small muted">
            {formatTime(rec.created_at)} &middot; {formatDuration(rec.duration_seconds)} &middot; {formatBytes(rec.size_bytes)}
            {rec.backed_up_at ? (
              <span className="tone-ok" title={`Backed up ${rec.backed_up_at}`}>
                {' '}
                &middot; &#10003; backed up
              </span>
            ) : (
              <span className="tone-warn"> &middot; not backed up yet</span>
            )}
          </div>
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        <AudioPlayer
          src={rec.audio_url}
          label={title}
          onPlay={() => {
            if (!rec.listened) mark.mutate({ id: rec.id });
          }}
        />
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        {rec.listened ? (
          <button className="btn small ghost" onClick={() => mark.mutate({ id: rec.id, listened: false })} disabled={mark.isPending}>
            Mark unlistened
          </button>
        ) : (
          <button className="btn small" onClick={() => mark.mutate({ id: rec.id })} disabled={mark.isPending}>
            Mark listened
          </button>
        )}
        <a className="btn small ghost" href={rec.audio_url} download={`tincan-${rec.kind}-${rec.id}.wav`}>
          Download
        </a>
      </div>
      <ErrorText error={mark.error} />
    </li>
  );
}

export function MemoriesPage() {
  const [kind, setKind] = useState<RecordingKind | ''>('');
  const [contactId, setContactId] = useState<number | ''>('');
  const contacts = useContacts();
  const recordings = useRecordings({
    kind: kind || undefined,
    contact_id: contactId === '' ? undefined : contactId,
  });

  const groups = useMemo(() => {
    const map = new Map<string, Recording[]>();
    for (const r of recordings.data ?? []) {
      const k = dayKey(r.created_at);
      map.set(k, [...(map.get(k) ?? []), r]);
    }
    return [...map.entries()].sort(([a], [b]) => (a < b ? 1 : -1));
  }, [recordings.data]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Memories</h1>
      </header>
      <div className="field-row">
        <div className="field">
          <label htmlFor="m-kind">Kind</label>
          <select id="m-kind" value={kind} onChange={(e) => setKind(e.target.value as RecordingKind | '')}>
            <option value="">All</option>
            <option value="call">Calls</option>
            <option value="secret">Secret messages</option>
            <option value="voicemail">Voicemails</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="m-contact">Who</label>
          <select
            id="m-contact"
            value={contactId}
            onChange={(e) => setContactId(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value="">Anyone</option>
            {contacts.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <ErrorText error={recordings.error} />
      {recordings.isLoading && <div className="muted">Loading&hellip;</div>}
      {recordings.data?.length === 0 && <div className="empty">No memories match.</div>}
      {groups.map(([day, recs]) => (
        <section key={day}>
          <h2>{formatDay(recs[0]!.created_at)}</h2>
          <div className="card">
            <ul className="list">
              {recs.map((r) => (
                <RecordingRow key={r.id} rec={r} who={contactName(contacts.data, r.contact_id)} />
              ))}
            </ul>
          </div>
        </section>
      ))}
    </div>
  );
}
