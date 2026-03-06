from __future__ import annotations
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from src.models import RaceId
from src.agents.runner import AgentRunner
from src.agents.council import CouncilProcess
from src.logging import RaceLogger

BETTING_MINUTES_BEFORE = 3  # 発走何分前にbettingを実行するか


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

    def _wait_until_before_post(self, prefetch_data: dict) -> None:
        """発走BETTING_MINUTES_BEFORE分前まで待機する。"""
        post_time_str = prefetch_data.get("race_info", {}).get("race", {}).get("post_time", "")
        if not post_time_str or len(post_time_str) < 4:
            print(f"  ⚠ 発走時刻不明、待機スキップ", file=sys.stderr, flush=True)
            return

        hh, mm = int(post_time_str[:2]), int(post_time_str[2:4])
        now = datetime.now()
        post_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        target = post_dt - timedelta(minutes=BETTING_MINUTES_BEFORE)
        wait_seconds = (target - now).total_seconds()

        if wait_seconds <= 0:
            print(f"  発走{BETTING_MINUTES_BEFORE}分前を既に過ぎています、即実行",
                  file=sys.stderr, flush=True)
            return

        print(f"\n{'='*60}", file=sys.stderr, flush=True)
        print(f"  [{time.strftime('%H:%M:%S')}] 発走 {hh:02d}:{mm:02d} の{BETTING_MINUTES_BEFORE}分前まで待機",
              file=sys.stderr, flush=True)
        print(f"  → {target.strftime('%H:%M:%S')} まで {wait_seconds:.0f}秒",
              file=sys.stderr, flush=True)
        print(f"{'='*60}", file=sys.stderr, flush=True)

        time.sleep(wait_seconds)
        print(f"  [{time.strftime('%H:%M:%S')}] 待機完了", file=sys.stderr, flush=True)

    @staticmethod
    def _refresh_odds(race_id: str, prefetch_path: Path) -> None:
        """オッズを再取得してprefetchキャッシュを更新する。"""
        import toon
        from data.api.odds import get_odds

        print(f"  オッズ再取得: {race_id}...", file=sys.stderr, flush=True)
        odds_data = get_odds(race_id)
        (prefetch_path / "odds.toon").write_text(
            toon.encode(odds_data), encoding="utf-8"
        )
        source = odds_data.get("odds_source", "")
        print(f"  ✓ オッズ更新完了 (source={source})", file=sys.stderr, flush=True)

    async def predict_and_bet(self, date: str, venue: str, race_number: int, *, live: bool = False, balance_override: int | None = None) -> dict:
        race_id = RaceId(date=date, venue=venue, race_number=race_number)
        rid = str(race_id)

        t0 = time.time()
        print(f"\n{'#'*60}", file=sys.stderr, flush=True)
        print(f"  予想開始: {rid}", file=sys.stderr, flush=True)
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr, flush=True)
        print(f"{'#'*60}\n", file=sys.stderr, flush=True)

        # データ事前一括取得（並列）
        from data.api.prefetch import prefetch_async, save_cache as save_prefetch
        print(f"{'='*60}", file=sys.stderr, flush=True)
        print(f"  [{time.strftime('%H:%M:%S')}] データ事前取得", file=sys.stderr, flush=True)
        print(f"{'='*60}", file=sys.stderr, flush=True)
        prefetch_data = await prefetch_async(rid)
        prefetch_path = save_prefetch(rid, prefetch_data)
        print(f"  → {prefetch_path}\n", file=sys.stderr, flush=True)

        result = await self.council.execute(race_id, prefetch_path=prefetch_path, live=live)

        elapsed = time.time() - t0
        print(f"\n{'#'*60}", file=sys.stderr, flush=True)
        print(f"  分析・合議完了: {rid} ({elapsed:.0f}s = {elapsed/60:.1f}min)", file=sys.stderr, flush=True)
        print(f"{'#'*60}\n", file=sys.stderr, flush=True)

        # 本番: 発走3分前まで待機 → オッズ再取得
        if live:
            self._wait_until_before_post(prefetch_data)
            self._refresh_odds(rid, prefetch_path)

        # betting（機械的ケリー基準）
        judge = result.get("council", {}).get("judge", {})
        bet_decision = self.council.run_betting_layer(
            judge, prefetch_path=prefetch_path, balance_override=balance_override,
        )
        result["bet_decision"] = bet_decision

        self.logger.save(rid, result)
        for agent_name, agent_result in result.get("analyses", {}).items():
            self.logger.save_agent_log(rid, agent_name, agent_result)
        bets = bet_decision.get("bets", [])
        if bets and not bet_decision.get("pass_races", False):
            from data.api.bet import place_bet
            total = bet_decision.get("total_amount", 0)
            check_only = not live
            mode = "本番投票" if live else "投票チェック (betchk)"
            print(f"\n{'='*60}", file=sys.stderr, flush=True)
            print(f"  [{time.strftime('%H:%M:%S')}] {mode}", file=sys.stderr, flush=True)
            print(f"{'='*60}", file=sys.stderr, flush=True)

            # 取消馬を抽出（race_info の horses から abnormal != 0 の馬番）
            # NOTE: prefetch時点のデータを使用。直前の取消には対応できない
            scratched = set()
            race_info = prefetch_data.get("race_info", {})
            for h in race_info.get("horses", []):
                num = h.get("number")
                if num is not None and h.get("abnormal", 0) != 0:
                    scratched.add(num)
            if scratched:
                print(f"  ⚠ 取消馬: {sorted(scratched)}", file=sys.stderr, flush=True)

            bet_result = place_bet(
                date, venue, race_number, bets, total,
                check_only=check_only, scratched_numbers=scratched,
            )
            result["bet_result"] = bet_result
            if bet_result.get("ret") == 0:
                print(f"  ✓ {mode}OK (buyeye: {bet_result['buyeye']})", file=sys.stderr, flush=True)
            else:
                print(f"  ✗ {mode}NG: {bet_result.get('msg')}", file=sys.stderr, flush=True)
        else:
            result["bet_result"] = {"skipped": True, "reason": "見送り or 馬券なし"}
            print(f"\n  投票見送り", file=sys.stderr, flush=True)

        # X投稿（本番のみ）
        if live:
            try:
                from src.notifiers.card_image import generate_card_image
                from src.notifiers.x_poster import post_to_x

                race_info = prefetch_data.get("race_info", {})
                card_path = generate_card_image(race_info, bet_decision)
                tweet_id = post_to_x(card_path)
                result["tweet_id"] = tweet_id
            except Exception as e:
                print(f"  ✗ X投稿処理エラー: {e}", file=sys.stderr, flush=True)

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
