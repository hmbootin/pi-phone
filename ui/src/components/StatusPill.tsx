interface Props {
  label: string;
  state: string;
}

const good = new Set(['connected', 'registered']);
const meh = new Set(['unconfigured']);

export function StatusPill({ label, state }: Props) {
  const tone = good.has(state) ? 'ok' : meh.has(state) ? 'warn' : 'bad';
  return (
    <span className="pill" title={`${label}: ${state}`}>
      <span className={`dot ${tone}`} aria-hidden />
      <span>
        {label} <span className="muted">{state}</span>
      </span>
    </span>
  );
}
