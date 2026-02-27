from __future__ import annotations
import asyncio
import json
import sys
import time
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

        t0 = time.time()
        print(f"\n{'#'*60}", file=sys.stderr, flush=True)
        print(f"  予想開始: {rid}", file=sys.stderr, flush=True)
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr, flush=True)
        print(f"{'#'*60}\n", file=sys.stderr, flush=True)

        # データ事前一括取得
        from data.api.prefetch import prefetch, save_cache as save_prefetch
        print(f"{'='*60}", file=sys.stderr, flush=True)
        print(f"  [{time.strftime('%H:%M:%S')}] データ事前取得", file=sys.stderr, flush=True)
        print(f"{'='*60}", file=sys.stderr, flush=True)
        prefetch_data = prefetch(rid)
        prefetch_path = save_prefetch(rid, prefetch_data)
        print(f"  → {prefetch_path}\n", file=sys.stderr, flush=True)

        result = await self.council.execute(race_id, prefetch_path=prefetch_path)

        elapsed = time.time() - t0
        print(f"\n{'#'*60}", file=sys.stderr, flush=True)
        print(f"  予想完了: {rid} ({elapsed:.0f}s = {elapsed/60:.1f}min)", file=sys.stderr, flush=True)
        print(f"{'#'*60}\n", file=sys.stderr, flush=True)

        self.logger.save(rid, result)
        for agent_name, agent_result in result.get("analyses", {}).items():
            self.logger.save_agent_log(rid, agent_name, agent_result)

        # 投票チェック (betchk)
        bet_decision = result.get("bet_decision", {})
        bets = bet_decision.get("bets", [])
        if bets and not bet_decision.get("pass_races", False):
            from data.api.bet import place_bet
            total = bet_decision.get("total_amount", 0)
            print(f"\n{'='*60}", file=sys.stderr, flush=True)
            print(f"  [{time.strftime('%H:%M:%S')}] 投票チェック (betchk)", file=sys.stderr, flush=True)
            print(f"{'='*60}", file=sys.stderr, flush=True)
            bet_result = place_bet(
                date, venue, race_number, bets, total, check_only=True,
            )
            result["bet_check"] = bet_result
            if bet_result.get("ret") == 0:
                print(f"  ✓ 投票チェックOK (buyeye: {bet_result['buyeye']})", file=sys.stderr, flush=True)
            else:
                print(f"  ✗ 投票チェックNG: {bet_result.get('msg')}", file=sys.stderr, flush=True)
        else:
            result["bet_check"] = {"skipped": True, "reason": "見送り or 馬券なし"}
            print(f"\n  投票見送り", file=sys.stderr, flush=True)

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
