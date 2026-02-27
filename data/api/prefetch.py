"""レース分析に必要な全APIデータを事前一括取得する。

Usage:
    python data/api/prefetch.py <race_id>
    例: python data/api/prefetch.py 20260222_tokyo_03

出力: .cache/prefetch/<race_id>.json
"""
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

CACHE_DIR = ROOT / ".cache" / "prefetch"


def prefetch(race_id: str) -> dict:
    """全APIを順次呼び出し、結果を1つのdictにまとめる"""
    results = {}
    apis = [
        ("race_info", lambda: get_race_info(race_id)),
        ("horse_detail", lambda: get_horse_details(race_id)),
        ("jockey_stats", lambda: get_jockey_stats(race_id)),
        ("trainer_stats", lambda: get_trainer_stats(race_id)),
        ("past_results", lambda: get_past_results(race_id)),
        ("training", lambda: get_training(race_id)),
    ]

    for name, fn in apis:
        t0 = time.time()
        try:
            results[name] = fn()
            elapsed = time.time() - t0
            print(f"  ✓ {name:16s} ({elapsed:.1f}s)", file=sys.stderr, flush=True)
        except Exception as e:
            results[name] = {"error": str(e)}
            elapsed = time.time() - t0
            print(f"  ✗ {name:16s} ({elapsed:.1f}s): {e}", file=sys.stderr, flush=True)

    return results


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
