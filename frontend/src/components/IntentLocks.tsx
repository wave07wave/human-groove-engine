import type { BassIntentLocks } from '../types/generated'
import { EMPTY_INTENT_LOCKS } from '../utils/intentLocks'

const options: [keyof BassIntentLocks, string][] = [
  ['keep_rhythm_feel', 'Rhythm feel'],
  ['keep_register', 'Register'],
  ['keep_kick_relationship', 'Kick relationship'],
]

export function IntentLocks({ value, onChange }: {
  value: BassIntentLocks
  onChange: (value: BassIntentLocks) => void
}) {
  const active = options.filter(([key]) => value[key]).length
  return <fieldset className="intent-locks">
    <legend>INTENT LOCKS · {active} ACTIVE</legend>
    {options.map(([key, label]) => <label key={key}><input type="checkbox" checked={value[key]} onChange={event => onChange({ ...value, [key]: event.target.checked })} /> {label}</label>)}
    <button type="button" disabled={!active} onClick={() => onChange({ ...EMPTY_INTENT_LOCKS })}>CLEAR</button>
  </fieldset>
}
