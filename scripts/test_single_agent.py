"""単体エージェントのE2Eテスト。

Usage: python scripts/test_single_agent.py <agent_name> <race_id>
  例: python scripts/test_single_agent.py bloodline 20260222_tokyo_03
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.runner import AgentRunner


async def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/test_single_agent.py <agent_name> <race_id>")
        print("  agents: bloodline, training, jockey, past_races, lap, x_opinion")
        sys.exit(1)

    agent_name = sys.argv[1]
    race_id = sys.argv[2]

    runner = AgentRunner()
    prompt = f"以下のレースの分析をせよ: {race_id}"

    print(f"[{agent_name}] 実行開始... race_id={race_id}")
    start = time.time()

    try:
        result = await runner.run(agent_name, prompt, max_turns=30)
        elapsed = time.time() - start
        print(f"[{agent_name}] 完了 ({elapsed:.1f}s)")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{agent_name}] エラー ({elapsed:.1f}s): {e}")


if __name__ == "__main__":
    asyncio.run(main())
