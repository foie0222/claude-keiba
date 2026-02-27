"""本番実行: 予想→投票。

Usage: python run.py <date> <venue> <race_number>
  例: python run.py 20260228 hanshin 11
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.orchestrator import Orchestrator


async def main():
    if len(sys.argv) < 4:
        print("Usage: python run.py <date> <venue> <race_number>")
        print("  例: python run.py 20260228 hanshin 11")
        sys.exit(1)

    date, venue, race_number = sys.argv[1], sys.argv[2], int(sys.argv[3])

    orchestrator = Orchestrator()
    result = await orchestrator.predict_and_bet(date, venue, race_number, live=True)

    print(json.dumps(result.get("bet_decision", {}), ensure_ascii=False, indent=2))
    if "bet_result" in result:
        print(json.dumps(result["bet_result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
