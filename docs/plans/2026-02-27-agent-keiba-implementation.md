# AIエージェント競馬自動投票システム Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** LLMマルチエージェント合議制による競馬予想・自動投票システムをClaude Agent SDKで構築する

**Architecture:** 10エージェント3層構造（分析6並列→合議3逐次→投票判断1）。Pythonオーケストレータが`claude-agent-sdk`の`query()`でエージェントを起動。各エージェントはMCPツール経由でデータ取得APIを呼び出す。

**Tech Stack:** Python 3.12+, claude-agent-sdk, asyncio, pydantic

---

### Task 1: プロジェクト初期化とPython環境セットアップ

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`

**Step 1: pyproject.toml作成**

```toml
[project]
name = "claude-keiba"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "claude-agent-sdk>=0.1.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]
```

**Step 2: Python環境を作成**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Step 3: .python-version作成**

```
3.12
```

**Step 4: 動作確認**

Run: `python -c "import claude_agent_sdk; print('OK')"`
Expected: `OK`

**Step 5: コミット**

```bash
git add pyproject.toml .python-version
git commit -m "chore: initialize Python project with claude-agent-sdk"
```

---

### Task 2: Pydanticデータモデル定義

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

**Step 1: テスト作成**

```python
# tests/test_models.py
from src.models import RaceId, AnalysisResult, HorseRanking, CouncilJudgment, BetDecision, Bet

def test_race_id_to_string():
    r = RaceId(date="20260301", venue="nakayama", race_number=11)
    assert str(r) == "20260301_nakayama_11"

def test_analysis_result_validation():
    result = AnalysisResult(
        analyst="bloodline",
        race_id="20260301_nakayama_11",
        analysis="血統分析の結果",
        rankings=[HorseRanking(horse_number=3, score=9.2, reason="父系の適性が高い")],
        confidence=0.75,
        warnings=["初距離"],
    )
    assert result.analyst == "bloodline"
    assert result.rankings[0].score == 9.2

def test_bet_decision_total():
    decision = BetDecision(
        bets=[
            Bet(type="win", horses=[3], amount=3000, expected_value=1.35),
            Bet(type="wide", horses=[3, 7], amount=2000, expected_value=1.22),
        ],
        total_amount=5000,
        reasoning="期待値が高い",
    )
    assert decision.total_amount == 5000
    assert len(decision.bets) == 2
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (import error)

**Step 3: モデル実装**

```python
# src/models.py
from __future__ import annotations
from pydantic import BaseModel

class RaceId(BaseModel):
    date: str         # "20260301"
    venue: str        # "nakayama"
    race_number: int  # 11

    def __str__(self) -> str:
        return f"{self.date}_{self.venue}_{self.race_number}"

class HorseRanking(BaseModel):
    horse_number: int
    score: float
    reason: str

class AnalysisResult(BaseModel):
    analyst: str
    race_id: str
    analysis: str
    rankings: list[HorseRanking]
    confidence: float
    warnings: list[str] = []

class HorseEvaluation(BaseModel):
    horse_number: int
    overall_score: float
    summary: str
    dissenting_views: list[str] = []

class CouncilJudgment(BaseModel):
    evaluations: list[HorseEvaluation]
    recommended_top: list[int]
    race_assessment: str

class Bet(BaseModel):
    type: str              # "win", "place", "wide", "quinella"
    horses: list[int]
    amount: int
    expected_value: float

class BetDecision(BaseModel):
    bets: list[Bet]
    total_amount: int
    reasoning: str
```

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed

**Step 5: コミット**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add pydantic data models for race, analysis, and betting"
```

---

### Task 3: エージェントランナー（claude-agent-sdk ラッパー）

**Files:**
- Create: `src/agents/runner.py`
- Create: `tests/test_runner.py`

**Step 1: テスト作成**

エージェントランナーはclaude-agent-sdkを呼ぶため、ユニットテストではモックを使う。

```python
# tests/test_runner.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.runner import AgentRunner, extract_json_from_messages
from src.models import AnalysisResult

def test_extract_json_from_text():
    """テキスト中のJSONブロックを抽出できる"""
    text = 'Here is the analysis:\n```json\n{"analyst":"bloodline","race_id":"test","analysis":"test","rankings":[],"confidence":0.5,"warnings":[]}\n```'
    result = extract_json_from_messages(text)
    assert result["analyst"] == "bloodline"

def test_extract_json_bare():
    """JSONが直接返された場合も抽出できる"""
    text = '{"analyst":"bloodline","race_id":"test","analysis":"test","rankings":[],"confidence":0.5,"warnings":[]}'
    result = extract_json_from_messages(text)
    assert result["analyst"] == "bloodline"

def test_extract_json_not_found():
    """JSONが見つからない場合はNoneを返す"""
    result = extract_json_from_messages("No JSON here")
    assert result is None
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL

**Step 3: ランナー実装**

```python
# src/agents/runner.py
from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock, ResultMessage

def extract_json_from_messages(text: str) -> dict | None:
    """テキストからJSON部分を抽出する"""
    # ```json ... ``` ブロック内を探す
    match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 直接JSONを探す
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None

class AgentRunner:
    """claude-agent-sdk経由でエージェントを実行するラッパー"""

    def __init__(self, prompts_dir: Path = Path("agents/prompts")):
        self.prompts_dir = prompts_dir

    def load_prompt(self, agent_name: str) -> str:
        path = self.prompts_dir / f"{agent_name}.md"
        return path.read_text(encoding="utf-8")

    async def run(
        self,
        agent_name: str,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        max_turns: int = 20,
        mcp_servers: dict | None = None,
        allowed_tools: list[str] | None = None,
        output_schema: dict | None = None,
    ) -> dict:
        """1つのエージェントを実行し、JSON結果を返す"""
        if system_prompt is None:
            system_prompt = self.load_prompt(agent_name)

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            max_turns=max_turns,
            permission_mode="bypassPermissions",
            allowed_tools=allowed_tools or ["Bash", "Read", "Write"],
        )
        if mcp_servers:
            options.mcp_servers = mcp_servers
        if output_schema:
            options.output_format = {"type": "json_schema", "schema": output_schema}

        collected_text = []
        result_data = None

        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected_text.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.structured_output:
                    result_data = message.structured_output

        if result_data:
            return result_data

        full_text = "\n".join(collected_text)
        extracted = extract_json_from_messages(full_text)
        if extracted:
            return extracted

        return {"raw_text": full_text, "error": "JSON extraction failed"}

    async def run_parallel(
        self,
        agents: list[tuple[str, str]],
        **kwargs,
    ) -> dict[str, dict]:
        """複数エージェントを並列実行。agents = [(agent_name, user_prompt), ...]"""
        tasks = [self.run(name, prompt, **kwargs) for name, prompt in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            name: (r if not isinstance(r, Exception) else {"error": str(r)})
            for (name, _), r in zip(agents, results)
        }
```

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_runner.py -v`
Expected: 3 passed

**Step 5: コミット**

```bash
git add src/agents/runner.py tests/test_runner.py
git commit -m "feat: add agent runner wrapper for claude-agent-sdk"
```

---

### Task 4: 合議プロセス管理（オーケストレーション）

**Files:**
- Create: `src/agents/council.py`
- Create: `tests/test_council.py`

**Step 1: テスト作成**

```python
# tests/test_council.py
import pytest
import json
from src.agents.council import format_analyses_for_secretary

def test_format_analyses_for_secretary():
    """分析結果群を書記エージェント向けにフォーマットできる"""
    analyses = {
        "bloodline": {"analyst": "bloodline", "analysis": "血統分析結果", "rankings": [{"horse_number": 3, "score": 9.0, "reason": "適性高"}], "confidence": 0.8, "warnings": []},
        "training": {"analyst": "training", "analysis": "調教分析結果", "rankings": [{"horse_number": 3, "score": 8.5, "reason": "好調教"}], "confidence": 0.7, "warnings": []},
    }
    result = format_analyses_for_secretary(analyses)
    assert "bloodline" in result
    assert "training" in result
    assert "血統分析結果" in result
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_council.py -v`
Expected: FAIL

**Step 3: 合議プロセス実装**

```python
# src/agents/council.py
from __future__ import annotations
import json
from src.agents.runner import AgentRunner
from src.models import RaceId

def format_analyses_for_secretary(analyses: dict[str, dict]) -> str:
    """6つの分析結果を書記エージェント向けにフォーマット"""
    sections = []
    for name, result in analyses.items():
        sections.append(f"## {name} の分析\n\n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return "\n\n---\n\n".join(sections)

class CouncilProcess:
    """合議プロセス: 書記→監視→統括→投票判断"""

    def __init__(self, runner: AgentRunner):
        self.runner = runner

    async def run_analysis_layer(self, race_id: RaceId) -> dict[str, dict]:
        """レイヤー1: 6つの分析エージェントを並列実行"""
        rid = str(race_id)
        agents = [
            ("bloodline",  f"以下のレースの血統分析をせよ: {rid}"),
            ("training",   f"以下のレースの調教分析をせよ: {rid}"),
            ("jockey",     f"以下のレースの騎手・厩舎分析をせよ: {rid}"),
            ("past_races", f"以下のレースの過去走分析をせよ: {rid}"),
            ("lap",        f"以下のレースのラップ・展開分析をせよ: {rid}"),
            ("x_opinion",  f"以下のレースのX(Twitter)世論分析をせよ: {rid}"),
        ]
        return await self.runner.run_parallel(agents)

    async def run_council_layer(self, analyses: dict[str, dict]) -> dict:
        """レイヤー2: 合議（書記→監視→統括）"""
        formatted = format_analyses_for_secretary(analyses)

        # 書記: 情報整理
        secretary_result = await self.runner.run(
            "secretary",
            f"以下の6つの分析結果を整理・構造化してください:\n\n{formatted}",
        )

        # 監視: 矛盾検出
        monitor_result = await self.runner.run(
            "monitor",
            f"以下の統合レポートの矛盾や論理的問題を検出してください:\n\n{json.dumps(secretary_result, ensure_ascii=False, indent=2)}",
        )

        # 統括: 最終判断
        judge_result = await self.runner.run(
            "judge",
            f"以下の検証済みレポートを基に各馬の総合評価と推奨順位を決定してください:\n\n{json.dumps(monitor_result, ensure_ascii=False, indent=2)}",
        )

        return {
            "secretary": secretary_result,
            "monitor": monitor_result,
            "judge": judge_result,
        }

    async def run_betting_layer(self, judgment: dict) -> dict:
        """レイヤー3: 投票判断"""
        return await self.runner.run(
            "betting",
            f"以下の統括判断結果を基に、最新オッズを取得し、馬券種・買い目・金額を決定してください:\n\n{json.dumps(judgment, ensure_ascii=False, indent=2)}",
        )

    async def execute(self, race_id: RaceId) -> dict:
        """全レイヤーを通して実行"""
        analyses = await self.run_analysis_layer(race_id)
        council = await self.run_council_layer(analyses)
        bet_decision = await self.run_betting_layer(council["judge"])
        return {
            "race_id": str(race_id),
            "analyses": analyses,
            "council": council,
            "bet_decision": bet_decision,
        }
```

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_council.py -v`
Expected: 1 passed

**Step 5: コミット**

```bash
git add src/agents/council.py tests/test_council.py
git commit -m "feat: add council process orchestration for 3-layer agent flow"
```

---

### Task 5: ログ保存機能

**Files:**
- Create: `src/logging.py`
- Create: `tests/test_logging.py`

**Step 1: テスト作成**

```python
# tests/test_logging.py
import pytest
import json
from pathlib import Path
from src.logging import RaceLogger

def test_save_and_load(tmp_path):
    logger = RaceLogger(base_dir=tmp_path / "logs")
    race_id = "20260301_nakayama_11"
    data = {"analyses": {"bloodline": {"score": 9.0}}, "bet_decision": {"total_amount": 5000}}

    logger.save(race_id, data)

    log_dir = tmp_path / "logs" / "20260301" / "nakayama_11"
    assert log_dir.exists()
    assert (log_dir / "full_result.json").exists()

    loaded = json.loads((log_dir / "full_result.json").read_text())
    assert loaded["bet_decision"]["total_amount"] == 5000

def test_save_agent_log(tmp_path):
    logger = RaceLogger(base_dir=tmp_path / "logs")
    race_id = "20260301_nakayama_11"
    logger.save_agent_log(race_id, "bloodline", {"analysis": "test"})

    path = tmp_path / "logs" / "20260301" / "nakayama_11" / "agents" / "bloodline.json"
    assert path.exists()
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_logging.py -v`
Expected: FAIL

**Step 3: ロガー実装**

```python
# src/logging.py
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

class RaceLogger:
    """レースごとの全推論ログを保存する"""

    def __init__(self, base_dir: Path = Path("logs")):
        self.base_dir = base_dir

    def _race_dir(self, race_id: str) -> Path:
        """race_id = "20260301_nakayama_11" → logs/20260301/nakayama_11/"""
        parts = race_id.split("_", 1)
        date_str = parts[0]
        rest = parts[1] if len(parts) > 1 else "unknown"
        return self.base_dir / date_str / rest

    def save(self, race_id: str, data: dict) -> Path:
        """全結果を一括保存"""
        d = self._race_dir(race_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "full_result.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_agent_log(self, race_id: str, agent_name: str, data: dict) -> Path:
        """個別エージェントのログを保存"""
        d = self._race_dir(race_id) / "agents"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{agent_name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_result(self, race_id: str, result: dict) -> Path:
        """レース結果を後から追記"""
        d = self._race_dir(race_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "race_result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
```

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_logging.py -v`
Expected: 2 passed

**Step 5: コミット**

```bash
git add src/logging.py tests/test_logging.py
git commit -m "feat: add race logger for saving agent reasoning logs"
```

---

### Task 6: メインオーケストレータ

**Files:**
- Create: `src/orchestrator.py`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

**Step 1: オーケストレータ実装**

```python
# src/orchestrator.py
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from src.models import RaceId
from src.agents.runner import AgentRunner
from src.agents.council import CouncilProcess
from src.logging import RaceLogger

class Orchestrator:
    """メインオーケストレータ: 全体フローの制御"""

    def __init__(
        self,
        prompts_dir: Path = Path("agents/prompts"),
        logs_dir: Path = Path("logs"),
    ):
        self.runner = AgentRunner(prompts_dir=prompts_dir)
        self.council = CouncilProcess(self.runner)
        self.logger = RaceLogger(base_dir=logs_dir)

    async def predict_and_bet(self, date: str, venue: str, race_number: int) -> dict:
        """1レースの予想→投票を実行"""
        race_id = RaceId(date=date, venue=venue, race_number=race_number)
        rid = str(race_id)

        print(f"[{rid}] 分析開始...")
        result = await self.council.execute(race_id)

        # ログ保存
        self.logger.save(rid, result)
        for agent_name, agent_result in result.get("analyses", {}).items():
            self.logger.save_agent_log(rid, agent_name, agent_result)

        print(f"[{rid}] 完了: {json.dumps(result.get('bet_decision', {}), ensure_ascii=False)}")
        return result

async def main():
    """CLI エントリポイント"""
    import sys
    if len(sys.argv) != 4:
        print("Usage: python -m src.orchestrator <date> <venue> <race_number>")
        print("Example: python -m src.orchestrator 20260301 nakayama 11")
        sys.exit(1)

    date, venue, race_number = sys.argv[1], sys.argv[2], int(sys.argv[3])
    orchestrator = Orchestrator()
    result = await orchestrator.predict_and_bet(date, venue, race_number)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: __init__.py作成**

```python
# src/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

**Step 3: コミット**

```bash
git add src/orchestrator.py src/__init__.py tests/__init__.py
git commit -m "feat: add main orchestrator for predict-and-bet flow"
```

---

### Task 7: エージェントプロンプト作成（6分析エージェント）

**Files:**
- Create: `agents/prompts/bloodline.md`
- Create: `agents/prompts/training.md`
- Create: `agents/prompts/jockey.md`
- Create: `agents/prompts/past_races.md`
- Create: `agents/prompts/lap.md`
- Create: `agents/prompts/x_opinion.md`

各プロンプトは以下の共通構造を持つ:

1. 役割と専門分野の定義
2. 入力（レースID）の受け取り方
3. データ取得方法の指示（Bashツールで`python data/api/xxx.py <race_id>`を実行）
4. 分析の観点
5. 出力JSONフォーマットの厳密な指定

**Step 1: 血統分析エージェントのプロンプト作成**

```markdown
# 血統分析エージェント

あなたは競馬の血統分析の専門家です。

## 役割
与えられたレースの出走馬について、血統的観点から各馬の能力と適性を分析します。

## データ取得
Bashツールで以下を実行してレースの出走馬情報を取得してください:
```
python data/api/race_info.py <race_id>
```

## 分析の観点
- 父系・母系の特徴（スピード型/スタミナ型/万能型）
- 距離適性（血統から推定される最適距離）
- 馬場適性（良馬場/重馬場/ダートへの適性）
- コース適性（該当コースでの系統別成績傾向）
- 成長力（晩成/早熟の血統パターン）

## 出力フォーマット
必ず以下のJSONフォーマットで出力してください:
```json
{
  "analyst": "bloodline",
  "race_id": "<レースID>",
  "analysis": "<自然言語での総合分析>",
  "rankings": [
    {"horse_number": <馬番>, "score": <1.0-10.0>, "reason": "<根拠>"}
  ],
  "confidence": <0.0-1.0>,
  "warnings": ["<注意点>"]
}
```

rankingsは全出走馬についてスコア降順で記載してください。
```

**Step 2: 残り5つの分析エージェントプロンプトを同様に作成**

各エージェントで「分析の観点」が異なる:

- **training.md**: 調教タイム、追い切り内容、調教場所と馬場、調教パターンの変化、仕上がり度合い
- **jockey.md**: 騎手のコース別成績、厩舎の出走パターン、騎手×厩舎の相性、乗り替わり影響
- **past_races.md**: 過去着順推移、ローテーション、クラス別成績、前走からの間隔、成長曲線
- **lap.md**: 過去レースのラップ構成、ペース予想（ハイ/ミドル/スロー）、脚質分布、枠順バイアス
- **x_opinion.md**: 予想家の推奨馬、トレンドワード、関係者の示唆的な発言、市場の過大/過小評価の兆候

各プロンプトでデータ取得コマンドが異なる:
- training: `python data/api/training.py <race_id>`
- jockey: `python data/api/race_info.py <race_id>` (騎手情報含む)
- past_races: `python data/api/race_info.py <race_id>`
- lap: `python data/api/race_info.py <race_id>`
- x_opinion: `python data/api/x_search.py <race_id>`

**Step 3: コミット**

```bash
git add agents/prompts/bloodline.md agents/prompts/training.md agents/prompts/jockey.md agents/prompts/past_races.md agents/prompts/lap.md agents/prompts/x_opinion.md
git commit -m "feat: add system prompts for 6 analysis agents"
```

---

### Task 8: エージェントプロンプト作成（合議3 + 投票判断1）

**Files:**
- Create: `agents/prompts/secretary.md`
- Create: `agents/prompts/monitor.md`
- Create: `agents/prompts/judge.md`
- Create: `agents/prompts/betting.md`

**Step 1: 書記エージェントプロンプト**

```markdown
# 書記エージェント

あなたは競馬分析チームの書記です。

## 役割
6つの専門家（血統・調教・騎手/厩舎・過去走・ラップ/展開・X世論）から提出された分析結果を整理・構造化し、統合レポートを作成します。

## 作業内容
1. 各専門家の分析結果を読み込む
2. 馬ごとに各専門家のスコアと根拠をまとめる
3. 専門家間で見解が一致している点と分かれている点を明示する
4. 特に注意すべき警告事項をまとめる

## 出力フォーマット
```json
{
  "summary": "<全体的な傾向の要約>",
  "horse_profiles": [
    {
      "horse_number": <馬番>,
      "scores_by_analyst": {"bloodline": <score>, "training": <score>, ...},
      "consensus_points": ["<一致点>"],
      "disagreement_points": ["<不一致点>"],
      "average_score": <平均スコア>
    }
  ],
  "key_warnings": ["<注意事項>"]
}
```
```

**Step 2: 監視エージェントプロンプト**

役割: 書記の統合レポートに矛盾・論理的問題がないかチェック。具体的には:
- スコアの極端な乖離がないか
- 根拠と結論が整合しているか
- 見落とされている重要な観点がないか
- バイアス（人気馬への偏り等）がないか

**Step 3: 統括判断エージェントプロンプト**

役割: 検証済みレポートから各馬の総合評価を行い、推奨順位を決定。

**Step 4: 投票戦略エージェントプロンプト**

役割: 統括判断 × 最新オッズ → 期待値計算 → 買い目決定。
データ取得: `python data/api/odds.py <race_id>` でオッズ取得。

**Step 5: コミット**

```bash
git add agents/prompts/secretary.md agents/prompts/monitor.md agents/prompts/judge.md agents/prompts/betting.md
git commit -m "feat: add system prompts for council and betting agents"
```

---

### Task 9: データ取得APIスクリプト（スタブ実装）

**Files:**
- Create: `data/api/race_info.py`
- Create: `data/api/odds.py`
- Create: `data/api/training.py`
- Create: `data/api/x_search.py`
- Create: `tests/test_data_api.py`

最初はスタブ（ダミーデータ返却）で実装し、後でデータソース接続時に実APIに差し替える。

**Step 1: テスト作成**

```python
# tests/test_data_api.py
import subprocess
import json

def test_race_info_stub():
    result = subprocess.run(
        ["python", "data/api/race_info.py", "20260301_nakayama_11"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert "race" in data
    assert "horses" in data
    assert len(data["horses"]) > 0

def test_odds_stub():
    result = subprocess.run(
        ["python", "data/api/odds.py", "20260301_nakayama_11"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert "win" in data
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_data_api.py -v`
Expected: FAIL

**Step 3: スタブ実装**

各スクリプトはCLI引数でrace_idを受け取り、JSONをstdoutに出力する。
スタブは8頭立てのダミーデータを返す。

```python
# data/api/race_info.py
"""レース情報取得スタブ。引数: race_id (例: 20260301_nakayama_11)"""
import json
import sys

def get_race_info(race_id: str) -> dict:
    # TODO: 実データソースに接続
    parts = race_id.split("_")
    return {
        "race": {
            "race_id": race_id,
            "date": parts[0] if len(parts) > 0 else "",
            "venue": parts[1] if len(parts) > 1 else "",
            "race_number": int(parts[2]) if len(parts) > 2 else 0,
            "name": "スタブレース",
            "distance": 2000,
            "surface": "芝",
            "condition": "良",
        },
        "horses": [
            {"number": i, "name": f"Horse{i}", "jockey": f"Jockey{i}", "trainer": f"Trainer{i}", "sire": f"Sire{i}", "dam_sire": f"DamSire{i}"}
            for i in range(1, 9)
        ],
    }

if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_race_info(race_id), ensure_ascii=False))
```

odds.py, training.py, x_search.py も同様のスタブを作成。

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_data_api.py -v`
Expected: 2 passed

**Step 5: コミット**

```bash
git add data/api/ tests/test_data_api.py
git commit -m "feat: add stub data API scripts for agent data fetching"
```

---

### Task 10: E2Eスモークテスト（スタブデータで全フロー動作確認）

**Files:**
- Create: `tests/test_e2e_smoke.py`

**Step 1: スモークテスト作成**

```python
# tests/test_e2e_smoke.py
"""
E2Eスモークテスト。実際にclaude-agent-sdkを呼ぶため、
CI環境ではスキップし、手動実行で確認する。
"""
import pytest
import asyncio
from pathlib import Path
from src.orchestrator import Orchestrator

@pytest.mark.skipif(
    not Path.home().joinpath(".claude").exists(),
    reason="Claude Code CLI not available"
)
@pytest.mark.asyncio
async def test_e2e_single_race():
    """1レースの全フローが通ることを確認（スタブデータ）"""
    orchestrator = Orchestrator(
        prompts_dir=Path("agents/prompts"),
        logs_dir=Path("logs/test"),
    )
    result = await orchestrator.predict_and_bet("20260301", "nakayama", 11)

    assert "analyses" in result
    assert "council" in result
    assert "bet_decision" in result

    # ログが保存されていること
    log_dir = Path("logs/test/20260301/nakayama_11")
    assert log_dir.exists()
```

**Step 2: 手動実行で確認**

Run: `pytest tests/test_e2e_smoke.py -v -s`

これは実際にClaude APIを呼ぶため時間がかかる（6-9分）。
最初のスモークテストなので結果の正確性ではなく「全フローが通ること」を確認。

**Step 3: コミット**

```bash
git add tests/test_e2e_smoke.py
git commit -m "test: add E2E smoke test for full predict-and-bet flow"
```

---

### Task 11: 投票実行モジュール（スタブ）

**Files:**
- Create: `src/betting/executor.py`
- Create: `tests/test_betting.py`

**Step 1: テスト作成**

```python
# tests/test_betting.py
from src.betting.executor import BettingExecutor
from src.models import BetDecision, Bet

def test_executor_dry_run():
    """ドライラン（実際に投票しない）で買い目が正しくフォーマットされる"""
    executor = BettingExecutor(dry_run=True)
    decision = BetDecision(
        bets=[Bet(type="win", horses=[3], amount=3000, expected_value=1.35)],
        total_amount=3000,
        reasoning="test",
    )
    result = executor.execute(decision)
    assert result["status"] == "dry_run"
    assert result["bets_placed"] == 1
```

**Step 2: テスト実行して失敗確認**

Run: `pytest tests/test_betting.py -v`
Expected: FAIL

**Step 3: 投票実行モジュール実装**

```python
# src/betting/executor.py
from __future__ import annotations
from src.models import BetDecision

class BettingExecutor:
    """馬券購入を実行する。dry_run=Trueで実際には購入しない。"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def execute(self, decision: BetDecision) -> dict:
        if self.dry_run:
            return {
                "status": "dry_run",
                "bets_placed": len(decision.bets),
                "total_amount": decision.total_amount,
                "detail": [b.model_dump() for b in decision.bets],
            }
        # TODO: 実際の投票API連携
        raise NotImplementedError("Real betting not implemented yet")
```

**Step 4: テスト実行して成功確認**

Run: `pytest tests/test_betting.py -v`
Expected: 1 passed

**Step 5: コミット**

```bash
git add src/betting/executor.py tests/test_betting.py
git commit -m "feat: add betting executor with dry-run mode"
```

---

### Task 12: 全テスト通過確認 + 初期ドキュメント整理

**Step 1: 全テスト実行**

Run: `pytest tests/ -v --ignore=tests/test_e2e_smoke.py`
Expected: All passed（E2Eテストはスキップ）

**Step 2: ディレクトリ構造の最終確認**

Run: `find . -type f -name "*.py" | sort`

期待される構造:
```
./data/api/odds.py
./data/api/race_info.py
./data/api/training.py
./data/api/x_search.py
./src/__init__.py
./src/agents/council.py
./src/agents/runner.py
./src/betting/executor.py
./src/logging.py
./src/models.py
./src/orchestrator.py
./tests/__init__.py
./tests/test_betting.py
./tests/test_council.py
./tests/test_data_api.py
./tests/test_logging.py
./tests/test_models.py
./tests/test_e2e_smoke.py
```

**Step 3: コミット**

```bash
git add -A
git commit -m "chore: finalize initial project structure and verify all tests pass"
```
