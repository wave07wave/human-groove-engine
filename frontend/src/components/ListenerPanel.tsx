import type { GrooveAnalysis } from '../types/generated'

const fields: [keyof GrooveAnalysis['listener'], string][] = [
  ['predicted_groove', 'Groove予測'], ['movement_proxy', '身体同期'], ['beat_confidence', '拍の明確さ'],
  ['resolvable_surprise', '解決できる意外性'], ['learning_progress', '学習の進み具合'], ['boredom', '単調さ'], ['confusion', '混乱度'],
]

export function ListenerPanel({ analysis }: { analysis: GrooveAnalysis | null }) {
  if (!analysis) return <aside className="listener panel"><p className="eyebrow">バーチャル・リスナー</p><p className="muted">Grooveを作成すると、聴こえ方の分析を表示します。</p></aside>
  return <aside className="listener panel">
    <div className="panel-title"><div><p className="eyebrow">バーチャル・リスナー</p><h2>聴こえ方の分析</h2></div><span className="confidence">分析の信頼度 {Math.round(analysis.confidence.overall * 100)}%</span></div>
    <div className="score-hero"><span>{Math.round((analysis.embodied?.estimates.urge_to_move_prior ?? analysis.listener.predicted_groove) * 100)}</span><small>動きたくなる予測</small></div>
    <div className="meters">{fields.slice(1).map(([key, label]) => {
      const value = Number(analysis.listener[key]); return <div className="meter" key={key}>
        <div><span>{label}</span><b>{Math.round(Math.max(0, value) * 100)}</b></div>
        <i><em style={{ width: `${Math.max(0, value) * 100}%` }} /></i>
      </div>
    })}</div>
    {analysis.embodied&&<div className="render-analysis"><p className="eyebrow">身体化グルーヴの内訳</p><div><span>拍の足場 <b>{Math.round(Math.max(analysis.embodied.motor_scaffold.tactus.clarity, analysis.embodied.motor_scaffold.half_time.clarity)*100)}</b></span><span>タイミング整合 <b>{Math.round(analysis.embodied.timing_coherence.coherence*100)}</b></span><span>戻り <b>{Math.round(analysis.embodied.phrase_renewal.reentry_strength*100)}</b></span></div><small>予測の不確実性 {Math.round(analysis.embodied.estimates.uncertainty*100)}%</small></div>}
    {analysis.rendered_audio&&<div className="render-analysis"><p className="eyebrow">参照音色シミュレーション</p><div><span>オンセット明瞭度 <b>{Math.round(analysis.rendered_audio.onset_clarity*100)}</b></span><span>低域の重なり <b>{analysis.rendered_audio.low_end_collision_applicable?Math.round(analysis.rendered_audio.low_end_collision*100):'—'}</b></span><span>ヘッドルーム <b>{Math.round(analysis.rendered_audio.headroom*100)}</b></span></div><small>{analysis.rendered_audio.profile_id} · 録音音声の解析ではありません</small></div>}
    <p className="model-note">予測モデルによるヒューリスティック値であり、生理学的測定ではありません。「必ず踊る」という保証でもありません。</p>
  </aside>
}
