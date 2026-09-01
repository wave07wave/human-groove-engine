import type { DetroitSoulMode, DetroitSoulSettings } from '../types/generated'

export const DEFAULT_DETROIT_SOUL: DetroitSoulSettings = {
  mode: 'standard',
  blend: { benny: 1 / 3, pistol: 1 / 3, uriel: 1 / 3 },
}

export const DETROIT_SOUL_OPTIONS: {
  value: DetroitSoulMode
  label: string
  description: string
}[] = [
  { value: 'standard', label: '標準', description: 'ジャンルとGroove DNAを中心に生成します。' },
  { value: 'benny', label: 'Benny inspired', description: '最もタイト。前へ進むキック／スネアと、短く大胆なフィル。' },
  { value: 'pistol', label: 'Pistol inspired', description: '柔軟なポケット。強いバックビートと重いハイハットの会話。' },
  { value: 'uriel', label: 'Uriel inspired', description: '少し後ろ重心。広い間、ゴーストノート、強い一打。' },
  { value: 'blend', label: '3人をブレンド', description: '3つの演奏傾向を、指定した影響度で連続的に合成します。' },
]

export const DETROIT_SOUL_DISCLAIMER = '歴史的な演奏特徴に着想を得た生成スタイルです。本人の演奏の完全な再現、公式な提携、既存録音の複製を意味するものではありません。'
