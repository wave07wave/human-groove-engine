import { useEffect, useMemo, useState } from 'react'
import { bassApi } from '../api/client'
import { toggleBassPreview, type BassPreviewMode } from '../audio/bassPreview'
import { useHistory } from '../hooks/useHistory'
import type { BassEvent, BassGenerateRequest, BassGenerationRecord, BassIntent, BassIntentDNA, BassMutationOperation, BassPattern, BassPatternExchange, BassPreferenceSummary, BassPreserveOptions, BassPresetsResponse, BassVoicePolicy, GrooveContext, GroovePattern, IntegrationMode, JointGenerationResult } from '../types/generated'
import { METERS, METER_OPTIONS } from '../utils/meters'
import { replaceCandidateRevision } from '../utils/candidates'
import { EMPTY_PRESERVE_OPTIONS } from '../utils/preserveOptions'
import { BassPianoRoll } from './BassPianoRoll'
import { HarmonyEditor } from './HarmonyEditor'
import { IntentLocks } from './IntentLocks'
import { Knob } from './Knob'
import { PreserveOptions } from './PreserveOptions'
import './bass.css'
import './groove-link.css'
import './interaction.css'

const macroControls: [string, keyof BassIntentDNA][] = [
  ['Stability', 'root_strength'], ['Motion', 'melodic_motion'], ['Syncopation', 'syncopation'],
  ['Kick lock', 'kick_lock'], ['Melodic', 'stepwise_motion'], ['Chromatic', 'chromaticism'],
  ['Density', 'density'], ['Silence', 'silence'], ['Human feel', 'human_feel'], ['Development', 'phrase_development'],
]
const modeOptions = ['major', 'natural_minor', 'harmonic_minor', 'melodic_minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'aeolian', 'locrian', 'major_pentatonic', 'minor_pentatonic', 'blues', 'chromatic'] as const
const mutations: { value: BassMutationOperation, label: string }[] = [
  { value: 'regenerate', label: 'ALL FIELDS' }, { value: 'pitch_only', label: 'PITCH ONLY' },
  { value: 'rhythm_only', label: 'RHYTHM ONLY' }, { value: 'timing_only', label: 'TIMING ONLY' },
  { value: 'duration_only', label: 'DURATION ONLY' }, { value: 'articulation_only', label: 'ARTICULATION ONLY' },
]

function score(value: number | null | undefined) { return Math.round((value ?? 0) * 100) }

const qualitySuffix: Record<string, string> = { major: '', minor: 'm', major7: 'maj7', dominant7: '7', minor7: 'm7', minor7b5: 'm7b5', dim: 'dim', dim7: 'dim7', aug: 'aug', sus2: 'sus2', sus4: 'sus4', '6': '6', minor6: 'm6', add9: 'add9', '9': '9', '11': '11', '13': '13' }
function pitchClassText(pitch: { letter: string, accidental: number }) { return `${pitch.letter}${pitch.accidental > 0 ? '#'.repeat(pitch.accidental) : 'b'.repeat(-pitch.accidental)}` }
function harmonyText(pattern: BassPattern) { return pattern.harmony.events.map(event => { if (!event.chord) return 'NO_CHORD'; const chord = event.chord; const slash = chord.bass_note ? `/${pitchClassText(chord.bass_note)}` : ''; return `${pitchClassText(chord.root)}${qualitySuffix[chord.quality] ?? chord.quality}${slash}` }).join(' | ') }

export function BassApp({ groovePattern, onGrooveUpdate }: { groovePattern: GroovePattern | null, onGrooveUpdate?: (pattern: GroovePattern) => void }) {
  const [presets, setPresets] = useState<BassPresetsResponse | null>(null)
  const [intent, setIntent] = useState<BassIntent | null>(null)
  const [preset, setPreset] = useState('Supportive')
  const [bpm, setBpm] = useState(100); const [bars, setBars] = useState(8); const [meter, setMeter] = useState('4/4'); const [seed, setSeed] = useState(42); const [voicePolicy, setVoicePolicy] = useState<BassVoicePolicy>('monophonic_retrigger'); const [midiChannel, setMidiChannel] = useState(0)
  const [inputMode, setInputMode] = useState<BassGenerateRequest['input_mode']>('chord_progression')
  const [harmony, setHarmony] = useState('Dm7 | G7 | Cmaj7 | A7'); const [keyName, setKeyName] = useState('C'); const [scaleMode, setScaleMode] = useState<BassGenerateRequest['mode']>('major')
  const [candidates, setCandidates] = useState<BassPattern[]>([]); const history = useHistory<BassPattern>(null)
  const replaceHistory = history.replace
  const [selected, setSelected] = useState<BassEvent | null>(null); const [selectedBars, setSelectedBars] = useState(new Set<number>())
  const [operation, setOperation] = useState<BassMutationOperation>('pitch_only'); const [busy, setBusy] = useState(false); const [playing, setPlaying] = useState(false); const [error, setError] = useState('')
  const [preserve, setPreserve] = useState<BassPreserveOptions>({ ...EMPTY_PRESERVE_OPTIONS })
  const [grooveContext, setGrooveContext] = useState<GrooveContext | null>(null); const [previewMode, setPreviewMode] = useState<BassPreviewMode>('bass_only')
  const [integrationMode, setIntegrationMode] = useState<IntegrationMode>('follow'); const [complexityBudget, setComplexityBudget] = useState(.55); const [bassShare, setBassShare] = useState(.60); const [jointResults, setJointResults] = useState<JointGenerationResult[]>([])
  const [preference, setPreference] = useState<BassPreferenceSummary | null>(null); const [pairSwapped, setPairSwapped] = useState(false); const [preferenceNotice, setPreferenceNotice] = useState('')
  const [registerLow, setRegisterLow] = useState(28); const [registerHigh, setRegisterHigh] = useState(60); const [registerCenter, setRegisterCenter] = useState(42); const [maxLeap, setMaxLeap] = useState(12)
  const [presetName, setPresetName] = useState(''); const [savedPatterns, setSavedPatterns] = useState<BassPattern[]>([]); const [savedPatternId, setSavedPatternId] = useState(''); const [persistenceNotice, setPersistenceNotice] = useState('')
  const [generationHistory, setGenerationHistory] = useState<BassGenerationRecord[]>([]); const [generationId, setGenerationId] = useState('')
  const [evaluationStatus, setEvaluationStatus] = useState('')
  const pattern = history.present

  useEffect(() => { bassApi.presets().then(data => { setPresets(data); setIntent(structuredClone(data.built_in.Supportive)) }).catch(() => setError('Bass APIに接続できません。Backendを起動してください。')) }, [])
  useEffect(() => { bassApi.preferences().then(setPreference).catch(() => undefined) }, [])
  useEffect(() => { bassApi.patterns().then(data => setSavedPatterns(Array.isArray(data) ? data : [])).catch(() => undefined) }, [])
  useEffect(() => { bassApi.generationHistory().then(data => setGenerationHistory(Array.isArray(data) ? data : [])).catch(() => undefined) }, [])
  useEffect(() => { setGrooveContext(null) }, [groovePattern?.pattern_id])
  useEffect(() => {
    setSelected(current => current && pattern ? pattern.events.find(event => event.event_id === current.event_id) ?? null : null)
  }, [pattern])
  useEffect(() => {
    if (!pattern) { setEvaluationStatus(''); return }
    if (pattern.analysis) return
    let active = true
    setEvaluationStatus('RE-EVALUATING EDIT…')
    const timer = window.setTimeout(() => {
      bassApi.evaluate(pattern).then(evaluated => {
        if (!active) return
        replaceHistory(evaluated)
        setCandidates(items => items.map(item => item.pattern_id === evaluated.pattern_id ? evaluated : item))
        setSelected(current => current ? evaluated.events.find(event => event.event_id === current.event_id) ?? null : null)
        setEvaluationStatus('ANALYSIS UPDATED')
      }).catch(cause => {
        if (!active) return
        setEvaluationStatus('')
        setError(`Bass evaluation failed: ${String(cause)}`)
      })
    }, 350)
    return () => { active = false; window.clearTimeout(timer) }
  }, [pattern, replaceHistory])
  const choosePreset = (name: string) => { setPreset(name); const found = presets?.user[name] ?? presets?.built_in[name]; if (found) setIntent(structuredClone(found)) }
  const setDNA = (key: keyof BassIntentDNA, value: number) => setIntent(current => current ? { ...current, target: { ...current.target, [key]: value } } : current)
  const generate = async () => { if (!intent) return; setBusy(true); setError(''); setEvaluationStatus(''); try {
    const joint = integrationMode !== 'follow'
    if (joint && !groovePattern) throw new Error('NEGOTIATE / CO-CREATEにはGroove候補が必要です。')
    const request: BassGenerateRequest = { bpm: joint ? groovePattern!.bpm : bpm, bars: joint ? groovePattern!.bars : bars, meter: joint ? groovePattern!.meter : METERS[meter], input_mode: inputMode, harmony, key: keyName || null, mode: scaleMode, intent, preset, seed, candidate_count: 4, register_limits: { lowest_midi_note: registerLow, highest_midi_note: registerHigh, preferred_center: registerCenter, preferred_zone: 'core', max_single_leap: maxLeap }, voice_policy: voicePolicy, groove_context: grooveContext }
    if (joint) {
      const response = await bassApi.jointGenerate(groovePattern!, request, integrationMode, complexityBudget, bassShare)
      const bassCandidates = response.candidates.map(candidate => candidate.bass_pattern)
      setJointResults(response.candidates); setCandidates(bassCandidates); history.commit(bassCandidates[0]); onGrooveUpdate?.(response.candidates[0].groove_pattern)
    } else {
      const response = await bassApi.generate(request); setPreference(response.preference_profile ?? null); setJointResults([]); setCandidates(response.candidates); history.commit(response.candidates[0])
    }
    bassApi.generationHistory().then(data => setGenerationHistory(Array.isArray(data) ? data : [])).catch(() => undefined)
    setPairSwapped(Math.random() < .5); setPreferenceNotice(''); setSelected(null); setSelectedBars(new Set())
  } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const commit = (next: BassPattern) => { const previousId = pattern?.pattern_id; history.commit(next); setEvaluationStatus(''); setJointResults([]); setCandidates(items => replaceCandidateRevision(items, next, previousId)); setSelected(current => current ? next.events.find(event => event.event_id === current.event_id) ?? null : null) }
  const mutate = async () => { if (!pattern) return; setBusy(true); try { const next = await bassApi.mutate(pattern, [...selectedBars], operation, preserve); commit(next); const recent = await bassApi.generationHistory(); setGenerationHistory(Array.isArray(recent) ? recent : []) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const refine = async () => { if (!pattern) return; setBusy(true); try { commit(await bassApi.refine(pattern)); const recent = await bassApi.generationHistory(); setGenerationHistory(Array.isArray(recent) ? recent : []) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const useGroove = async () => { if (!groovePattern) return; setBusy(true); setError(''); try { const context = await bassApi.contextFromGroove(groovePattern); setGrooveContext(context); setBpm(groovePattern.bpm); setBars(groovePattern.bars); const meterName = `${groovePattern.meter.numerator}/${groovePattern.meter.denominator}`; if (METERS[meterName]) setMeter(meterName) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const chooseCandidate = (candidate: BassPattern, index: number) => { history.commit(candidate); setEvaluationStatus(''); setSelected(null); if (jointResults[index]) onGrooveUpdate?.(jointResults[index].groove_pattern) }
  const measured = useMemo(() => pattern?.analysis ? [
    ['Root', pattern.analysis.atomic.root_ratio], ['Chord tones', pattern.analysis.atomic.chord_tone_ratio],
    ['Syncopation', pattern.analysis.atomic.syncopation_index], ['Occupancy', pattern.analysis.atomic.active_occupancy],
    ['Motion', pattern.analysis.dna.melodic_motion], ['Pulse support', pattern.analysis.dna.pulse_support],
    ['Resolution', pattern.analysis.dna.resolution_strength], ['Motif identity', pattern.analysis.dna.motif_identity],
  ] as [string, number][] : [], [pattern])
  const selectedJoint = useMemo(() => jointResults.find(result => result.bass_pattern.pattern_id === pattern?.pattern_id), [jointResults, pattern?.pattern_id])
  const comparisonPair = useMemo(() => candidates.length < 2 ? [] : pairSwapped ? [candidates[1], candidates[0]] : [candidates[0], candidates[1]], [candidates, pairSwapped])
  const recordPreference = async (position: 0 | 1) => { if (comparisonPair.length < 2) return; setPreferenceNotice('LEARNING…'); try { const next = await bassApi.prefer(comparisonPair[0], comparisonPair[1], position === 0 ? 'A' : 'B', comparisonPair.map(item => item.pattern_id)); setPreference(next); setPreferenceNotice(`LEARNED · ${next.comparisons} COMPARISONS`); setPairSwapped(value => !value) } catch (cause) { setError(String(cause)); setPreferenceNotice('') } }
  const strongestPreferences = useMemo(() => Object.entries(preference?.preferred_ranges ?? {}).sort((left, right) => left[1].uncertainty - right[1].uncertainty).slice(0, 3), [preference])
  const savePreset = async () => { const name = presetName.trim(); if (!intent || !name) return; setBusy(true); try { await bassApi.savePreset(name, intent); const next = await bassApi.presets(); setPresets(next); setPreset(name); setPresetName(''); setPersistenceNotice(`PRESET SAVED · ${name}`) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const saveCurrentPattern = async () => { if (!pattern) return; setBusy(true); try { await bassApi.savePattern(pattern); const next = await bassApi.patterns(); setSavedPatterns(next); setSavedPatternId(pattern.pattern_id); setPersistenceNotice(`PATTERN SAVED · ${pattern.name}`) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const applyPattern = (next: BassPattern) => { history.commit(next); setEvaluationStatus(''); setCandidates([next]); setJointResults([]); setIntent(structuredClone(next.intent)); setHarmony(harmonyText(next)); setBpm(next.bpm); setBars(next.bars); setVoicePolicy(next.voice_policy); setInputMode(next.input_mode); setGrooveContext(next.groove_context ?? null); const meterName = `${next.meter.numerator}/${next.meter.denominator}`; if (METERS[meterName]) setMeter(meterName); if (next.key_context) { setKeyName(pitchClassText(next.key_context.tonic)); setScaleMode(next.key_context.mode) } else { setKeyName('') }; setRegisterLow(next.register_limits.lowest_midi_note); setRegisterHigh(next.register_limits.highest_midi_note); setRegisterCenter(next.register_limits.preferred_center); setMaxLeap(next.register_limits.max_single_leap); setSelected(null); setSelectedBars(new Set()) }
  const loadSavedPattern = () => { const found = savedPatterns.find(item => item.pattern_id === savedPatternId); if (found) { applyPattern(found); setPersistenceNotice(`PATTERN LOADED · ${found.name}`) } }
  const deleteSavedPattern = async () => { if (!savedPatternId) return; setBusy(true); try { await bassApi.deletePattern(savedPatternId); setSavedPatterns(items => items.filter(item => item.pattern_id !== savedPatternId)); setSavedPatternId(''); setPersistenceNotice('PATTERN DELETED') } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const loadGeneration = async () => { if (!generationId) return; setBusy(true); try { const loaded = await bassApi.generationPattern(generationId); applyPattern(loaded); setPersistenceNotice(`HISTORY LOADED · ${loaded.name}`) } catch (cause) { setError(String(cause)) } finally { setBusy(false) } }
  const exportJson = async () => { if (!pattern) return; try { const exchange = await bassApi.exportPattern(pattern); const href = URL.createObjectURL(new Blob([JSON.stringify(exchange, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = href; link.download = `${pattern.name}.hbe.json`; link.click(); URL.revokeObjectURL(href) } catch (cause) { setError(String(cause)) } }
  const importJson = async (file: File | undefined) => { if (!file) return; setBusy(true); try { const exchange = JSON.parse(await file.text()) as BassPatternExchange; const imported = await bassApi.importPattern(exchange); applyPattern(imported); const next = await bassApi.patterns(); setSavedPatterns(next); setSavedPatternId(imported.pattern_id); setPersistenceNotice(`PATTERN IMPORTED · ${imported.name}`) } catch (cause) { setError(`JSON import failed: ${String(cause)}`) } finally { setBusy(false) } }

  return <div className="app-shell bass-app">
    <header><div className="brand-mark bass-brand">HBE</div><div><p className="eyebrow">HUMAN BASS ENGINE</p><h1>Anchor. Move. Approach. Resolve.</h1></div><div className="header-actions"><button className="ghost-button" disabled={!history.canUndo} onClick={history.undo}>↶ Undo</button><button className="ghost-button" disabled={!history.canRedo} onClick={history.redo}>↷ Redo</button></div></header>
    <main>
      <section className="control-panel panel bass-controls">
        <div className="harmony-control"><label>INPUT MODE<select value={inputMode} onChange={e => setInputMode(e.target.value as BassGenerateRequest['input_mode'])}><option value="chord_progression">Chord progression</option><option value="key_mode">Key / Mode</option><option value="root_guide">Root guide</option><option value="no_harmony">No harmony</option></select></label><label className="harmony-input">HARMONY / ROOT GUIDE<input value={harmony} onChange={e => setHarmony(e.target.value)} placeholder="Dm7 | G7 | Cmaj7 | A7" /></label><label>KEY<input value={keyName} onChange={e => setKeyName(e.target.value)} /></label><label>MODE<select value={scaleMode} onChange={e => setScaleMode(e.target.value as BassGenerateRequest['mode'])}>{modeOptions.map(mode => <option key={mode}>{mode.replaceAll('_', ' ')}</option>)}</select></label></div>
        {inputMode === 'chord_progression' && <HarmonyEditor value={harmony} bars={bars} onChange={setHarmony} />}
        <div className="transport-settings bass-transport"><label>BPM<input type="number" min="30" max="300" value={bpm} onChange={e => setBpm(Number(e.target.value))} /></label><label>BARS<select value={bars} onChange={e => setBars(Number(e.target.value))}>{[1, 2, 4, 8, 16, 32, 64].map(value => <option key={value}>{value}</option>)}</select></label><label>METER<select value={meter} onChange={e => setMeter(e.target.value)}>{METER_OPTIONS.map(value => <option key={value}>{value}</option>)}</select></label><label>SEED<input type="number" min="0" value={seed} onChange={e => setSeed(Number(e.target.value))} /></label><label>BEHAVIOUR<select value={preset} onChange={e => choosePreset(e.target.value)}>{[...new Set([...Object.keys(presets?.built_in ?? { Supportive: 1 }), ...Object.keys(presets?.user ?? {})])].map(name => <option key={name}>{name}</option>)}</select></label><label>VOICE POLICY<select value={voicePolicy} onChange={e => setVoicePolicy(e.target.value as BassVoicePolicy)}><option value="monophonic_retrigger">Monophonic retrigger</option><option value="monophonic_legato">Monophonic legato</option><option value="allow_overlap">Allow overlap</option></select></label><label>MIDI CHANNEL<input type="number" min="1" max="16" value={midiChannel + 1} onChange={e => setMidiChannel(Math.max(0, Math.min(15, Number(e.target.value) - 1)))} /></label></div>
        <div className="register-preset-controls"><fieldset><legend>REGISTER POLICY</legend><label>LOW<input aria-label="REGISTER LOW" type="number" min="0" max={registerHigh - 1} value={registerLow} onChange={e => { const value = Number(e.target.value); setRegisterLow(value); if (registerCenter < value) setRegisterCenter(value) }} /></label><label>CENTER<input aria-label="REGISTER CENTER" type="number" min={registerLow} max={registerHigh} value={registerCenter} onChange={e => setRegisterCenter(Number(e.target.value))} /></label><label>HIGH<input aria-label="REGISTER HIGH" type="number" min={registerLow + 1} max="127" value={registerHigh} onChange={e => { const value = Number(e.target.value); setRegisterHigh(value); if (registerCenter > value) setRegisterCenter(value) }} /></label><label>MAX LEAP<input aria-label="MAX LEAP" type="number" min="1" max="36" value={maxLeap} onChange={e => setMaxLeap(Number(e.target.value))} /></label></fieldset><div className="preset-save"><label>SAVE CURRENT INTENT<input aria-label="PRESET NAME" value={presetName} maxLength={80} onChange={e => setPresetName(e.target.value)} placeholder="My pocket" /></label><button className="secondary" disabled={!intent || !presetName.trim() || busy} onClick={savePreset}>SAVE PRESET</button></div></div>
        {intent && <><div className="knob-row bass-knobs">{macroControls.map(([label, key]) => <Knob key={key} label={label} value={intent.target[key]} onChange={value => setDNA(key, value)} />)}</div><label className="chromatic-switch"><input type="checkbox" checked={intent.allow_chromatic_notes} onChange={e => setIntent({ ...intent, allow_chromatic_notes: e.target.checked })} /> ALLOW CHROMATIC NOTES</label></>}
        <div className="groove-link"><button className={grooveContext ? 'secondary linked' : 'secondary'} disabled={!groovePattern || busy} onClick={useGroove}>{grooveContext ? '✓ GROOVE CONTEXT LINKED' : 'LINK CURRENT GROOVE'}</button><span>{groovePattern ? `${groovePattern.name} · ${groovePattern.events.filter(event => event.instrument === 'kick').length} kicks` : 'Generate or select a Groove candidate first'}</span><label>MODE<select value={integrationMode} onChange={e => setIntegrationMode(e.target.value as IntegrationMode)}><option value="follow">FOLLOW · Drums fixed</option><option value="negotiate">NEGOTIATE · Small Kick repair</option><option value="co_create">CO-CREATE · Joint Kick + Bass</option></select></label><label>COMPLEXITY<input type="range" min="0" max="1" step=".01" value={complexityBudget} onChange={e => setComplexityBudget(Number(e.target.value))} /><b>{Math.round(complexityBudget * 100)}</b></label><label>BASS SHARE<input type="range" min="0" max="1" step=".01" value={bassShare} onChange={e => setBassShare(Number(e.target.value))} /><b>{Math.round(bassShare * 100)}</b></label></div>
        <PreserveOptions value={preserve} onChange={setPreserve} />
        {pattern && <IntentLocks value={pattern.intent_locks} onChange={intentLocks => commit({ ...pattern, intent_locks: intentLocks })} />}
        <div className="primary-actions"><button className="generate" disabled={busy || !intent} onClick={generate}>{busy ? 'COMPOSING…' : 'GENERATE BASS'}</button><select className="operation preview-mode" value={previewMode} onChange={e => setPreviewMode(e.target.value as BassPreviewMode)}><option value="bass_only">Bass Only</option><option value="bass_click">Bass + Click</option><option value="bass_kick">Bass + Kick</option><option value="bass_chords">Bass + Chords</option><option value="bass_kick_chords">Bass + Kick + Chords</option></select><button className={playing ? 'play active' : 'play'} disabled={!pattern} onClick={() => pattern && toggleBassPreview(pattern, previewMode, setPlaying)}>{playing ? '■ STOP' : '▶ PREVIEW'}</button><button className="secondary" disabled={!pattern || busy} onClick={refine}>REFINE CURRENT</button><select className="operation" value={operation} onChange={e => setOperation(e.target.value as BassMutationOperation)}>{mutations.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select><button className="secondary" disabled={!pattern || busy} onClick={mutate}>REGENERATE {selectedBars.size ? `${selectedBars.size} BAR` : 'ALL'}</button><button className="secondary" disabled={!pattern} onClick={() => pattern && bassApi.midi(pattern, midiChannel)}>↓ MIDI</button></div>
        <div className="asset-actions"><button className="secondary" disabled={!pattern || busy} onClick={saveCurrentPattern}>SAVE PATTERN</button><select aria-label="SAVED PATTERNS" value={savedPatternId} onChange={e => setSavedPatternId(e.target.value)}><option value="">SAVED PATTERNS</option>{savedPatterns.map(item => <option key={item.pattern_id} value={item.pattern_id}>{item.name}</option>)}</select><button className="secondary" disabled={!savedPatternId || busy} onClick={loadSavedPattern}>LOAD</button><button className="secondary" disabled={!savedPatternId || busy} onClick={deleteSavedPattern}>DELETE</button><button className="secondary" disabled={!pattern} onClick={exportJson}>↓ JSON</button><label className="file-button">IMPORT JSON<input type="file" accept=".json,application/json" onChange={e => importJson(e.target.files?.[0])} /></label>{persistenceNotice && <span>{persistenceNotice}</span>}</div>
        <div className="generation-history"><label>GENERATION HISTORY<select aria-label="GENERATION HISTORY" value={generationId} onChange={e => setGenerationId(e.target.value)}><option value="">RECENT GENERATIONS</option>{generationHistory.map(item => <option key={item.pattern_id} value={item.pattern_id}>{item.name} · {item.pattern_id.slice(-8)}</option>)}</select></label><button className="secondary" disabled={!generationId || busy} onClick={loadGeneration}>LOAD HISTORY</button><span>{generationHistory.length} retained</span></div>
        {error && <p className="error">{error}</p>}
        {evaluationStatus && <p className="evaluation-status">{evaluationStatus}</p>}
      </section>
      {candidates.length > 0 && <><section className="candidates bass-candidates">{candidates.map((candidate, index) => { const joint = jointResults[index]; return <button key={candidate.pattern_id} className={pattern?.pattern_id === candidate.pattern_id ? 'candidate active' : 'candidate'} onClick={() => chooseCandidate(candidate, index)}><b>{String.fromCharCode(65 + index)}</b><span>{score(candidate.analysis?.listener.predicted_bass_groove.value)} bass groove</span><small>{joint ? `${Math.round(joint.joint_fitness * 100)} joint · ${joint.changes?.length ?? 0} change` : `${candidate.events.length} notes`}</small></button> })}{comparisonPair.length === 2 && <div className="ab-choice"><span>Which supports the song?<small>ORDER RANDOMIZED</small></span>{comparisonPair.map((candidate, position) => <button key={candidate.pattern_id} onClick={() => recordPreference(position as 0 | 1)}>{String.fromCharCode(65 + candidates.indexOf(candidate))}</button>)}</div>}</section><section className="preference-profile panel"><div><p className="eyebrow">PERSONAL TASTE · PAIRWISE LEARNING</p><strong>{preference?.comparisons ?? 0}</strong><span>comparisons · {score(preference?.personal_weight)}% personal blend</span>{preferenceNotice && <small>{preferenceNotice}</small>}</div><div className="preference-ranges">{strongestPreferences.length ? strongestPreferences.map(([name, range]) => <div key={name}><span>{name.replaceAll('_', ' ')}</span><i><em style={{ left: `${range.low * 100}%`, width: `${(range.high - range.low) * 100}%` }} /><b style={{ left: `${range.mean * 100}%` }} /></i><small>±{Math.round(range.uncertainty * 100)} uncertainty</small></div>) : <p>Choose between two candidates to start learning a preferred range.</p>}</div></section></>}
      {jointResults.length > 0 && pattern && <section className="panel interaction-trace"><p className="eyebrow">INTERACTION CORE · {integrationMode.toUpperCase().replace('_', '-')}</p><div className="interaction-summary"><span>Joint fitness <b>{Math.round((selectedJoint?.joint_fitness ?? 0) * 100)}</b></span><span>Complexity fit <b>{Math.round((selectedJoint?.complexity_fit ?? 0) * 100)}</b></span><span>Change cost <b>{Math.round((selectedJoint?.change_cost ?? 0) * 100)}</b></span></div><ul className="interaction-changes" aria-label="Joint changes">{selectedJoint?.changes?.length ? selectedJoint.changes.map((change, index) => <li key={`${change.event_id ?? change.target}-${index}`}><b>{change.target.replaceAll('_', ' ')}</b><span>{change.operation.replaceAll('_', ' ')}</span>{change.tick_before !== null && change.tick_before !== undefined && <small>{change.tick_before} → {change.tick_after ?? '—'} ticks</small>}<em>{change.reason}</em></li>) : <li className="unchanged"><b>groove</b><em>Drums kept fixed</em></li>}</ul></section>}
      {pattern && <><BassPianoRoll pattern={pattern} selected={selected} selectedBars={selectedBars} onSelect={setSelected} onBars={setSelectedBars} onChange={commit} /><section className="panel bass-analysis"><div><p className="eyebrow">VIRTUAL LISTENER · PROXY</p><strong>{score(pattern.analysis?.listener.predicted_bass_groove.value)}</strong><span>Predicted Bass Groove</span><small>{pattern.analysis?.listener.kick_bass_quality.applicable ? `${score(pattern.analysis.listener.kick_bass_quality.value)} kick relationship` : 'Kick relationship: not applicable'}</small></div><div className="dna-table">{measured.map(([label, value]) => <div key={label}><span>{label}</span><i><em style={{ width: `${Math.min(100, value * 100)}%` }} /></i><b>{score(value)}</b></div>)}</div><p className="model-note">Target and measured values are separate. Listener scores are explainable structural proxies, not physiological measurements.</p></section></>}
    </main><footer><span>BASS ENGINE 0.1 · PPQ 960 · PCG64DXSM</span><span>Harmony + motion + body + space + memory</span></footer>
  </div>
}
