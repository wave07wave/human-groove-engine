import type { MotownBassMode, MotownBassSettings } from '../types/generated'
import {
  MOTOWN_BASS_DISCLAIMER,
  MOTOWN_BASS_OPTIONS,
} from '../utils/motownBass'

type Props = {
  value: MotownBassSettings
  onChange: (value: MotownBassSettings) => void
}

export function MotownBassControl({ value, onChange }: Props) {
  const selected = MOTOWN_BASS_OPTIONS.find(option => option.value === value.mode)
    ?? MOTOWN_BASS_OPTIONS[0]

  return <section className="motown-bass-control">
    <div>
      <label>Motown ベーススタイル
        <select
          value={value.mode}
          onChange={event => onChange({ mode: event.target.value as MotownBassMode })}
        >
          {MOTOWN_BASS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <p>{selected.description}</p>
    </div>
    <ul aria-label="Motown ベーススタイルの特徴">
      {selected.features.map(feature => <li key={feature}>{feature}</li>)}
    </ul>
    <small>{MOTOWN_BASS_DISCLAIMER}</small>
  </section>
}
