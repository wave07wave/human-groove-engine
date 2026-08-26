import type { GrooveEvent, GroovePattern, Instrument } from '../types/generated'

const lanes: [Instrument, string][] = [
  ['kick', 'KICK'], ['snare', 'SNARE'], ['closed_hat', 'CLOSED HAT'],
  ['open_hat', 'OPEN HAT'], ['percussion', 'PERC'], ['bass', 'BASS'],
]

interface Props {
  pattern: GroovePattern; selectedBars: Set<number>; selectedInstrument: Instrument | null
  onToggle: (instrument: Instrument, tick: number) => void; onSelectEvent: (event: GrooveEvent) => void
  onSelectBar: (bar: number) => void; onSelectInstrument: (instrument: Instrument) => void
  onLockInstrument: (instrument: Instrument) => void
}

export function StepGrid(props: Props) {
  const { pattern } = props
  const barTicks = pattern.meter.numerator * 960 * 4 / pattern.meter.denominator
  const stepTick = 240; const steps = pattern.bars * barTicks / stepTick
  const eventAt = (instrument: Instrument, tick: number) => pattern.events.find(event => event.instrument === instrument && event.grid_tick === tick)
  return <section className="sequencer panel">
    <div className="grid-toolbar"><div><p className="eyebrow">PATTERN</p><h2>{pattern.name}</h2></div><div className="legend"><span className="anchor">● Anchor</span><span className="ghost">● Ghost</span><span className="violation">● Violation</span><span className="recovery">● Recovery</span></div></div>
    <div className="grid-scroll">
      <div className="bar-row" style={{ gridTemplateColumns: `130px repeat(${steps}, 30px)` }}><span />
        {Array.from({ length: steps }, (_, step) => {
          const tick = step * stepTick; const bar = Math.floor(tick / barTicks)
          const starts = tick % barTicks === 0
          return <button key={step} className={`${starts ? 'bar-start' : ''} ${props.selectedBars.has(bar) ? 'selected-bar' : ''}`} onClick={() => props.onSelectBar(bar)}>{starts ? bar + 1 : ''}</button>
        })}
      </div>
      {lanes.map(([instrument, label]) => <div className="lane" key={instrument} style={{ gridTemplateColumns: `130px repeat(${steps}, 30px)` }}>
        <div className={`lane-label ${props.selectedInstrument === instrument ? 'selected' : ''}`} onClick={() => props.onSelectInstrument(instrument)}>
          <span>{label}</span><button title="Instrument lock" className={pattern.instrument_locks.includes(instrument) ? 'locked' : ''} onClick={event => { event.stopPropagation(); props.onLockInstrument(instrument) }}>{pattern.instrument_locks.includes(instrument) ? '◆' : '◇'}</button>
        </div>
        {Array.from({ length: steps }, (_, step) => {
          const tick = step * stepTick; const event = eventAt(instrument, tick); const barLine = tick % barTicks === 0
          return <button aria-label={`${instrument} step ${step + 1}`} key={step} className={`step ${barLine ? 'bar-line' : ''} ${event ? `on ${event.primary_role}` : ''} ${event?.locked ? 'event-locked' : ''}`} onClick={() => event ? props.onSelectEvent(event) : props.onToggle(instrument, tick)} onDoubleClick={() => event && props.onToggle(instrument, tick)}><i style={{ opacity: event ? .35 + event.velocity / 190 : 0 }} /></button>
        })}
      </div>)}
    </div>
    <p className="grid-tip">空セルをクリックして追加。イベントをクリックして詳細編集、ダブルクリックで削除。◇ はパート固定。</p>
  </section>
}
