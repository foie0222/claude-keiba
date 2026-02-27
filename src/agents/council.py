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
    """合議プロセス: 分析→書記→監視→統括→投票判断"""

    def __init__(self, runner: AgentRunner):
        self.runner = runner

    async def run_analysis_layer(self, race_id: RaceId) -> dict[str, dict]:
        """レイヤー1: 6つの分析エージェントを並列実行"""
        rid = str(race_id)

        # Chrome MCPツール不要のエージェント群
        standard_agents = [
            ("bloodline",  f"以下のレースの血統分析をせよ: {rid}"),
            ("training",   f"以下のレースの調教分析をせよ: {rid}"),
            ("jockey",     f"以下のレースの騎手・厩舎分析をせよ: {rid}"),
            ("past_races", f"以下のレースの過去走分析をせよ: {rid}"),
            ("lap",        f"以下のレースのラップ・展開分析をせよ: {rid}"),
        ]
        standard_results = await self.runner.run_parallel(standard_agents)

        # x_opinion: Chrome MCPツール付きで実行
        x_opinion_result = await self.runner.run(
            "x_opinion",
            f"以下のレースのX(Twitter)世論分析をせよ: {rid}",
            allowed_tools=[
                "Bash", "Read", "Write",
                "mcp__claude-in-chrome__tabs_context_mcp",
                "mcp__claude-in-chrome__tabs_create_mcp",
                "mcp__claude-in-chrome__navigate",
                "mcp__claude-in-chrome__javascript_tool",
                "mcp__claude-in-chrome__computer",
                "mcp__claude-in-chrome__read_page",
                "mcp__claude-in-chrome__find",
            ],
        )
        standard_results["x_opinion"] = x_opinion_result
        return standard_results

    async def run_council_layer(self, analyses: dict[str, dict]) -> dict:
        """レイヤー2: 合議（書記→監視→統括）"""
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
