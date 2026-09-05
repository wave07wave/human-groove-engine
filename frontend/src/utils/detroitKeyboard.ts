import type { DetroitKeyboardSettings, KeyboardStyleMode } from '../types/generated'

export const DEFAULT_DETROIT_KEYBOARD: DetroitKeyboardSettings = {
  mode: 'standard',
  blend: { earl: 1 / 3, joe: 1 / 3, johnny: 1 / 3 },
}

export function withKeyboardBlendInfluence(
  settings: DetroitKeyboardSettings,
  key: keyof DetroitKeyboardSettings['blend'],
  amount: number,
): DetroitKeyboardSettings {
  const blend = { ...settings.blend, [key]: amount }
  if (blend.earl + blend.joe + blend.johnny <= 0) blend[key] = 0.01
  return { ...settings, blend }
}

export function normalizedKeyboardBlend(blend: DetroitKeyboardSettings['blend']) {
  const total = blend.earl + blend.joe + blend.johnny
  if (total <= 0) return { earl: 1 / 3, joe: 1 / 3, johnny: 1 / 3 }
  return {
    earl: blend.earl / total,
    joe: blend.joe / total,
    johnny: blend.johnny / total,
  }
}

export const DETROIT_KEYBOARD_OPTIONS: {
  value: KeyboardStyleMode
  label: string
  description: string
  features: string[]
}[] = [
  {
    value: 'standard',
    label: '標準',
    description: '素直なコード伴奏を中心に、既存のGrooveとBassを支えます。',
    features: ['中域中心', '安定した強弱', '控えめな装飾'],
  },
  {
    value: 'earl',
    label: 'Earl Van Dyke inspired',
    description: '低域から押し出す、力強くタイトなジャズ・ファンクのコンピング。',
    features: ['強いアタック', '低域の両手ボイシング', '前寄りのタイミング', 'ピアノ／オルガン'],
  },
  {
    value: 'joe',
    label: 'Joe Hunter inspired',
    description: 'ブルースとニューオーリンズの香りを持つ、転がるような伴奏。',
    features: ['3連の揺れ', '装飾音', '広い強弱', 'ドラムへの応答'],
  },
  {
    value: 'johnny',
    label: 'Johnny Griffith inspired',
    description: '美しいタッチと上声の動きで、主役を邪魔せず色彩を添えます。',
    features: ['高めの音域', '流麗なボイスリーディング', '旋律的な合いの手', '多彩な鍵盤音色'],
  },
  {
    value: 'blend',
    label: '3人をブレンド',
    description: '3人の影響度を混ぜ、強さ、揺れ、音域、装飾、音色を連続的に変えます。',
    features: ['影響度を個別調整', '固定フレーズなし', 'シードごとに変化'],
  },
]

export const DETROIT_KEYBOARD_DISCLAIMER =
  '歴史的な演奏特徴に着想を得た生成スタイルです。本人の演奏の完全な再現、公式な提携、既存録音の複製を意味するものではありません。'
