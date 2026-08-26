interface Props { label: string; value: number; onChange: (value: number) => void }

export function Knob({ label, value, onChange }: Props) {
  return <label className="knob">
    <span>{label}</span><strong>{Math.round(value * 100)}</strong>
    <input aria-label={label} type="range" min="0" max="1" step="0.01" value={value} onChange={event => onChange(Number(event.target.value))} />
  </label>
}
