import type { GrooveDNA, GroovePattern } from './types/generated'

export type DNAAdvancedTab = '拍の安定' | 'シンコペーション' | '楽器の噛み合い' | '強弱' | 'タイミング' | 'フレーズ' | '複雑さ'
export type AdvancedTab = DNAAdvancedTab | 'リスナー'
type AdvancedDNAGroup = { description: string, controls: [string, keyof GrooveDNA][] }

export const ADVANCED_DNA_GROUPS: Record<DNAAdvancedTab, AdvancedDNAGroup> = {
  '拍の安定': { description: '足元のパルス、拍の見え方、KickとBassの重心を整えます。', controls: [['パルスの安定度','pulse_stability'],['拍の明瞭さ','beat_salience'],['低音の軸','low_end_anchor']] },
  'シンコペーション': { description: '裏拍、先取り、意図的な音抜きと、その後の戻り方を作ります。', controls: [['裏拍の強さ','syncopation'],['先取り','anticipation'],['音抜き','omission'],['予想外の変化','surprise'],['戻りの強さ','recovery_strength']] },
  '楽器の噛み合い': { description: 'Kick、Bass、Percussionの会話と、身体が乗れる複雑さを調整します。', controls: [['楽器の噛み合い','interlock'],['身体が乗る度合い','motor_affordance']] },
  '強弱': { description: '主役と脇役の強弱差、Snareの小さなゴーストノートを整えます。', controls: [['強弱のコントラスト','velocity_contrast'],['ゴーストノート','ghost_density']] },
  'タイミング': { description: 'スウィング、前後の揺らぎ、短い音と長い音の差を作ります。', controls: [['スウィング','swing'],['タイミングの揺らぎ','microtiming'],['音の長さの差','duration_contrast']] },
  'フレーズ': { description: '同じモチーフを保ちながら、展開と着地の物語を作ります。', controls: [['反復','repetition'],['小節ごとの変化','variation'],['催眠的な反復','hypnotic'],['フレーズ展開','phrase_development']] },
  '複雑さ': { description: '音数と拍の曖昧さを別々に扱い、忙しさを狙って作ります。', controls: [['総合的な密度','density'],['拍の曖昧さ','metric_ambiguity']] },
}

export const advancedTabs: AdvancedTab[] = [
  ...(Object.keys(ADVANCED_DNA_GROUPS) as DNAAdvancedTab[]),
  'リスナー',
]

export const listenerMetrics: [string, keyof NonNullable<GroovePattern['analysis']>['listener']][] = [
  ['総合グルーヴ','predicted_groove'],['拍の確信度','beat_confidence'],['拍子の確信度','meter_confidence'],['身体の動き','movement_proxy'],['快さの代理値','pleasure_proxy'],['解決できる意外性','resolvable_surprise'],['退屈さ','boredom'],['混乱','confusion'],['刺激の強さ','irritation'],['評価の確信度','confidence'],
]
