import type { BassPreserveOptions } from '../types/generated'
import { EMPTY_PRESERVE_OPTIONS } from '../utils/preserveOptions'

const options: [keyof BassPreserveOptions, string][] = [
  ['keep_rhythm', 'Rhythm'],
  ['keep_pitch', 'Pitch'],
  ['keep_duration', 'Duration'],
  ['keep_timing', 'Timing'],
  ['keep_motif', 'Motif'],
  ['keep_kick_relation', 'Kick relation'],
  ['keep_register_shape', 'Register shape'],
]

export function PreserveOptions({ value, onChange }: {
  value: BassPreserveOptions
  onChange: (value: BassPreserveOptions) => void
}) {
  const active = options.filter(([key]) => value[key]).length
  return <fieldset className="preserve-options">
    <legend>PRESERVE ON REGEN · {active} ACTIVE</legend>
    {options.map(([key, label]) => <label key={key}><input type="checkbox" checked={value[key]} onChange={event => onChange({ ...value, [key]: event.target.checked })} /> {label}</label>)}
    <button type="button" disabled={!active} onClick={() => onChange({ ...EMPTY_PRESERVE_OPTIONS })}>CLEAR</button>
  </fieldset>
}
