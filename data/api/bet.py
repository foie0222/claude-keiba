"""IPAT投票API。

Usage: python data/api/bet.py (テスト用: betchkモードで投票チェック)

buyeye フォーマット:
  日付,レース場コード,レース番号,式別,方式,金額,買い目,マルチ:...
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API_URL = "https://api.gamble-os.net/systems/ip-bet-kb"

VENUE_TO_CODE = {
    "sapporo": "01", "hakodate": "02", "fukushima": "03", "niigata": "04",
    "tokyo": "05", "nakayama": "06", "chukyo": "07", "kyoto": "08",
    "hanshin": "09", "kokura": "10",
}

# betting.md の type → IPAT 式別
TYPE_TO_SHIKIBETSU = {
    "win": "TAN",
    "place": "FUKU",
    "wide": "WIDE",
    "quinella": "UMAFUKU",
}


def _build_buyeye_entry(
    date: str, venue_code: str, race_no: int, bet: dict,
) -> str:
    """1つの馬券を buyeye の1エントリに変換する。

    Args:
        date: YYYYMMDD
        venue_code: 2桁レース場コード (例: "09")
        race_no: レース番号
        bet: {"type": "win", "horses": [3], "amount": 2000, ...}
    """
    shikibetsu = TYPE_TO_SHIKIBETSU[bet["type"]]
    amount = int(bet["amount"])
    horses = bet["horses"]

    if bet["type"] in ("win", "place"):
        # 単勝・複勝: 馬番1頭 "03"
        eye = f"{horses[0]:02d}"
    else:
        # 馬連・ワイド: 馬番2頭 "0102" (小さい番号が先)
        sorted_h = sorted(horses)
        eye = "".join(f"{h:02d}" for h in sorted_h)

    return f"{date},{venue_code},{race_no:02d},{shikibetsu},NORMAL,{amount},{eye},"


def build_buyeye(date: str, venue: str, race_no: int, bets: list[dict]) -> str:
    """bet_decision の bets リストから buyeye 文字列を組み立てる。"""
    venue_code = VENUE_TO_CODE.get(venue, venue)
    entries = []
    for bet in bets:
        if bet["type"] not in TYPE_TO_SHIKIBETSU:
            continue
        entries.append(_build_buyeye_entry(date, venue_code, race_no, bet))
    return ":".join(entries)


def place_bet(
    date: str,
    venue: str,
    race_no: int,
    bets: list[dict],
    total_amount: int,
    *,
    check_only: bool = True,
) -> dict:
    """IPAT投票APIを呼び出す。

    Args:
        date: YYYYMMDD
        venue: 会場名 (例: "hanshin")
        race_no: レース番号
        bets: betting エージェントの出力 bets リスト
        total_amount: 合計金額
        check_only: True=betchk (投票チェックのみ), False=bet (実際に投票)
    """
    buyeye = build_buyeye(date, venue, race_no, bets)
    if not buyeye:
        return {"error": "有効な馬券がありません", "ret": -1}

    data = {
        "tncid": os.environ["TNCID"],
        "tncpw": os.environ["TNCPW"],
        "gov": "C",
        "uno": os.environ["IPAT_UNO"],
        "pin": os.environ["IPAT_PIN"],
        "pno": os.environ["IPAT_PNO"],
        "betcd": "betchk" if check_only else "bet",
        "money": str(total_amount),
        "buyeye": buyeye,
    }

    resp = requests.post(API_URL, data=data)
    resp.raise_for_status()
    body = resp.json()

    return {
        "ret": body.get("ret"),
        "msg": body.get("msg", ""),
        "check_only": check_only,
        "buyeye": buyeye,
        "total_amount": total_amount,
    }


if __name__ == "__main__":
    # テスト用: サンプル馬券で betchk
    sample_bets = [
        {"type": "win", "horses": [3], "amount": 100},
        {"type": "place", "horses": [5], "amount": 200},
    ]
    buyeye = build_buyeye("20260301", "hanshin", 11, sample_bets)
    print(f"buyeye: {buyeye}")
    print(f"money: 300")
    print()
    result = place_bet("20260301", "hanshin", 11, sample_bets, 300, check_only=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
