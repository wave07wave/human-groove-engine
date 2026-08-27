import type { BassPreserveOptions } from '../types/generated'
import { EMPTY_PRESERVE_OPTIONS } from '../utils/preserveOptions'

const options: [keyof BassPreserveOptions, string][] = [
  ['keep_rhythm', 'リズム'], ['keep_pitch', '音程'], ['keep_duration', '音の長さ'],
  ['keep_timing', 'タイミング'], ['keep_motif', 'モチーフ'], ['keep_kick_relation', 'Kickとの関係'], ['keep_register_shape', '音域の形'],
]

export function PreserveOptions({ value, onChange }: {
  value: BassPreserveOptions
  onChange: (value: BassPreserveOptions) => void
}) {
  const active = options.filter(([key]) => value[key]).length
  return <fieldset className="preserve-options">
    <legend>再生成で維持 · {active}項目</legend>
    {options.map(([key, label]) => <label key={key}><input type="checkbox" checked={value[key]} onChange={event => onChange({ ...value, [key]: event.target.checked })} /> {label}</label>)}
    <button type="button" disabled={!active} onClick={() => onChange({ ...EMPTY_PRESERVE_OPTIONS })}>解除</button>
  </fieldset>
}
