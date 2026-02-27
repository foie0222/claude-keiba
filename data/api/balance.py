"""IPAT残高（購入限度額）を取得する。

Usage: python data/api/balance.py
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API_URL = "https://api.gamble-os.net/systems/ip-balance"


def get_balance() -> dict:
    """IPAT残高を取得して返す。"""
    data = {
        "tncid": os.environ["TNCID"],
        "tncpw": os.environ["TNCPW"],
        "gov": "C",
        "uno": os.environ["IPAT_UNO"],
        "pin": os.environ["IPAT_PIN"],
        "pno": os.environ["IPAT_PNO"],
    }
    resp = requests.post(API_URL, data=data)
    resp.raise_for_status()
    body = resp.json()

    if body.get("ret") != 0:
        return {"error": body.get("msg", "unknown error"), "ret": body.get("ret")}

    results = body["results"]
    return {
        "buy_limit_money": int(results["buy_limit_money"]),
        "day_buy_money": int(results["day_buy_money"]),
        "total_buy_money": int(results["total_buy_money"]),
        "day_refund_money": int(results["day_refund_money"]),
        "total_refund_money": int(results["total_refund_money"]),
        "buy_possible_count": int(results["buy_possible_count"]),
    }


if __name__ == "__main__":
    data = get_balance()
    print(json.dumps(data, ensure_ascii=False, indent=2))
