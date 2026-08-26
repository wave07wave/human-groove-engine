import { useEffect, useMemo, useState } from 'react'
import { api } from './api/client'
import { togglePreview } from './audio/preview'
import { EventInspector } from './components/EventInspector'
import { BassApp } from './components/BassApp'
import { Knob } from './components/Knob'
import { ListenerPanel } from './components/ListenerPanel'
import { StepGrid } from './components/StepGrid'
import { useHistory } from './hooks/useHistory'
import type { GenerateRequest, GrooveDNA, GrooveEvent, GrooveIntent, GroovePattern, Instrument, PresetsResponse } from './types/generated'
import { METERS, METER_OPTIONS } from './utils/meters'
const baseDNA: GrooveDNA = { pulse_stability:.75,beat_salience:.75,syncopation:.45,anticipation:.35,omission:.2,density:.5,repetition:.65,variation:.35,interlock:.6,swing:.15,microtiming:.3,velocity_contrast:.45,duration_contrast:.3,low_end_anchor:.7,metric_ambiguity:.2,ghost_density:.25,surprise:.35,recovery_strength:.7,motor_affordance:.75,hypnotic:.35,phrase_development:.4 }
const baseIntent: GrooveIntent = { target_dna: baseDNA, tolerance: { default:.12,per_dimension:{} }, priorities: { weights:{ pulse_stability:1.2,syncopation:1,density:.8,variation:.7,interlock:1,surprise:.8 } }, movement_target:'bounce' }
const controlMap: [string, keyof GrooveDNA][] = [['Stability','pulse_stability'],['Syncopation','syncopation'],['Surprise','surprise'],['Bounce','motor_affordance'],['Human feel','microtiming'],['Variation','variation'],['Complexity','metric_ambiguity'],['Density','density']]
const pitches: Record<Instrument, number> = { kick:36,snare:38,closed_hat:42,open_hat:46,percussion:39,bass:36 }

function GrooveApp({ onPatternChange, externalPattern }: { onPatternChange?: (pattern: GroovePattern | null) => void, externalPattern?: GroovePattern | null }) {
  const [presets, setPresets] = useState<PresetsResponse | null>(null)
  const [intent, setIntent] = useState<GrooveIntent>(baseIntent); const [preset, setPreset] = useState('Balanced')
  const [bpm, setBpm] = useState(100); const [bars, setBars] = useState(4); const [meter, setMeter] = useState('4/4'); const [seed, setSeed] = useState(42)
  const [candidates, setCandidates] = useState<GroovePattern[]>([]); const history = useHistory<GroovePattern>(null)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [playing, setPlaying] = useState(false)
  const [selectedBars, setSelectedBars] = useState(new Set<number>()); const [selectedInstrument, setSelectedInstrument] = useState<Instrument | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<GrooveEvent | null>(null); const [advanced, setAdvanced] = useState('Pulse')
  const pattern = history.present
  useEffect(() => { onPatternChange?.(pattern) }, [pattern, onPatternChange])
  useEffect(() => { if (externalPattern && externalPattern.pattern_id !== pattern?.pattern_id) history.commit(externalPattern) }, [externalPattern, pattern?.pattern_id, history])
  useEffect(() => { api.presets().then(data => { setPresets(data); setIntent(data.built_in.Balanced) }).catch(() => setError('Backendに接続できません。起動手順を確認してください。')) }, [])
  const generate = async () => { setBusy(true); setError(''); try {
    const request: GenerateRequest = { bpm,bars,meter:METERS[meter],intent,preset,seed,mode:'preview',candidate_count:4 }
    const response = await api.generate(request); setCandidates(response.candidates); history.commit(response.candidates[0]); setSelectedBars(new Set()); setSelectedEvent(null)
  } catch (e) { setError(String(e)) } finally { setBusy(false) } }
  const choosePreset = (name: string) => { setPreset(name); const found = presets?.built_in[name] ?? presets?.user[name]; if (found) setIntent(structuredClone(found)) }
  const setDNA = (key: keyof GrooveDNA, value: number) => setIntent(valueNow => ({ ...valueNow, target_dna:{ ...valueNow.target_dna,[key]:value } }))
  const selectCandidate = (candidate: GroovePattern) => { history.commit(candidate); setSelectedEvent(null) }
  const updateAndEvaluate = async (next: GroovePattern) => { history.commit(next); try { const measured = await api.evaluate(next); history.commit(measured) } catch { /* local edit remains usable */ } }
  const toggleStep = (instrument: Instrument, tick: number) => { if (!pattern) return
    const existing = pattern.events.find(e => e.instrument===instrument && e.grid_tick===tick)
    const events = existing ? pattern.events.filter(e => e.event_id!==existing.event_id) : [...pattern.events, { event_id:crypto.randomUUID(),instrument,grid_tick:tick,structural_offset_tick:0,micro_offset_us:0,duration_tick:180,velocity:instrument==='closed_hat'?72:92,pitch:pitches[instrument],primary_role:tick%960===0?'anchor':'decoration',role_tags:[],accent:tick%960===0?.8:.45,timbre_variant:null,duration_style:'medium',choke_group:instrument.includes('hat')?'hihat':null,locked:false,origin:'user_edited' } as GrooveEvent]
    void updateAndEvaluate({ ...pattern,events:events.sort((a,b)=>a.grid_tick-b.grid_tick),analysis:null })
  }
  const updateEvent = (event: GrooveEvent) => { if (!pattern) return; const edited = { ...event, origin: 'user_edited' as const }; setSelectedEvent(edited); void updateAndEvaluate({ ...pattern,events:pattern.events.map(item=>item.event_id===edited.event_id?edited:item),analysis:null }) }
  const lockInstrument = (instrument: Instrument) => { if (!pattern) return; const locks=pattern.instrument_locks.includes(instrument)?pattern.instrument_locks.filter(x=>x!==instrument):[...pattern.instrument_locks,instrument]; history.commit({ ...pattern,instrument_locks:locks }) }
  const regenerate = async () => { if (!pattern) return; setBusy(true); try { const next=await api.mutate(pattern,selectedInstrument?[selectedInstrument]:[],[...selectedBars]); history.commit(next); setCandidates(items=>[next,...items.slice(1)]); setSelectedEvent(null) } catch(e){setError(String(e))} finally {setBusy(false)} }
  const targetVsMeasured = useMemo(() => pattern?.analysis ? Object.entries(pattern.analysis.measured_dna).slice(0,8) : [], [pattern])
  return <div className="app-shell">
    <header><div className="brand-mark">HGE</div><div><p className="eyebrow">HUMAN GROOVE ENGINE</p><h1>Prediction needs a little friction.</h1></div><div className="header-actions"><button className="ghost-button" disabled={!history.canUndo} onClick={history.undo}>↶ Undo</button><button className="ghost-button" disabled={!history.canRedo} onClick={history.redo}>↷ Redo</button></div></header>
    <main>
      <section className="control-panel panel">
        <div className="transport-settings">
          <label>BPM<input type="number" min="30" max="300" value={bpm} onChange={e=>setBpm(Number(e.target.value))}/></label>
          <label>BARS<select value={bars} onChange={e=>setBars(Number(e.target.value))}>{[1,2,4,8,12,16,32,64].map(x=><option key={x}>{x}</option>)}</select></label>
          <label>METER<select value={meter} onChange={e=>setMeter(e.target.value)}>{METER_OPTIONS.map(x=><option key={x}>{x}</option>)}</select></label>
          <label>SEED<input type="number" min="0" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label>
          <label>STYLE<select value={preset} onChange={e=>choosePreset(e.target.value)}>{Object.keys(presets?.built_in??{Balanced:1}).map(x=><option key={x}>{x}</option>)}</select></label>
        </div>
        <div className="knob-row">{controlMap.map(([label,key])=><Knob key={key} label={label} value={intent.target_dna[key]} onChange={value=>setDNA(key,value)}/>)}</div>
        <div className="primary-actions"><button className="generate" disabled={busy} onClick={generate}>{busy?'CALCULATING…':'GENERATE'}</button><button disabled={!pattern} className={playing?'play active':'play'} onClick={()=>pattern&&togglePreview(pattern,setPlaying)}>{playing?'■ STOP':'▶ PLAY'}</button><button disabled={!pattern||busy} className="secondary" onClick={regenerate}>↻ REGENERATE SELECTED</button><button disabled={!pattern} className="secondary" onClick={()=>pattern&&api.midi(pattern)}>↓ MIDI</button></div>
        {error&&<p className="error">{error}</p>}
      </section>
      {candidates.length>0&&<section className="candidates">{candidates.map((item,index)=><button className={pattern?.pattern_id===item.pattern_id?'candidate active':'candidate'} key={item.pattern_id} onClick={()=>selectCandidate(item)}><b>{String.fromCharCode(65+index)}</b><span>{Math.round((item.analysis?.listener.predicted_groove??0)*100)} groove</span><small>{item.events.length} events</small></button>)}<div className="ab-choice"><span>Which moves you?</span><button disabled={candidates.length<2} onClick={()=>api.prefer(candidates[0],candidates[1],'A')}>A</button><button disabled={candidates.length<2} onClick={()=>api.prefer(candidates[0],candidates[1],'B')}>B</button></div></section>}
      {pattern&&<div className="workspace"><div className="pattern-column"><StepGrid pattern={pattern} selectedBars={selectedBars} selectedInstrument={selectedInstrument} onToggle={toggleStep} onSelectEvent={setSelectedEvent} onSelectBar={bar=>setSelectedBars(current=>{const next=new Set(current);if(next.has(bar))next.delete(bar);else next.add(bar);return next})} onSelectInstrument={setSelectedInstrument} onLockInstrument={lockInstrument}/>{selectedEvent&&<EventInspector event={selectedEvent} onChange={updateEvent} onClose={()=>setSelectedEvent(null)}/>}</div><ListenerPanel analysis={pattern.analysis}/></div>}
      {pattern&&<section className="advanced panel"><div className="tabs">{['Pulse','Syncopation','Interlock','Dynamics','Timing','Phrase','Complexity','Listener'].map(tab=><button className={advanced===tab?'active':''} key={tab} onClick={()=>setAdvanced(tab)}>{tab}</button>)}</div><div className="advanced-body"><div><p className="eyebrow">{advanced.toUpperCase()} / TARGET ↔ MEASURED</p><h2>The target guides. The pattern answers.</h2><p className="muted">Measured DNA is derived from the generated events; it is never copied from the controls.</p></div><div className="dna-table">{targetVsMeasured.map(([key,value])=><div key={key}><span>{key.replaceAll('_',' ')}</span><i><em style={{width:`${Number(value)*100}%`}}/></i><b>{Math.round(intent.target_dna[key as keyof GrooveDNA]*100)} → {Math.round(Number(value)*100)}</b></div>)}</div></div></section>}
    </main><footer><span>ENGINE 0.1 · PPQ 960 · PCG64DXSM</span><span>Stable pulse → controlled violation → recovery</span></footer>
  </div>
}

export default function App() {
  const [engine, setEngine] = useState<'groove' | 'bass'>('groove')
  const [sharedGroove, setSharedGroove] = useState<GroovePattern | null>(null)
  return <><nav className="engine-switch" aria-label="Engine selection"><button className={engine === 'groove' ? 'active' : ''} onClick={() => setEngine('groove')}>GROOVE</button><button className={engine === 'bass' ? 'active' : ''} onClick={() => setEngine('bass')}>BASS</button></nav><div hidden={engine !== 'groove'}><GrooveApp onPatternChange={setSharedGroove} externalPattern={sharedGroove} /></div><div hidden={engine !== 'bass'}><BassApp groovePattern={sharedGroove} onGrooveUpdate={setSharedGroove} /></div></>
}
