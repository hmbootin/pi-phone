interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
  hideLabel?: boolean;
}

export function Toggle({ checked, onChange, label, disabled, hideLabel }: Props) {
  return (
    <label className="toggle">
      <input
        type="checkbox"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {!hideLabel && <span className="small">{label}</span>}
    </label>
  );
}
