import type { DetroitKeyboardSettings, KeyboardStyleMode } from '../types/generated'
import {
  DETROIT_KEYBOARD_DISCLAIMER,
  DETROIT_KEYBOARD_OPTIONS,
  normalizedKeyboardBlend,
  withKeyboardBlendInfluence,
} from '../utils/detroitKeyboard'

type Props = {
  value: DetroitKeyboardSettings
  onChange: (value: DetroitKeyboardSettings) => void
  compact?: boolean
}

const blendFields = [
  ['earl', 'Earl の影響度'],
  ['joe', 'Joe の影響度'],
  ['johnny', 'Johnny の影響度'],
] as const

export function DetroitKeyboardControl({ value, onChange, compact = false }: Props) {
  const selected = DETROIT_KEYBOARD_OPTIONS.find(option => option.value === value.mode)
    ?? DETROIT_KEYBOARD_OPTIONS[0]
  const normalizedBlend = normalizedKeyboardBlend(value.blend)
  const updateBlend = (key: keyof DetroitKeyboardSettings['blend'], amount: number) => {
    onChange(withKeyboardBlendInfluence(value, key, amount))
  }

  return <section className={compact ? 'detroit-keyboard-control compact' : 'detroit-keyboard-control'}>
    <div className="keyboard-style-heading">
      <label>Detroit Soul キーボード
        <select
          value={value.mode}
          onChange={event => onChange({ ...value, mode: event.target.value as KeyboardStyleMode })}
        >
          {DETROIT_KEYBOARD_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <p>{selected.description}</p>
    </div>
    {!compact && <ul aria-label="Detroit Soul キーボードの特徴">
      {selected.features.map(feature => <li key={feature}>{feature}</li>)}
    </ul>}
    {value.mode === 'blend' && <div className="keyboard-blend-controls">
      {blendFields.map(([key, label]) => <label key={key}>{label}
        <input
          aria-label={label}
          type="range"
          min="0"
          max="1"
          step=".01"
          value={value.blend[key]}
          onChange={event => updateBlend(key, Number(event.target.value))}
        />
        <b>{Math.round(normalizedBlend[key] * 100)}%</b>
      </label>)}
    </div>}
    {!compact && <small>{DETROIT_KEYBOARD_DISCLAIMER}</small>}
  </section>
}
