import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { EmbodiedEvaluationSummary, GroovePattern, MotorTempoProfile } from '../types/generated'

const sessionKey = 'hge-embodied-session-v1'
let memorySessionId: string | null = null

export function anonymousSessionId() {
  let storage: Storage | null = null
  try { storage = globalThis.localStorage ?? null } catch { storage = null }
  const existing = storage?.getItem(sessionKey)
  if (existing) return existing
  if (memorySessionId) return memorySessionId
  const value = globalThis.crypto?.randomUUID?.().replaceAll('_', '-') ?? `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
  try { storage?.setItem(sessionKey, value) } catch { /* in-memory fallback for private/test contexts */ }
  memorySessionId = value
  return value
}

function tapVariability(taps: number[]) {
  if (taps.length < 4) return null
  const intervals = taps.slice(1).map((value, index) => value - taps[index])
  const median = [...intervals].sort((a, b) => a - b)[Math.floor(intervals.length / 2)]
  return Math.min(1, intervals.reduce((sum, value) => sum + Math.abs(value - median), 0) / intervals.length / Math.max(1, median))
}

export function EmbodiedFeedbackPanel({ pattern, onTempoSuggested }: { pattern: GroovePattern, onTempoSuggested?: (bpm:number) => void }) {
  const [urge, setUrge] = useState(50); const [pleasure, setPleasure] = useState(50); const [clarity, setClarity] = useState(50); const [familiarity, setFamiliarity] = useState(50); const [styleLiking, setStyleLiking] = useState(50)
  const [taps, setTaps] = useState<number[]>([]); const [calibration, setCalibration] = useState<number[]>([])
  const [profile, setProfile] = useState<MotorTempoProfile | null>(null); const [message, setMessage] = useState('')
  const [motionConsent, setMotionConsent] = useState(false); const [motion, setMotion] = useState<{periodic_energy:number,movement_energy:number,device_quality:number}|null>(null)
  const [summary, setSummary] = useState<EmbodiedEvaluationSummary | null>(null)
  const motionSamples = useRef<number[]>([])
  const refreshSummary = () => api.embodiedEvaluationSummary(anonymousSessionId()).then(setSummary).catch(() => undefined)
  useEffect(() => { void refreshSummary() }, [])
  const tap = () => setTaps(current => [...current, performance.now()].slice(-24))
  const calibrateTap = () => setCalibration(current => [...current, performance.now()].slice(-24))
  const finishCalibration = async () => {
    try { const next = await api.calibrateMotorTempo(anonymousSessionId(), calibration); setProfile(next); if (next.confidence >= .35) onTempoSuggested?.(next.bpm); setMessage(`自然なテンポ: ${Math.round(next.bpm)} BPM（信頼度 ${Math.round(next.confidence * 100)}%）`); setCalibration([]) }
    catch (error) { setMessage(`校正できませんでした: ${String(error)}`) }
  }
  const captureMotion = async () => {
    if (!motionConsent) { setMessage('動きの計測に同意してください。'); return }
    const Motion = DeviceMotionEvent as typeof DeviceMotionEvent & { requestPermission?: () => Promise<'granted'|'denied'> }
    if (Motion.requestPermission && await Motion.requestPermission() !== 'granted') { setMessage('端末が動きの計測を許可しませんでした。'); return }
    motionSamples.current = []
    const listener = (event: DeviceMotionEvent) => { const value = event.accelerationIncludingGravity; if (value) motionSamples.current.push(Math.hypot(value.x ?? 0, value.y ?? 0, value.z ?? 0)) }
    window.addEventListener('devicemotion', listener); setMessage('6秒間、好きに体を動かしてください。')
    window.setTimeout(() => { window.removeEventListener('devicemotion', listener); const values = motionSamples.current; const mean = values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length); const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / Math.max(1, values.length); setMotion({ movement_energy:Math.min(1, mean / 18), periodic_energy:Math.min(1, Math.sqrt(variance) / 8), device_quality:Math.min(1, values.length / 80) }); setMessage(values.length ? '動きの要約を用意しました。生のセンサー値は保存しません。' : '動きを取得できませんでした。') }, 6000)
  }
  const submit = async () => {
    try {
      const result = await api.submitEmbodiedEvaluation({ anonymous_session_id:anonymousSessionId(), pattern, urge_to_move:urge, pleasure, beat_clarity:clarity, familiarity, style_liking:styleLiking, listening_context:'unknown', posture:'unknown', motion_consent:motionConsent, tap_observation:taps.length >= 4 ? { phase_error:null, period_error:null, variability:tapVariability(taps) } : undefined, motion_observation:motion ?? undefined })
      setMessage(result.evidence_class === 'motion' ? '主観評価と動きの要約を保存しました。' : '主観評価を保存しました。'); void refreshSummary()
    } catch (error) { setMessage(`保存できませんでした: ${String(error)}`) }
  }
  const sliders: [string, number, (value:number) => void][] = [['動きたくなる',urge,setUrge],['心地よい',pleasure,setPleasure],['拍が分かる',clarity,setClarity],['聴き慣れ',familiarity,setFamiliarity],['スタイルの好み',styleLiking,setStyleLiking]]
  return <section className="embodied-feedback panel"><div><p className="eyebrow">身体のフィードバック</p><h2>動きたくなる感覚を教えてください</h2><p className="muted">予測値の学習用です。動きや個人情報を出さなくても使えます。</p></div><div className="embodied-sliders">{sliders.map(([label,value,setter])=><label key={label}><span>{label}</span><input type="range" min="0" max="100" value={value} onChange={event => setter(Number(event.target.value))}/><b>{value}</b></label>)}</div><div className="embodied-actions"><button onClick={tap}>● 拍に合わせてタップ</button><small>{taps.length} taps</small><button onClick={() => void submit()}>評価を保存</button></div><div className="motor-tempo"><b>自分の自然なテンポ</b><small>音なしで気持ちよく12回以上タップします。</small><button onClick={calibrateTap}>● 自然にタップ</button><span>{calibration.length} taps</span><button disabled={calibration.length < 12} onClick={() => void finishCalibration()}>テンポを測る</button>{profile&&<em>{Math.round(profile.bpm)} BPM · {profile.tempo_aliases.map(value=>Math.round(value)).join(' / ')}</em>}</div><div className="motion-feedback"><label><input type="checkbox" checked={motionConsent} onChange={event=>setMotionConsent(event.target.checked)}/> 6秒間の動きの要約を、この評価に使う</label><button disabled={!motionConsent} onClick={() => void captureMotion()}>動きを計測</button><small>生のモーション値は保存しません。</small></div>{summary&&<div className="embodied-summary"><b>あなたの評価傾向 · {summary.total_evaluations}件</b>{summary.operator_arms.map(arm=><span key={arm.operator_arm}>{arm.operator_arm} · 動 {Math.round(arm.average_urge_to_move)} / 心 {Math.round(arm.average_pleasure)} <small>({arm.evaluations}件)</small></span>)}<small>{summary.sufficient_for_personal_comparison ? '個人内の比較の目安が集まりました。' : `各アーム${summary.minimum_evaluations_per_arm}件以上で比較の目安になります。`}</small></div>}{message&&<p className="capture-notice">{message}</p>}</section>
}
