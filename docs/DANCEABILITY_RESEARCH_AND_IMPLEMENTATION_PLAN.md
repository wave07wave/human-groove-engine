# 身体が動き出すリズム生成：深層リサーチと実装計画

作成日: 2026-08-31  
対象: Human Groove Engine 0.10 / Phase 25 完了時点  
状態: 実装完了（人間評価のデータ収集・効果判定はこれから）  
想定読者: プロダクト、音楽設計、バックエンド、フロントエンド、評価担当

## 1. 結論

次の強化では「踊れる度」という単一スコアを上げない。代わりに、次の循環を生成・解析・学習する **Embodied Groove Loop（身体化グルーヴ循環）** を実装する。

1. 複数の時間階層に、身体が追える安定した足場を作る。
2. 足場を壊し切らない範囲で、予測違反を置く。
3. 繰り返しによってパターンを身体に学習させる。
4. ブレイク、音抜き、レイヤー追加で期待を更新する。
5. 強い再着地によって同期を回復させる。
6. どの程度が心地よいかを、拍子・スタイル・テンポ・本人の反応から学ぶ。

実装の中心は次の8概念とする。

| 新概念 | 役割 | 現行機能との差 |
|---|---|---|
| Motor Scaffold Field | サブディビジョン、拍、ハーフタイム、1小節の各階層で「乗れる足場」を測る | `pulse_stability` という単一値を階層化 |
| Prediction-Error Budget | 予測違反の量、位置、集中、回収を測る | `surprise` の平均値から、文脈付きの違反設計へ |
| Embodied Complexity Envelope | その人・拍子・スタイルに合う複雑さの「幅」と不確実性を持つ | 0.48を頂点とする固定の逆U字を廃止 |
| Temporal Coherence Tensor | レーン間の前後関係、ばらつき、共通ドリフトを測る | ランダムなズレ量を「人間味」とみなさない |
| Kinetic Low-End Coupling | Kick/Bassの配置に加えて低域の変化量、立ち上がり、減衰を測る | 記号上の`low_end_anchor`を実音へ接続 |
| Motif Memory & Renewal | 覚えやすさ、ブレイク、レイヤー登場、再着地を測る | `repetition`と`variation`をフレーズ状態へ発展 |
| Personal Motor Resonance | 本人が無意識に刻みやすいテンポ帯を推定する | 外部音に合わせるTap-to-Grooveと分離 |
| Evidence Stack | 予測、自己申告、タップ、任意の身体運動を別々に扱う | 仮想リスナーの総合値を人間の反応と混同しない |

この方針は、現行の決定論的生成、21個のGrooveDNA、意図忠実度、個人のA/B学習、ブラインド評価を壊さずに追加できる。最初からGrooveDNAを増やすのではなく、まず解析専用の特徴量として検証し、人間による効果が確認できた要素だけを操作項目へ昇格させる。

### 実装状況（2026-08-31）

- Phase 26: `EmbodiedGrooveFeatures`、階層的な足場、予測誤差、タイミング整合性、低域・フレーズ解析を実装。
- Phase 27: 決定論的なchallenge / renewal介入アームと、Phase 25を保つbaselineを実装。
- Phase 28: 「動きたくなる」「心地よい」「拍が分かる」、任意タップ、明示同意した任意モーション要約の評価保存を実装。
- Phase 29: 任意の快適タップ校正、信頼度、倍／半分テンポ候補、BPM提案を実装。
- Phase 30: 通常可聴域の低域フラックス、Kick/Bassオンセット整合、低域エンベロープを参照レンダー解析へ実装。超低域生成は実装していない。
- Phase 31: スタイルの適用範囲と注意書きを持つ知識パック契約を実装し、範囲外では中立生成へ戻す。
- Phase 32: 同一匿名セッションの拍子・スタイル別フィードバックを、少数回答では中立へ縮退させながら候補アーム選択へ反映する基盤を実装。
- 継続改善: 個人内の介入アーム別サマリー、比較に必要な最小件数の表示、聴き慣れ／スタイル嗜好を分離した評価入力を実装。

人間評価の結果がまだないため、「人を踊らせる効果」は主張しない。実装済みなのは、その効果を安全に生成・測定・検証・個人適応できる基盤である。

## 2. 調査範囲と判断基準

### 2.1 今回調べた問い

- 何が「拍を理解できる」状態を作り、何が身体同期を促すのか。
- シンコペーション、複雑さ、反復、変化はどこまで増やすべきか。
- タイミングのズレは本当にグルーヴを強くするのか。
- 低音と身体運動の関係を、通常再生でどこまで利用できるか。
- 拍子、文化的な慣れ、演奏経験、好み、テンポの個人差をどう扱うか。
- 主観的な「動きたい」と実際の身体運動をどう分けて検証するか。
- 既存コードへ、後方互換かつ検証可能な形でどう追加するか。

### 2.2 情報源の優先順位

一次実験、モーションキャプチャ研究、自然なドラムパターンを使う大規模研究、文化横断研究、体系的レビューを優先した。理論論文は生成仮説を考える材料に使うが、単独では製品の既定値にしない。2026年8月31日時点で確認できる研究を対象とした。

### 2.3 対象外

- 医療、治療、神経学的効果の保証
- 全人類に共通する「最高のリズム」の断定
- 特定文化のリズムを民族属性から自動推定すること
- 可聴域外・超低域を一般端末で生成して身体効果をうたうこと
- カメラやモーションセンサーを既定で有効にすること
- 人間評価前に大規模な生成AIモデルを導入すること

## 3. 研究で分かったこと

### 3.1 複雑さの「中間が最高」は条件付き

[Witekらの統制実験](https://pmc.ncbi.nlm.nih.gov/articles/PMC3989225/)では、中程度のシンコペーションが「動きたい」と快感を最大化した。[リズムと和声の複雑さを独立操作した研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC6328141/)も、強い拍の足場と適度な複雑さの相互作用を支持する。

ただし、これは固定ルールにはできない。[熟練ドラマーが作った自然なパターンを使う2024年研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC11567550/)では明確な逆U字が再現されず、実験者が作った不自然な両極端刺激が初期知見を強めた可能性が示された。さらに[2025年の3実験](https://pmc.ncbi.nlm.nih.gov/articles/PMC12708351/)では、西洋の参加者における中程度の最適点は慣れた4/4でのみ現れ、慣れにくい拍子では単純なリズムの評価が最も高かった。

したがって、実装するのは固定の最適点ではなく **条件付きの複雑さ範囲** である。

- 初期状態では低・中・高の候補を均等に提示する。
- 4/4の集団事前分布を、5/8、7/8、9/8などへ流用しない。
- スタイルの好み、拍子への慣れ、音楽・ダンス経験、本人の選択で範囲を更新する。
- 証拠が少ない間は範囲を広く保ち、強い最適化をしない。

証拠強度: **中**。予測可能性と挑戦の相互作用は有力だが、最適点は刺激と人に依存する。

### 3.2 身体は一つの拍だけを追っていない

[自由な身体運動を計測した研究](https://pubmed.ncbi.nlm.nih.gov/28028583/)では、高いシンコペーションは全体の同期を弱め、手は細かく複雑に、胴体は主拍へ同期しやすかった。[全身モーションキャプチャ研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC4224089/)では、パルスの明瞭さは拍レベルの運動同期と、50–100 Hzの低域スペクトル変化は拍および小節レベルの運動同期と関連した。テンポが速いほど、身体はより遅い上位階層へ乗り換える傾向もあった。

したがって、単一の`beat_confidence`だけでは不足する。次の時間階層を別々に測る。

- subdivision: ハイハット、ゴースト、細かな手の運動の候補
- tactus: 足踏み、上下動の中心となる拍
- half/double time: テンポが速い・遅いときに自然に選ばれる代替周期
- bar cycle: 腰、左右スウェイ、フレーズの大きな周回

生成では「すべての階層を強くする」のではなく、少なくとも1階層を安定させ、別の階層に挑戦を置く。

証拠強度: **中**。階層的同期は支持されるが、特定の身体部位を必ず動かすという因果規則ではない。

### 3.3 人間味はランダムなズレではない

自然演奏の微細タイミングを扱った複数の研究は、「ズラすほど良い」を支持しない。[ジャズのタイミング研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC6934603/)では量子化版が僅かに高く評価され、ズレを拡大すると悪化した。[自然なズレを縮小したモーション研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC4542135/)では専門家に小さな運動効果があったが、普遍的ではない。[英国・ウルグアイ・マリの文化横断研究](https://pubmed.ncbi.nlm.nih.gov/35724531/)は、全体では楽器間の同期が好まれ、非等時性への好みは文化的な慣れと専門性に依存すると報告する。

したがって、`microtiming`はランダム量ではなく、次の構造へ置き換える。

- レーンごとの平均前後位置
- 同一レーン内の頑健なばらつき
- Kick–Snare、Kick–Bass、Hat–Snareの相対位相
- スウィング比の小節間一貫性
- 複数レーンが共有する緩やかなドリフト
- 無相関な高周波ジッターへの罰則

量子化されたタイトな演奏も、完全に正しいスタイル選択として残す。

証拠強度: **高**（ランダムジッターを避ける判断）。個別スタイルのズレ量については **中**。

### 3.4 低音は配置だけでなく、時間的な変化が重要

[モーションキャプチャ研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC4224089/)では、50–100 Hz帯のスペクトル変化と拍・小節レベルの同期が関連した。[ライブ会場で8–37 Hzを操作した研究](https://pubmed.ncbi.nlm.nih.gov/36347227/)では、意識的に検出しにくい超低域を加えた区間で観客の運動量が増えた。ただし後者は特殊なスピーカーを用いた限定的な因果実験であり、ノートPCや一般ヘッドホンで同じ効果を再現できる根拠ではない。

実装対象は、安全に通常再生できる範囲の次の解析である。

- 50–100 Hzを中心とする低域スペクトルフラックス
- KickとBassのオンセット一致・交互応答
- 低域同士の衝突と過長な減衰
- 拍・小節・フレーズ単位の低域エンベロープ
- オンセット明瞭度、ヘッドルーム、ラウドネス条件

可聴域外の合成、音量増加、身体効果の保証は行わない。

証拠強度: 通常低域の運動手掛かりとして **中**。超低域については再生条件の狭い因果証拠。

### 3.5 音数とレイヤーは、多ければ良いわけではない

[5ジャンル100例の研究](https://pubmed.ncbi.nlm.nih.gov/21728462/)は、拍の明瞭さと拍間イベント密度を有力な説明変数とした。一方、[248パターン・665人の自然パターン研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC6025871/)では、シンコペーションと密度の効果は小さく、スタイルの好みと既知感の効果がはるかに大きかった。ドラム単体では、密度が高いほど単に音が充実して聞こえる交絡もある。[2025年のレイヤー数研究](https://doi.org/10.1016/j.cognition.2025.106178)も、レイヤー数とシンコペーションの相互作用を報告している。

このため、評価時には音数、レイヤー数、音色、音量、BPM、拍子を可能な限り一致させる。生成では密度を単調に上げず、レイヤーの入退場と役割分担を操作する。

証拠強度: 拍の足場と拍間活動の併存は **中**。密度を増やす単純則は **低**。

### 3.6 反復は、記憶と更新の循環として設計する

[複数パートの入りを操作した研究](https://pubmed.ncbi.nlm.nih.gov/24979362/)では、同時に鳴る楽器数と段階的な登場がグルーヴ報告・感覚運動結合を高めた。[反復中のドラムブレイクを扱った研究](https://pubmed.ncbi.nlm.nih.gov/24972303/)は、ブレイクが予測更新に関わる領域を動員し、タップの変動も増やすことを示した。つまり変化は注意を戻す一方、一時的に同期を壊しうる。

[Learning Progressモデル](https://pmc.ncbi.nlm.nih.gov/articles/PMC10503533/)は、解消可能な予測誤差を徐々に学べることが快感と運動欲求を生むという有望な仮説だが、現時点では理論として扱う。

実装するフレーズ状態:

1. establish: 足場とモチーフを提示
2. reinforce: 主要輪郭を保って反復
3. challenge: 限定したシンコペーション、音抜き、レイヤー変化
4. release: ブレイクまたは密度低下
5. re-entry: 主拍、Kick/Bass、アクセントを再結合

証拠強度: ブレイクと登場が同期・注意を変える点は **中**。最適な循環長は **低〜中**で実験対象。

### 3.7 本人が刻みやすいテンポは固定値ではない

[自発運動テンポと好みの研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC9713942/)は、無音で自然に刻むテンポが音楽の好みのテンポへ寄与すると報告した。一方、[体系的レビュー](https://pmc.ncbi.nlm.nih.gov/articles/PMC10619865/)は年齢、課題、覚醒、状況による大きなばらつきを示す。約500–600 msを全員の正解にはできない。

既存のTap-to-Grooveは外部のリズムへ合わせた入力なので、別に「心地よい速さで刻む」任意校正を用意する。中央値だけでなく分散と再現性を保存し、ハーフ／ダブルテンポ候補も評価する。

証拠強度: **中**。

### 3.8 好み、慣れ、文化、場面を音楽特徴から切り離せない

[自然パターン研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC6025871/)では、スタイルの好みと既知感が記号的特徴より大きな説明力を持った。[拍子の文化的学習を扱う研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC5915898/)と[タイミング嗜好の文化横断研究](https://pubmed.ncbi.nlm.nih.gov/35724531/)は、拍子・非等時性の受け取り方に学習された事前分布があることを示す。

実装は「国籍や民族 → リズム」という推定をしない。本人が任意に示すスタイルへの慣れ、好み、ダンス経験と、実際の選択履歴だけを使う。集団の知見は適用範囲と出典を持つ知識パックとして扱い、本人の証拠を常に優先する。

証拠強度: 文脈が重要なことは **高**。製品内での最適な重みは **未確定**。

### 3.9 「動きたい」「気持ちいい」「実際に動く」は分けて測る

グルーヴ研究では両者が強く関連することが多いが、[自然刺激と個人差を扱う研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC11037533/)、[身体マップ研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC12503160/)、[音楽的無快感を扱う研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC11706506/)は、「動きたい」と快感が完全には同一でないことを示す。また、多くの研究は座った参加者の自己申告で、実際のダンスを観測していない。

評価は次の4層を混ぜない。

1. engine prediction: 解析モデルによる仮説
2. self report: 動きたい / 気持ちいい / 拍が分かる
3. synchronization: 任意のタップ位相・安定性
4. movement: 明示同意を得た端末モーションの周期・運動量

証拠強度: 分離して測る判断は **高**。人類共通の合格閾値は存在しない。

## 4. 現行エンジンの監査結果

### 4.1 すでに活用できる強み

- 21次元のGrooveDNAと意図許容差
- 構造的タイミングと微細タイミングの分離
- 拍子対応の弱拍、call / answer / turnaround
- Funk、Hip Hop、House、Rockの限定的な語彙
- GMD由来の決定論的パフォーマンスモデル
- 参照レンダーの低域衝突、マスキング、オンセット、ヘッドルーム解析
- 個人のA/B選択と信頼度制限付きの探索
- ランダム化ブラインド評価
- 生成の再現性、意図方向、候補多様性、レイテンシの技術監査
- 実音サンプルと速度依存のドラム再生

### 4.2 そのままでは危険な点

| 現状 | 問題 | 修正 |
|---|---|---|
| `motor_affordance = exp(-((difficulty - 0.48)^2)/0.12)` | 固定の中間最適を人間一般へ適用 | 文脈付き範囲と不確実性へ置換 |
| `predicted_groove` | 快感、運動、拍、意外性を混合 | 目的別の予測と根拠を分離 |
| `beat_confidence` / `meter_confidence` | 身体が乗る階層を区別しない | Motor Scaffold Fieldを追加 |
| `surprise` | 出現頻度中心で、音抜きと文化的拍子事前分布が弱い | Prediction-Error Budgetへ発展 |
| `microtiming` / irregularity | 一貫したポケットと無相関ジッターを区別しない | Temporal Coherence Tensorを追加 |
| `low_end_anchor` | 記号配置のみ | 通常低域の実音フラックスと減衰へ接続 |
| `repetition` / `variation` | 学習、ブレイク、再着地が明示状態でない | Motif Memory & Renewalを追加 |
| 評価の勝敗 | なぜ選んだか、身体反応か快感かが不明 | 結果別の評価イベントへ拡張 |

### 4.3 互換性上の重要判断

`GrooveDNA`のフィールドは個人学習、監査、UI、OpenAPI型へ自動的に波及する。研究段階の特徴をそこへ追加すると、未検証の概念が意図入力と学習特徴へ同時に入り、既存モデルも壊す。このため以下を守る。

- Phase 26–31ではGrooveDNAの21項目を維持する。
- 新特徴は`EmbodiedGrooveFeatures`という解析専用モデルへ追加する。
- ユーザー向けには技術名を見せず、「足場」「刺激」「戻り」「低音の動き」などの説明だけを表示する。
- 人間評価を通過した特徴だけを、将来のGrooveDNA v2候補にする。
- 既存Preference v1の保存データはそのまま読み、新文脈付きデータをv2イベントとして併存させる。

## 5. 目標アーキテクチャ

### 5.1 新しい解析契約

概念上、`GrooveAnalysis`へ次を追加する。すべて任意フィールドから開始し、旧クライアントを壊さない。

```text
EmbodiedGrooveFeatures
├─ schema_version
├─ motor_scaffold
│  ├─ subdivision {clarity, phase_stability, activity}
│  ├─ tactus      {clarity, phase_stability, activity}
│  ├─ half_time   {clarity, phase_stability, activity}
│  └─ bar_cycle   {clarity, phase_stability, activity}
├─ prediction_error
│  ├─ event_surprise
│  ├─ omission_surprise
│  ├─ concentration
│  ├─ recoverable_ratio
│  └─ context_confidence
├─ timing_coherence
│  ├─ lane_offsets
│  ├─ within_lane_dispersion
│  ├─ pairwise_phase_relations
│  ├─ shared_drift
│  └─ independent_jitter
├─ low_end_motion
│  ├─ symbolic_coupling
│  ├─ spectral_flux_50_100hz
│  ├─ onset_coherence
│  ├─ envelope_cycle
│  └─ render_applicable
├─ phrase_renewal
│  ├─ motif_memory
│  ├─ layer_entry_lift
│  ├─ challenge_strength
│  └─ reentry_strength
└─ estimates
   ├─ urge_to_move_prior
   ├─ pleasure_prior
   ├─ uncertainty
   └─ caveat
```

`urge_to_move_prior`と`pleasure_prior`は観測値ではなく、候補探索用の説明可能な事前予測である。UIには必ず「機械による予測」と表示し、本人の評価と別保存する。

### 5.2 Motor Scaffold Field

各楽器のオンセット列を、速度、一次役割、帯域クラスで重み付けする。拍子から得た候補周期ごとに以下を計算する。

- periodic energy: その周期に沿うエネルギー
- phase concentration: 小節間で位相が維持される度合い
- persistence: 途中で足場が消えない度合い
- ambiguity: 競合周期との差

初期式は校正前の工学指標として、`clarity = periodic_energy × phase_concentration × persistence`のような単調で説明可能な形にする。数値を心理学的確率とは呼ばない。

生成制約:

- tactusまたはhalf-timeのどちらかに最低足場を残す。
- challenge中も全レーン同時に足場を消さない。
- 高速BPMでは上位周期の足場候補を優先できる。
- subdivision活動が高くても、tactus位相を曖昧にし過ぎない候補を残す。

### 5.3 Prediction-Error Budget

現在の出現頻度に、拍子重力、楽器、フレーズ状態、スタイル知識を加えた平滑化確率を作る。

- 発音の驚き: `-log P(onset | instrument, position, phrase_state, context)`
- 音抜きの驚き: 強く期待される位置に音がない場合の`-log(1 - P(onset))`
- 集中: 驚きが一箇所へ過度集中していないか
- 回収: 違反後1〜2 tactus以内に強い足場へ戻るか
- 信頼度: その事前分布が対象の拍子・スタイル・本人にどれだけ適用可能か

最適化では平均値だけでなく、予算範囲、配置、回収率を使う。未知の拍子・スタイルでは一般的な拍子重力だけに縮退し、強い集団事前分布を使わない。

### 5.4 Embodied Complexity Envelope

複雑さを1点ではなく、`lower / preferred / upper / uncertainty / scope`で表す。初期値は固定の正解ではなく、候補集合の分位点を使って低・中・高を必ず探索する。

更新入力:

- meterとその慣れ
- styleとその慣れ・好み
- BPMと本人のMotor Tempo Profile
- groove・bassそれぞれのA/B選択
- urge-to-move、pleasureの自己申告
- 任意のtap/motion観測

集団事前分布より本人の反復証拠を強くする。少数回答では範囲を狭めない。異なる拍子・スタイル間で安易に学習を転移しない。

### 5.5 Temporal Coherence Tensor

マイクロタイミングを次の4層で分析する。

1. lane timing: 楽器ごとの平均オフセットと頑健分散
2. pair timing: Kick–Bass、Kick–Snareなどの相対差
3. subdivision timing: スウィング比と非等時性の一貫性
4. phrase timing: 複数レーンが共有する緩やかなドリフト

`independent_jitter`を明示し、高すぎる場合は候補探索で不利にする。一方、style packで根拠のある非等時性は、単なる不規則として罰しない。

### 5.6 Kinetic Low-End Coupling

記号解析とレンダー解析を分離する。

- symbolic: Kick/Bassの同時、応答、空間、主拍への寄与
- rendered: 50–100 Hz flux、オンセット、衝突、減衰、周期的エンベロープ
- playback caveat: プロファイルと再生機器に依存することを明示

既存の`RenderedAudioAnalysis`へ後方互換で追加し、レンダーしない高速探索では`render_applicable = false`にする。上位候補だけを二段目でレンダー解析する。

### 5.7 Motif Memory & Renewal

各フレーズに`establish / reinforce / challenge / release / re-entry`状態を付ける。既存のcall / answer / turnaroundをこの状態機械へ接続する。

- motif memory: 小節間の役割付き編集距離と反復間隔
- layer entry lift: 新しいレーンの登場によるエネルギー差
- challenge strength: 弱拍、音抜き、配置転換の総量
- re-entry strength: 主要Kick/Bass、Snare、Hat足場の同時回復

変化演算子は必ず名前とパラメータを持たせ、評価で因果比較できるようにする。

### 5.8 Personal Motor Resonance

任意の「心地よい速さで刻む」校正を追加する。

- 2ブロック×15タップを初期案とし、パイロットで調整する。
- 各ブロックの最初の3タップを慣らしとして除外する。
- inter-tap intervalの中央値、MAD、ブロック間一致を保存する。
- 0.5倍、1倍、2倍のテンポ別名を候補として持つ。
- 不一致が大きい場合は信頼度を下げ、テンポ推奨へ強く使わない。
- リセット、無効化、未保存の選択を可能にする。

この校正は外部音へ同期する既存Tap-to-Grooveとは別機能にする。

### 5.9 Evidence Stack

保存イベントを次に分ける。

```text
EmbodiedEvaluationEvent
├─ anonymous_session_id
├─ pattern_id / seed / engine_version / operator_arm
├─ meter / bpm / style / sound_profile
├─ self_report
│  ├─ urge_to_move
│  ├─ pleasure
│  ├─ beat_clarity
│  └─ familiarity / style_liking
├─ tap_observation? {phase_error, period_error, variability}
├─ motion_observation? {periodic_energy, movement_energy, device_quality}
├─ context? {headphones, speakers, seated, standing, social}
├─ consent_scope
└─ created_at
```

文化的属性を推定しない。必要なのは出身ではなく、その拍子・スタイルをどれだけ聴くかという本人申告である。モーションは明示同意、端末内特徴抽出、最小保存を原則とし、生のセンサーストリームは既定で保存しない。

## 6. 生成・探索アルゴリズム

### 6.1 単一スコアを使わない

既存Optimizerの多目的設計を維持し、次の目的ベクトルを使う。

```text
intent_fidelity
personal_preference
urge_to_move_prior
pleasure_prior
motor_scaffold
complexity_envelope_fit
prediction_error_recoverability
timing_coherence
render_quality
candidate_diversity
```

探索順:

1. 意図、ロック、拍子、MIDI安全性に違反する候補を除外。
2. 足場が消失する候補、回収不能な候補、無相関ジッター過多を除外。
3. Pareto frontを構成。
4. 低・中・高challengeと異なるフレーズ演算子から代表を選ぶ。
5. 上位だけを実音レンダー解析。
6. 本人の証拠が十分な範囲だけ、個人事前分布で再順位付け。

`urge_to_move_prior`が高くても、意図忠実度、快感、音質の悪化を隠してはならない。

### 6.2 因果比較可能な演算子

最初に導入する演算子は、強さ0/1/2の離散アームを持つ。

| 演算子 | 変更 | 保護条件 |
|---|---|---|
| single-strong-syncopation | フレーズ内に少数の強い弱拍イベント | tactus足場と次のrecoveryを保護 |
| fast-level-activity | Hat/Percussionへ拍間活動を追加 | 総音量と主要アクセントを一致 |
| layer-stagger | レーンを段階的に登場 | 比較時の最終レイヤー数を一致 |
| planned-omission | 期待位置を限定的に抜く | 全低域足場を同時に消さない |
| break-and-reentry | 低密度化後に主要役割を再結合 | re-entryの強度と位置を明示 |
| low-end-alternation | Kick/Bassの同時と応答を切替 | 低域衝突、音価、ヘッドルームを監視 |

連続ランダム変異だけでなく、どの演算子がどの結果を変えたか追跡できる候補を必ず混ぜる。

### 6.3 初期探索の安全策

- 複雑さの集団事前分布は候補生成比率にのみ使い、ユーザー意図を上書きしない。
- 4/4以外は、本人の証拠がなければchallengeを保守的にしつつ低・中・高を残す。
- style packが適用不能な場合は現行の中立な拍子対応生成へ戻る。
- モーション観測がないときに「実際に踊る確率」を出さない。
- 快感と運動欲求の予測が対立するときは両方を表示し、総合値へ隠さない。

## 7. 段階的実装計画

優先度は P0（必須）、P1（有力）、P2（検証後）で示す。工数は相対値 S / M / L であり、日数の約束ではない。

### Phase 26 — 測定基盤と契約分離（P0 / L）

目的: 未検証の最適化を始める前に、身体同期・快感・予測・タイミングを別々に観測可能にする。

主な変更:

- `backend/app/models/analysis.py`
  - `EmbodiedGrooveFeatures`と下位モデルを任意フィールドで追加
  - `ListenerAnalysis.predicted_groove`を残しつつ、deprecated予定の説明を追加
- `backend/app/analysis/embodied.py`（新規）
  - Motor Scaffold Field
  - Prediction-Error Budget
  - Motif Memory & Renewal
- `backend/app/analysis/timing_coherence.py`（新規）
  - lane / pair / subdivision / phrase timing
- `backend/app/analysis/listener.py`
  - urgeとpleasureの事前予測を別計算
  - 固定0.48のmotor式を探索目的から外す
- `frontend/src/components/ListenerPanel.tsx`と高度解析UI
  - 「動きたくなる予測」「心地よさ予測」「拍の足場」「戻り」を分離
  - 総合グルーヴを主役表示しない
- OpenAPI型を再生成し、旧レスポンス互換を維持

受け入れ基準:

- 既存パターンのJSONが変更なしで読み込める。
- 同じseed・要求から同じ生成結果と同じ解析値が得られる。
- tactusだけ強い、bar-cycleだけ強い、競合周期がある手作りfixtureを識別できる。
- 独立ランダムジッターはcoherenceを下げ、共通オフセットは同程度に罰しない。
- urgeとpleasureのフィールドは別々に変化できる。
- 既存の完全テスト、型検査、lint、production build、品質監査が通る。

### Phase 27 — 介入可能なフレーズ演算子（P0 / L）

目的: 研究知見を「何が効いたか検証できる」生成操作へ変換する。

主な変更:

- `backend/app/engine/embodied_operators.py`（新規）
  - 6演算子と0/1/2の介入レベル
- `backend/app/engine/phrase.py`
  - establish / reinforce / challenge / release / re-entry状態
- `backend/app/engine/rhythm_language.py`
  - 既存call / answer / turnaroundを状態へ接続
- `backend/app/engine/generator.py`
  - 候補集合に低・中・高challengeの層化サンプルを保証
- `backend/app/engine/optimizer.py`
  - 新特徴をPareto目的へ追加するが、個人データ前は強く順位付けしない

受け入れ基準:

- 各演算子を単独でON/OFFでき、差分イベントに出典ラベルが付く。
- 演算子OFFはPhase 25出力と一致する。
- challenge後1〜2 tactus内のrecovery制約が保たれる。
- 音数を合わせた対照候補を生成できる。
- 4/4、3/4、5/4、5/8、6/8、12/8で合法位置だけを使う。
- 既存のロック、保護オプション、Bass連携を破壊しない。

### Phase 28 — 人間評価の基盤とパイロット（P0 / L）

目的: 予測値を調整する前に、本人が「動きたい」と感じるかを正しく測る。

主な変更:

- `backend/app/models/evaluation.py`
  - `EmbodiedEvaluationEvent`、介入アーム、同意範囲を追加
- `backend/app/evaluation.py`
  - urge / pleasure / beat clarityを分離した試行
  - 順番のランダム化と再試行アンカー
- `frontend/src/components/BlindEvaluationPanel.tsx`
  - 非技術的な2問評価
  - 任意の拍タップ試行
- persistence
  - v2イベントテーブルを追加し、v1評価を変更しない
- 集計スクリプト
  - 参加者・刺激をランダム効果とするモデル用の匿名化出力

パイロット設計:

- Phase 25 baselineとPhase 27介入を、同じmeter、BPM、sound profile、概ね同じ音数で比較。
- 単独試聴では「動きたい」「心地よい」「拍が分かる」を0–100で別評価。
- A/Bではどちらを保存したいかと確信度を取得。
- 評価順、候補左右、演算子アームをランダム化。
- style liking、familiarity、音楽経験、dance affinity、再生環境は任意取得。
- 同一刺激を一部再提示し、回答一貫性を推定。
- 標本数は固定の思いつきで決めず、想定効果を複数置く事前power simulationで決める。

受け入れ基準:

- 主要評価項目、除外基準、比較、分析モデルを収集前に固定できる。
- v1とv2の結果が混ざらず、engine versionとoperator armを追跡できる。
- 不完全試行、極端に短い回答、端末品質不足をフラグ化できる。
- 本人がモーションや詳細属性を提供しなくても通常評価を完了できる。

### Phase 29 — Personal Motor Resonance（P1 / M）

目的: 全員を同じBPMへ寄せず、本人が自然に刻む周期を候補探索へ利用する。

主な変更:

- 無音・無メトロノームの快適タップUI
- robust median、MAD、block reliability、tempo alias推定
- `preference_scope.py`へBPM範囲と信頼度を追加
- 候補BPMの提案にだけ利用し、ユーザー指定BPMを上書きしない

受け入れ基準:

- 少ない／不安定／加速するタップでは低信頼となる。
- 0.5倍・2倍の誤同定を候補として保持する。
- 校正なし、保存なし、リセットで完全に従来動作へ戻る。
- 外部リズムに合わせるTap-to-Grooveとデータ・説明が混ざらない。

### Phase 30 — 低域と実音の身体手掛かり（P1 / M）

目的: 記号上のKick/Bass関係を、通常再生で聞こえる低域の動きへ接続する。

主な変更:

- `backend/app/audio/render_analysis.py`
  - 50–100 Hz flux、低域周期エンベロープ、kick/bass onset coherence、decay crowding
- 音源プロファイルへ安全な帯域・減衰メタデータを追加
- optimizerの二段階解析
  - 全候補は記号解析
  - 上位候補だけ実音解析
- UIに再生機器依存の注意書き

受け入れ基準:

- Kick配置が同じでも、音源減衰やBass重なりの違いを区別できる。
- 低域を増幅するだけでスコアが上がらない。
- headroomとtransient maskingの既存安全基準を維持する。
- 8–37 Hz合成や自動音量増加を行わない。
- 実音解析なしでは低域効果を断定しない。

### Phase 31 — 拍子・スタイル知識パック（P1 / L）

目的: 西洋4/4のルールを全拍子・全ユーザーへ誤適用せず、根拠ある文脈だけを使う。

知識パックの必須メタデータ:

- `pack_id` / `version`
- meter family / tempo scope / instrument scope
- source corpus / license / provenance
- listener scope and research caveat
- timing relations and uncertainty
- allowed operators and protected anchors
- validation status

最初は現行のFunk、Hip Hop、House、Rockをv1 packへ移し、挙動を変えずに契約だけ作る。新文化・新スタイルは、権利確認済みコーパス、演奏実態、当該スタイルに詳しい人の評価が揃ってから追加する。

受け入れ基準:

- 適用範囲外では中立エンジンへ戻る。
- パック名だけで国籍・民族・文化的好みを推定しない。
- timing規則に出典、データ範囲、信頼度がある。
- 未知meterへ4/4の複雑さ事前分布を適用しない。
- パックごとの回帰fixtureとブラインド評価結果を保存する。

### Phase 32 — 証拠に基づく適応探索と段階公開（P2 / L）

目的: 十分な人間証拠がある範囲だけ、候補探索を個人へ適応させる。

主な変更:

- contextual preference model v2
  - meter、BPM、style familiarity、operator arm、Embodied特徴を条件化
- uncertainty-aware search
  - 探索と活用の割合を信頼度で調整
- multi-objective feedback
  - save preference、urge、pleasure、tap/motionを別目的で保持
- feature flagと段階公開
  - measurement-only → suggested → adaptive → default

受け入れ基準:

- 少数回答で一つのスタイルへ固定しない。
- 異なるmeter/styleへの転移量に上限がある。
- 本人の最近の一貫した証拠が集団事前分布を上書きできる。
- 予測根拠と信頼度を説明できる。
- holdout seed、未学習BPM、未学習音色で改善が再現する。
- 改善がないセグメントでは自動的にPhase 25相当へフォールバックする。

## 8. テスト戦略

### 8.1 単体テスト

- metric-level scaffoldを既知の人工パターンで検証
- 発音驚き、音抜き驚き、回収位置の境界条件
- lane offset、shared drift、independent jitterの分離
- motif recurrenceとre-entryの既知値fixture
- 50–100 Hz fluxの合成参照信号
- Motor Tempo Profileの外れ値、倍テンポ、低信頼
- 知識パックのscope、license、fallback検証

### 8.2 性質ベーステスト

- seed決定性
- meter内の合法tick
- ロック済みevent不変
- velocity、duration、micro offsetの範囲
- challengeを上げても最低scaffoldを破壊しない
- recoveryを上げると回収不能率が悪化しない
- independent jitterを上げるとcoherenceが改善しない
- 低域ゲインだけでqualityが単調増加しない

### 8.3 回帰テスト

- Phase 25 flag OFF時のgolden一致
- 21 GrooveDNA方向監査
- preference v1の読み込みと選択再現
- frontendの旧保存データ復元
- MIDI exportの同一性
- 実音サンプルのライセンス・notice維持

### 8.4 性能テスト

- 記号解析は全候補、実音解析はshortlistだけに限定
- 現行の品質監査レイテンシ上限を維持
- 新機能OFF時のp95を現行から実質悪化させない
- 新機能ON時は各段のp50 / p95 / worstを別記録
- 低性能端末ではmotion/tap解析を停止しても生成を継続

## 9. 人間評価計画

### 9.1 主要仮説

H1: 階層的な足場を保ったchallenge候補は、音数・音色・BPMを合わせたPhase 25候補よりurge-to-moveが高い。  
H2: challenge後の強いre-entryは、同量の変化をランダム配置した候補よりurge-to-moveとbeat clarityが高い。  
H3: independent jitterはtiming coherenceと選好を下げ、coherent style timingは対象スタイルに慣れた参加者でのみ改善する可能性がある。  
H4: 個人Motor Tempoに近い候補は遠い候補より好まれるが、倍・半分周期を考慮する必要がある。  
H5: 実音低域fluxは記号上のlow-end anchorを超えて任意の運動観測を説明するが、再生環境によって効果が変わる。

### 9.2 評価の順序

1. Technical intervention check
   - 各演算子が意図した特徴だけを主に変えるか。
2. Small pilot
   - 質問理解、疲労、試行時間、音量一致、効果分散を確認。
3. Powered confirmatory study
   - パイロットから分散を推定して事前power simulation。
4. Ecological validation
   - 本人の制作セッション内で、保存率、完成時間、再試聴選択を確認。
5. Optional movement study
   - 明示同意した立位参加者で、タップ以外の周期運動を検証。

### 9.3 統計と報告

- participantとstimulusにランダム切片・必要なランダム傾きを持つmixed-effects modelを基本にする。
- 主解析、除外、変換、停止条件を収集前に固定する。
- 平均だけでなく効果量、信頼区間、meter/style/familiarity別の異質性を報告する。
- 多重比較を補正し、探索分析と確認分析を明記する。
- producer、drummer、general listener、dance affinityの高低を一つに潰さない。
- 勝率だけでなくtie、無回答、回答時間、再試行一致を含める。
- 客観的なmotion改善を測っていない段階では「人を踊らせる」と表現しない。

### 9.4 公開ゲート

新しい探索重みを既定にするには、次をすべて満たす。

- 技術ゲート: 決定性、意図、ロック、拍子、MIDI、音量安全、性能が合格。
- 主観ゲート: 事前指定した対象範囲でurge-to-moveが改善し、pleasureが悪化しない。
- 一般化ゲート: holdout seed、BPM、sound profileで方向が再現。
- 異質性ゲート: 改善しないmeter/style/経験層を把握し、誤適用を止められる。
- 説明ゲート: どの演算子と証拠が順位を変えたか追跡できる。
- 表現ゲート: UIの言葉が測定した証拠の範囲を超えない。

「実際の身体運動が増える」と告知する場合だけは、さらに任意motion観測で改善を確認する。

## 10. データ、プライバシー、倫理

- 収集は必要最小限とし、評価なしでも生成機能を使える。
- 生のマイク、カメラ、モーション波形は既定で保存しない。
- 端末内で周期・運動量へ要約し、同意範囲をイベントへ記録する。
- 国籍、民族、推定文化属性を生成条件にしない。
- style familiarityは本人申告または本人の選択履歴だけを使う。
- profileのエクスポート、リセット、削除を可能にする。
- 音量を上げて評価を稼がないようラウドネスを一致させる。
- 聴覚保護のためheadroom、ピーク、安全な既定音量を維持する。
- 外部コーパスと音源はlicense、出典、用途を知識パックへ固定する。

## 11. 主なリスクと対策

| リスク | 起きること | 対策 |
|---|---|---|
| Proxy Goodhart | 機械スコアだけ高く、不自然になる | 目的分離、対照アーム、人間評価、上限付き重み |
| 西洋4/4偏重 | 他拍子を「複雑で悪い」と誤判定 | scope付きprior、中立fallback、本人証拠優先 |
| novelty効果 | 初回だけ新鮮な候補を過大評価 | 再提示、一貫性、長期保存・再試聴を測定 |
| 音量・音色交絡 | 大きい／厚い音が勝つ | ラウドネス、音数、レイヤー、profileを一致 |
| microtiming神話 | ランダムジッターが増える | coherence計測、quantizedを正当な選択として保持 |
| 低音の誇張 | 再生不能な超低域効果をうたう | 50–100 Hz通常解析、VLF非実装、機器依存表示 |
| 個人過学習 | 少数回答で候補が単調になる | 不確実性、探索率、scope別履歴、リセット |
| センサーの侵襲性 | 信頼と利用率を損なう | 完全任意、端末内要約、生データ非保存 |
| 疲労・需要特性 | 評価が実際の制作と乖離 | 短いブロック、順番無作為化、自然制作で再検証 |
| 遅延 | 実音解析で操作感が悪化 | 二段shortlist、cache、feature flag、性能gate |

## 12. 実装順と停止条件

実装順は次の通りとする。

1. Phase 26で測れるようにする。
2. Phase 27で因果比較できる操作を作る。
3. Phase 28で人間パイロットを行う。
4. 証拠が得られた軸だけPhase 29–31へ進める。
5. 十分な個人データが集まった範囲だけPhase 32で適応する。

停止または見直し条件:

- urge-to-moveと既存意図忠実度が持続的にトレードオフになる。
- 効果が音量、音数、音色だけで説明される。
- 特定meter/style以外へ一般化しないのにscope制御できない。
- 自己申告改善が再試行で再現しない。
- モデルの信頼度と実際の誤差が校正されない。
- UIが非技術ユーザーへ誤った科学的確実性を与える。

この場合、新特徴は解析・実験フラグに留め、Phase 25を既定として維持する。

## 13. 完了定義

この計画全体の完了は「新しいスコアが追加されたこと」ではない。次を満たした状態とする。

- 人が乗るための足場、挑戦、記憶、再着地、低域、タイミングを別々に説明できる。
- 同じ音量・音色・BPM条件で、各演算子の効果を比較できる。
- urge-to-move、pleasure、tap、motionが混ざらず保存される。
- 個人差と拍子・スタイルの適用範囲が不確実性込みで扱われる。
- 結果が出ない人・拍子・スタイルでは安全に従来エンジンへ戻る。
- 実際の人間評価が、技術代理指標より優先される。
- 「最高」「人間なら踊る」という普遍的主張をせず、対象範囲と証拠を示せる。

## 14. 主要参考文献

### 複雑さ、予測、運動欲求

- Witek, M. A. G. et al. (2014). [Syncopation, Body-Movement and Pleasure in Groove Music](https://pmc.ncbi.nlm.nih.gov/articles/PMC3989225/). PLOS ONE.
- Witek, M. A. G. et al. (2017). [Syncopation affects free body-movement in musical groove](https://pubmed.ncbi.nlm.nih.gov/28028583/). Experimental Brain Research.
- Matthews, T. E. et al. (2019). [The sensation of groove is affected by the interaction of rhythmic and harmonic complexity](https://pmc.ncbi.nlm.nih.gov/articles/PMC6328141/). PLOS ONE.
- Hosken, F. et al. (2024). [Null effect of perceived drum pattern complexity on experience of groove](https://pmc.ncbi.nlm.nih.gov/articles/PMC11567550/). PLOS ONE.
- Spiech, C. R. et al. (2025). [4/4 and more, rhythmic complexity more strongly predicts groove in common meters](https://pmc.ncbi.nlm.nih.gov/articles/PMC12708351/). Scientific Reports.
- Matthews, T. E. et al. (2024). [Predictive coding in musical anhedonia: A study of groove](https://pmc.ncbi.nlm.nih.gov/articles/PMC11037533/). PLOS ONE.
- Vuust, P. & Witek, M. A. G. (2014). [Rhythmic complexity and predictive coding](https://pmc.ncbi.nlm.nih.gov/articles/PMC4181238/). Frontiers in Psychology.
- Matthews, T. E. et al. (2023). [The Pleasurable Urge to Move to Music Through the Lens of Learning Progress](https://pmc.ncbi.nlm.nih.gov/articles/PMC10503533/). Journal of Cognition.

### 身体同期、低音、レイヤー、フレーズ

- Burger, B. et al. (2014). [Hunting for the beat in the body](https://pmc.ncbi.nlm.nih.gov/articles/PMC4224089/). Frontiers in Human Neuroscience.
- Cameron, D. J. et al. (2022). [Undetectable very-low frequency sound increases dancing at a live concert](https://pubmed.ncbi.nlm.nih.gov/36347227/). Current Biology.
- Madison, G. et al. (2011). [Modeling the tendency for music to induce movement in humans](https://pubmed.ncbi.nlm.nih.gov/21728462/). Music Perception.
- Senn, O. et al. (2018). [Groove in drum patterns as a function of both rhythmic properties and listeners' attitudes](https://pmc.ncbi.nlm.nih.gov/articles/PMC6025871/). PLOS ONE.
- Madison, G. & Sioros, G. (2014). [What musicians do to induce the sensation of groove](https://pmc.ncbi.nlm.nih.gov/articles/PMC4137755/). Frontiers in Psychology.
- Sioros, G. et al. (2014). [Syncopation creates the sensation of groove in synthesized music examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC4165312/). Frontiers in Psychology.
- Stupacher, J. et al. (2014). [When the bass starts to groove: Staggered entrances to multipart music enhance movement and reward](https://pubmed.ncbi.nlm.nih.gov/24979362/). PLOS ONE.
- Danielsen, A. et al. (2014). [The sound of surprise: Musical breaks and prediction update](https://pubmed.ncbi.nlm.nih.gov/24972303/). Cerebral Cortex.
- Seeberg, A. B. et al. (2025). [Beyond syncopation: The number of rhythmic layers shapes the pleasurable urge to move to music](https://doi.org/10.1016/j.cognition.2025.106178). Cognition.

### 微細タイミング、文化、個人差

- Datseris, G. et al. (2019). [Microtiming Deviations and Swing Feel in Jazz](https://pmc.ncbi.nlm.nih.gov/articles/PMC6934603/). Scientific Reports.
- Kilchenmann, L. & Senn, O. (2015). [Microtiming in Swing and Funk affects the body movement behavior of music expert listeners](https://pmc.ncbi.nlm.nih.gov/articles/PMC4542135/). Frontiers in Psychology.
- Jakubowski, K. et al. (2022). [Aesthetics of musical timing: Culture and expertise affect preferences for isochrony but not synchrony](https://pubmed.ncbi.nlm.nih.gov/35724531/). Cognition.
- Hannon, E. E. et al. (2018). [Effects of enculturation on metric perception](https://pmc.ncbi.nlm.nih.gov/articles/PMC5915898/). Neuropsychologia.
- Hine, K. et al. (2022). [Spontaneous motor tempo contributes to preferred music tempo regardless of familiarity](https://pmc.ncbi.nlm.nih.gov/articles/PMC9713942/). Frontiers in Psychology.
- Rocha, S. et al. (2023). [Which factors modulate spontaneous motor tempo? A systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10619865/).

### 測定の分離

- Janata, P. et al. (2012). [Sensorimotor coupling in music and the psychology of the groove](https://pubmed.ncbi.nlm.nih.gov/21767048/). Journal of Experimental Psychology: General.
- Matthews, T. E. et al. (2025). [Body maps of the sensation of musical groove](https://pmc.ncbi.nlm.nih.gov/articles/PMC12503160/). PNAS Nexus.
- Romkey, I. D. et al. (2025). [The pleasurable urge to move to music is unchanged in people with musical anhedonia](https://pmc.ncbi.nlm.nih.gov/articles/PMC11706506/). PLOS ONE.

---

この文書は研究知見を実装仮説へ変換した計画であり、各特徴が特定の個人を踊らせることを保証するものではない。Phase 28の人間評価を通過するまでは、新しい予測値を実験的指標として扱う。
