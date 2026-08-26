import type { GrooveAnalysis } from '../types/generated'

const fields: [keyof GrooveAnalysis['listener'], string][] = [
  ['predicted_groove', 'Groove予測'], ['movement_proxy', '身体同期'], ['beat_confidence', 'Beat confidence'],
  ['resolvable_surprise', '解決できる驚き'], ['learning_progress', 'Learning'], ['boredom', 'Boredom'],
  ['confusion', 'Confusion'],
]

export function ListenerPanel({ analysis }: { analysis: GrooveAnalysis | null }) {
  if (!analysis) return <aside className="listener panel"><p className="eyebrow">VIRTUAL LISTENER</p><p className="muted">Generate a pattern to see the listener model.</p></aside>
  return <aside className="listener panel">
    <div className="panel-title"><div><p className="eyebrow">VIRTUAL LISTENER</p><h2>How it lands</h2></div><span className="confidence">{Math.round(analysis.confidence.overall * 100)}% model confidence</span></div>
    <div className="score-hero"><span>{Math.round(analysis.listener.predicted_groove * 100)}</span><small>groove proxy</small></div>
    <div className="meters">{fields.slice(1).map(([key, label]) => {
      const value = Number(analysis.listener[key]); return <div className="meter" key={key}>
        <div><span>{label}</span><b>{Math.round(Math.max(0, value) * 100)}</b></div>
        <i><em style={{ width: `${Math.max(0, value) * 100}%` }} /></i>
      </div>
    })}</div>
    <p className="model-note">予測モデルによるヒューリスティック値であり、生理学的測定ではありません。</p>
  </aside>
}
