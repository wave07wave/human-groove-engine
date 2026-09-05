import { useEffect, useRef, useState } from 'react'
import { keyboardApi } from '../api/client'
import { stopActivePreview } from '../audio/previewCoordinator'
import { useHistory } from '../hooks/useHistory'
import type { BassPattern, DetroitKeyboardSettings, GroovePattern, KeyboardEvent, KeyboardGenerateRequest, KeyboardGenerationRecord, KeyboardPattern } from '../types/generated'
import { DEFAULT_DETROIT_KEYBOARD } from '../utils/detroitKeyboard'
import { layoutKeyboardBarEvents } from '../utils/keyboardLayout'
import { METERS } from '../utils/meters'
import { DetroitKeyboardControl } from './DetroitKeyboardControl'
import './keyboard.css'

const meterOptions = ['4/4', '3/4', '6/8']
const instrumentLabels = {
  acoustic_piano: 'Piano',
  tonewheel_organ: 'Organ',
  electric_piano: 'Electric',
  celeste: 'Celeste',
}
const pitchNames = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B']
const pitchLabel = (pitch: number) => `${pitchNames[pitch % 12]}${Math.floor(pitch / 12) - 1}`

function rhythmContext(groove: GroovePattern | null, bass: BassPattern | null) {
  return {
    kick_ticks: groove?.events.filter(event => event.instrument === 'kick').map(event => event.grid_tick + event.structural_offset_tick) ?? [],
    snare_ticks: groove?.events.filter(event => event.instrument === 'snare').map(event => event.grid_tick + event.structural_offset_tick) ?? [],
    bass_ticks: bass?.events.map(event => event.grid_tick + event.structural_offset_tick) ?? [],
  }
}

type Props = {
  groovePattern: GroovePattern | null
  bassPattern: BassPattern | null
  externalPattern?: KeyboardPattern | null
  onKeyboardPatternChange?: (pattern: KeyboardPattern | null) => void
}

export function KeyboardApp({ groovePattern, bassPattern, externalPattern, onKeyboardPatternChange }: Props) {
  const [bpm, setBpm] = useState(100)
  const [bars, setBars] = useState(4)
  const [meter, setMeter] = useState('4/4')
  const [seed, setSeed] = useState(42)
  const [harmony, setHarmony] = useState('Dm7 | G7 | Cmaj7 | A7')
  const [settings, setSettings] = useState<DetroitKeyboardSettings>(DEFAULT_DETROIT_KEYBOARD)
  const [candidates, setCandidates] = useState<KeyboardPattern[]>([])
  const [selectedBars, setSelectedBars] = useState(new Set<number>())
  const [savedPatterns, setSavedPatterns] = useState<KeyboardPattern[]>([])
  const [savedPatternId, setSavedPatternId] = useState('')
  const [generationHistory, setGenerationHistory] = useState<KeyboardGenerationRecord[]>([])
  const [generationId, setGenerationId] = useState('')
  const [busy, setBusy] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const history = useHistory<KeyboardPattern>(null)
  const pattern = history.present
  const commitPattern = history.commit
  const appliedExternalId = useRef<string | null>(null)
  const restoredId = useRef<string | null>(null)
  const patternBarTicks = pattern ? pattern.meter.numerator * 960 * 4 / pattern.meter.denominator : 3840
  const currentContext = rhythmContext(groovePattern, bassPattern)
  const settingsDirty = Boolean(pattern && (
    pattern.bpm !== bpm
    || pattern.bars !== bars
    || `${pattern.meter.numerator}/${pattern.meter.denominator}` !== meter
    || pattern.harmony_text !== harmony
    || pattern.metadata.master_seed !== seed
    || JSON.stringify(pattern.metadata.detroit_keyboard ?? DEFAULT_DETROIT_KEYBOARD) !== JSON.stringify(settings)
    || ((groovePattern || bassPattern)
      && JSON.stringify(pattern.rhythm_context) !== JSON.stringify(currentContext))
  ))

  useEffect(() => {
    if (!pattern && externalPattern) return
    onKeyboardPatternChange?.(pattern)
  }, [externalPattern, onKeyboardPatternChange, pattern])
  useEffect(() => {
    Promise.all([keyboardApi.patterns(), keyboardApi.generationHistory()])
      .then(([saved, generations]) => {
        setSavedPatterns(saved)
        setGenerationHistory(generations)
      })
      .catch(() => setError('Keysの保存一覧または履歴を読み込めませんでした。'))
  }, [])
  useEffect(() => () => stopActivePreview('keyboard'), [pattern?.pattern_id])
  useEffect(() => {
    if (!externalPattern || appliedExternalId.current === externalPattern.pattern_id) return
    appliedExternalId.current = externalPattern.pattern_id
    if (externalPattern.pattern_id === pattern?.pattern_id) return
    commitPattern(externalPattern)
    setCandidates([externalPattern])
  }, [commitPattern, externalPattern, pattern?.pattern_id])
  useEffect(() => {
    if (!pattern || restoredId.current === pattern.pattern_id) return
    restoredId.current = pattern.pattern_id
    setSettings(structuredClone(pattern.metadata.detroit_keyboard ?? DEFAULT_DETROIT_KEYBOARD))
    setBpm(pattern.bpm)
    setBars(pattern.bars)
    setSeed(pattern.metadata.master_seed)
    setHarmony(pattern.harmony_text)
    const name = `${pattern.meter.numerator}/${pattern.meter.denominator}`
    if (METERS[name]) setMeter(name)
  }, [pattern])

  const generate = async () => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const nextSeed = seed >= 2_147_483_647 ? 0 : seed + 1
      setSeed(nextSeed)
      const request: KeyboardGenerateRequest = {
        bpm,
        bars,
        meter: METERS[meter],
        harmony,
        key: 'C',
        mode: 'major',
        seed: nextSeed,
        candidate_count: 4,
        detroit_keyboard: settings,
        rhythm_context: rhythmContext(groovePattern, bassPattern),
      }
      const response = await keyboardApi.generate(request)
      setCandidates(response.candidates)
      history.commit(response.candidates[0])
      setSelectedBars(new Set())
      keyboardApi.generationHistory().then(setGenerationHistory)
        .catch(() => setNotice('Keysは生成されましたが、履歴一覧を更新できませんでした。'))
    } catch (cause) {
      setError(`Keysを生成できませんでした: ${String(cause)}`)
    } finally {
      setBusy(false)
    }
  }

  const regenerate = async () => {
    if (!pattern) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const next = await keyboardApi.mutate(pattern, [...selectedBars])
      history.commit(next)
      setCandidates(items => {
        const index = items.findIndex(item => item.pattern_id === pattern.pattern_id)
        if (index < 0) return [next, ...items].slice(0, 4)
        return items.map((item, itemIndex) => itemIndex === index ? next : item)
      })
      setSelectedBars(new Set())
      keyboardApi.generationHistory().then(setGenerationHistory)
        .catch(() => setNotice('Keysは再生成されましたが、履歴一覧を更新できませんでした。'))
    } catch (cause) {
      setError(`Keysを再生成できませんでした: ${String(cause)}`)
    } finally {
      setBusy(false)
    }
  }

  const toggleEventLock = (event: KeyboardEvent) => {
    if (!pattern) return
    history.commit({
      ...pattern,
      events: pattern.events.map(item => item.event_id === event.event_id ? { ...item, locked: !item.locked } : item),
    })
  }
  const toggleBar = (bar: number) => setSelectedBars(current => {
    const next = new Set(current)
    if (next.has(bar)) next.delete(bar); else next.add(bar)
    return next
  })
  const syncRhythmSection = () => {
    const source = groovePattern ?? bassPattern
    if (!source) return
    setBpm(source.bpm)
    setBars(source.bars)
    const name = `${source.meter.numerator}/${source.meter.denominator}`
    if (METERS[name]) setMeter(name)
    setNotice('現在のGroove / Bassへ同期しました')
  }
  const savePattern = async () => {
    if (!pattern) return
    setBusy(true)
    setError('')
    try {
      await keyboardApi.savePattern(pattern)
      setSavedPatternId(pattern.pattern_id)
      setNotice('Keysパターンを保存しました')
      keyboardApi.patterns().then(setSavedPatterns)
        .catch(() => setNotice('保存しましたが、保存一覧を更新できませんでした。'))
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const applyPattern = (next: KeyboardPattern) => {
    history.commit(next)
    setCandidates([next])
    setSelectedBars(new Set())
  }
  const selectCandidate = (next: KeyboardPattern) => {
    history.commit(next)
    setSelectedBars(new Set())
  }
  const loadSaved = () => {
    const found = savedPatterns.find(item => item.pattern_id === savedPatternId)
    if (found) applyPattern(found)
  }
  const loadGeneration = async () => {
    if (!generationId) return
    setBusy(true)
    try { applyPattern(await keyboardApi.generationPattern(Number(generationId))) }
    catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const exportMidi = async () => {
    if (!pattern) return
    setError('')
    try { await keyboardApi.midi(pattern) }
    catch (cause) { setError(`MIDIを書き出せませんでした: ${String(cause)}`) }
  }

  return <div className="app-shell keyboard-app">
    <header>
      <div className="brand-mark keyboard-brand">KEYS</div>
      <div><p className="eyebrow">HUMAN KEYS ENGINE</p><h1>響き、支え、応答する。</h1></div>
      <div className="header-actions"><button className="ghost-button" disabled={!history.canUndo} onClick={history.undo}>↶ 戻す</button><button className="ghost-button" disabled={!history.canRedo} onClick={history.redo}>↷ やり直す</button></div>
    </header>
    <main>
      <section className="control-panel panel">
        <div className="keyboard-transport">
          <label>BPM<input aria-label="KEYS BPM" type="number" min="30" max="300" value={bpm} onChange={event => setBpm(Number(event.target.value))} /></label>
          <label>小節数<select aria-label="KEYS BARS" value={bars} onChange={event => setBars(Number(event.target.value))}>{[1, 2, 4, 8, 16, 32, 64].map(value => <option key={value}>{value}</option>)}</select></label>
          <label>拍子<select aria-label="KEYS METER" value={meter} onChange={event => setMeter(event.target.value)}>{meterOptions.map(value => <option key={value}>{value}</option>)}</select></label>
          <label>ランダム値<input aria-label="KEYS SEED" type="number" min="0" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
          <label className="keyboard-harmony">コード進行<input aria-label="KEYS HARMONY" value={harmony} onChange={event => setHarmony(event.target.value)} /></label>
        </div>
        <DetroitKeyboardControl value={settings} onChange={setSettings} />
        <div className="keyboard-link">
          <button className="secondary" disabled={!groovePattern && !bassPattern} onClick={syncRhythmSection}>Groove / Bassへ同期</button>
          <span>{groovePattern || bassPattern ? `Kick ${groovePattern?.events.filter(event => event.instrument === 'kick').length ?? 0} · Bass ${bassPattern?.events.length ?? 0} 音を参照` : 'GrooveとBassがある場合は自動的に会話へ反映します'}</span>
        </div>
        <div className="primary-actions">
          <button className="generate" disabled={busy} onClick={generate}>{busy ? '作成中…' : 'Keysを作成'}</button>
          <button className={playing ? 'play active' : 'play'} disabled={!pattern} onClick={() => { if (pattern) void import('../audio/keyboardPreview').then(module => module.toggleKeyboardPreview(pattern, setPlaying)).catch(cause => setError(String(cause))) }}>{playing ? '■ 停止' : '▶ Keys再生'}</button>
          <button className="secondary" disabled={!pattern || busy} onClick={regenerate}>{selectedBars.size ? '↻ 選択小節を再作成' : '↻ 全小節を再作成'}</button>
          <button className="secondary" disabled={!pattern || busy} onClick={exportMidi}>↓ MIDI</button>
        </div>
        {settingsDirty && <p className="keyboard-pending" role="status">設定が変わっています。「Keysを作成」で新しい設定を反映できます。再生・保存・MIDIは現在表示中のパターンを使用します。</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p className="keyboard-notice" role="status">{notice}</p>}
      </section>

      {candidates.length > 0 && <section className="candidates keyboard-candidates">{candidates.map((item, index) => <button aria-pressed={pattern?.pattern_id === item.pattern_id} className={pattern?.pattern_id === item.pattern_id ? 'candidate active' : 'candidate'} key={item.pattern_id} onClick={() => selectCandidate(item)}><b>{String.fromCharCode(65 + index)}</b><span>Keys候補</span><small>{item.events.length} onsets</small></button>)}</section>}

      {pattern && <section className="keyboard-roll panel">
        <div className="keyboard-roll-heading"><div><p className="eyebrow">KEYBOARD TIMELINE</p><h2>{pattern.name}</h2></div><span>小節番号を選び、部分再生成できます。鍵盤イベントを押すとロックします。</span></div>
        <div className="keyboard-bars">{Array.from({ length: pattern.bars }, (_, bar) => {
          const barEvents = pattern.events.filter(event => Math.floor(event.grid_tick / patternBarTicks) === bar)
          const positioned = layoutKeyboardBarEvents(barEvents, patternBarTicks)
          const laneCount = Math.max(1, ...positioned.map(item => item.lane + 1))
          return <article key={bar} className={selectedBars.has(bar) ? 'selected' : ''} style={{ minHeight: `${Math.max(54, laneCount * 44 + 10)}px` }}>
            <button aria-pressed={selectedBars.has(bar)} className="bar-selector" onClick={() => toggleBar(bar)}>BAR {bar + 1}</button>
            <div>{positioned.map(({ event, lane, edge }) => {
              const pitches = event.pitches.map(pitchLabel).join(' · ')
              const lockState = event.locked ? 'ロック済み' : '未ロック'
              const position = (event.grid_tick % patternBarTicks) / patternBarTicks
              return <button aria-pressed={event.locked} aria-label={`${instrumentLabels[event.instrument]}、${pitches}、${event.role}、${lockState}`} title={pitches} className={`keyboard-event ${event.instrument} ${edge ? 'edge' : ''} ${event.locked ? 'locked' : ''}`} key={event.event_id} onClick={() => toggleEventLock(event)} style={{ left: `${position * 100}%`, top: `${7 + lane * 44}px` }}><b>{instrumentLabels[event.instrument]}</b><small>{pitchLabel(event.pitches.at(-1) ?? 60)} · {event.role}</small></button>
            })}</div>
          </article>
        })}</div>
      </section>}

      {pattern?.analysis && <section className="keyboard-analysis panel">
        <div><strong>{pattern.analysis.onsets_per_bar.toFixed(1)}</strong><span>発音／小節</span></div>
        <dl>
          <div><dt>シンコペーション</dt><dd>{Math.round(pattern.analysis.syncopation_ratio * 100)}</dd></div>
          <div><dt>平均ベロシティ</dt><dd>{Math.round(pattern.analysis.mean_velocity)}</dd></div>
          <div><dt>タイミング幅</dt><dd>{Math.round(pattern.analysis.timing_spread_us)}µs</dd></div>
          <div><dt>平均音域</dt><dd>{pitchLabel(Math.round(pattern.analysis.register_mean))}</dd></div>
          <div><dt>左手／両手</dt><dd>{Math.round(pattern.analysis.left_hand_ratio * 100)}%</dd></div>
          <div><dt>旋律的な応答</dt><dd>{Math.round(pattern.analysis.melodic_ratio * 100)}%</dd></div>
        </dl>
      </section>}

      <section className="keyboard-library panel">
        <div><label>保存済み<select value={savedPatternId} onChange={event => setSavedPatternId(event.target.value)}><option value="">選択…</option>{savedPatterns.map(item => <option key={item.pattern_id} value={item.pattern_id}>{item.name}</option>)}</select></label><button className="secondary" disabled={!pattern || busy} onClick={savePattern}>保存</button><button className="secondary" disabled={!savedPatternId} onClick={loadSaved}>読込</button></div>
        <div><label>生成履歴<select value={generationId} onChange={event => setGenerationId(event.target.value)}><option value="">選択…</option>{generationHistory.map(item => <option key={item.generation_id} value={item.generation_id}>{item.name} · {item.style}</option>)}</select></label><button className="secondary" disabled={!generationId || busy} onClick={loadGeneration}>履歴を読込</button></div>
      </section>
    </main>
    <footer><span>KEYS ENGINE · GENERATIVE VOICING</span><span>Register → touch → conversation → resolution</span></footer>
  </div>
}
