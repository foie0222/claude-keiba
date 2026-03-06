"""バックテスト: 指定日・開催のレースを予想→結果照合→回収率計算。

Usage: python scripts/backtest.py <date> <venue> [race_number]
  例: python scripts/backtest.py 20260301 kokura        # 全12レース
      python scripts/backtest.py 20260222 hanshin 8     # 8Rのみ

ログから betting 再実行:
  python scripts/backtest.py --from-log logs/20260301/hanshin_3/full_result.json
  python scripts/backtest.py --from-log logs/20260301/hanshin_*/full_result.json
"""
import asyncio
import glob as globmod
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestrator import Orchestrator
from data.api.race_info import get_race_info
from data.api.odds import get_odds


# ─── 的中判定 ─────────────────────────────────────────────

def _build_result_map(horses: list[dict]) -> dict[int, int]:
    """馬番 → 着順 のマップを構築。"""
    return {h["number"]: h.get("result", 0) for h in horses if h.get("result")}


def _normalize_combo(horses: list[int]) -> str:
    """馬番リストを小さい順にソートして "H1-H2" 形式に。"""
    return "-".join(str(h) for h in sorted(horses))


def judge_bet(bet: dict, result_map: dict[int, int], confirmed_odds: dict) -> dict:
    """単一 bet の的中判定と払戻計算。

    Returns: {hit: bool, payout: int, odds_used: float|None, detail: str}
    """
    bet_type = bet["type"]
    horses = bet["horses"]
    amount = bet["amount"]

    if bet_type == "win":
        h = horses[0]
        rank = result_map.get(h, 0)
        hit = rank == 1
        odds_val = None
        if hit:
            win_odds = confirmed_odds.get("win", {}).get(str(h), {})
            odds_val = win_odds.get("odds")
        payout = int(amount * odds_val) if hit and odds_val else 0
        detail = f"{h}番は{rank}着" if rank else f"{h}番は着順不明"
        return {"hit": hit, "payout": payout, "odds_used": odds_val, "detail": detail}

    if bet_type == "place":
        h = horses[0]
        rank = result_map.get(h, 0)
        hit = 1 <= rank <= 3
        odds_val = None
        if hit:
            place_odds = confirmed_odds.get("place", {}).get(str(h), {})
            o_min = place_odds.get("odds_min")
            o_max = place_odds.get("odds_max")
            if o_min is not None and o_max is not None:
                odds_val = (o_min + o_max) / 2
            elif o_min is not None:
                odds_val = o_min
        payout = int(amount * odds_val) if hit and odds_val else 0
        detail = f"{h}番は{rank}着" if rank else f"{h}番は着順不明"
        return {"hit": hit, "payout": payout, "odds_used": odds_val, "detail": detail}

    if bet_type == "quinella":
        h1, h2 = horses[0], horses[1]
        r1, r2 = result_map.get(h1, 0), result_map.get(h2, 0)
        hit = {r1, r2} == {1, 2}
        odds_val = None
        if hit:
            combo_key = _normalize_combo([h1, h2])
            for entry in confirmed_odds.get("quinella", []):
                if entry.get("combination") == combo_key:
                    odds_val = entry.get("odds")
                    break
        payout = int(amount * odds_val) if hit and odds_val else 0
        detail = f"{h1}番{r1}着,{h2}番{r2}着" if r1 and r2 else f"{h1}-{h2}着順不明"
        return {"hit": hit, "payout": payout, "odds_used": odds_val, "detail": detail}

    if bet_type == "wide":
        h1, h2 = horses[0], horses[1]
        r1, r2 = result_map.get(h1, 0), result_map.get(h2, 0)
        hit = 1 <= r1 <= 3 and 1 <= r2 <= 3
        odds_val = None
        if hit:
            combo_key = _normalize_combo([h1, h2])
            for entry in confirmed_odds.get("wide", []):
                if entry.get("combination") == combo_key:
                    odds_val = entry.get("odds")
                    break
        payout = int(amount * odds_val) if hit and odds_val else 0
        detail = f"{h1}番{r1}着,{h2}番{r2}着" if r1 and r2 else f"{h1}-{h2}着順不明"
        return {"hit": hit, "payout": payout, "odds_used": odds_val, "detail": detail}

    return {"hit": False, "payout": 0, "odds_used": None, "detail": f"未対応券種: {bet_type}"}


# ─── 結果照合・的中判定 ───────────────────────────────────

def evaluate_predictions(predictions: list[dict]) -> list[dict]:
    """全予想に対して結果を取得し、的中判定を行う。"""
    results = []

    for pred in predictions:
        race_id = pred["race_id"]
        race_no = pred["race_number"]
        bet_decision = pred["bet_decision"]
        bets = bet_decision.get("bets", [])
        pass_races = bet_decision.get("pass_races", False)

        entry = {
            "race_number": race_no,
            "race_id": race_id,
            "error": pred["error"],
            "pass_races": pass_races or not bets,
            "bets_detail": [],
            "total_stake": 0,
            "total_payout": 0,
        }

        if pred["error"] or pass_races or not bets:
            results.append(entry)
            continue

        # 結果取得
        print(f"  結果取得: {race_id}...", file=sys.stderr, flush=True)
        try:
            race_info = get_race_info(race_id, include_result=True)
            horses = race_info.get("horses", [])
            result_map = _build_result_map(horses)
        except Exception as e:
            print(f"  !! 結果取得エラー: {e}", file=sys.stderr, flush=True)
            entry["error"] = f"結果取得エラー: {e}"
            results.append(entry)
            continue

        # 確定オッズ取得
        try:
            confirmed_odds = get_odds(race_id)
        except Exception as e:
            print(f"  !! オッズ取得エラー: {e}", file=sys.stderr, flush=True)
            confirmed_odds = {}

        # 各 bet の判定
        total_stake = 0
        total_payout = 0
        for bet in bets:
            judgment = judge_bet(bet, result_map, confirmed_odds)
            bet_detail = {
                "type": bet["type"],
                "horses": bet["horses"],
                "amount": bet["amount"],
                **judgment,
            }
            entry["bets_detail"].append(bet_detail)
            total_stake += bet["amount"]
            total_payout += judgment["payout"]

        entry["total_stake"] = total_stake
        entry["total_payout"] = total_payout
        results.append(entry)

    return results


# ─── Phase 4: サマリー出力 ─────────────────────────────────

TYPE_LABEL = {"win": "単勝", "place": "複勝", "quinella": "馬連", "wide": "ワイド"}
TYPE_ORDER = {"win": 0, "place": 1, "wide": 2, "quinella": 3}


def print_summary(date: str, venue: str, results: list[dict], race_numbers: list[int] | None = None):
    """的中結果のサマリーを表示する。"""
    races_label = f"{race_numbers[0]}R" if race_numbers and len(race_numbers) == 1 else f"全{len(results)}レース"
    print(f"\n{'='*60}")
    print(f"=== バックテスト結果: {date} {venue} {races_label} ===")
    print(f"{'='*60}")

    total_stake = 0
    total_payout = 0
    predicted_count = 0
    pass_count = 0
    error_count = 0
    total_bets = 0
    total_hits = 0

    for r in results:
        rn = r["race_number"]

        if r["error"]:
            print(f"\n{rn}R: エラー ({r['error']})")
            error_count += 1
            continue

        if r["pass_races"]:
            print(f"\n{rn}R: 見送り")
            pass_count += 1
            continue

        predicted_count += 1
        stake = r["total_stake"]
        payout = r["total_payout"]
        total_stake += stake
        total_payout += payout
        hit_label = "的中!" if payout > 0 else "ハズレ"
        print(f"\n{rn}R: 投入 {stake:,}円 → 回収 {payout:,}円 ({hit_label})")

        for bd in sorted(r["bets_detail"], key=lambda b: (TYPE_ORDER.get(b["type"], 99), b["horses"])):
            t = TYPE_LABEL.get(bd["type"], bd["type"])
            horses_str = "-".join(str(h) for h in bd["horses"])
            mark = "○" if bd["hit"] else "×"
            total_bets += 1
            if bd["hit"]:
                total_hits += 1
            odds_str = f"@{bd['odds_used']:.2f}" if bd["odds_used"] else ""
            payout_str = f" 払戻 {bd['payout']:,}円" if bd["hit"] else ""
            print(f"  - {t} {horses_str} {bd['amount']:,}円 {odds_str} → {bd['detail']} {mark}{payout_str}")

    # 全体サマリー
    print(f"\n{'='*60}")
    print(f"[全体サマリー]")
    print(f"レース数: {len(results)}")
    print(f"予想実施: {predicted_count} / 見送り: {pass_count} / エラー: {error_count}")
    print(f"投入合計: {total_stake:,}円")
    print(f"回収合計: {total_payout:,}円")
    profit = total_payout - total_stake
    sign = "+" if profit >= 0 else ""
    print(f"収支: {sign}{profit:,}円")
    roi = (total_payout / total_stake * 100) if total_stake > 0 else 0
    print(f"回収率: {roi:.1f}%")
    hit_rate = f"{total_hits}/{total_bets} ({total_hits/total_bets*100:.1f}%)" if total_bets > 0 else "0/0"
    print(f"的中率: {hit_rate}")
    print(f"{'='*60}")


# ─── Phase 5: JSON保存 ─────────────────────────────────────

def save_json(date: str, venue: str, results: list[dict]):
    """全結果をJSONに保存。"""
    out_dir = Path("logs/backtest")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date}_{venue}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "venue": venue, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n結果保存: {out_path}", file=sys.stderr, flush=True)
    return out_path


INITIAL_BALANCE = 100_000

PREFETCH_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "prefetch"


# ─── from-log: ログからbetting再実行 ─────────────────────────

def _parse_race_id(race_id: str) -> tuple[str, str, int]:
    """race_id文字列 → (date, venue, race_number)"""
    parts = race_id.split("_")
    return parts[0], parts[1], int(parts[2])


def _prepare_prefetch_for_rebetting(race_id: str, balance: int) -> Path:
    """betting再実行用にprefetchキャッシュのodds/balanceを更新する。"""
    import toon

    cache_dir = PREFETCH_CACHE_DIR / race_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    # オッズ再取得
    print(f"  オッズ再取得: {race_id}...", file=sys.stderr, flush=True)
    odds_data = get_odds(race_id)
    (cache_dir / "odds.toon").write_text(toon.encode(odds_data), encoding="utf-8")

    # 残高上書き
    balance_data = {
        "buy_limit_money": balance,
        "day_buy_money": 0,
        "total_buy_money": 0,
        "day_refund_money": 0,
        "total_refund_money": 0,
        "buy_possible_count": 99,
    }
    (cache_dir / "balance.toon").write_text(toon.encode(balance_data), encoding="utf-8")

    return cache_dir


def run_from_logs(log_paths: list[Path]):
    """既存ログからbetting以降を再実行してバックテストする。"""
    from src.betting.kelly import compute_from_prefetch

    # ログを読み込み、race_number順にソート
    logs = []
    for p in log_paths:
        with open(p) as f:
            data = json.load(f)
        logs.append((p, data))
    logs.sort(key=lambda x: _parse_race_id(x[1]["race_id"])[2])

    # date/venue を最初のログから取得
    first_race_id = logs[0][1]["race_id"]
    date, venue, _ = _parse_race_id(first_race_id)

    t0 = time.time()
    print(f"\n{'#'*60}", file=sys.stderr, flush=True)
    print(f"  バックテスト(from-log): {date} {venue} {len(logs)}レース", file=sys.stderr, flush=True)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr, flush=True)
    print(f"{'#'*60}\n", file=sys.stderr, flush=True)

    all_results = []
    balance = INITIAL_BALANCE
    print(f"  初期残高: {balance:,}円", file=sys.stderr, flush=True)

    for i, (log_path, log_data) in enumerate(logs, 1):
        race_id = log_data["race_id"]
        _, _, race_no = _parse_race_id(race_id)
        judge = log_data.get("council", {}).get("judge", {})

        print(f"\n{'='*60}", file=sys.stderr, flush=True)
        print(f"  betting再実行: {race_id} ({i}/{len(logs)}) 残高: {balance:,}円", file=sys.stderr, flush=True)
        print(f"  ソース: {log_path}", file=sys.stderr, flush=True)
        print(f"{'='*60}", file=sys.stderr, flush=True)

        if not judge:
            print(f"  !! judge結果なし、スキップ", file=sys.stderr, flush=True)
            all_results.append({
                "race_number": race_no, "race_id": race_id,
                "error": "judge結果なし", "pass_races": True,
                "bets_detail": [], "total_stake": 0, "total_payout": 0,
            })
            continue

        try:
            prefetch_path = _prepare_prefetch_for_rebetting(race_id, balance)
            bet_decision = compute_from_prefetch(judge, prefetch_path, balance)

            if bet_decision["pass_races"]:
                print(f"  → 見送り: {bet_decision['reasoning']}", file=sys.stderr, flush=True)
            else:
                print(f"  → {len(bet_decision['bets'])}点 合計{bet_decision['total_amount']:,}円",
                      file=sys.stderr, flush=True)

            pred = {
                "race_number": race_no,
                "race_id": race_id,
                "bet_decision": bet_decision,
                "error": None,
            }
        except Exception as e:
            print(f"  !! {race_no}R エラー: {e}", file=sys.stderr, flush=True)
            pred = {
                "race_number": race_no,
                "race_id": race_id,
                "bet_decision": {},
                "error": str(e),
            }

        race_results = evaluate_predictions([pred])
        all_results.extend(race_results)

        r = race_results[0]
        if not r["error"] and not r["pass_races"]:
            balance = balance - r["total_stake"] + r["total_payout"]
            print(f"  → 残高: {balance:,}円", file=sys.stderr, flush=True)

        print_summary(date, venue, race_results, [race_no])

    if len(logs) > 1:
        print_summary(date, venue, all_results)
        print(f"最終残高: {balance:,}円 (初期: {INITIAL_BALANCE:,}円 → 損益: {balance - INITIAL_BALANCE:+,}円)")

    save_json(date, venue, all_results)

    elapsed = time.time() - t0
    print(f"\n  総所要時間: {elapsed:.0f}s ({elapsed/60:.1f}min)", file=sys.stderr, flush=True)


# ─── main ──────────────────────────────────────────────────

async def main():
    # --from-log モード
    if len(sys.argv) >= 3 and sys.argv[1] == "--from-log":
        patterns = sys.argv[2:]
        log_paths = []
        for pattern in patterns:
            matched = globmod.glob(pattern)
            log_paths.extend(Path(p) for p in matched)
        if not log_paths:
            print(f"ログファイルが見つかりません: {patterns}", file=sys.stderr)
            sys.exit(1)
        log_paths = sorted(set(log_paths))
        run_from_logs(log_paths)
        return

    if len(sys.argv) < 3:
        print("Usage: python scripts/backtest.py <date> <venue> [race_number]")
        print("  例: python scripts/backtest.py 20260301 kokura        # 全12レース")
        print("      python scripts/backtest.py 20260222 hanshin 8     # 8Rのみ")
        print()
        print("ログからbetting再実行:")
        print("  python scripts/backtest.py --from-log logs/20260301/hanshin_3/full_result.json")
        sys.exit(1)

    date, venue = sys.argv[1], sys.argv[2]
    race_numbers = [int(sys.argv[3])] if len(sys.argv) >= 4 else None
    races_label = f"{race_numbers[0]}R" if race_numbers else "全12レース"

    t0 = time.time()
    print(f"\n{'#'*60}", file=sys.stderr, flush=True)
    print(f"  バックテスト開始: {date} {venue} {races_label}", file=sys.stderr, flush=True)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr, flush=True)
    print(f"{'#'*60}\n", file=sys.stderr, flush=True)

    orchestrator = Orchestrator()
    races = race_numbers or list(range(1, 13))
    total = len(races)
    all_results = []
    balance = INITIAL_BALANCE

    print(f"  初期残高: {balance:,}円", file=sys.stderr, flush=True)

    for i, race_no in enumerate(races, 1):
        race_id = f"{date}_{venue}_{race_no}"
        print(f"\n{'='*60}", file=sys.stderr, flush=True)
        print(f"  バックテスト: {race_id} ({i}/{total}) 残高: {balance:,}円", file=sys.stderr, flush=True)
        print(f"{'='*60}", file=sys.stderr, flush=True)

        # 予想（残高をoverride）
        try:
            result = await orchestrator.predict_and_bet(date, venue, race_no, live=False, balance_override=balance)
            bet_decision = result.get("bet_decision", {})
            pred = {
                "race_number": race_no,
                "race_id": race_id,
                "bet_decision": bet_decision,
                "error": None,
            }
        except Exception as e:
            print(f"  !! {race_no}R エラー: {e}", file=sys.stderr, flush=True)
            pred = {
                "race_number": race_no,
                "race_id": race_id,
                "bet_decision": {},
                "error": str(e),
            }

        # 結果照合・的中判定
        race_results = evaluate_predictions([pred])
        all_results.extend(race_results)

        # 残高更新
        r = race_results[0]
        if not r["error"] and not r["pass_races"]:
            balance = balance - r["total_stake"] + r["total_payout"]
            print(f"  → 残高: {balance:,}円", file=sys.stderr, flush=True)

        # レース結果表示
        print_summary(date, venue, race_results, [race_no])

    # 全体サマリー
    if total > 1:
        print_summary(date, venue, all_results, race_numbers)
        print(f"最終残高: {balance:,}円 (初期: {INITIAL_BALANCE:,}円 → 損益: {balance - INITIAL_BALANCE:+,}円)")

    # JSON保存
    save_json(date, venue, all_results)

    elapsed = time.time() - t0
    print(f"\n  総所要時間: {elapsed:.0f}s ({elapsed/60:.1f}min)", file=sys.stderr, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
