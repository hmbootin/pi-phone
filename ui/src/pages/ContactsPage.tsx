import { useState } from 'react';
import { useContactMutations, useContacts, useFeatures } from '../api/hooks';
import type { Contact, ContactInput, Feature } from '../api/types';
import { ErrorText } from '../components/ErrorText';
import { Toggle } from '../components/Toggle';
import { FEATURE_LABELS, formatRelativeUntil, isDndActive, nextMorning } from '../lib/format';

const EMPTY: ContactInput = {
  name: '',
  spoken_name: '',
  number: '',
  speed_dial: -1,
  enabled: true,
  inbound_allowed: true,
  dnd_until: null,
  max_call_minutes: null,
};

type DigitUse =
  | { kind: 'free' }
  | { kind: 'self' }
  | { kind: 'contact'; name: string }
  | { kind: 'feature'; label: string };

function digitUses(contacts: Contact[], features: Feature[], selfId: number | null): DigitUse[] {
  return Array.from({ length: 10 }, (_, d) => {
    const c = contacts.find((x) => x.speed_dial === d);
    if (c) return c.id === selfId ? { kind: 'self' } : { kind: 'contact', name: c.name };
    const f = features.find((x) => x.digit === d);
    if (f && f.kind !== 'none' && f.kind !== 'speed_dial') return { kind: 'feature', label: FEATURE_LABELS[f.kind] };
    return { kind: 'free' };
  });
}

export function DigitPicker({
  value,
  onChange,
  uses,
}: {
  value: number;
  onChange: (d: number) => void;
  uses: DigitUse[];
}) {
  return (
    <div className="field">
      <span className="label" id="speed-dial-label">
        Speed dial digit
      </span>
      <div className="digit-picker" role="radiogroup" aria-labelledby="speed-dial-label">
        {uses.map((u, d) => {
          const taken = u.kind === 'contact';
          const sub = u.kind === 'contact' ? u.name : u.kind === 'feature' ? u.label : u.kind === 'self' ? 'current' : 'free';
          return (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={value === d}
              aria-label={`Digit ${d}, ${sub}`}
              className={value === d ? 'selected' : ''}
              disabled={taken}
              onClick={() => onChange(d)}
              title={taken ? `Used by ${u.name}` : undefined}
            >
              <span className="d">{d}</span>
              <span className="u">{sub}</span>
            </button>
          );
        })}
      </div>
      <span className="hint">Digits used by a feature can be reassigned; the feature will be replaced.</span>
    </div>
  );
}

function ContactForm({
  initial,
  selfId,
  contacts,
  features,
  onCancel,
  onSaved,
}: {
  initial: ContactInput;
  selfId: number | null;
  contacts: Contact[];
  features: Feature[];
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<ContactInput>(initial);
  const { create, update } = useContactMutations();
  const m = selfId == null ? create : update;
  const uses = digitUses(contacts, features, selfId);
  const set = <K extends keyof ContactInput>(k: K, v: ContactInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (selfId == null) await create.mutateAsync(form);
      else await update.mutateAsync({ id: selfId, patch: form });
      onSaved();
    } catch {
      // error surfaces via mutation state
    }
  };

  return (
    <form className="card" onSubmit={submit} aria-label={selfId == null ? 'New contact' : 'Edit contact'}>
      <div className="field">
        <label htmlFor="c-name">Name</label>
        <input id="c-name" type="text" required value={form.name} onChange={(e) => set('name', e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="c-spoken">Spoken name</label>
        <input
          id="c-spoken"
          type="text"
          placeholder={form.name || 'How the phone says it'}
          value={form.spoken_name}
          onChange={(e) => set('spoken_name', e.target.value)}
        />
        <span className="hint">Used in prompts like &ldquo;calling Grandma Jo&rdquo;.</span>
      </div>
      <div className="field">
        <label htmlFor="c-number">Phone number</label>
        <input
          id="c-number"
          type="tel"
          required
          placeholder="+15555550123"
          value={form.number}
          onChange={(e) => set('number', e.target.value)}
        />
      </div>
      <DigitPicker value={form.speed_dial} onChange={(d) => set('speed_dial', d)} uses={uses} />
      <div className="field">
        <label htmlFor="c-max">Max minutes per call</label>
        <input
          id="c-max"
          type="number"
          min={1}
          max={120}
          placeholder="Use the default"
          value={form.max_call_minutes ?? ''}
          onChange={(e) => set('max_call_minutes', e.target.value === '' ? null : Number(e.target.value))}
        />
      </div>
      <div className="stack" style={{ marginBottom: 12 }}>
        <Toggle label="Enabled" checked={form.enabled} onChange={(v) => set('enabled', v)} />
        <Toggle label="Can call in" checked={form.inbound_allowed} onChange={(v) => set('inbound_allowed', v)} />
      </div>
      <ErrorText error={m.error} />
      <div className="row">
        <button type="button" className="btn grow" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="submit"
          className="btn primary grow"
          disabled={m.isPending || form.speed_dial < 0 || !form.name || !form.number}
        >
          {m.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  );
}

function DndControls({ contact }: { contact: Contact }) {
  const { dnd } = useContactMutations();
  const active = isDndActive(contact);
  const run = (body: Parameters<typeof dnd.mutate>[0]['body']) => dnd.mutate({ id: contact.id, body });
  return (
    <div className="stack">
      <div className="row between">
        <span className="small">
          Do not disturb
          {active && contact.dnd_until && (
            <span className="tone-warn"> &middot; {formatRelativeUntil(contact.dnd_until)}</span>
          )}
        </span>
        {active && (
          <button className="btn small" onClick={() => run({ clear: true })} disabled={dnd.isPending}>
            Clear
          </button>
        )}
      </div>
      <div className="segmented">
        <button className="btn small" onClick={() => run({ minutes: 60 })} disabled={dnd.isPending}>
          1h
        </button>
        <button className="btn small" onClick={() => run({ minutes: 120 })} disabled={dnd.isPending}>
          2h
        </button>
        <button
          className="btn small"
          onClick={() => run({ until: nextMorning().toISOString() })}
          disabled={dnd.isPending}
                  aria-label="Until tomorrow 7:30"
        >
          Until 7:30 am
        </button>
      </div>
      <ErrorText error={dnd.error} />
    </div>
  );
}

function ContactCard({
  contact,
  contacts,
  features,
}: {
  contact: Contact;
  contacts: Contact[];
  features: Feature[];
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { update, remove } = useContactMutations();

  if (editing) {
    const initial: ContactInput = {
      name: contact.name,
      spoken_name: contact.spoken_name,
      number: contact.number,
      speed_dial: contact.speed_dial,
      enabled: contact.enabled,
      inbound_allowed: contact.inbound_allowed,
      dnd_until: contact.dnd_until,
      max_call_minutes: contact.max_call_minutes,
    };
    return (
      <ContactForm
        initial={initial}
        selfId={contact.id}
        contacts={contacts}
        features={features}
        onCancel={() => setEditing(false)}
        onSaved={() => setEditing(false)}
      />
    );
  }

  return (
    <article className="card" aria-label={contact.name}>
      <div className="row">
        <span className={`badge digit ${contact.enabled ? '' : 'off'}`} aria-label={`Speed dial ${contact.speed_dial}`}>
          {contact.speed_dial}
        </span>
        <div className="grow">
          <div className="strong truncate">{contact.name}</div>
          <div className="small muted truncate">
            {contact.number}
            {contact.max_call_minutes != null && ` · ${contact.max_call_minutes} min max`}
            {!contact.inbound_allowed && ' · outgoing only'}
          </div>
        </div>
        <Toggle
          label={`Enable ${contact.name}`}
          hideLabel
          checked={contact.enabled}
          onChange={(v) => update.mutate({ id: contact.id, patch: { enabled: v } })}
          disabled={update.isPending}
        />
      </div>
      <div style={{ marginTop: 10 }}>
        <DndControls contact={contact} />
      </div>
      <ErrorText error={update.error ?? remove.error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn small ghost" onClick={() => setEditing(true)}>
          Edit
        </button>
        {confirmDelete ? (
          <>
            <button className="btn small danger" onClick={() => remove.mutate(contact.id)} disabled={remove.isPending}>
              Really delete
            </button>
            <button className="btn small ghost" onClick={() => setConfirmDelete(false)}>
              Keep
            </button>
          </>
        ) : (
          <button className="btn small ghost" onClick={() => setConfirmDelete(true)}>
            Delete
          </button>
        )}
      </div>
    </article>
  );
}

export function ContactsPage() {
  const contacts = useContacts();
  const features = useFeatures();
  const [adding, setAdding] = useState(false);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Contacts</h1>
        {!adding && (
          <button className="btn primary small" onClick={() => setAdding(true)}>
            Add contact
          </button>
        )}
      </header>

      {adding && (
        <ContactForm
          initial={EMPTY}
          selfId={null}
          contacts={contacts.data ?? []}
          features={features.data ?? []}
          onCancel={() => setAdding(false)}
          onSaved={() => setAdding(false)}
        />
      )}

      <ErrorText error={contacts.error} />
      {contacts.isLoading && <div className="muted">Loading&hellip;</div>}
      {contacts.data?.length === 0 && !adding && <div className="empty">No contacts yet. Add the first one.</div>}
      {[...(contacts.data ?? [])]
        .sort((a, b) => a.speed_dial - b.speed_dial)
        .map((c) => (
          <ContactCard key={c.id} contact={c} contacts={contacts.data ?? []} features={features.data ?? []} />
        ))}
    </div>
  );
}
