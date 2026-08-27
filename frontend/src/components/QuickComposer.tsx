import { useEffect, useState } from 'react'
import { api, bassApi } from '../api/client'
import { toggleMixPreview } from '../audio/mixPreview'
import type { BassGenerateRequest, BassPresetsResponse, BassPattern, GroovePattern, PresetsResponse } from '../types/generated'
import { METERS } from '../utils/meters'

type Props = {
  groove: GroovePattern | null
  bass: BassPattern | null
  onReady: (groove: GroovePattern, bass: BassPattern) => void
  onOpenDetails: () => void
}

export function QuickComposer({ groove, bass, onReady, onOpenDetails }: Props) {
  const [groovePresets, setGroovePresets] = useState<PresetsResponse | null>(null)
  const [bassPresets, setBassPresets] = useState<BassPresetsResponse | null>(null)
  const [style, setStyle] = useState('Balanced')
  const [bassRole, setBassRole] = useState('Supportive')
  const [bpm, setBpm] = useState(100)
  const [bars, setBars] = useState(4)
  const [seed, setSeed] = useState(42)
  const [busy, setBusy] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.presets().then(setGroovePresets).catch(cause => setError(String(cause)))
    bassApi.presets().then(setBassPresets).catch(cause => setError(String(cause)))
  }, [])

  const generateSong = async () => {
    const grooveIntent = groovePresets?.built_in[style] ?? groovePresets?.built_in.Balanced
    const bassIntent = bassPresets?.built_in[bassRole] ?? bassPresets?.built_in.Supportive
    if (!grooveIntent || !bassIntent) return
    setBusy(true)
    setError('')
    try {
      const nextSeed = seed >= 2_147_483_647 ? 0 : seed + 1
      setSeed(nextSeed)
      const grooveResponse = await api.generate({
        bpm, bars, meter: METERS['4/4'], intent: grooveIntent, preset: style,
        seed: nextSeed, mode: 'preview', candidate_count: 1,
      })
      const nextGroove = grooveResponse.candidates[0]
      const request: BassGenerateRequest = {
        bpm, bars, meter: METERS['4/4'], input_mode: 'chord_progression',
        harmony: 'Dm7 | G7 | Cmaj7 | A7', key: 'C', mode: 'major', intent: bassIntent,
        preset: bassRole, seed: nextSeed, candidate_count: 1,
        register_limits: { lowest_midi_note: 28, highest_midi_note: 60, preferred_center: 42, preferred_zone: 'core', max_single_leap: 12 },
        voice_policy: 'monophonic_retrigger', groove_context: null,
      }
      const response = await bassApi.jointGenerate(nextGroove, request, 'follow', .55, .60)
      const selected = response.candidates[0]
      onReady(selected.groove_pattern, selected.bass_pattern)
    } catch (cause) {
      setError(`生成できませんでした: ${String(cause)}`)
    } finally {
      setBusy(false)
    }
  }

  return <main className="quick-composer">
    <section className="quick-hero panel">
      <p className="eyebrow">かんたんモード · GROOVE + BASS</p>
      <h1>少ない設定で、すぐに一曲の土台を。</h1>
      <p>スタイル、Bassの役割、テンポだけを選べば、GrooveとBassを一緒に組み立てます。</p>
      <div className="quick-settings">
        <label>Grooveのスタイル<select value={style} onChange={event => setStyle(event.target.value)}>{Object.keys(groovePresets?.built_in ?? { Balanced: 1 }).map(name => <option key={name}>{name}</option>)}</select></label>
        <label>Bassの役割<select value={bassRole} onChange={event => setBassRole(event.target.value)}>{Object.keys(bassPresets?.built_in ?? { Supportive: 1 }).map(name => <option key={name}>{name}</option>)}</select></label>
        <label>BPM<input type="number" min="30" max="300" value={bpm} onChange={event => setBpm(Number(event.target.value))} /></label>
        <label>長さ<select value={bars} onChange={event => setBars(Number(event.target.value))}>{[2, 4, 8, 16].map(value => <option key={value} value={value}>{value}小節</option>)}</select></label>
      </div>
    </section>
    <section className="quick-status panel">
      <div><b>{groove && bass ? '準備完了' : '手順 1'}</b><span>{groove && bass ? 'GrooveとBassを一緒に再生できます。' : '設定を選んで「まとめて作成」を押してください。'}</span></div>
      <button className="secondary" disabled={!groove || !bass} onClick={onOpenDetails}>詳細編集 →</button>
    </section>
    {error && <p className="error">{error}</p>}
    <div className="quick-actions" aria-label="Easy mode actions">
      <button className="generate" disabled={busy || !groovePresets || !bassPresets} onClick={generateSong}>{busy ? '作成中…' : 'まとめて作成'}</button>
      <button className={playing ? 'play active' : 'play'} disabled={!groove || !bass} onClick={() => { if (groove && bass) void toggleMixPreview(groove, bass, setPlaying).catch(cause => setError(`音声を開始できません: ${String(cause)}`)) }}>{playing ? '■ 停止' : '▶ 同時再生'}</button>
    </div>
  </main>
}
