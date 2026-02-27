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
        race_id = RaceId(date=date, venue=venue, race_number=race_number)
        rid = str(race_id)

        print(f"[{rid}] 分析開始...")
        result = await self.council.execute(race_id)

        self.logger.save(rid, result)
        for agent_name, agent_result in result.get("analyses", {}).items():
            self.logger.save_agent_log(rid, agent_name, agent_result)

        print(f"[{rid}] 完了: {json.dumps(result.get('bet_decision', {}), ensure_ascii=False)}")
        return result


async def main():
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
