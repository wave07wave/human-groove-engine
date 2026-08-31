import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { BlindResponseResult, BlindSession, EvaluationSummary, GenerateRequest, ParticipantGroup, QualityAuditReport } from '../types/generated'

const groupLabels: Record<ParticipantGroup, string> = {
  producer: '音楽制作者', drummer: 'ドラマー', general: '一般リスナー', undisclosed: '回答しない',
}

export function BlindEvaluationPanel({ generation }: { generation: GenerateRequest }) {
  const [group, setGroup] = useState<ParticipantGroup>('undisclosed')
  const [consent, setConsent] = useState(false)
  const [session, setSession] = useState<BlindSession | null>(null)
  const [blockGeneration, setBlockGeneration] = useState<GenerateRequest | null>(null)
  const [studyRunId, setStudyRunId] = useState('')
  const [trialIndex, setTrialIndex] = useState(0)
  const [startedAt, setStartedAt] = useState(0)
  const [heard, setHeard] = useState(new Set<'left'|'right'>())
  const [playing, setPlaying] = useState<'left'|'right'|null>(null)
  const [saveChoice, setSaveChoice] = useState(false)
  const [result, setResult] = useState<BlindResponseResult | null>(null)
  const [summary, setSummary] = useState<EvaluationSummary | null>(null)
  const [qualityAudit, setQualityAudit] = useState<QualityAuditReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.evaluationSummary().then(setSummary).catch(() => undefined) }, [])
  useEffect(() => { api.qualityAudit().then(setQualityAudit).catch(() => undefined) }, [])
  const startTrial = async (nextTrial: number, existingRunId?: string) => {
    setBusy(true); setError('')
    try {
      const runId = existingRunId || crypto.randomUUID()
      const frozenGeneration = existingRunId && blockGeneration ? blockGeneration : structuredClone(generation)
      if (!existingRunId) setBlockGeneration(frozenGeneration)
      const seedOffset = nextTrial === 5 ? 0 : nextTrial
      const trialSeed = (frozenGeneration.seed + seedOffset) % 2_147_483_648
      const next = await api.startEvaluation(group, { ...frozenGeneration, seed: trialSeed, candidate_count: 1 }, runId, nextTrial)
      setStudyRunId(runId); setTrialIndex(nextTrial); setSession(next); setStartedAt(performance.now()); setHeard(new Set()); setResult(null); setSaveChoice(false)
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const play = (position: 'left'|'right') => {
    const candidate = session?.candidates.find(item => item.position === position)
    if (!candidate) return
    setHeard(current => new Set(current).add(position))
    void import('../audio/preview').then(module => module.togglePreview(candidate.pattern, value => setPlaying(value ? position : null))).catch(cause => setError(`音声を開始できません: ${String(cause)}`))
  }
  const answer = async (selected: 'left'|'right'|'tie') => {
    if (!session || heard.size < 2) return
    setBusy(true); setError('')
    try {
      const elapsed = Math.max(250, Math.round(performance.now() - startedAt))
      const next = await api.submitEvaluation(session.session_id, selected, elapsed, saveChoice && selected !== 'tie' ? selected : 'none')
      setResult(next); setSummary(await api.evaluationSummary())
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const declared = summary?.groups.filter(item => item.participant_group !== 'undisclosed') ?? []

  return <section className="blind-evaluation panel">
    <div className="blind-heading"><div><p className="eyebrow">ブラインド試聴</p><h2>点数を見ずに、耳で選ぶ。</h2></div><span>{summary?.completed ?? 0} 回の回答</span></div>
    {!session ? <div className="blind-start">
      <label>あなたに近い区分<select value={group} onChange={event => setGroup(event.target.value as ParticipantGroup)}>{Object.entries(groupLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/> 匿名の試聴結果を端末の評価集計へ保存することに同意します。</label>
      <button disabled={!consent || busy} onClick={() => startTrial(0)}>{busy ? '準備中…' : '6回の比較を始める'}</button>
    </div> : <>
      <p className="blind-guide">試行 {trialIndex + 1}/6 · 左右は同じリズム構造・再生環境です。両方を聴いて、演奏のノリだけで選んでください。</p>
      <div className="blind-candidates">{(['left','right'] as const).map((position,index) => <div key={position}><b>候補 {index + 1}</b><button className={playing === position ? 'active' : ''} onClick={() => play(position)}>{playing === position ? '■ 停止' : '▶ 再生'}</button><small>{heard.has(position) ? '試聴済み' : '未試聴'}</small></div>)}</div>
      {!result ? <div className="blind-answer"><button disabled={heard.size < 2 || busy} onClick={() => answer('left')}>候補 1 が好き</button><button disabled={heard.size < 2 || busy} onClick={() => answer('tie')}>同じくらい</button><button disabled={heard.size < 2 || busy} onClick={() => answer('right')}>候補 2 が好き</button><label><input type="checkbox" checked={saveChoice} onChange={event => setSaveChoice(event.target.checked)}/> 選んだ候補を保存候補として記録</label></div> : <div className="blind-result"><b>回答を記録しました</b><span>候補 1: {result.left_variant === 'learned' ? '学習済み演奏' : 'ルール演奏'} ／ 候補 2: {result.right_variant === 'learned' ? '学習済み演奏' : 'ルール演奏'}</span>{trialIndex < 5 ? <button disabled={busy} onClick={() => startTrial(trialIndex + 1, studyRunId)}>次の比較</button> : <button onClick={() => { setSession(null); setStudyRunId(''); setBlockGeneration(null); setTrialIndex(0) }}>ブロックを完了</button>}</div>}
    </>}
    {declared.length > 0 && <div className="evaluation-progress">{declared.map(item => <span key={item.participant_group}>{groupLabels[item.participant_group]} <b>{item.completed_blocks}/{summary?.minimum_blocks_per_declared_group}ブロック</b><small>{item.comparisons}回答</small></span>)}</div>}
    {summary && summary.eligible_repeat_pairs > 0 && <div className="repeat-consistency">再テスト一貫性 <b>{Math.round((summary.repeat_consistency ?? 0) * 100)}%</b> · {summary.eligible_repeat_pairs}組</div>}
    {qualityAudit && <div className={qualityAudit.passed ? 'technical-audit passed' : 'technical-audit failed'}><div><p className="eyebrow">技術品質監査 · ENGINE {qualityAudit.engine_version}</p><b>{qualityAudit.passed ? '全項目合格' : '要確認'}</b></div><span>操作 {qualityAudit.controls.filter(item => item.passed).length}/{qualityAudit.controls.length}</span><span>候補最小距離 {qualityAudit.diversity.minimum_distance.toFixed(3)}</span><span>再現不一致 {qualityAudit.determinism.mismatches}</span><span>生成P95 {Math.round(qualityAudit.latency.p95_seconds * 1000)}ms</span><small>技術的な回帰検査であり、聴感上の優位性を証明するものではありません。</small></div>}
    <small className="blind-caveat">個人の匿名評価です。3区分を別々に集計し、普遍的な「かっこよさ」の点数にはしません。</small>
    {error && <p className="error">{error}</p>}
  </section>
}
