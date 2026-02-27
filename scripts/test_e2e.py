"""E2Eテスト: 全パイプラインを通す。

Usage: python scripts/test_e2e.py <date> <venue> <race_number>
  例: python scripts/test_e2e.py 20260222 tokyo 3
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.orchestrator import Orchestrator


async def main():
    if len(sys.argv) < 4:
        print("Usage: python scripts/test_e2e.py <date> <venue> <race_number>")
        print("  例: python scripts/test_e2e.py 20260222 tokyo 3")
        sys.exit(1)

    date, venue, race_number = sys.argv[1], sys.argv[2], int(sys.argv[3])
    race_id = f"{date}_{venue}_{race_number:02d}"

    print(f"=== E2Eテスト開始: {race_id} ===")
    start = time.time()

    orchestrator = Orchestrator()
    result = await orchestrator.predict_and_bet(date, venue, race_number)

    elapsed = time.time() - start
    print(f"\n=== 完了 ({elapsed:.1f}s) ===")
    print(json.dumps(result.get("bet_decision", {}), ensure_ascii=False, indent=2))
    if "bet_result" in result:
        print("\n--- 投票チェック ---")
        print(json.dumps(result["bet_result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
