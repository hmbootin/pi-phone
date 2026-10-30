import { useEffect, useState } from 'react';
import { useContacts, useFeatureMutations, useFeatures } from '../api/hooks';
import type { Feature, FeatureConfig, FeatureInput, FeatureKind, FeaturePreview } from '../api/types';
import { AudioPlayer } from '../components/AudioPlayer';
import { ErrorText } from '../components/ErrorText';
import { Toggle } from '../components/Toggle';
import { FEATURE_HINTS, FEATURE_LABELS, contactName } from '../lib/format';

const EDITABLE_KINDS: FeatureKind[] = ['weather', 'fun_fact', 'secret_message', 'mailbox', 'song', 'none'];
const KEY_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0];

function FeatureEditor({ feature, onClose }: { feature: Feature; onClose: () => void }) {
  const { put, preview } = useFeatureMutations();
  const [kind, setKind] = useState<FeatureKind>(feature.kind === 'speed_dial' ? 'none' : feature.kind);
  const [config, setConfig] = useState<FeatureConfig>(feature.config);
  const [enabled, setEnabled] = useState(feature.enabled);
  const [result, setResult] = useState<FeaturePreview | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setKind(feature.kind === 'speed_dial' ? 'none' : feature.kind);
    setConfig(feature.config);
    setEnabled(feature.enabled);
    setResult(null);
    setSaved(false);
    // Only reset when switching digits; a refetch after save must not wipe local edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feature.digit]);

  const setCfg = (k: keyof FeatureConfig, v: string) => setConfig((c) => ({ ...c, [k]: v }));

  const input = (): FeatureInput => ({ kind, config: cleanConfig(kind, config), enabled });

  const save = async () => {
    setSaved(false);
    try {
      await put.mutateAsync({ digit: feature.digit, input: input() });
      setSaved(true);
    } catch {
      // surfaced via put.error
    }
  };

  const doPreview = async () => {
    setResult(null);
    try {
      // Save first so the preview reflects what's on screen.
      await put.mutateAsync({ digit: feature.digit, input: input() });
      setSaved(true);
      setResult(await preview.mutateAsync(feature.digit));
    } catch {
      // surfaced via mutation errors
    }
  };

  return (
    <section className="card sheet" aria-label={`Digit ${feature.digit} settings`}>
      <div className="row between">
        <h3>
          Digit {feature.digit} &middot; {FEATURE_LABELS[kind]}
        </h3>
        <button className="btn small ghost" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="field" style={{ marginTop: 10 }}>
        <label htmlFor="f-kind">What happens</label>
        <select
          id="f-kind"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value as FeatureKind);
            setResult(null);
          }}
        >
          {EDITABLE_KINDS.map((k) => (
            <option key={k} value={k}>
              {FEATURE_LABELS[k]}
            </option>
          ))}
        </select>
        <span className="hint">{FEATURE_HINTS[kind]}</span>
      </div>

      {kind === 'fun_fact' && (
        <div className="field">
          <label htmlFor="f-topic">Topic</label>
          <input
            id="f-topic"
            type="text"
            placeholder="dinosaurs"
            value={config.topic ?? ''}
            onChange={(e) => setCfg('topic', e.target.value)}
          />
        </div>
      )}

      {kind === 'secret_message' && (
        <div className="field-row">
          <div className="field">
            <label htmlFor="f-recipient">For</label>
            <input
              id="f-recipient"
              type="text"
              placeholder="Mom"
              value={config.recipient ?? ''}
              onChange={(e) => setCfg('recipient', e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="f-notify">Notify via</label>
            <select id="f-notify" value={config.notify ?? 'ntfy'} onChange={(e) => setCfg('notify', e.target.value)}>
              <option value="ntfy">Push (ntfy)</option>
              <option value="email">Email</option>
              <option value="both">Both</option>
            </select>
          </div>
        </div>
      )}

      {kind === 'song' && (
        <div className="field">
          <label htmlFor="f-title">Song</label>
          <input
            id="f-title"
            type="text"
            placeholder="Twinkle Twinkle"
            value={config.title ?? ''}
            onChange={(e) => setCfg('title', e.target.value)}
          />
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <Toggle label="Enabled" checked={enabled} onChange={setEnabled} />
      </div>

      <ErrorText error={put.error ?? preview.error} />
      {saved && !put.isPending && <div className="notice">Saved.</div>}

      <div className="row">
        <button className="btn grow" onClick={doPreview} disabled={put.isPending || preview.isPending}>
          {preview.isPending ? 'Rendering…' : 'Preview'}
        </button>
        <button className="btn primary grow" onClick={save} disabled={put.isPending}>
          {put.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>

      {result && (
        <div className="stack" style={{ marginTop: 12 }}>
          <blockquote className="muted" style={{ margin: 0 }}>
            &ldquo;{result.text}&rdquo;
          </blockquote>
          <AudioPlayer src={result.audio_url} autoPlay label={`Preview of digit ${feature.digit}`} />
        </div>
      )}
    </section>
  );
}

function cleanConfig(kind: FeatureKind, config: FeatureConfig): FeatureConfig {
  switch (kind) {
    case 'fun_fact':
      return { topic: config.topic ?? '' };
    case 'secret_message':
      return { recipient: config.recipient ?? '', notify: config.notify ?? 'ntfy' };
    case 'song':
      return { title: config.title ?? '' };
    default:
      return {};
  }
}

export function DialPadPage() {
  const features = useFeatures();
  const contacts = useContacts();
  const [selected, setSelected] = useState<number | null>(null);

  const byDigit = new Map((features.data ?? []).map((f) => [f.digit, f]));
  const selectedFeature = selected != null ? byDigit.get(selected) : undefined;

  const labelFor = (f: Feature | undefined): string => {
    if (!f) return '';
    if (f.kind === 'speed_dial') {
      const cid = typeof f.config.contact_id === 'number' ? f.config.contact_id : null;
      const name = cid != null ? contactName(contacts.data, cid) : contacts.data?.find((c) => c.speed_dial === f.digit)?.name;
      return name ?? 'Contact';
    }
    if (f.kind === 'fun_fact' && f.config.topic) return `Fun fact: ${f.config.topic}`;
    if (f.kind === 'secret_message' && f.config.recipient) return `Secret for ${f.config.recipient}`;
    if (f.kind === 'song' && f.config.title) return `Song: ${f.config.title}`;
    return FEATURE_LABELS[f.kind];
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>Dial pad</h1>
      </header>
      <p className="muted small" style={{ marginTop: 0 }}>
        What each button does. Tap a button that isn&apos;t a contact to change it.
      </p>
      <ErrorText error={features.error} />
      <div className="dialpad" role="list">
        {KEY_ORDER.map((d) => {
          const f = byDigit.get(d);
          const isContact = f?.kind === 'speed_dial';
          const cls = [
            'key',
            d === 0 ? 'zero' : '',
            isContact ? 'contact' : '',
            selected === d ? 'selected' : '',
            f && !f.enabled ? 'disabled' : '',
          ]
            .filter(Boolean)
            .join(' ');
          return (
            <button
              key={d}
              role="listitem"
              className={cls}
              aria-label={`Digit ${d}: ${labelFor(f) || 'loading'}`}
              aria-pressed={selected === d}
              onClick={() => setSelected(isContact ? null : d)}
              title={isContact ? 'Edit this on the Contacts page' : undefined}
            >
              <span className="digit">{d}</span>
              <span className="label">{labelFor(f)}</span>
            </button>
          );
        })}
      </div>
      {selectedFeature && selectedFeature.kind !== 'speed_dial' && (
        <FeatureEditor feature={selectedFeature} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
