import type { GrooveEvent } from '../types/generated'

export function EventInspector({ event, onChange, onClose }: { event: GrooveEvent; onChange: (event: GrooveEvent) => void; onClose: () => void }) {
  return <div className="inspector panel">
    <div className="panel-title"><div><p className="eyebrow">イベント詳細</p><h2>{event.instrument.replace('_', ' ')}</h2></div><button className="icon-button" onClick={onClose}>×</button></div>
    <label>ベロシティ <b>{event.velocity}</b><input type="range" min="1" max="127" value={event.velocity} onChange={e => onChange({ ...event, velocity: Number(e.target.value) })} /></label>
    <label>音の長さ <b>{event.duration_tick} ticks</b><input type="range" min="60" max="1920" step="30" value={event.duration_tick} onChange={e => onChange({ ...event, duration_tick: Number(e.target.value) })} /></label>
    <label>タイミング <b>{Math.round(event.micro_offset_us / 1000)} ms</b><input type="range" min="-25000" max="25000" step="500" value={event.micro_offset_us} onChange={e => onChange({ ...event, micro_offset_us: Number(e.target.value) })} /></label>
    <button className={event.locked ? 'small active' : 'small'} onClick={() => onChange({ ...event, locked: !event.locked })}>{event.locked ? 'イベントを固定中' : 'イベントを固定'}</button>
  </div>
}
