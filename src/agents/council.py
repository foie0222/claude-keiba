from __future__ import annotations
import asyncio
import json
import sys
import time
from src.agents.runner import AgentRunner
from src.models import RaceId


def _phase(msg: str) -> None:
    """フェーズ区切りログ"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print(f"  [{timestamp}] {msg}", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)


def format_analyses_for_secretary(analyses: dict[str, dict]) -> str:
    """6つの分析結果を書記エージェント向けにフォーマット"""
    sections = []
    for name, result in analyses.items():
        sections.append(f"## {name} の分析\n\n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return "\n\n---\n\n".join(sections)


class CouncilProcess:
    """合議プロセス: 分析→書記→監視→統括→投票判断"""

    def __init__(self, runner: AgentRunner):
        self.runner = runner

    async def run_analysis_layer(
        self, race_id: RaceId, prefetch_path: str | None = None,
    ) -> dict[str, dict]:
        """レイヤー1: 6つの分析エージェントを並列実行"""
        rid = str(race_id)
        _phase("レイヤー1: 分析エージェント (6並列)")

        data_instruction = ""
        if prefetch_path:
            data_instruction = (
                f"\n\n【データ】事前取得済みデータが {prefetch_path}/ ディレクトリにあります。"
                f"各セクションは {prefetch_path}/<セクション名>.json として保存されています"
                f"（例: race_info.json, horse_detail.json, past_results.json 等）。"
                f"Readツールで必要なファイルを読み、そのデータを使って分析してください。"
                f"追加データが必要な場合のみBashでAPIを呼んでください。"
            )

        # 全6エージェントを同時起動
        standard_task = self.runner.run_parallel([
            ("bloodline",  f"以下のレースの血統分析をせよ: {rid}{data_instruction}"),
            ("training",   f"以下のレースの調教分析をせよ: {rid}{data_instruction}"),
            ("jockey",     f"以下のレースの騎手・厩舎分析をせよ: {rid}{data_instruction}"),
            ("past_races", f"以下のレースの過去走分析をせよ: {rid}{data_instruction}"),
            ("lap",        f"以下のレースのラップ・展開分析をせよ: {rid}{data_instruction}"),
        ])

        x_opinion_task = self.runner.run(
            "x_opinion",
            f"以下のレースのX(Twitter)世論分析をせよ: {rid}",
            mcp_servers={
                "chrome": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "chrome-devtools-mcp@latest",
                             "--browserUrl=http://127.0.0.1:9222"],
                },
            },
            allowed_tools=[
                "Bash", "Read", "Write",
                "mcp__chrome__navigate_page",
                "mcp__chrome__new_page",
                "mcp__chrome__evaluate_script",
                "mcp__chrome__take_snapshot",
                "mcp__chrome__take_screenshot",
                "mcp__chrome__click",
                "mcp__chrome__fill",
                "mcp__chrome__press_key",
                "mcp__chrome__wait_for",
                "mcp__chrome__list_pages",
                "mcp__chrome__select_page",
            ],
        )

        standard_results, x_opinion_result = await asyncio.gather(
            standard_task, x_opinion_task,
        )
        standard_results["x_opinion"] = x_opinion_result
        return standard_results

    async def run_council_layer(self, analyses: dict[str, dict]) -> dict:
        """レイヤー2: 合議（書記→監視→統括）"""
        _phase("レイヤー2: 合議 (secretary → monitor → judge)")
        formatted = format_analyses_for_secretary(analyses)

        secretary_result = await self.runner.run(
            "secretary",
            f"以下の6つの分析結果を整理・構造化してください:\n\n{formatted}",
        )

        monitor_result = await self.runner.run(
            "monitor",
            f"以下の統合レポートの矛盾や論理的問題を検出してください:\n\n{json.dumps(secretary_result, ensure_ascii=False, indent=2)}",
        )

        judge_result = await self.runner.run(
            "judge",
            f"以下の検証済みレポートを基に各馬の総合評価と推奨順位を決定してください:\n\n{json.dumps(monitor_result, ensure_ascii=False, indent=2)}",
        )

        return {
            "secretary": secretary_result,
            "monitor": monitor_result,
            "judge": judge_result,
        }

    async def run_betting_layer(
        self, judgment: dict, prefetch_path: str | None = None,
    ) -> dict:
        """レイヤー3: 投票判断"""
        _phase("レイヤー3: 投票判断 (betting)")
        data_instruction = ""
        if prefetch_path:
            data_instruction = (
                f"\n\n【オッズデータ】{prefetch_path}/odds.json をReadツールで読み込んでください。"
                f"\n【IPAT残高】{prefetch_path}/balance.json をReadツールで読み込んでください。"
            )
        return await self.runner.run(
            "betting",
            f"以下の統括判断結果を基に、オッズと残高を照合し、馬券種・買い目・金額を決定してください:\n\n{json.dumps(judgment, ensure_ascii=False, indent=2)}{data_instruction}",
        )

    async def execute(self, race_id: RaceId, prefetch_path: str | None = None) -> dict:
        """全レイヤーを通して実行"""
        analyses = await self.run_analysis_layer(race_id, prefetch_path=prefetch_path)
        council = await self.run_council_layer(analyses)
        bet_decision = await self.run_betting_layer(council["judge"], prefetch_path=prefetch_path)
        return {
            "race_id": str(race_id),
            "analyses": analyses,
            "council": council,
            "bet_decision": bet_decision,
        }
