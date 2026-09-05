import type { BillEvansProfile, DetroitKeyboardSettings, KeyboardStyleMode } from '../types/generated'
import {
  DEFAULT_DETROIT_KEYBOARD,
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
  const billEvans = value.bill_evans ?? DEFAULT_DETROIT_KEYBOARD.bill_evans!
  const updateBlend = (key: keyof DetroitKeyboardSettings['blend'], amount: number) => {
    onChange(withKeyboardBlendInfluence(value, key, amount))
  }
  const updateBillEvans = (next: Partial<DetroitKeyboardSettings['bill_evans']>) => {
    onChange({ ...value, bill_evans: { ...billEvans, ...next } })
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
    {value.mode === 'bill_evans' && <div className="keyboard-blend-controls bill-evans-controls">
      <label>演奏プロファイル
        <select aria-label="Bill Evans 演奏プロファイル" value={billEvans.profile} onChange={event => updateBillEvans({ profile: event.target.value as BillEvansProfile })}>
          <option value="lyrical_ballad">Lyrical Ballad</option>
          <option value="interactive_trio">Interactive Trio</option>
          <option value="solo_reflective">Solo Reflective</option>
          <option value="waltz">Waltz</option>
          <option value="uptempo">Uptempo</option>
        </select>
      </label>
      <label>演奏編成
        <select aria-label="Bill Evans 演奏編成" value={billEvans.performance_context} onChange={event => updateBillEvans({ performance_context: event.target.value as NonNullable<DetroitKeyboardSettings['bill_evans']>['performance_context'] })}>
          <option value="solo">Solo</option>
          <option value="trio_with_bass">Trio with Bass</option>
          <option value="full_trio">Full Trio</option>
        </select>
      </label>
      <label>コード維持
        <input aria-label="Bill Evans コード維持" type="range" min="0" max="4" step="1" value={billEvans.chord_retention} onChange={event => updateBillEvans({ chord_retention: Number(event.target.value) })} />
        <b>{['Strict', 'Conservative', 'Balanced', 'Adventurous', 'Transformative'][billEvans.chord_retention]}</b>
      </label>
    </div>}
    {!compact && <small>{DETROIT_KEYBOARD_DISCLAIMER}</small>}
  </section>
}
