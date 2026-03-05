"""netkeiba追い切りページから調教データを取得。

Usage: python data/api/training.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260222_tokyo_11)

Source: https://race.netkeiba.com/race/oikiri.html?race_id=<nk_id>&type=2
type=2は最終追い切り1本のみ（コメント＋タイム＋評価）。
全頭データの取得にはnetkeibaログインが必要（非ログインは3頭まで）。
"""
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from odds import _resolve_netkeiba_race_id

OIKIRI_URL = "https://race.netkeiba.com/race/oikiri.html"
LOGIN_URL = "https://regist.netkeiba.com/account/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}


def _login_session() -> requests.Session:
    """netkeibaにログインしたセッションを返す。"""
    session = requests.Session()
    session.headers.update(HEADERS)
    email = os.environ.get("NETKEIBA_EMAIL", "")
    password = os.environ.get("NETKEIBA_PASSWORD", "")
    if not email or not password:
        return session
    session.post(LOGIN_URL, data={
        "pid": "login",
        "action": "auth",
        "login_id": email,
        "pswd": password,
    }, allow_redirects=True)
    return session


def _parse_time_lap(raw: str) -> dict:
    """タイムラップ文字列をパース。

    例: '83.8(17.3)66.5(15.7)50.8(13.2)37.6(26.0)11.6(11.6)内タナスーペルノーバ馬也と併入'
    → { "raw": ..., "final_time": "83.8", "f1": "11.6", "laps": [...], "partner_note": "..." }
    """
    result = {"raw": raw}

    # 併せ馬情報を分離（タイム部分の後の日本語テキスト）
    # タイムは数字と括弧とハイフンとピリオドで構成
    m = re.match(r'^[-\d.()]+', raw)
    if m:
        time_part = m.group(0)
        partner_note = raw[m.end():].strip()
        if partner_note:
            result["partner_note"] = partner_note
    else:
        time_part = raw

    # ラップ解析: 数値(数値)数値(数値)...
    laps = re.findall(r'(\d+\.?\d*)\((\d+\.?\d*)\)', time_part)
    if laps:
        result["final_time"] = laps[0][0]
        result["f1"] = laps[-1][0]
        result["laps"] = [{"cumulative": c, "section": s} for c, s in laps]

    return result


def get_training(race_id: str) -> dict:
    """追い切りデータを取得。"""
    try:
        nk_id = _resolve_netkeiba_race_id(race_id)
    except (ValueError, RuntimeError) as e:
        return {"race_id": race_id, "error": str(e)}

    session = _login_session()
    resp = session.get(OIKIRI_URL, params={"race_id": nk_id, "type": "2"})
    resp.raise_for_status()
    resp.encoding = "EUC-JP"
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="OikiriTable")
    if not table:
        return {"race_id": race_id, "netkeiba_race_id": nk_id, "entries": [],
                "error": "追い切りデータなし"}

    rows = table.find_all("tr")[1:]  # skip header
    entries = []
    i = 0
    while i < len(rows):
        cells = rows[i].find_all(["th", "td"])
        cell_texts = [c.get_text(strip=True) for c in cells]

        if len(cell_texts) < 4 or not cell_texts[0].isdigit() or not cell_texts[1].isdigit():
            i += 1
            continue

        horse_number = int(cell_texts[1])
        horse_name = re.sub(r'前走$', '', cell_texts[3])

        if len(cell_texts) >= 10:
            # Format B: 1行/馬（コメントなし）
            # [枠,馬番,印,馬名,日付,コース,馬場,乗り役,タイム,位置,脚色,評価,等級]
            entry = {
                "horse_number": horse_number,
                "horse_name": horse_name,
                "comment": "",
                "date": cell_texts[4],
                "course": cell_texts[5],
                "condition": cell_texts[6],
                "rider": cell_texts[7],
                "position": cell_texts[9] if len(cell_texts) > 9 else "",
                "leg_color": cell_texts[10] if len(cell_texts) > 10 else "",
                "evaluation": cell_texts[11] if len(cell_texts) > 11 else "",
                "grade": cell_texts[12] if len(cell_texts) > 12 else "",
            }
            if len(cell_texts) > 8:
                entry["time_lap"] = _parse_time_lap(cell_texts[8])
            i += 1
        else:
            # Format A: 2行/馬（コメント付き）
            # Row1=[枠,馬番,印,馬名,コメント] Row2=[日付,コース,馬場,乗り役,タイム,位置,脚色,評価,等級]
            comment = cell_texts[4] if len(cell_texts) > 4 else ""
            entry = {
                "horse_number": horse_number,
                "horse_name": horse_name,
                "comment": comment,
            }
            if i + 1 < len(rows):
                data_cells = [c.get_text(strip=True) for c in rows[i + 1].find_all(["th", "td"])]
                if data_cells:
                    entry["date"] = data_cells[0] if len(data_cells) > 0 else ""
                    entry["course"] = data_cells[1] if len(data_cells) > 1 else ""
                    entry["condition"] = data_cells[2] if len(data_cells) > 2 else ""
                    entry["rider"] = data_cells[3] if len(data_cells) > 3 else ""
                    if len(data_cells) > 4:
                        entry["time_lap"] = _parse_time_lap(data_cells[4])
                    entry["position"] = data_cells[5] if len(data_cells) > 5 else ""
                    entry["leg_color"] = data_cells[6] if len(data_cells) > 6 else ""
                    entry["evaluation"] = data_cells[7] if len(data_cells) > 7 else ""
                    entry["grade"] = data_cells[8] if len(data_cells) > 8 else ""
                i += 2
            else:
                i += 1

        entries.append(entry)

    return {
        "race_id": race_id,
        "netkeiba_race_id": nk_id,
        "entry_count": len(entries),
        "entries": entries,
    }


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_training(race_id), ensure_ascii=False, indent=2))
