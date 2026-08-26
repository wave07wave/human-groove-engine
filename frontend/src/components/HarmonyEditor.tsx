import { HARMONY_QUALITIES as qualities, HARMONY_ROOTS as roots, parseHarmonyPlan, serializeHarmonyPlan, type HarmonyPlanItem } from '../utils/harmonyPlan'

export function HarmonyEditor({ value, bars, onChange }: { value: string, bars: number, onChange: (value: string) => void }) {
  const plan = parseHarmonyPlan(value)
  if (!plan) return <div className="harmony-editor invalid"><span>Structured editor is waiting for a supported chord progression.</span></div>
  const update = (index: number, changes: Partial<HarmonyPlanItem>) => onChange(serializeHarmonyPlan(plan.map((item, itemIndex) => itemIndex === index ? { ...item, ...changes } : item)))
  const cycle = serializeHarmonyPlan(plan).split(' | ')
  const preview = Array.from({ length: Math.min(16, bars) }, (_, index) => cycle[index % cycle.length])
  return <div className="harmony-editor">
    <div className="harmony-plan-title"><span>CHORD TIMELINE · {cycle.length} BAR CYCLE</span><button onClick={() => onChange(serializeHarmonyPlan([...plan, { root: 'C', quality: 'maj7', slashBass: '', durationBars: 1 }]))}>＋ CHORD</button></div>
    <div className="harmony-plan-scroll">{plan.map((item, index) => <fieldset key={`${index}-${item.root}-${item.quality}-${item.slashBass}`}><legend>EVENT {index + 1}</legend><label>ROOT<select aria-label={`ROOT ${index + 1}`} value={item.root} onChange={event => update(index, { root: event.target.value })}>{roots.map(root => <option key={root}>{root}</option>)}</select></label><label>QUALITY<select aria-label={`QUALITY ${index + 1}`} value={item.quality} onChange={event => update(index, { quality: event.target.value })}>{qualities.map(([suffix, label]) => <option key={suffix || 'major'} value={suffix}>{label}</option>)}</select></label><label>DURATION<select aria-label={`DURATION ${index + 1}`} value={item.durationBars} onChange={event => update(index, { durationBars: Number(event.target.value) })}>{Array.from({ length: 16 }, (_, duration) => <option key={duration + 1} value={duration + 1}>{duration + 1} bar{duration ? 's' : ''}</option>)}</select></label><label>SLASH BASS<select aria-label={`SLASH BASS ${index + 1}`} value={item.slashBass} onChange={event => update(index, { slashBass: event.target.value })}><option value="">None</option>{roots.map(root => <option key={root}>{root}</option>)}</select></label><button className="remove-chord" disabled={plan.length === 1} onClick={() => onChange(serializeHarmonyPlan(plan.filter((_, itemIndex) => itemIndex !== index)))}>×</button></fieldset>)}</div>
    <div className="harmony-bar-preview">{preview.map((symbol, index) => <span key={index}><small>BAR {index + 1}</small>{symbol}</span>)}{bars > 16 && <i>+{bars - 16} bars</i>}</div>
  </div>
}
