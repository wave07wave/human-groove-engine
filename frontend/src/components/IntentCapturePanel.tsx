import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { GrooveIntent } from '../types/generated'

type ApplyOptions = { bpm?: number, style?: string, notice?: string }
type Props = {
  intent: GrooveIntent
  onApply: (intent: GrooveIntent, options?: ApplyOptions) => void
}

const defaultCurve = [.3, .58, .82, .38]

function encodeBase64(bytes: Uint8Array) {
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192))
  }
  return btoa(binary)
}

export function IntentCapturePanel({ intent, onApply }: Props) {
  const [taps, setTaps] = useState<number[]>([])
  const [direction, setDirection] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const curve = useMemo(() => intent.phrase_energy_curve?.length === 4 ? intent.phrase_energy_curve : defaultCurve, [intent.phrase_energy_curve])

  const tap = () => {
    const now = performance.now()
    setTaps(current => current.length && now - current[current.length - 1] > 2500 ? [now] : [...current, now].slice(-16))
    setNotice('')
  }
  const applyTaps = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.analyzeTaps(taps, intent)
      onApply(result.suggested_intent, { bpm: result.bpm, notice: `タップ ${result.accepted_taps}回 · ${Math.round(result.bpm)} BPM · 信頼度 ${Math.round(result.confidence * 100)}%` })
      setNotice('タップのテンポと揺れを反映しました。')
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const applyMidi = async (file: File | undefined) => {
    if (!file) return
    if (file.size > 2_000_000) { setError('MIDIは2MB以下にしてください。'); return }
    setBusy(true); setError('')
    try {
      const payload = encodeBase64(new Uint8Array(await file.arrayBuffer()))
      const result = await api.analyzeMidi(file.name, payload, intent)
      onApply(result.suggested_intent, { bpm: result.bpm, notice: `${result.hit_count}打点を解析 · ${Math.round(result.bpm)} BPM · ${result.meter.numerator}/${result.meter.denominator}` })
      setNotice('MIDIのリズム特性を反映しました。ファイルは保存していません。')
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const applyDirection = async () => {
    if (!direction.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api.transformIntent(direction, intent)
      if (!result.changes.length) { setNotice('対応する音楽表現が見つからなかったため、設定は変更していません。'); return }
      onApply(result.intent, { style: result.suggested_style ?? undefined, notice: `${result.changes.length}項目を変更` })
      setNotice(`${result.changes.map(change => change.dimension.replaceAll('_', ' ')).join('・')} を調整しました。`)
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const updateCurve = (index: number, value: number) => {
    const next = [...curve]; next[index] = value
    onApply({ ...intent, phrase_energy_curve: next }, { notice: 'フレーズのエネルギー曲線を更新' })
  }

  return <section className="intent-capture panel">
    <div className="capture-title"><div><p className="eyebrow">感じ方から作る</p><h2>叩く・読み込む・言葉で伝える</h2></div><small>すべてIntentへ変換してから生成します</small></div>
    <div className="capture-grid">
      <div className="tap-capture"><b>タップ</b><p>ボタンを拍に合わせて3回以上叩きます。</p><div><button disabled={busy} onClick={tap}>● TAP</button><span>{taps.length} taps</span><button disabled={busy || taps.length < 3} onClick={applyTaps}>反映</button><button disabled={!taps.length} onClick={() => setTaps([])}>消去</button></div></div>
      <div><b>MIDIを参照</b><p>ドラムMIDIの特徴だけを抽出します。データは保存しません。</p><label className="midi-reference">MIDIを選択<input type="file" accept=".mid,.midi,audio/midi" disabled={busy} onChange={event => void applyMidi(event.target.files?.[0])}/></label></div>
      <div><b>言葉で調整</b><p>例：もっと跳ねてファンキーに／後ろへ溜める／シンプルに</p><div className="direction-input"><input value={direction} maxLength={240} onChange={event => setDirection(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void applyDirection() }} placeholder="どんなノリにしたい？"/><button disabled={busy || !direction.trim()} onClick={applyDirection}>適用</button></div></div>
    </div>
    <div className="energy-curve"><div><b>フレーズの流れ</b><small>導入 → 展開 → 山場 → 着地</small></div>{curve.map((value, index) => <label key={index}><span>{['導入','展開','山場','着地'][index]}</span><input aria-label={`energy point ${index + 1}`} type="range" min="0" max="1" step=".01" value={value} onChange={event => updateCurve(index, Number(event.target.value))}/><em>{Math.round(value * 100)}</em></label>)}<button onClick={() => onApply({ ...intent, phrase_energy_curve: [] }, { notice: '自動フレーズ曲線へ戻しました' })}>自動</button></div>
    {notice&&<p className="capture-notice">{notice}</p>}{error&&<p className="error">{error}</p>}
  </section>
}
