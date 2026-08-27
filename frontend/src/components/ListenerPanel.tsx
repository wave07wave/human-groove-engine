import type { GrooveAnalysis } from '../types/generated'

const fields: [keyof GrooveAnalysis['listener'], string][] = [
  ['predicted_groove', 'Groove予測'], ['movement_proxy', '身体同期'], ['beat_confidence', '拍の明確さ'],
  ['resolvable_surprise', '解決できる意外性'], ['learning_progress', '学習の進み具合'], ['boredom', '単調さ'], ['confusion', '混乱度'],
]

export function ListenerPanel({ analysis }: { analysis: GrooveAnalysis | null }) {
  if (!analysis) return <aside className="listener panel"><p className="eyebrow">バーチャル・リスナー</p><p className="muted">Grooveを作成すると、聴こえ方の分析を表示します。</p></aside>
  return <aside className="listener panel">
    <div className="panel-title"><div><p className="eyebrow">バーチャル・リスナー</p><h2>聴こえ方の分析</h2></div><span className="confidence">分析の信頼度 {Math.round(analysis.confidence.overall * 100)}%</span></div>
    <div className="score-hero"><span>{Math.round(analysis.listener.predicted_groove * 100)}</span><small>Groove指標</small></div>
    <div className="meters">{fields.slice(1).map(([key, label]) => {
      const value = Number(analysis.listener[key]); return <div className="meter" key={key}>
        <div><span>{label}</span><b>{Math.round(Math.max(0, value) * 100)}</b></div>
        <i><em style={{ width: `${Math.max(0, value) * 100}%` }} /></i>
      </div>
    })}</div>
    <p className="model-note">予測モデルによるヒューリスティック値であり、生理学的測定ではありません。</p>
  </aside>
}
