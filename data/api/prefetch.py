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
from race_laps import get_race_laps
from training import get_training
from odds import get_odds
from balance import get_balance
from sire_stats_filter import filter_for_race

CACHE_DIR = ROOT / ".cache" / "prefetch"


def _run_api_sync(name: str, fn) -> tuple[str, dict]:
    """同期APIを実行し、名前と結果のタプルを返す"""
    t0 = time.time()
    try:
        result = fn()
        elapsed = time.time() - t0
        print(f"  ✓ {name:16s} ({elapsed:.1f}s)", file=sys.stderr, flush=True)
        return name, result
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ✗ {name:16s} ({elapsed:.1f}s): {e}", file=sys.stderr, flush=True)
        return name, {"error": str(e)}


async def _run_api_thread(name: str, fn) -> tuple[str, dict]:
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


async def prefetch_async(race_id: str) -> dict:
    """APIを取得。KBDB系は同一スレッドで直列、非KBDB系はスレッド並列。

    KBDB APIは同時セッション数制限があるため、1クエリが完全に完了してから
    次を開始する必要がある（submit/wait/fetch_csvの全工程が認証を消費）。

    構成:
      直列(メインスレッド): race_info → horse_detail → jockey_stats → trainer_stats → past_results
      並列(別スレッド):     odds + training + balance + race_laps (非KBDB、上記と同時実行)
    """
    results = {}

    # 非KBDB系を別スレッドで並列実行開始
    # race_lapsは初回にKBDB 2クエリ → その後netkeiba scraping の流れ。
    # KBDBレートリミッタ(ファイルロック)で自動シリアライズされるため並列グループで安全。
    non_kbdb_task = asyncio.gather(
        _run_api_thread("odds", lambda: get_odds(race_id)),
        _run_api_thread("training", lambda: get_training(race_id)),
        _run_api_thread("balance", get_balance),
        _run_api_thread("race_laps", lambda: get_race_laps(race_id)),
    )

    # KBDB系をメインスレッドで直列実行（同時セッション制限を回避）
    kbdb_apis = [
        ("race_info", lambda: get_race_info(race_id)),
        ("horse_detail", lambda: get_horse_details(race_id)),
        ("jockey_stats", lambda: get_jockey_stats(race_id)),
        ("trainer_stats", lambda: get_trainer_stats(race_id)),
        ("past_results", lambda: get_past_results(race_id)),
    ]
    kbdb_task = asyncio.to_thread(_run_kbdb_all_sync, kbdb_apis)

    kbdb_results, non_kbdb_results = await asyncio.gather(kbdb_task, non_kbdb_task)

    for name, data in kbdb_results:
        results[name] = data
    for name, data in non_kbdb_results:
        results[name] = data

    return results


def _run_kbdb_all_sync(apis: list) -> list[tuple[str, dict]]:
    """KBDB系APIを同一スレッドで直列実行（セッション制限対策）"""
    results = []
    for name, fn in apis:
        results.append(_run_api_sync(name, fn))
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

    # 産駒成績フィルタ: horse_detailから種牡馬・母父を抽出しTOONファイルをフィルタ
    horse_detail = data.get("horse_detail", {})
    if "error" not in horse_detail:
        sire_stats_toon = filter_for_race(horse_detail)
        if sire_stats_toon:
            toon_path = race_dir / "sire_stats.toon"
            toon_path.write_text(sire_stats_toon, encoding="utf-8")
            print(f"  ✓ sire_stats.toon (filtered)", file=sys.stderr, flush=True)

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
