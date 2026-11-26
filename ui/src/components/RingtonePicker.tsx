import { useRingtoneMutations, useRingtones } from '../api/hooks';
import { AudioPlayer } from './AudioPlayer';
import { ErrorText } from './ErrorText';

interface Props {
  /** The ringtone name in the (unsaved) settings form. */
  value: string;
  volume: number;
  onChange: (name: string) => void;
  onVolume: (volume: number) => void;
}

const DEFAULT_RINGTONE = 'classic';

function label(name: string): string {
  return name.replace(/[-_]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

export function RingtonePicker({ value, volume, onChange, onVolume }: Props) {
  const ringtones = useRingtones();
  const { upload, remove } = useRingtoneMutations();

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      const added = await upload.mutateAsync(file);
      onChange(added.name);
    } catch {
      // surfaced via upload.error
    }
  };

  const onRemove = async (name: string) => {
    try {
      await remove.mutateAsync(name);
      if (value === name) onChange(DEFAULT_RINGTONE);
    } catch {
      // surfaced via remove.error
    }
  };

  return (
    <div className="card">
      <ErrorText error={ringtones.error} />
      {ringtones.isPending && <div className="muted">Loading ringtones&hellip;</div>}
      <ul className="list ringtones" aria-label="Ringtones">
        {ringtones.data?.map((r) => (
          <li key={r.name} className="ringtone">
            <label className="ringtone-pick">
              <input type="radio" name="ringtone" value={r.name} checked={value === r.name} onChange={() => onChange(r.name)} />
              <span className="ringtone-name">{label(r.name)}</span>
              <span className="small muted">
                {r.builtin ? 'built in' : 'uploaded'} · {r.duration_seconds.toFixed(1)} s
              </span>
            </label>
            <div className="row ringtone-actions">
              <AudioPlayer src={r.audio_url} label={`Preview of ${label(r.name)}`} />
              {!r.builtin && (
                <button type="button" className="btn small ghost" disabled={remove.isPending} onClick={() => void onRemove(r.name)} aria-label={`Delete ${label(r.name)}`}>
                  Delete
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <ErrorText error={remove.error} />

      <div className="field">
        <label htmlFor="s-ringvol">Ringer volume ({volume}%)</label>
        <input id="s-ringvol" type="range" min={0} max={100} step={5} value={volume} onChange={(e) => onVolume(Number(e.target.value))} />
      </div>

      <div className="field">
        <label htmlFor="s-ringfile">Upload a ringtone</label>
        <input id="s-ringfile" type="file" accept=".wav,audio/wav,audio/x-wav" disabled={upload.isPending} onChange={(e) => void onFile(e)} />
        <span className="hint">A WAV file up to 10 seconds. It plays as a 2 s burst on the base speaker; the file name becomes its name.</span>
        {upload.isPending && <div className="muted small">Uploading&hellip;</div>}
        <ErrorText error={upload.error} />
      </div>
    </div>
  );
}
