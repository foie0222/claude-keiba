# AIエージェント競馬自動投票システム設計書

## 概要

LLMマルチエージェントによる合議制競馬予想・自動投票システム。
Claude (Max Plan) をエンジンとし、Claude Code SDK経由で複数のAIエージェントを並列起動。
各エージェントが専門分野の分析を行い、合議を経て投票判断・自動購入まで完全自動で実行する。

### 設計思想

- **再現性の低さを堀（moat）として活用**: LLMの確率的推論により、同じ入力でも異なる判断が生まれる。これは模倣困難性の源泉である
- **合議制**: 単一モデルのバイアスを排除し、多角的な分析を統合
- **完全自動化**: 判断から投票まで人間の介入なし。エージェントに全てを委ねる

## 対象・馬券種

| 項目 | 内容 |
|------|------|
| 対象 | JRA中央競馬 |
| 馬券種 | 単勝・複勝・ワイド・馬連 |
| 資金管理 | エージェント判断（入金額が天然リミット） |
| 実行タイミング | 各レース発走15分前にトリガー、締切直前に購入 |

## アーキテクチャ

### 技術スタック

- **LLMエンジン**: Claude (Max Plan)
- **エージェント制御**: Claude Code SDK (Python)
- **オーケストレータ**: Python (asyncio)
- **データ取得**: 各エージェントが自律的にAPI/スクレイピングで取得

### 3層構造

```
入力: (date, venue, race_number)
        │
        ↓
┌─────────────────────────────────────────────────┐
│  レイヤー1: 情報分析エージェント群（並列実行）        │
│                                                   │
│  ① 血統分析エージェント                             │
│     → 血統背景、父母の特徴、距離・馬場適性           │
│                                                   │
│  ② 調教分析エージェント                             │
│     → 調教タイム、調教内容、仕上がり具合             │
│                                                   │
│  ③ 騎手・厩舎分析エージェント                       │
│     → 騎手成績、厩舎傾向、騎手×馬の相性             │
│                                                   │
│  ④ 過去走分析エージェント                           │
│     → 過去成績、着順推移、ローテーション              │
│                                                   │
│  ⑤ ラップ・展開分析エージェント                      │
│     → 過去ラップ、ペース予想、脚質・枠順              │
│                                                   │
│  ⑥ X(Twitter)世論分析エージェント                   │
│     → 予想家・関係者の投稿、市場センチメント          │
│                                                   │
└──────────────────┬──────────────────────────────┘
                   ↓ 各分析結果JSON
┌─────────────────────────────────────────────────┐
│  レイヤー2: 合議エージェント（逐次実行）              │
│                                                   │
│  ⑦ 書記エージェント                                │
│     → 6つの分析結果を整理・構造化                    │
│                                                   │
│  ⑧ 監視エージェント                                │
│     → 矛盾検出・論理チェック・迷走防止               │
│                                                   │
│  ⑨ 統括判断エージェント                             │
│     → 全情報を統合し、各馬の評価と順位を決定          │
│                                                   │
└──────────────────┬──────────────────────────────┘
                   ↓ 馬の評価・順位
┌─────────────────────────────────────────────────┐
│  レイヤー3: 投票判断エージェント                      │
│                                                   │
│  ⑩ 投票戦略エージェント                             │
│     → 評価結果 × 最新オッズ → 期待値計算            │
│     → 馬券種選択・買い目・金額配分を決定             │
│                                                   │
└──────────────────┬──────────────────────────────┘
                   ↓
              [自動投票実行]
```

## エージェント詳細

### レイヤー1: 分析エージェント（並列実行）

各エージェントは独立したClaude Code SDKサブプロセスとして起動。
入力はレースID `(date, venue, race_number)` のみ。
各エージェントが自分で必要なデータをAPIから取得する。

| # | エージェント | 取得データ | 分析内容 | 出力 |
|---|-------------|----------|---------|------|
| ① | 血統分析 | 血統DB | 父母の特徴、距離・馬場適性、系統の傾向 | 各馬のスコア+根拠 |
| ② | 調教分析 | 調教データ | 調教タイム、内容、仕上がり評価 | 各馬のスコア+根拠 |
| ③ | 騎手・厩舎分析 | 騎手・厩舎成績 | 勝率、コース適性、騎手×馬の相性 | 各馬のスコア+根拠 |
| ④ | 過去走分析 | 過去成績 | 着順推移、ローテーション、成長曲線 | 各馬のスコア+根拠 |
| ⑤ | ラップ・展開分析 | ラップデータ | ペース予想、脚質、枠順影響 | 各馬のスコア+根拠 |
| ⑥ | X世論分析 | X API | 予想家の見解、市場センチメント、内部情報的な兆候 | 各馬のスコア+根拠 |

#### 分析エージェントの統一出力フォーマット

```json
{
  "analyst": "bloodline",
  "race_id": "20260301_nakayama_11",
  "analysis": "自然言語での分析",
  "rankings": [
    {"horse_number": 3, "score": 9.2, "reason": "父系の中山芝適性が高い"},
    {"horse_number": 7, "score": 8.5, "reason": "母父の底力が2000mで活きる"}
  ],
  "confidence": 0.75,
  "warnings": ["初距離で不確実性あり"]
}
```

### レイヤー2: 合議エージェント（逐次実行）

| # | エージェント | 入力 | 処理内容 | 出力 |
|---|-------------|------|---------|------|
| ⑦ | 書記 | 6つの分析結果 | 情報の整理・構造化 | 統合レポート |
| ⑧ | 監視 | 統合レポート | 矛盾検出、論理チェック、迷走防止 | 検証済みレポート |
| ⑨ | 統括判断 | 検証済みレポート | 各馬の総合評価、順位決定 | 評価・推奨馬リスト |

#### 統括判断エージェントの出力フォーマット

```json
{
  "evaluations": [
    {
      "horse_number": 3,
      "overall_score": 8.8,
      "summary": "血統・展開ともに高評価。調教も好仕上がり",
      "dissenting_views": ["X世論では人気薄の見方も"]
    }
  ],
  "recommended_top": [3, 7, 1],
  "race_assessment": "ペースが流れれば差し馬有利。軸は3番"
}
```

### レイヤー3: 投票判断エージェント

| # | エージェント | 入力 | 処理内容 | 出力 |
|---|-------------|------|---------|------|
| ⑩ | 投票戦略 | 評価結果 + 最新オッズ | 期待値計算、馬券種選択、金額配分 | 買い目リスト |

自ら最新オッズをAPI取得し、統括判断結果と照合して期待値を算出。

#### 投票判断エージェントの出力フォーマット

```json
{
  "bets": [
    {"type": "win", "horse": 3, "amount": 3000, "expected_value": 1.35},
    {"type": "wide", "horses": [3, 7], "amount": 2000, "expected_value": 1.22}
  ],
  "total_amount": 5000,
  "reasoning": "3番の単勝オッズ3.5に対し推定勝率35%で期待値1.22..."
}
```

## Claude Code SDK 実行モデル

### エージェント実行

```python
from claude_code_sdk import query, ClaudeCodeOptions

async def run_agent(agent_name: str, system_prompt: str, user_prompt: str):
    options = ClaudeCodeOptions(
        system_prompt=system_prompt,
        allowed_tools=["Bash", "Read", "Write"],
        max_turns=20,
    )
    result = []
    async for message in query(prompt=user_prompt, options=options):
        result.append(message)
    return extract_json_output(result)
```

### レイヤー1並列実行

```python
async def run_analysis_layer(race_id: str):
    agents = [
        ("bloodline",  load_prompt("bloodline"),  f"レース{race_id}の血統分析をせよ"),
        ("training",   load_prompt("training"),   f"レース{race_id}の調教分析をせよ"),
        ("jockey",     load_prompt("jockey"),     f"レース{race_id}の騎手・厩舎分析をせよ"),
        ("past_races", load_prompt("past_races"), f"レース{race_id}の過去走分析をせよ"),
        ("lap",        load_prompt("lap"),        f"レース{race_id}のラップ・展開分析をせよ"),
        ("x_opinion",  load_prompt("x_opinion"),  f"レース{race_id}のX世論分析をせよ"),
    ]
    tasks = [run_agent(name, sp, up) for name, sp, up in agents]
    results = await asyncio.gather(*tasks)
    return dict(zip([a[0] for a in agents], results))
```

### 全体フロー

```python
async def predict_and_bet(date: str, venue: str, race_number: int):
    race_id = f"{date}_{venue}_{race_number}"

    # レイヤー1: 分析（並列）
    analyses = await run_analysis_layer(race_id)

    # レイヤー2: 合議（逐次: 書記→監視→統括）
    summary = await run_agent("secretary", ..., format_analyses(analyses))
    reviewed = await run_agent("monitor", ..., summary)
    judgment = await run_agent("judge", ..., reviewed)

    # レイヤー3: 投票判断
    bet_decision = await run_agent("betting", ..., judgment)

    # 投票実行
    execute_bet(bet_decision)

    # ログ保存
    save_log(race_id, analyses, summary, reviewed, judgment, bet_decision)
```

## 実行時間見積もり

| フェーズ | 所要時間（見積もり） |
|---------|-------------------|
| レイヤー1: 分析（6エージェント並列） | 2-3分 |
| レイヤー2: 合議（3エージェント逐次） | 3-5分 |
| レイヤー3: 投票判断 | 1分 |
| 投票実行 | 30秒 |
| **合計** | **約6-9分** |

→ レース発走の**15分前**にトリガー

## ログ構造

```
logs/
└── 2026-03-01/
    └── nakayama_11/
        ├── input.json
        ├── agents/
        │   ├── bloodline.json
        │   ├── training.json
        │   ├── jockey.json
        │   ├── past_races.json
        │   ├── lap.json
        │   └── x_opinion.json
        ├── council/
        │   ├── secretary.json
        │   ├── monitor.json
        │   └── judge.json
        ├── betting_decision.json
        ├── execution.json
        └── result.json           # レース結果（後で追記）
```

## スケジューラ

```
schedule:
  - trigger: 開催日の朝 (8:00)
    action: fetch_race_schedule(date)  # その日のレース一覧取得

  - trigger: 各レース発走15分前
    action: predict_and_bet(date, venue, race_number)

  - trigger: 各レース確定後 (約30分後)
    action: record_result(date, venue, race_number)

  - trigger: 開催日の夜 (18:00)
    action: generate_daily_summary(date)
```

## ディレクトリ構成

```
claude-keiba/
├── orchestrator/
│   ├── main.py              # エントリポイント
│   ├── scheduler.py         # スケジューラ
│   └── config.py            # 設定
│
├── agents/
│   ├── prompts/             # 各エージェントのシステムプロンプト
│   │   ├── bloodline.md
│   │   ├── training.md
│   │   ├── jockey.md
│   │   ├── past_races.md
│   │   ├── lap.md
│   │   ├── x_opinion.md
│   │   ├── secretary.md
│   │   ├── monitor.md
│   │   ├── judge.md
│   │   └── betting.md
│   ├── runner.py            # claude-code-sdk呼び出しラッパー
│   └── council.py           # 合議プロセス管理
│
├── data/
│   ├── api/                 # データ取得用スクリプト（エージェントから呼ばれる）
│   │   ├── race_info.py
│   │   ├── odds.py
│   │   ├── training.py
│   │   ├── bloodline.py
│   │   └── x_search.py
│   └── models.py            # データモデル
│
├── betting/
│   ├── executor.py          # 自動投票実行
│   └── formatter.py         # 買い目フォーマット
│
├── logs/                    # 全ログ保存（日付/レース別）
│
├── docs/
│   └── plans/
│
└── pyproject.toml
```
