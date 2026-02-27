"""netkeiba APIからオッズデータを取得。

Usage: python data/api/odds.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260222_tokyo_11)

netkeiba odds API:
  https://race.netkeiba.com/api/api_get_jra_odds.html
  type: 1=単勝/複勝, 3=枠連, 4=馬連, 5=ワイド, 6=馬単, 7=三連複, 8=三連単
  レスポンスのdataはZLIB+Base64圧縮(compress=1)。
"""
import base64
import json
import sys
import zlib
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient

VENUE_TO_CODE = {
    "sapporo": "01", "hakodate": "02", "fukushima": "03", "niigata": "04",
    "tokyo": "05", "nakayama": "06", "chukyo": "07", "kyoto": "08",
    "hanshin": "09", "kokura": "10",
}

API_URL = "https://race.netkeiba.com/api/api_get_jra_odds.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Referer": "https://race.netkeiba.com/odds/index.html",
}

ODDS_TYPE_MAP = {
    "win": "1",       # 単勝
    "place": "2",     # 複勝 (type=1で同時取得)
    "bracket": "3",   # 枠連
    "quinella": "4",  # 馬連
    "wide": "5",      # ワイド
    "exacta": "6",    # 馬単
    "trio": "7",      # 三連複
    "trifecta": "8",  # 三連単
}


def _resolve_netkeiba_race_id(race_id: str) -> str:
    """KBDB race_id → netkeiba race_id (12桁) に変換。"""
    parts = race_id.split("_")
    date_str, venue, race_no = parts[0], parts[1], int(parts[2])
    course_cd = VENUE_TO_CODE.get(venue, venue)

    client = KBDBClient()
    rows = client.query(
        f"SELECT KAI, NITIME FROM RACEMST "
        f"WHERE OPDT='{date_str}' AND RCOURSECD='{course_cd}' AND RNO={race_no};"
    )
    if not rows:
        raise ValueError(f"Race not found in KBDB: {race_id}")

    kai = rows[0]["KAI"].zfill(2)
    nichiji = rows[0]["NITIME"].zfill(2)
    year = date_str[:4]
    return f"{year}{course_cd}{kai}{nichiji}{race_no:02d}"


def _fetch_odds_api(netkeiba_race_id: str, odds_type: str) -> tuple[dict, str]:
    """netkeiba APIからオッズを取得。(data, source) を返す。

    source: "realtime" | "confirmed" | ""
    優先順位: リアルタイム(発売中) → 確定オッズ(レース後)
    """
    # 1) リアルタイム(action なし) → 2) 確定(action=update)
    actions = [
        ("", "realtime"),
        ("update", "confirmed"),
    ]
    for action, source in actions:
        params = {
            "pid": "api_get_jra_odds",
            "race_id": netkeiba_race_id,
            "type": odds_type,
            "compress": "1",
        }
        if action:
            params["action"] = action

        resp = requests.get(API_URL, params=params, headers=HEADERS)
        resp.raise_for_status()
        body = resp.json()

        data_raw = body.get("data")
        if not data_raw:
            continue

        if isinstance(data_raw, str):
            decoded = base64.b64decode(data_raw)
            decompressed = zlib.decompress(decoded)
            return json.loads(decompressed), source

        if isinstance(data_raw, dict) and data_raw.get("odds"):
            return data_raw, source

    return {}, ""


def _parse_win_place(raw_odds: dict) -> dict:
    """type=1のレスポンスから単勝・複勝を整形。"""
    result = {"win": {}, "place": {}}
    odds = raw_odds.get("odds", {})

    for umaban, vals in odds.get("1", {}).items():
        num = str(int(umaban))
        result["win"][num] = {
            "odds": float(vals[0]) if vals[0] else None,
            "popularity": vals[2] if len(vals) > 2 else None,
        }

    for umaban, vals in odds.get("2", {}).items():
        num = str(int(umaban))
        result["place"][num] = {
            "odds_min": float(vals[0]) if vals[0] else None,
            "odds_max": float(vals[1]) if vals[1] else None,
            "popularity": vals[2] if len(vals) > 2 else None,
        }

    return result


def _parse_pair_odds(raw_odds: dict, type_key: str, key_len: int) -> list:
    """馬連・ワイド・枠連・馬単 等のペア型オッズを整形。"""
    result = []
    odds = raw_odds.get("odds", {}).get(type_key, {})

    for combo, vals in odds.items():
        if key_len == 4:
            h1, h2 = str(int(combo[:2])), str(int(combo[2:]))
        elif key_len == 6:
            h1, h2, h3 = str(int(combo[:2])), str(int(combo[2:4])), str(int(combo[4:]))
        else:
            continue

        odds_val = vals[0]
        if isinstance(odds_val, str):
            odds_val = odds_val.replace(",", "")
        entry = {"odds": float(odds_val) if odds_val else None}

        if vals[1] is not None:
            odds_max = vals[1]
            if isinstance(odds_max, str):
                odds_max = odds_max.replace(",", "")
            entry["odds_max"] = float(odds_max)

        if len(vals) > 2:
            entry["popularity"] = vals[2]

        if key_len == 4:
            entry["combination"] = f"{h1}-{h2}"
        else:
            entry["combination"] = f"{h1}-{h2}-{h3}"

        result.append(entry)

    return result


def get_odds(race_id: str) -> dict:
    """全馬券種のオッズを取得。"""
    try:
        nk_id = _resolve_netkeiba_race_id(race_id)
    except (ValueError, RuntimeError) as e:
        return {"race_id": race_id, "error": str(e)}

    result = {
        "race_id": race_id,
        "netkeiba_race_id": nk_id,
    }

    # 単勝・複勝 (type=1で両方取れる)
    raw, source = _fetch_odds_api(nk_id, "1")
    if raw:
        wp = _parse_win_place(raw)
        result["win"] = wp["win"]
        result["place"] = wp["place"]
        result["official_datetime"] = raw.get("official_datetime", "")
        result["odds_source"] = source
    else:
        result["win"] = {}
        result["place"] = {}
        result["odds_source"] = ""
        result["error_win_place"] = "オッズ未発売"

    # 馬連 (type=4)
    raw, _ = _fetch_odds_api(nk_id, "4")
    if raw:
        result["quinella"] = _parse_pair_odds(raw, "4", 4)

    # ワイド (type=5)
    raw, _ = _fetch_odds_api(nk_id, "5")
    if raw:
        result["wide"] = _parse_pair_odds(raw, "5", 4)

    # 馬単 (type=6)
    raw, _ = _fetch_odds_api(nk_id, "6")
    if raw:
        result["exacta"] = _parse_pair_odds(raw, "6", 4)

    # 三連複 (type=7)
    raw, _ = _fetch_odds_api(nk_id, "7")
    if raw:
        result["trio"] = _parse_pair_odds(raw, "7", 6)

    # 三連単 (type=8)
    raw, _ = _fetch_odds_api(nk_id, "8")
    if raw:
        result["trifecta"] = _parse_pair_odds(raw, "8", 6)

    return result


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    data = get_odds(race_id)
    print(json.dumps(data, ensure_ascii=False, indent=2))
