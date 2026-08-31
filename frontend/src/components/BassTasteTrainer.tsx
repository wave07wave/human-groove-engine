import { useMemo, useRef, useState } from 'react'
import { bassApi } from '../api/client'
import type { BassPreviewMode } from '../audio/bassPreview'
import type { BassPattern, BassPreferenceSummary } from '../types/generated'
import type { AdaptivePairReason } from '../utils/adaptivePairing'
import { buildBassPreferencePairPlans } from '../utils/bassTastePairs'

type AuditionPosition = 'first' | 'second'
type PreferenceChoice = AuditionPosition | 'tie'

const featureLabels: Record<string, string> = {
  syncopation: 'シンコペーション', density: '密度', silence: '休符',
  root_usage: 'ルート感', chromatic_tolerance: 'クロマチック', pitch_motion: '音程の動き',
  register: '音域', kick_relation: 'Kickとの関係', timing: 'タイミング', duration: '音の長さ',
}

const pairReasonLabels: Record<AdaptivePairReason, string> = {
  broad_contrast: 'まず違いが分かりやすい組み合わせから始めます',
  uncertain_features: 'まだ好みが定まっていない特徴を学べる組み合わせです',
  decision_boundary: '現在の予測が拮抗する組み合わせで、好みの境界を確かめます',
}

function randomOrder() { return Math.random() < .5 }

function listeningMode(pair: [BassPattern, BassPattern]): BassPreviewMode {
  const hasKick = pair.every(pattern => (pattern.groove_context?.kick_events?.length ?? 0) > 0)
  const hasChords = pair.every(pattern => pattern.harmony.events.some(event => event.chord))
  if (hasKick && hasChords) return 'bass_kick_chords'
  if (hasKick) return 'bass_kick'
  if (hasChords) return 'bass_chords'
  return 'bass_click'
}

const modeLabels: Record<BassPreviewMode, string> = {
  bass_only: 'Bassのみ', bass_click: 'Bass + Click', bass_kick: 'Bass + Kick',
  bass_chords: 'Bass + Chords', bass_kick_chords: 'Bass + Kick + Chords',
}

function rangeStrength(range: { evidence?: number, uncertainty: number }): number {
  return (range.evidence ?? 0) * (1 - range.uncertainty)
}

export function BassTasteTrainer({
  candidates, preference, onPreference,
}: {
  candidates: BassPattern[]
  preference: BassPreferenceSummary | null
  onPreference: (profile: BassPreferenceSummary) => void
}) {
  const plans = useMemo(
    () => buildBassPreferencePairPlans(candidates, preference), [candidates, preference],
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
  const displayed = pair ? (swapped ? [pair[1], pair[0]] : pair) as [BassPattern, BassPattern] : null
  const mode = displayed ? listeningMode(displayed) : 'bass_click'
  const scope = preference?.profile_scope ?? candidates[0]?.metadata.preset
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
      const module = await import('../audio/bassPreview')
      if (playing) {
        module.stopBassPreview(() => setPlaying(null))
        if (playing === position) return
      }
      await module.toggleBassPreview(candidate, mode, value => {
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
      const next = await bassApi.prefer(
        displayed[0], displayed[1], selected,
        displayed.map(candidate => candidate.pattern_id), comparisonId, elapsed,
      )
      const module = await import('../audio/bassPreview')
      module.stopBassPreview(() => setPlaying(null))
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

  return <section className="taste-trainer panel bass-taste-trainer" aria-label="あなたのBass学習">
    <div className="taste-heading"><div><p className="eyebrow">あなたのBASS · {scope ?? '現在のスタイル'}</p><h2>点数を隠して、曲を支える方を耳で選ぶ。</h2></div><div className="taste-stats"><span><b>{comparisons}</b>回答</span><span><b>{effective.toFixed(1)}</b>有効比較</span><span><b>{Math.round(confidence * 100)}%</b>学習信頼度</span><span><b>{Math.round(personalWeight * 100)}%</b>次回生成へ反映</span></div></div>
    {!displayed ? <p className="muted">比較には2候補以上が必要です。</p> : complete ? <div className="taste-complete"><b>この候補セットの比較が完了しました。</b><span>新しいBassを作ると、このスタイルで学んだ好みを反映して続けられます。</span></div> : <>
      <p className="taste-guide">比較 {completedPairKeys.size + 1}/{plans.length} · {modeLabels[mode]}で同じ伴奏条件を使います。{currentPlan ? pairReasonLabels[currentPlan.reason] : ''}。両方を聴くまで回答はできません。</p>
      <div className="taste-candidates">{(['first', 'second'] as const).map((position, index) => <div key={position}><b>候補 {index + 1}</b><button aria-label={`Bass比較候補 ${index + 1} を再生`} className={playing === position ? 'active' : ''} onClick={() => void audition(position)}>{playing === position ? '■ 停止' : '▶ 再生'}</button><small>{heard.has(position) ? '試聴済み' : '未試聴'}</small></div>)}</div>
      {!answered ? <div className="taste-answer"><button disabled={heard.size < 2 || busy} onClick={() => void answer('first')}>候補 1 が支える</button><button disabled={heard.size < 2 || busy} onClick={() => void answer('tie')}>差がない</button><button disabled={heard.size < 2 || busy} onClick={() => void answer('second')}>候補 2 が支える</button></div> : <div className="taste-result"><b>このスタイルの好みを学習しました</b><span>{hasRemainingPairs ? '回答を反映し、残りを学習に役立ちやすい順へ選び直しました。' : 'この候補セットで学んだ好みを次回の候補順位へ反映します。'}</span><button onClick={nextPair}>{hasRemainingPairs ? '次の組み合わせ' : 'この比較を完了'}</button></div>}
    </>}
    {ranges.length > 0 && <div className="taste-ranges">{ranges.map(([name, range]) => <div key={name}><span>{featureLabels[name] ?? name.replaceAll('_', ' ')}</span><i><em style={{ left: `${range.low * 100}%`, width: `${(range.high - range.low) * 100}%` }}/><b style={{ left: `${range.mean * 100}%` }}/></i><small>順位への根拠 {Math.round(rangeStrength(range) * 100)}% · 不確かさ {Math.round(range.uncertainty * 100)}%</small></div>)}</div>}
    <small className="taste-caveat">方向の好みと、比較で裏づけられた好みの帯を次回順位へ反映します。偶然似ただけの特徴や不確かな帯は反映しません。</small>
    {error && <p className="error">{error}</p>}
  </section>
}
