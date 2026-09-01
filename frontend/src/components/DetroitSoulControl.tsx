import type { DetroitSoulMode, DetroitSoulSettings } from '../types/generated'
import { DETROIT_SOUL_DISCLAIMER, DETROIT_SOUL_OPTIONS } from '../utils/detroitSoul'

const BLEND_LABELS = {
  benny: 'Benny の影響度',
  pistol: 'Pistol の影響度',
  uriel: 'Uriel の影響度',
} as const

export function DetroitSoulControl({ value, onChange }: {
  value: DetroitSoulSettings
  onChange: (value: DetroitSoulSettings) => void
}) {
  const selected = DETROIT_SOUL_OPTIONS.find(option => option.value === value.mode) ?? DETROIT_SOUL_OPTIONS[0]
  const changeBlend = (key: keyof DetroitSoulSettings['blend'], nextValue: number) => {
    const blend = { ...value.blend, [key]: nextValue }
    if (blend.benny + blend.pistol + blend.uriel > 0) onChange({ ...value, blend })
  }
  return <section className="detroit-soul-control">
    <div>
      <label id="detroit-soul-title">Detroit Soul ドラマー
        <select value={value.mode} onChange={event => onChange({ ...value, mode: event.target.value as DetroitSoulMode })}>
          {DETROIT_SOUL_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <p>{selected.description}</p>
    </div>
    {value.mode === 'blend' && <div className="detroit-blend">
      {(Object.keys(BLEND_LABELS) as (keyof DetroitSoulSettings['blend'])[]).map(key => <label key={key}>
        <span>{BLEND_LABELS[key]}</span><b>{Math.round(value.blend[key] * 100)}</b>
        <input aria-label={BLEND_LABELS[key]} type="range" min="0" max="1" step=".01" value={value.blend[key]} onChange={event => changeBlend(key, Number(event.target.value))}/>
      </label>)}
    </div>}
    <small>{DETROIT_SOUL_DISCLAIMER}</small>
  </section>
}
