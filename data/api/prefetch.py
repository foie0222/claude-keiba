"""レース分析に必要な全APIデータを事前一括取得する。

Usage:
    python data/api/prefetch.py <race_id>
    例: python data/api/prefetch.py 20260222_tokyo_03

出力: .cache/prefetch/<race_id>.json
"""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "api"))

from race_info import get_race_info
from horse_detail import get_horse_details
from jockey_stats import get_jockey_stats
from trainer_stats import get_trainer_stats
from past_results import get_past_results
from training import get_training
from odds import get_odds
from balance import get_balance

CACHE_DIR = ROOT / ".cache" / "prefetch"


async def _run_api(name: str, fn) -> tuple[str, dict]:
    """同期APIをスレッドで実行し、名前と結果のタプルを返す"""
    t0 = time.time()
    try:
        result = await asyncio.to_thread(fn)
        elapsed = time.time() - t0
        print(f"  ✓ {name:16s} ({elapsed:.1f}s)", file=sys.stderr, flush=True)
        return name, result
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ✗ {name:16s} ({elapsed:.1f}s): {e}", file=sys.stderr, flush=True)
        return name, {"error": str(e)}


async def _run_kbdb_sequential(race_id: str) -> list[tuple[str, dict]]:
    """KBDB系APIをレート制限に配慮して順次実行"""
    apis = [
        ("horse_detail", lambda: get_horse_details(race_id)),
        ("jockey_stats", lambda: get_jockey_stats(race_id)),
        ("trainer_stats", lambda: get_trainer_stats(race_id)),
        ("past_results", lambda: get_past_results(race_id)),
    ]
    results = []
    for name, fn in apis:
        results.append(await _run_api(name, fn))
    return results


async def prefetch_async(race_id: str) -> dict:
    """APIを並列で取得。KBDB系は順次、それ以外は並列実行。

    Step1: race_info (KBDB) を最初に取得
    Step2 並列: [KBDB系4つ(順次)] + [odds] + [training] + [balance]
    """
    # Step1: race_info を先に取得（他のKBDB APIと競合しないよう）
    _, race_info_data = await _run_api("race_info", lambda: get_race_info(race_id))
    results = {"race_info": race_info_data}

    # Step2: KBDB系(順次) と 非KBDB系(並列) を同時実行
    kbdb_task = _run_kbdb_sequential(race_id)
    odds_task = _run_api("odds", lambda: get_odds(race_id))
    training_task = _run_api("training", lambda: get_training(race_id))
    balance_task = _run_api("balance", get_balance)

    kbdb_results, odds_result, training_result, balance_result = await asyncio.gather(
        kbdb_task, odds_task, training_task, balance_task,
    )

    for name, data in kbdb_results:
        results[name] = data
    results[odds_result[0]] = odds_result[1]
    results[training_result[0]] = training_result[1]
    results[balance_result[0]] = balance_result[1]

    return results


def prefetch(race_id: str) -> dict:
    """全APIを取得し、結果を1つのdictにまとめる（同期ラッパー）

    注意: 既にイベントループが動いている場合は prefetch_async() を直接 await すること。
    """
    return asyncio.run(prefetch_async(race_id))


def save_cache(race_id: str, data: dict) -> Path:
    """セクション別にファイルを分割保存する"""
    race_dir = CACHE_DIR / race_id
    race_dir.mkdir(parents=True, exist_ok=True)
    for name, section_data in data.items():
        path = race_dir / f"{name}.json"
        path.write_text(json.dumps(section_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return race_dir


def main():
    if len(sys.argv) < 2:
        print("Usage: python data/api/prefetch.py <race_id>")
        sys.exit(1)

    race_id = sys.argv[1]
    print(f"データ一括取得: {race_id}", file=sys.stderr, flush=True)
    t0 = time.time()

    data = prefetch(race_id)
    path = save_cache(race_id, data)

    elapsed = time.time() - t0
    print(f"完了 ({elapsed:.1f}s) → {path}", file=sys.stderr, flush=True)
    # stdoutにはパスだけ出力
    print(str(path))


if __name__ == "__main__":
    main()
