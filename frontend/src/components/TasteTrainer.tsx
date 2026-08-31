import { useMemo, useRef, useState } from 'react'
import { ADVANCED_DNA_GROUPS } from '../advancedControls'
import { api } from '../api/client'
import type { GroovePattern, GroovePreferenceSummary } from '../types/generated'
import type { AdaptivePairReason } from '../utils/adaptivePairing'
import { buildPreferencePairPlans } from '../utils/tastePairs'

type AuditionPosition = 'first' | 'second'
type PreferenceChoice = AuditionPosition | 'tie'

const dnaLabels = Object.fromEntries(
  Object.values(ADVANCED_DNA_GROUPS).flatMap(group =>
    group.controls.map(([label, key]) => [key, label]),
  ),
)

const pairReasonLabels: Record<AdaptivePairReason, string> = {
  broad_contrast: 'まず違いが分かりやすい組み合わせから始めます',
  uncertain_features: 'まだ好みが定まっていない特徴を学べる組み合わせです',
  decision_boundary: '現在の予測が拮抗する組み合わせで、好みの境界を確かめます',
}

function randomOrder(): boolean {
  const byte = new Uint8Array(1)
  crypto.getRandomValues(byte)
  return Boolean(byte[0] & 1)
}

interface Props {
  candidates: GroovePattern[]
  preference: GroovePreferenceSummary | null
  onPreference: (preference: GroovePreferenceSummary) => void
}

function rangeStrength(range: { evidence?: number, uncertainty: number }): number {
  return (range.evidence ?? 0) * (1 - range.uncertainty)
}

export function TasteTrainer({ candidates, preference, onPreference }: Props) {
  const plans = useMemo(
    () => buildPreferencePairPlans(candidates, preference), [candidates, preference],
  )
  const [currentPlan, setCurrentPlan] = useState(() => plans[0] ?? null)
  const [completedPairKeys, setCompletedPairKeys] = useState(new Set<string>())
  const [swapped, setSwapped] = useState(randomOrder)
  const [comparisonId, setComparisonId] = useState(() => crypto.randomUUID())
  const [heard, setHeard] = useState(new Set<AuditionPosition>())
  const [playing, setPlaying] = useState<AuditionPosition | null>(null)
  const [answered, setAnswered] = useState(false)
  const [complete, setComplete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const startedAt = useRef(0)
  const submitting = useRef(false)
  const pair = currentPlan?.pair
  const displayed = pair ? (swapped ? [pair[1], pair[0]] : pair) : null
  const scope = preference?.profile_scope ?? candidates[0]?.metadata.style
  const ranges = Object.entries(preference?.preferred_ranges ?? {})
    .sort((left, right) => (
      rangeStrength(right[1]) - rangeStrength(left[1]) || left[0].localeCompare(right[0])
    ))
    .slice(0, 3)

  const audition = async (position: AuditionPosition) => {
    if (!displayed) return
    const candidate = displayed[position === 'first' ? 0 : 1]
    setError('')
    try {
      const module = await import('../audio/preview')
      await module.togglePreview(candidate, value => {
        setPlaying(value ? position : null)
        if (value) {
          setHeard(current => new Set(current).add(position))
          if (!startedAt.current) startedAt.current = performance.now()
        }
      })
    } catch (cause) {
      setError(`音声を開始できません: ${String(cause)}`)
    }
  }

  const answer = async (choice: PreferenceChoice) => {
    if (!displayed || heard.size < 2 || submitting.current) return
    submitting.current = true
    setBusy(true); setError('')
    try {
      const selected = choice === 'tie' ? 'tie' : choice === 'first' ? 'A' : 'B'
      const elapsed = Math.max(250, Math.round(performance.now() - startedAt.current))
      const next = await api.prefer(
        displayed[0], displayed[1], selected,
        displayed.map(candidate => candidate.pattern_id), comparisonId, elapsed,
      )
      const module = await import('../audio/preview')
      module.stopGroovePreview(() => setPlaying(null))
      onPreference(next)
      setAnswered(true)
    } catch (cause) {
      setError(String(cause))
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  const nextPair = () => {
    if (!currentPlan) return
    const completed = new Set(completedPairKeys).add(currentPlan.key)
    setCompletedPairKeys(completed)
    const next = plans.find(item => !completed.has(item.key))
    if (!next) {
      setComplete(true)
      return
    }
    setCurrentPlan(next)
    setSwapped(randomOrder())
    setComparisonId(crypto.randomUUID())
    setHeard(new Set())
    setPlaying(null)
    setAnswered(false)
    setError('')
    startedAt.current = 0
  }

  const comparisons = preference?.comparisons ?? 0
  const effective = preference?.effective_comparisons ?? 0
  const confidence = preference?.learning_confidence ?? 0
  const personalWeight = preference?.personal_weight ?? 0
  const hasRemainingPairs = completedPairKeys.size + 1 < plans.length

  return <section className="taste-trainer panel" aria-label="あなたのGroove学習">
    <div className="taste-heading"><div><p className="eyebrow">あなたのGROOVE · {scope ?? '現在のスタイル'}</p><h2>点数を隠して、耳だけで好みを学ぶ。</h2></div><div className="taste-stats"><span><b>{comparisons}</b>回答</span><span><b>{effective.toFixed(1)}</b>有効比較</span><span><b>{Math.round(confidence * 100)}%</b>学習信頼度</span><span><b>{Math.round(personalWeight * 100)}%</b>次回生成へ反映</span></div></div>
    {!displayed ? <p className="muted">比較には2候補以上が必要です。</p> : complete ? <div className="taste-complete"><b>この候補セットの比較が完了しました。</b><span>新しいGrooveを作ると、学習済みの好みを反映した候補で続けられます。</span></div> : <>
      <p className="taste-guide">比較 {completedPairKeys.size + 1}/{plans.length} · {currentPlan ? pairReasonLabels[currentPlan.reason] : ''}。両方を聴くまで回答はできません。</p>
      <div className="taste-candidates">{(['first', 'second'] as const).map((position, index) => <div key={position}><b>候補 {index + 1}</b><button aria-label={`比較候補 ${index + 1} を再生`} className={playing === position ? 'active' : ''} onClick={() => void audition(position)}>{playing === position ? '■ 停止' : '▶ 再生'}</button><small>{heard.has(position) ? '試聴済み' : '未試聴'}</small></div>)}</div>
      {!answered ? <div className="taste-answer"><button disabled={heard.size < 2 || busy} onClick={() => void answer('first')}>候補 1 が好き</button><button disabled={heard.size < 2 || busy} onClick={() => void answer('tie')}>差がない</button><button disabled={heard.size < 2 || busy} onClick={() => void answer('second')}>候補 2 が好き</button></div> : <div className="taste-result"><b>好みを学習しました</b><span>{hasRemainingPairs ? '回答を反映し、残りを学習に役立ちやすい順へ選び直しました。' : 'この候補セットで学んだ好みを次回の候補順位へ反映します。'}</span><button onClick={nextPair}>{hasRemainingPairs ? '次の組み合わせ' : 'この比較を完了'}</button></div>}
    </>}
    {ranges.length > 0 && <div className="taste-ranges">{ranges.map(([name, range]) => <div key={name}><span>{dnaLabels[name] ?? name.replaceAll('_', ' ')}</span><i><em style={{ left: `${range.low * 100}%`, width: `${(range.high - range.low) * 100}%` }}/><b style={{ left: `${range.mean * 100}%` }}/></i><small>順位への根拠 {Math.round(rangeStrength(range) * 100)}% · 不確かさ {Math.round(range.uncertainty * 100)}%</small></div>)}</div>}
    <small className="taste-caveat">方向の好みと、比較で裏づけられた好みの帯を次回順位へ反映します。偶然似ただけの特徴や不確かな帯は反映しません。</small>
    {error && <p className="error">{error}</p>}
  </section>
}
