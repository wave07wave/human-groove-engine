import type { BassIntentLocks } from '../types/generated'
import { EMPTY_INTENT_LOCKS } from '../utils/intentLocks'

const options: [keyof BassIntentLocks, string][] = [
  ['keep_rhythm_feel', 'リズムの感触'], ['keep_register', '音域'], ['keep_kick_relationship', 'Kickとの関係'],
]

export function IntentLocks({ value, onChange }: {
  value: BassIntentLocks
  onChange: (value: BassIntentLocks) => void
}) {
  const active = options.filter(([key]) => value[key]).length
  return <fieldset className="intent-locks">
    <legend>意図を固定 · {active}項目</legend>
    {options.map(([key, label]) => <label key={key}><input type="checkbox" checked={value[key]} onChange={event => onChange({ ...value, [key]: event.target.checked })} /> {label}</label>)}
    <button type="button" disabled={!active} onClick={() => onChange({ ...EMPTY_INTENT_LOCKS })}>解除</button>
  </fieldset>
}
