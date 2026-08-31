import { useState } from 'react'
import type { BassEvent, BassPattern } from '../types/generated'

const roleLabels: Record<string, string> = {
  structural_root: 'R!', root: 'R', third: '3', fifth: '5', seventh: '7',
  extension: 'E', scale_tone: 'S', passing: 'P', approach: 'A',
  chromatic_approach: 'C', enclosure: 'En', neighbor: 'N', pedal: 'Pd',
  anticipation: 'An', target: 'T',
}

function bounded(raw: string, minimum: number, maximum: number, fallback: number) {
  const value = Number(raw)
  return Number.isFinite(value) ? Math.max(minimum, Math.min(maximum, value)) : fallback
}

type Props = {
  pattern: BassPattern
  selected: BassEvent | null
  selectedBars: Set<number>
  onSelect: (event: BassEvent | null) => void
  onBars: (bars: Set<number>) => void
  onChange: (pattern: BassPattern) => void
}

export function BassPianoRoll({ pattern, selected, selectedBars, onSelect, onBars, onChange }: Props) {
  const [traceOpen, setTraceOpen] = useState(false)
  const [showStructure, setShowStructure] = useState(false)
  const low = pattern.register_limits.lowest_midi_note
  const high = pattern.register_limits.highest_midi_note
  const range = high - low + 1
  const barTicks = pattern.meter.numerator * 960 * 4 / pattern.meter.denominator
  const total = pattern.bars * barTicks
  const width = Math.max(920, pattern.bars * 150)
  const changeEvent = (next: BassEvent) => onChange({ ...pattern, events: pattern.events.map(event => event.event_id === next.event_id ? { ...next, decision_trace: null, provenance: { ...next.provenance, origin: 'user_edited' } } : event), analysis: null })
  const toggleLock = (field: keyof BassEvent['locks']) => selected && changeEvent({ ...selected, locks: { ...selected.locks, [field]: !selected.locks[field] } })
  const changeArticulation = (field: keyof BassEvent['articulation'], value: string | number) => {
    if (!selected) return
    changeEvent({ ...selected, articulation: { ...selected.articulation, [field]: value } })
  }
  const deleteEvent = () => selected && onChange({ ...pattern, events: pattern.events.filter(event => event.event_id !== selected.event_id && event.approach_target_id !== selected.event_id), structural_events: pattern.structural_events.map(event => event.target_event_id === selected.event_id ? { ...event, target_event_id: null } : event), analysis: null })
  const duplicate = () => { if (!selected) return; const wasApproach = ['approach', 'chromatic_approach'].includes(selected.harmonic_role); const stepTick = 960 / pattern.meter.subdivisions_per_quarter; const gridTick = Math.min(total - 1, selected.grid_tick + stepTick); const copy = { ...selected, event_id: crypto.randomUUID(), grid_tick: gridTick, structural_offset_tick: Math.max(-gridTick, Math.min(total - 1 - gridTick, selected.structural_offset_tick)), harmonic_role: wasApproach ? 'scale_tone' as const : selected.harmonic_role, rhythmic_role: wasApproach ? 'decoration' as const : selected.rhythmic_role, approach_target_id: null, decision_trace: null, provenance: { ...selected.provenance, origin: 'user_edited' } }; onChange({ ...pattern, events: [...pattern.events, copy].sort((a, b) => a.grid_tick - b.grid_tick), analysis: null }); onSelect(copy) }
  const toggleBar = (bar: number) => { const next = new Set(selectedBars); if (next.has(bar)) next.delete(bar); else next.add(bar); onBars(next) }
  return <section className="panel bass-roll-panel">
    <div className="panel-title"><div><p className="eyebrow">BASS PIANO ROLL</p><h2>Function, motion and space</h2></div><div className="roll-actions"><button className={showStructure ? 'active' : ''} onClick={() => setShowStructure(value => !value)}>STRUCTURE</button><span className="confidence">MIDI {low}–{high} · PPQ 960</span></div></div>
    <div className="bass-roll-scroll">
      <div className="bass-roll" style={{ width }}>
        <div className="bass-ruler">{Array.from({ length: pattern.bars }, (_, bar) => <button key={bar} className={selectedBars.has(bar) ? 'selected' : ''} style={{ width: `${100 / pattern.bars}%` }} onClick={() => toggleBar(bar)}>BAR {bar + 1}</button>)}</div>
        <div className="pitch-surface" style={{ height: range * 12 }} onClick={() => onSelect(null)}>
          {Array.from({ length: range }, (_, index) => { const pitch = high - index; return <div key={pitch} className={`pitch-row ${[1,3,6,8,10].includes(pitch % 12) ? 'black' : ''}`} style={{ top: index * 12 }}><span>{pitch % 12 === 0 ? `C · ${pitch}` : pitch}</span></div> })}
          {Array.from({ length: pattern.bars - 1 }, (_, index) => <i key={index} className="bar-guide" style={{ left: `${(index + 1) * 100 / pattern.bars}%` }} />)}
          {pattern.events.map(event => <button
            key={event.event_id}
            title={`${event.harmonic_role} · ${event.rhythmic_role}`}
            className={`bass-note ${selected?.event_id === event.event_id ? 'selected' : ''} ${event.harmonic_role.includes('approach') ? 'approach' : ''}`}
            style={{ left: `${event.grid_tick / total * 100}%`, width: `${Math.max(.3, event.duration_tick / total * 100)}%`, top: (high - event.pitch) * 12, opacity: .45 + event.velocity / 230 }}
            onClick={e => { e.stopPropagation(); onSelect(event) }}
          >{roleLabels[event.harmonic_role] ?? event.harmonic_role[0]}</button>)}
        </div>
        {showStructure && <div className="structural-preview"><span>STRUCTURE</span>{pattern.structural_events.length ? pattern.structural_events.map(event => <i key={event.event_id} title={event.role.replaceAll('_', ' ')} style={{ left: `${event.start_tick / total * 100}%`, width: `${Math.max(.5, event.duration_tick / total * 100)}%` }}>{event.role.replaceAll('_', ' ')}</i>) : <small>No structural events</small>}</div>}
        <div className="kick-overlay"><span>KICK</span>{pattern.groove_context?.kick_events?.map((kick, index) => <i key={index} style={{ left: `${kick.grid_tick / total * 100}%` }} />)}{!pattern.groove_context?.kick_events?.length && <small>No kick context · Bass-only analysis</small>}</div>
      </div>
    </div>
    {selected && <div className="bass-inspector">
      <div><b>{roleLabels[selected.harmonic_role] ?? '•'} · MIDI {selected.pitch}</b><small>{selected.harmonic_role.replaceAll('_', ' ')} / {selected.rhythmic_role}</small></div>
      <label>GRID TICK<input type="number" min="0" max={total - 1} value={selected.grid_tick} onChange={e => { const gridTick = bounded(e.target.value, 0, total - 1, selected.grid_tick); changeEvent({ ...selected, grid_tick: gridTick, structural_offset_tick: Math.max(-gridTick, Math.min(total - 1 - gridTick, selected.structural_offset_tick)), duration_tick: Math.min(selected.duration_tick, total - gridTick) }) }} /></label>
      <label>STRUCTURAL OFFSET<input type="number" min={-selected.grid_tick} max={total - 1 - selected.grid_tick} value={selected.structural_offset_tick} onChange={e => changeEvent({ ...selected, structural_offset_tick: bounded(e.target.value, -selected.grid_tick, total - 1 - selected.grid_tick, selected.structural_offset_tick) })} /></label>
      <label>PITCH<input type="number" min={low} max={high} value={selected.pitch} onChange={e => changeEvent({ ...selected, pitch: bounded(e.target.value, low, high, selected.pitch) })} /></label>
      <label>DURATION<input type="number" min="1" max={total - selected.grid_tick} value={selected.duration_tick} onChange={e => changeEvent({ ...selected, duration_tick: bounded(e.target.value, 1, total - selected.grid_tick, selected.duration_tick) })} /></label>
      <label>VELOCITY<input type="number" min="1" max="127" value={selected.velocity} onChange={e => changeEvent({ ...selected, velocity: bounded(e.target.value, 1, 127, selected.velocity) })} /></label>
      <label>MICRO µs<input type="number" min="-25000" max="25000" value={selected.micro_offset_us} onChange={e => changeEvent({ ...selected, micro_offset_us: bounded(e.target.value, -25000, 25000, selected.micro_offset_us) })} /></label>
      <label>CONNECTION<select value={selected.articulation.connection} onChange={e => changeArticulation('connection', e.target.value)}><option value="normal">Normal</option><option value="staccato">Staccato</option><option value="legato">Legato</option><option value="tenuto">Tenuto</option></select></label>
      <label>TECHNIQUE<select value={selected.articulation.technique} onChange={e => changeArticulation('technique', e.target.value)}><option value="normal">Normal</option><option value="mute">Mute</option><option value="ghost">Ghost</option><option value="slide_hint">Slide hint</option><option value="hammer_hint">Hammer hint</option><option value="pull_hint">Pull hint</option></select></label>
      <label>ACCENT<select value={selected.articulation.accent} onChange={e => changeArticulation('accent', e.target.value)}><option value="normal">Normal</option><option value="accent">Accent</option><option value="soft">Soft</option></select></label>
      <label>LEGATO OVERLAP<input type="number" min="0" max={selected.duration_tick} value={selected.articulation.legato_overlap_tick} onChange={e => changeArticulation('legato_overlap_tick', bounded(e.target.value, 0, selected.duration_tick, selected.articulation.legato_overlap_tick))} /></label>
      <div className="note-tools"><button onClick={() => toggleLock('pitch')}>{selected.locks.pitch ? '◆ PITCH' : '◇ PITCH'}</button><button onClick={() => toggleLock('timing')}>{selected.locks.timing ? '◆ TIME' : '◇ TIME'}</button><button onClick={() => toggleLock('duration')}>{selected.locks.duration ? '◆ DUR' : '◇ DUR'}</button><button onClick={() => toggleLock('velocity')}>{selected.locks.velocity ? '◆ VEL' : '◇ VEL'}</button><button onClick={() => toggleLock('articulation')}>{selected.locks.articulation ? '◆ ART' : '◇ ART'}</button><button className={traceOpen ? 'active' : ''} onClick={() => setTraceOpen(value => !value)}>{traceOpen ? 'TRACE ON' : 'TRACE'}</button><button onClick={duplicate}>DUPLICATE</button><button onClick={deleteEvent}>DELETE</button></div>
      <p className="explanation">{selected.decision_trace?.pitch_reason ?? `User-edited note: ${selected.harmonic_role.replaceAll('_', ' ')} at ${selected.phrase_id}. Analysis and trace will refresh automatically.`}</p>
      {traceOpen && selected.decision_trace && <div className="decision-trace"><p className="eyebrow">GENERATION TRACE · DEBUG</p><dl><div><dt>WHY THIS ONSET?</dt><dd>{selected.decision_trace.onset_reason}</dd></div><div><dt>WHY THIS PITCH?</dt><dd>{selected.decision_trace.pitch_reason}</dd></div><div><dt>WHY THIS DURATION?</dt><dd>{selected.decision_trace.duration_reason}</dd></div><div><dt>WHY THIS OCTAVE?</dt><dd>{selected.decision_trace.octave_reason}</dd></div><div><dt>WHY THIS ARTICULATION?</dt><dd>{selected.decision_trace.articulation_reason}</dd></div></dl><div className="trace-factors">{Object.entries(selected.decision_trace.factors ?? {}).map(([name, value]) => <span key={name}>{name.replaceAll('_', ' ')} <b>{Math.round(value * 100)}</b></span>)}</div></div>}
    </div>}
  </section>
}
