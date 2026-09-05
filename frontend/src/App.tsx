import { useEffect, useMemo, useRef, useState } from 'react'
import './quick.css'
import './advanced.css'
import { ADVANCED_DNA_GROUPS, advancedTabs, listenerMetrics } from './advancedControls'
import type { AdvancedTab } from './advancedControls'
import { api } from './api/client'
import { EventInspector } from './components/EventInspector'
import { IntentCapturePanel } from './components/IntentCapturePanel'
import { BassApp } from './components/BassApp'
import { KeyboardApp } from './components/KeyboardApp'
import { BlindEvaluationPanel } from './components/BlindEvaluationPanel'
import { EmbodiedFeedbackPanel } from './components/EmbodiedFeedbackPanel'
import { DetroitSoulControl } from './components/DetroitSoulControl'
import { Knob } from './components/Knob'
import { ListenerPanel } from './components/ListenerPanel'
import { QuickComposer } from './components/QuickComposer'
import { StepGrid } from './components/StepGrid'
import { TasteTrainer } from './components/TasteTrainer'
import { DRUM_SOUND_OPTIONS, type DrumSoundId } from './audio/drumKitProfile'
import { stopActivePreview } from './audio/previewCoordinator'
import { useHistory } from './hooks/useHistory'
import type { BassPattern, DetroitSoulSettings, GenerateRequest, GrooveDNA, GrooveEvent, GrooveIntent, GroovePattern, GroovePreferenceSummary, Instrument, KeyboardPattern, PresetsResponse } from './types/generated'
import { DEFAULT_DETROIT_SOUL } from './utils/detroitSoul'
import { METERS, METER_OPTIONS } from './utils/meters'
import { anonymousSessionId } from './utils/anonymousSession'
const baseDNA: GrooveDNA = { pulse_stability:.75,beat_salience:.75,syncopation:.45,anticipation:.35,omission:.2,density:.5,repetition:.65,variation:.35,interlock:.6,swing:.15,microtiming:.3,velocity_contrast:.45,duration_contrast:.3,low_end_anchor:.7,metric_ambiguity:.2,ghost_density:.25,surprise:.35,recovery_strength:.7,motor_affordance:.75,hypnotic:.35,phrase_development:.4 }
const baseIntent: GrooveIntent = { target_dna: baseDNA, tolerance: { default:.12,per_dimension:{} }, priorities: { weights:{ pulse_stability:1.2,syncopation:1,density:.8,variation:.7,interlock:1,surprise:.8 } }, movement_target:'bounce', embodied:{challenge:.5,renewal:.5,timing_coherence:.7,low_end_motion:.6,meter_familiarity:.5,style_familiarity:.5} }
const controlMap: [string, keyof GrooveDNA][] = [['安定感','pulse_stability'],['シンコペーション','syncopation'],['意外性','surprise'],['ノリ','motor_affordance'],['人間味','microtiming'],['変化','variation'],['複雑さ','metric_ambiguity'],['密度','density']]
const resolutions = [[2,'8分'],[3,'8分3連'],[4,'16分'],[6,'16分3連'],[8,'32分']] as const
const supportsResolution = (meterName: string, value: number) => { const current=METERS[meterName]; const barTicks=current.numerator*960*4/current.denominator; return Number.isInteger(barTicks/(960/value)) }
const pitches: Record<Instrument, number> = { kick:36,snare:38,closed_hat:42,open_hat:46,percussion:39,bass:36 }
type RenderProfile = DrumSoundId

export function GrooveApp({ onPatternChange, externalPattern }: { onPatternChange?: (pattern: GroovePattern | null) => void, externalPattern?: GroovePattern | null }) {
  const [presets, setPresets] = useState<PresetsResponse | null>(null)
  const [intent, setIntent] = useState<GrooveIntent>(baseIntent); const [preset, setPreset] = useState('Balanced')
  const [bpm, setBpm] = useState(100); const [bars, setBars] = useState(4); const [meter, setMeter] = useState('4/4'); const [resolution, setResolution] = useState(4); const [seed, setSeed] = useState(42)
  const [performanceMode, setPerformanceMode] = useState<'auto'|'rule'>('auto')
  const [detroitSoul, setDetroitSoul] = useState<DetroitSoulSettings>(DEFAULT_DETROIT_SOUL)
  const [renderProfile, setRenderProfile] = useState<RenderProfile>('studio-tight-v1')
  const [candidates, setCandidates] = useState<GroovePattern[]>([]); const history = useHistory<GroovePattern>(null)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [playing, setPlaying] = useState(false)
  const [selectedBars, setSelectedBars] = useState(new Set<number>()); const [selectedInstrument, setSelectedInstrument] = useState<Instrument | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<GrooveEvent | null>(null); const [advanced, setAdvanced] = useState<AdvancedTab>('拍の安定')
  const [preference, setPreference] = useState<GroovePreferenceSummary | null>(null)
  const evaluationSequence = useRef(0)
  const detroitPatternId = useRef<string | null>(null)
  const latestExternalPattern = useRef<GroovePattern | null | undefined>(externalPattern)
  const pattern = history.present
  const commitHistory = history.commit
  useEffect(() => { onPatternChange?.(pattern) }, [pattern, onPatternChange])
  useEffect(() => {
    latestExternalPattern.current = externalPattern
    if (!externalPattern || externalPattern.pattern_id === pattern?.pattern_id) return
    evaluationSequence.current += 1
    commitHistory(externalPattern)
    setBpm(externalPattern.bpm)
    setBars(externalPattern.bars)
    const meterName = `${externalPattern.meter.numerator}/${externalPattern.meter.denominator}`
    if (METERS[meterName]) setMeter(meterName)
    if (supportsResolution(meterName, externalPattern.meter.subdivisions_per_quarter)) {
      setResolution(externalPattern.meter.subdivisions_per_quarter)
    }
    setIntent(structuredClone(externalPattern.intent))
    setPreset(externalPattern.metadata.style)
    setPerformanceMode(externalPattern.metadata.performance_model === 'rule-pocket-v1' ? 'rule' : 'auto')
    setDetroitSoul(structuredClone(externalPattern.metadata.detroit_soul ?? DEFAULT_DETROIT_SOUL))
    const profile = externalPattern.metadata.render_profile
    if (DRUM_SOUND_OPTIONS.some(option => option.id === profile)) setRenderProfile(profile as RenderProfile)
  }, [externalPattern, pattern?.pattern_id, commitHistory])
  useEffect(() => {
    const profile = pattern?.metadata.render_profile
    if (DRUM_SOUND_OPTIONS.some(option => option.id === profile)) setRenderProfile(profile as RenderProfile)
  }, [pattern?.metadata.render_profile])
  useEffect(() => {
    if (!pattern || detroitPatternId.current === pattern.pattern_id) return
    detroitPatternId.current = pattern.pattern_id
    setDetroitSoul(structuredClone(pattern.metadata.detroit_soul ?? DEFAULT_DETROIT_SOUL))
  }, [pattern])
  useEffect(() => { api.presets().then(data => { setPresets(data); if (!latestExternalPattern.current) setIntent(data.built_in.Balanced) }).catch(() => setError('Backendに接続できません。起動手順を確認してください。')) }, [])
  useEffect(() => {
    let active = true
    api.preferences(preset).then(profile => { if (active) setPreference(profile) }).catch(() => undefined)
    return () => { active = false }
  }, [preset])
  useEffect(() => { setCandidates([]) }, [preset])
  const generate = async () => { const sequence = ++evaluationSequence.current; setBusy(true); setError(''); try {
    const nextSeed = seed >= 2_147_483_647 ? 0 : seed + 1
    setSeed(nextSeed)
    const request: GenerateRequest = { bpm,bars,meter:{...METERS[meter],subdivisions_per_quarter:resolution},intent,preset,seed:nextSeed,mode:'preview',performance_mode:performanceMode,render_profile:renderProfile,detroit_soul:detroitSoul,candidate_count:4,candidate_strategy:'quality', anonymous_session_id:anonymousSessionId() }
    const response = await api.generate(request); if (sequence !== evaluationSequence.current) return; setCandidates(response.candidates); setPreference(response.preference_profile); detroitPatternId.current=response.candidates[0].pattern_id; history.commit(response.candidates[0]); setSelectedBars(new Set()); setSelectedEvent(null)
  } catch (e) { setError(String(e)) } finally { setBusy(false) } }
  const choosePreset = (name: string) => { setPreset(name); const found = presets?.built_in[name] ?? presets?.user[name]; if (found) setIntent(structuredClone(found)) }
  const applyCapturedIntent = (next: GrooveIntent, options?: { bpm?: number, style?: string, notice?: string }) => { setIntent(next); if(options?.bpm)setBpm(Math.round(options.bpm)); if(options?.style)setPreset(options.style) }
  const setDNA = (key: keyof GrooveDNA, value: number) => setIntent(valueNow => ({ ...valueNow, target_dna:{ ...valueNow.target_dna,[key]:value } }))
  const selectCandidate = (candidate: GroovePattern) => { evaluationSequence.current += 1; history.commit(candidate); setSelectedEvent(null) }
  const updateAndEvaluate = async (next: GroovePattern) => { const sequence = ++evaluationSequence.current; history.commit(next); try { const measured = await api.evaluate(next); if (sequence === evaluationSequence.current) history.replace(measured) } catch { /* local edit remains usable */ } }
  const chooseRenderProfile = (profile: RenderProfile) => {
    setRenderProfile(profile)
    if (pattern && pattern.metadata.render_profile !== profile) {
      void updateAndEvaluate({
        ...pattern,
        metadata: { ...pattern.metadata, render_profile: profile },
        analysis: null,
      })
    }
  }
  const toggleStep = (instrument: Instrument, tick: number) => { if (!pattern) return
    const existing = pattern.events.find(e => e.instrument===instrument && e.grid_tick===tick)
    const events = existing ? pattern.events.filter(e => e.event_id!==existing.event_id) : [...pattern.events, { event_id:crypto.randomUUID(),instrument,grid_tick:tick,structural_offset_tick:0,micro_offset_us:0,duration_tick:180,velocity:instrument==='closed_hat'?72:92,pitch:pitches[instrument],primary_role:tick%960===0?'anchor':'decoration',role_tags:[],accent:tick%960===0?.8:.45,timbre_variant:null,duration_style:'medium',choke_group:instrument.includes('hat')?'hihat':null,locked:false,origin:'user_edited' } as GrooveEvent]
    void updateAndEvaluate({ ...pattern,events:events.sort((a,b)=>a.grid_tick-b.grid_tick),analysis:null })
  }
  const updateEvent = (event: GrooveEvent) => { if (!pattern) return; const edited = { ...event, origin: 'user_edited' as const }; setSelectedEvent(edited); void updateAndEvaluate({ ...pattern,events:pattern.events.map(item=>item.event_id===edited.event_id?edited:item),analysis:null }) }
  const lockInstrument = (instrument: Instrument) => { if (!pattern) return; evaluationSequence.current += 1; const locks=pattern.instrument_locks.includes(instrument)?pattern.instrument_locks.filter(x=>x!==instrument):[...pattern.instrument_locks,instrument]; history.commit({ ...pattern,instrument_locks:locks }) }
  const regenerate = async () => { if (!pattern) return; const sequence = ++evaluationSequence.current; setBusy(true); try { const next=await api.mutate(pattern,selectedInstrument?[selectedInstrument]:[],[...selectedBars]); if (sequence !== evaluationSequence.current) return; history.commit(next); setCandidates(items=>[next,...items.slice(1)]); setSelectedEvent(null) } catch(e){setError(String(e))} finally {setBusy(false)} }
  const undo = () => { evaluationSequence.current += 1; history.undo() }
  const redo = () => { evaluationSequence.current += 1; history.redo() }
  const activeDNAGroup = advanced === 'リスナー' ? null : ADVANCED_DNA_GROUPS[advanced]
  const evaluationRequest = useMemo<GenerateRequest>(() => ({ bpm,bars,meter:{...METERS[meter],subdivisions_per_quarter:resolution},intent,preset,seed,mode:'preview',performance_mode:'auto',render_profile:renderProfile,detroit_soul:detroitSoul,candidate_count:1,candidate_strategy:'quality', anonymous_session_id:anonymousSessionId() }), [bpm,bars,meter,resolution,intent,preset,seed,renderProfile,detroitSoul])
  return <div className="app-shell">
    <header><div className="brand-mark">HGE</div><div><p className="eyebrow">HUMAN GROOVE ENGINE</p><h1>少しの揺らぎが、Grooveを生む。</h1></div><div className="header-actions"><button className="ghost-button" disabled={!history.canUndo} onClick={undo}>↶ 戻す</button><button className="ghost-button" disabled={!history.canRedo} onClick={redo}>↷ やり直す</button></div></header>
    <main>
      <section className="control-panel panel">
        <div className="transport-settings">
          <label>BPM<input type="number" min="30" max="300" value={bpm} onChange={e=>setBpm(Number(e.target.value))}/></label>
          <label>小節数<select value={bars} onChange={e=>setBars(Number(e.target.value))}>{[1,2,4,8,12,16,32,64].map(x=><option key={x}>{x}</option>)}</select></label>
          <label>拍子<select value={meter} onChange={e=>{const next=e.target.value;setMeter(next);if(!supportsResolution(next,resolution))setResolution(4)}}>{METER_OPTIONS.map(x=><option key={x}>{x}</option>)}</select></label>
          <label>グリッド<select value={resolution} onChange={e=>setResolution(Number(e.target.value))}>{resolutions.map(([value,label])=><option key={value} value={value} disabled={!supportsResolution(meter,value)}>{label}</option>)}</select></label>
          <label>ランダム値<input type="number" min="0" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label>
          <label>スタイル<select value={preset} onChange={e=>choosePreset(e.target.value)}>{[...new Set([...Object.keys(presets?.built_in??{Balanced:1}),...Object.keys(presets?.user??{})])].map(x=><option key={x}>{x}</option>)}</select></label>
          <label>演奏感<select value={performanceMode} onChange={e=>setPerformanceMode(e.target.value as 'auto'|'rule')}><option value="auto">学習済みの人間演奏</option><option value="rule">精密なルール</option></select></label>
          <label>ドラム音色<select value={renderProfile} onChange={e=>chooseRenderProfile(e.target.value as RenderProfile)}>{DRUM_SOUND_OPTIONS.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        </div>
        <DetroitSoulControl value={detroitSoul} onChange={setDetroitSoul}/>
        <div className="knob-row">{controlMap.map(([label,key])=><Knob key={key} label={label} value={intent.target_dna[key]} onChange={value=>setDNA(key,value)}/>)}</div>
        <div className="primary-actions"><button className="generate" disabled={busy} onClick={generate}>{busy?'作成中…':'Grooveを作成'}</button><button disabled={!pattern} className={playing?'play active':'play'} onClick={()=>{ if (pattern) void import('./audio/preview').then(module=>module.togglePreview(pattern,setPlaying)).catch(cause=>setError(`音声を開始できません: ${String(cause)}`)) }}>{playing?'■ 停止':'▶ 再生'}</button><button disabled={!pattern||busy} className="secondary" onClick={regenerate}>↻ 選択範囲を再作成</button><button disabled={!pattern} className="secondary" onClick={()=>pattern&&api.midi(pattern)}>↓ MIDI</button></div>
        {error&&<p className="error">{error}</p>}
      </section>
      <IntentCapturePanel intent={intent} onApply={applyCapturedIntent}/>
      <BlindEvaluationPanel generation={evaluationRequest}/>
      {pattern&&<EmbodiedFeedbackPanel pattern={pattern} onTempoSuggested={value=>setBpm(Math.round(value))}/>}
      {candidates.length>0&&<><section className="candidates">{candidates.map((item,index)=><button className={pattern?.pattern_id===item.pattern_id?'candidate active':'candidate'} key={item.pattern_id} onClick={()=>selectCandidate(item)}><b>{String.fromCharCode(65+index)}</b><span>試聴候補</span><small>{item.metadata.preference_guided?'好み探索 · ':''}{item.events.length} events</small></button>)}</section><TasteTrainer key={candidates.map(item=>item.pattern_id).join('|')} candidates={candidates} preference={preference} onPreference={setPreference}/></>}
      {pattern&&<div className="workspace"><div className="pattern-column"><p className="performance-badge">演奏感 · {pattern.metadata.performance_model==='gmd-performance-v1'?'人間の演奏 32万打点から学習':'精密なルール'}</p><StepGrid pattern={pattern} selectedBars={selectedBars} selectedInstrument={selectedInstrument} onToggle={toggleStep} onSelectEvent={setSelectedEvent} onSelectBar={bar=>setSelectedBars(current=>{const next=new Set(current);if(next.has(bar))next.delete(bar);else next.add(bar);return next})} onSelectInstrument={setSelectedInstrument} onLockInstrument={lockInstrument}/>{selectedEvent&&<EventInspector event={selectedEvent} onChange={updateEvent} onClose={()=>setSelectedEvent(null)}/>}</div><ListenerPanel analysis={pattern.analysis}/></div>}
      {pattern&&<section className="advanced panel"><div className="tabs">{advancedTabs.map(tab=><button className={advanced===tab?'active':''} key={tab} onClick={()=>setAdvanced(tab)}>{tab}</button>)}</div><div className="advanced-body"><div><p className="eyebrow">{advanced} / {activeDNAGroup?'目標 ↔ 実測':'仮想リスナー'}</p><h2>{activeDNAGroup?'狙いを細部まで形にする。':'機械の評価を、判断材料の一つに。'}</h2><p className="muted">{activeDNAGroup?.description??'これらは説明可能な代理指標です。人の好みや身体反応を断定するものではありません。'}</p></div><div className="advanced-controls">{activeDNAGroup?<><div className="advanced-knobs">{activeDNAGroup.controls.map(([label,key])=><Knob key={key} label={label} value={intent.target_dna[key]} onChange={value=>setDNA(key,value)}/>)}</div>{pattern.analysis?<div className="dna-table">{activeDNAGroup.controls.map(([label,key])=><div key={key}><span>{label}</span><i><em style={{width:`${pattern.analysis!.measured_dna[key]*100}%`}}/></i><b>{Math.round(intent.target_dna[key]*100)} → {Math.round(pattern.analysis!.measured_dna[key]*100)}</b></div>)}</div>:<p className="muted">編集内容を再解析しています…</p>}</>:pattern.analysis?<div className="dna-table listener-table">{listenerMetrics.map(([label,key])=>{const value=pattern.analysis!.listener[key];return typeof value==='number'?<div key={key}><span>{label}</span><i><em style={{width:`${value*100}%`}}/></i><b>{Math.round(value*100)}</b></div>:null})}</div>:<p className="muted">編集内容を再解析しています…</p>}</div></div></section>}
    </main><footer><span>ENGINE 0.11 · 21-DIMENSION QUALITY AUDIT</span><span>Stable pulse → controlled violation → recovery</span></footer>
  </div>
}

export default function App() {
  const [engine, setEngine] = useState<'groove' | 'bass' | 'keyboard'>('groove')
  const [mode, setMode] = useState<'easy' | 'detail'>('detail')
  const [sharedGroove, setSharedGroove] = useState<GroovePattern | null>(null)
  const [sharedBass, setSharedBass] = useState<BassPattern | null>(null)
  const [sharedKeyboard, setSharedKeyboard] = useState<KeyboardPattern | null>(null)
  const [mixPlaying, setMixPlaying] = useState(false)
  const [mixError, setMixError] = useState('')
  const changeMode = (next: 'easy' | 'detail') => {
    stopActivePreview(engine)
    stopActivePreview('mix')
    setMixPlaying(false)
    setMode(next)
  }
  const changeEngine = (next: 'groove' | 'bass' | 'keyboard') => {
    stopActivePreview(engine)
    setEngine(next)
  }
  return <>
    <nav className="workspace-switch" aria-label="Workspace selection">
    <div className="mode-switch" aria-label="モード選択"><button aria-pressed={mode === 'easy'} className={mode === 'easy' ? 'active' : ''} onClick={() => changeMode('easy')}>かんたん</button><button aria-pressed={mode === 'detail'} className={mode === 'detail' ? 'active' : ''} onClick={() => changeMode('detail')}>詳細</button></div>
      {mode === 'detail' && <div className="engine-tabs"><button aria-pressed={engine === 'groove'} className={engine === 'groove' ? 'active' : ''} onClick={() => changeEngine('groove')}>GROOVE</button><button aria-pressed={engine === 'bass'} className={engine === 'bass' ? 'active' : ''} onClick={() => changeEngine('bass')}>BASS</button><button aria-pressed={engine === 'keyboard'} className={engine === 'keyboard' ? 'active' : ''} onClick={() => changeEngine('keyboard')}>KEYS</button></div>}
    </nav>
    {mode === 'detail' && sharedGroove && sharedBass && <aside className="mix-transport" aria-label="Groove、Bass、Keysの同時再生"><span>{sharedKeyboard ? 'Groove + Bass + Keys' : 'Groove + Bass'}</span><button className={mixPlaying ? 'play active' : 'play'} onClick={() => { setMixError(''); void import('./audio/mixPreview').then(module=>module.toggleMixPreview(sharedGroove,sharedBass,sharedKeyboard,setMixPlaying)).catch(cause => setMixError(`音声を開始できません: ${String(cause)}`)) }}>{mixPlaying ? '■ 停止' : '▶ 再生'}</button>{mixError && <small role="alert">{mixError}</small>}</aside>}
    {mode === 'easy' ? <QuickComposer groove={sharedGroove} bass={sharedBass} keyboard={sharedKeyboard} onReady={(groove, bass, keyboard) => { setSharedGroove(groove); setSharedBass(bass); setSharedKeyboard(keyboard) }} onOpenDetails={() => setMode('detail')} /> : <>
      <div hidden={engine !== 'groove'}><GrooveApp onPatternChange={setSharedGroove} externalPattern={sharedGroove} /></div>
      <div hidden={engine !== 'bass'}><BassApp groovePattern={sharedGroove} externalPattern={sharedBass} onGrooveUpdate={setSharedGroove} onBassPatternChange={setSharedBass} /></div>
      <div hidden={engine !== 'keyboard'}><KeyboardApp groovePattern={sharedGroove} bassPattern={sharedBass} externalPattern={sharedKeyboard} onKeyboardPatternChange={setSharedKeyboard} /></div>
    </>}
  </>
}
