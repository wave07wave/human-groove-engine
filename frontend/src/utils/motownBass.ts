import type { MotownBassMode, MotownBassSettings } from '../types/generated'

export const DEFAULT_MOTOWN_BASS: MotownBassSettings = { mode: 'standard' }

export const MOTOWN_BASS_OPTIONS: {
  value: MotownBassMode
  label: string
  description: string
  features: string[]
}[] = [
  {
    value: 'standard',
    label: '標準',
    description: '既存のBass生成を変更せず、そのまま使用します。',
    features: ['既存設定を保持', 'ジャンル／役割プリセットを優先'],
  },
  {
    value: 'jamerson',
    label: 'Jamerson inspired',
    description: '歌うような動きと前へ進むシンコペーションを、低音の土台と両立します。',
    features: [
      'クロマチックな接近',
      'コードトーンの輪郭',
      'ゴースト／ミュート',
      'キックとの応答',
      '小節ごとの自然な変化',
      'フレーズ終端の解決',
      'BPMに応じた音数補正',
    ],
  },
]

export const MOTOWN_BASS_DISCLAIMER =
  '歴史的な演奏特徴に着想を得た生成スタイルです。本人の演奏の完全な再現、公式な提携、既存録音の複製を意味するものではありません。'
