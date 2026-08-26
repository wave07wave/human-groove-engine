# Human Bass Engine × Human Groove Engine 統合計画書

## 1. 目的

Human Groove Engine（HGE）をリズム生成の所有者、Human Bass Engine（HBE）をBass生成の所有者とし、
内部クラスを直接共有せず、versioned DTOと明示的なInteraction Contractだけで統合する。

統合後も次の性質を維持する。

- 同一入力・Seed・Engine Versionから同一結果を生成する。
- FOLLOWではGroove Eventを一切変更しない。
- NEGOTIATE / CO-CREATEでもLock済みまたはUser Edited Eventを無断変更しない。
- Bass単体生成・編集・MIDI ExportはGroove Engineなしでも動作する。
- Target、Measured DNA、Listener評価を混同しない。
- 変更理由とChange CostをAPIレスポンスとUIから追跡できる。

## 2. 現在の統合準備状況

実装済みの境界は以下。

- `GroovePattern -> GrooveContext` adapter
- TempoMap、Meter、Phrase Boundary、Metric Gravity、Tension Curveの受け渡し
- performed Kick Eventの受け渡し
- `FOLLOW`、`NEGOTIATE`、`CO_CREATE`の3モード
- Shared Complexity BudgetとBass Complexity Share
- Joint Fitness、Interaction DNA、Change Cost
- Joint CandidateのGroove/Bass同時選択
- Pattern/Intent/Presetのversioned JSON exchange
- Groove/Bass Preview間のTransport排他制御
- Groove Context、Input Mode、Voice Policyを含むBass Pattern復元

## 3. 所有権と依存方向

| データ／処理 | 所有者 | 相手側の扱い |
|---|---|---|
| Groove Event、Drum Lock | HGE | HBEはDTOを読む。変更はInteraction Core経由のみ |
| Bass Event、Bass Lock | HBE | HGEはJoint Resultを読む。直接変更しない |
| Tempo、Meter、Canonical Tick | Shared Contract | 両EngineがPPQ 960で解釈 |
| HarmonyTimeline、BassIntent | HBE | HGEはBass内部生成へ介入しない |
| Shared Complexity Budget | Interaction Core | 両Engineへ配分する |
| Preference Profile | 各Engine | Joint rankingでは正規化済みScoreだけを使用 |
| Preview Transport | Frontend Coordinator | 同時所有を禁止 |

依存方向は次に固定する。

```text
HGE Pattern ──adapter──> GrooveContext DTO ──> HBE
      │                                        │
      └──────────── Interaction Core <─────────┘
                           │
                           └──> JointGenerationResult
```

HBEからHGE内部Generator、HGEからHBE内部Generatorを直接importしない。Interaction Coreだけが公開関数を
組み合わせる。

## 4. Canonical Contract

### GrooveContext

必須項目：

- `tempo_map`
- `meter`
- `phrase_boundaries`
- `beat_map`
- `metric_gravity`
- `tension_curve`
- `kick_events`
- `groove_dna`

Kick Eventは`grid_tick + structural_offset_tick + micro_offset_us`の3層を保持する。float beatを保存値にしない。

### BassPattern

統合上必要な復元項目：

- `input_mode`
- `harmony`
- `key_context`
- `groove_context`
- `voice_policy`
- `intent` / `intent_locks`
- `events` / `structural_events`
- `analysis` / `interaction_analysis`
- `metadata.schema_version` / `metadata.engine_version`

### JointGenerationResult

候補ごとに以下を返す。

- `groove_pattern`
- `bass_pattern`
- `joint_fitness`
- `complexity_fit`
- `change_cost`
- `changes[]`

`changes[]`には対象、Event ID、Operation、変更前後Tick、理由を残し、適用モードはResponse直下で管理する。

## 5. モード別処理

### FOLLOW

1. HGE PatternをGrooveContextへ変換する。
2. Groove Contextを固定入力としてBass候補を生成する。
3. Kick/Bass Interaction DNAを測定する。
4. Bass候補だけをrankingする。
5. Groove Patternのhashが入力前後で一致することを検証する。

### NEGOTIATE

1. FOLLOW候補を生成する。
2. Interaction上の局所問題を特定する。
3. unlockedかつnon-user-editedなKickだけを修正候補にする。
4. Bass修正、Kick修正、変更なしを比較する。
5. Joint Fitness改善がChange Costを上回る場合だけ最小変更を採用する。

### CO-CREATE

1. PhraseごとのComplexity配分を決定する。
2. unlocked Kick laneとBass Skeletonを共同候補化する。
3. Phrase RecoveryをKick/Bassのどちらが担うか分散する。
4. Interaction DNA、Intent Distance、Change Costでrankingする。
5. Candidate Diversityを確保して上位候補を返す。

## 6. 状態同期

- Groove候補変更時は既存GrooveContext Linkを解除し、明示的な再Linkを要求する。
- 保存Pattern、Generation History、JSON ImportではPattern内のGrooveContextを復元する。
- Bass Mutationが新しいPattern IDを発行した場合、元Candidate位置をRevisionで置換する。
- Joint Candidateを手編集または再生成した時点で、古いJoint Fitness表示を無効化する。
- Undo/Redoは各Engineで独立し、Joint Candidate選択時だけ両Engineの現在値を同時更新する。
- Preview Transportは一方のEngineだけが所有する。

## 7. Lockと変更コスト

変更禁止：

- HGE `locked` Event
- HGE Instrument/Bar Lock対象
- HBE Event field lock対象
- HBE Intent Lock対象
- request-level Preserve Option対象

Change Cost優先度：

```text
user_edited > explicit lock > persistent intent lock > generated event
```

HGE Eventは`origin`（`generated` / `user_edited` / `regenerated`）を保持し、Interaction Coreは
`user_edited`をLockと同等に保護する。

Collision Repairは変更対象Eventだけを移動し、固定Eventを避けて同一Bar内の最寄り有効Tickを選ぶ。

## 8. API統合手順

1. `GET /api/v1/bass/capabilities`で利用可能機能を確認する。
2. `POST /api/v1/bass/context/from-groove`でContract変換を検証する。
3. FOLLOWは`POST /api/v1/bass/generate`へGrooveContextを渡す。
4. NEGOTIATE / CO-CREATEは`POST /api/v1/interaction/generate`を使用する。
5. Pattern手編集後は`POST /api/v1/bass/evaluate`で再分析する。
6. OpenAPI変更ごとにFrontend型を再生成し、差分をCIで検出する。

## 9. テスト計画

### Contract Test

- Pydantic/OpenAPI schemaとFrontend generated typesの同期
- Schema Version不一致の拒否
- 旧Patternのdefault migration
- 全MeterでCanonical Tickを一致させる

### Mode Test

- FOLLOW：Groove完全不変
- NEGOTIATE：変更Kick数と対象制約
- CO-CREATE：unlocked Kick lane以外が不変
- 全モード：同一Seedで完全決定的

### Lock Test

- User Edited / Lock / Preserveの組合せ
- Partial Regeneration境界
- Collision Repairが固定Eventを動かさないこと

### Musical Test

- Kick Lock / Complement / Answerの測定応答
- Shared Complexity Budgetへの単調応答
- Phrase Recoveryの分散
- Candidate Diversity下限

### Frontend Integration Test

- Groove Link、解除、再Link
- Joint Candidate切替
- Revision Candidate同期
- Undo/Redo独立性
- Preview Transport排他
- 保存・履歴・JSON Import後のContext復元

## 10. 実施フェーズ

### Integration Phase A: Contract Freeze

- 現行Pydantic schemaを統合基準として固定
- OpenAPI generated type差分をゼロにする
- Contract fixtureをGolden Dataとして保存

終了条件：Contract Test、Backend Test、Frontend Typecheckが成功。

### Integration Phase B: FOLLOW Hardening

- Groove hash不変テスト
- 全Meter・1〜64 bars・Tempo境界テスト
- Bass-only fallbackテスト

終了条件：HGE Event変更ゼロ、Listener/Interaction Analysis生成成功。

### Integration Phase C: NEGOTIATE Hardening

- Change Cost閾値の固定
- User Edited Kick保護
- 最大変更数と局所修正範囲の固定

終了条件：許可外変更ゼロ、採用変更がJoint Fitnessを改善。

### Integration Phase D: CO-CREATE Hardening

- Phrase Complexity Migration
- Shared Recovery
- Candidate Diversity

終了条件：Complexity Budget適合、Lock違反ゼロ、決定性成功。

### Integration Phase E: UI / Persistence

- Engine間状態同期
- Joint Trace表示
- Preview排他
- Pattern/History/JSON round trip

終了条件：E2Eシナリオと再読込後の同値性が成功。

### Integration Phase F: Release Gate

- Golden Regression
- MIDI stuck-note検査
- Performance測定
- Capability API監査
- Known LimitationとVersion情報更新

終了条件：すべての自動検査成功、Critical/High issueが0件。

## 11. Performance目標

- 4 candidates / 8 bars：通常開発環境で対話的待ち時間内
- 64 bars：メモリ使用量がbarsに対して線形
- Partial Regeneration：非選択領域の再分析以外は局所処理
- SQLite History：indexed lookupを使用
- Frontend：Piano Rollは横スクロールを維持し、候補数を4に制限

性能測定値は環境依存のため、Release Gateで基準機を決めて記録する。

## 12. Rollbackと互換性

- Schema Versionを破壊的変更時に更新する。
- 旧Version importはmigration可能な項目だけdefault補完する。
- Interaction Core障害時はFOLLOWへfallbackし、Groove Patternを保持する。
- Joint Result適用前のGroove/Bass PatternをUndo履歴へ保持する。
- DB migrationは追加型を基本とし、既存payloadを破壊しない。

## 13. 統合完了条件

- FOLLOW / NEGOTIATE / CO-CREATEの全受入テスト成功
- LockおよびUser Edited Event違反0件
- Backend test、Ruff、Frontend test、ESLint、Typecheck、Production build成功
- OpenAPIとFrontend generated typesが同期
- Pattern/History/JSON/MIDI round trip成功
- Preview Transport競合なし
- Critical/High severity issue 0件

## 14. 実施状況（2026-08-26）

| Phase | 状態 | 完了内容 |
|---|---|---|
| A Contract Freeze | 完了 | Golden Contract、OpenAPI境界テスト、Schema/PPQ/Mode固定 |
| B FOLLOW Hardening | 完了 | Groove Pattern完全不変、全対応Meter、1〜64 bars |
| C NEGOTIATE Hardening | 完了 | 最大1 Kick変更、Instrument/Bar/Event/User Edit保護、Change Cost |
| D CO-CREATE Hardening | 完了 | Phrase Complexity Migration（確立→展開→ピーク→回復）、Kick/Bass Shared Recovery、unlocked Kick lane限定、User Edit保護、候補多様性、決定性、Shared Complexity Budget応答 |
| E UI / Persistence | 完了 | Context復元、Joint Candidate選択時のGroove/Bass同時適用、全Joint Change Trace表示、Preview排他、Groove生成→Bass Link E2E、Pattern/History/JSON round trip |
| F Release Gate | 完了 | Golden/MIDI回帰、OpenAPI一致、HGE/HBE/Interaction Capability互換性監査、全静的検査、再現可能な性能ベースライン |

ローカル基準環境でのCO-CREATE実測：

- 8 bars / 4 candidates：中央値 0.153秒（3回）
- 64 bars / 1 candidate：中央値 2.349秒（2回）

`backend/scripts/benchmark_interaction.py`で同一条件を再計測できる。実測値は性能保証値ではなく、
今後のRegression比較用ベースラインとする。
