"""同コース・同距離の直近レースからラップタイムを取得。

Usage: python data/api/race_laps.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

同じ会場・同じ距離・同じ馬場（芝/ダート）の直近レースを最大10件取得し、
netkeibaの走行データAJAXエンドポイントから1着馬のハロンごとラップタイムを取得する。
"""
import json
import os
import re
import sys
import time as time_mod
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id, CODE_TO_VENUE, TRACK_MAP, CONDITION_MAP, _safe_int

LAP_AJAX_URL = "https://db.netkeiba.com/race/ajax_race_result_horse_laptime.html"
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


def _surface_from_trackcd(trackcd: str) -> str:
    """TRACKCDの先頭2桁から馬場種別を返す。"""
    prefix = trackcd[:2] if trackcd else ""
    return TRACK_MAP.get(prefix, "")


def _build_netkeiba_id(opdt: str, course_cd: str, kai: str, nichiji: str, rno: int) -> str:
    """KBDB情報からnetkeiba race_id (12桁) を構築。"""
    year = opdt[:4]
    return f"{year}{course_cd}{kai.strip().zfill(2)}{nichiji.strip().zfill(2)}{rno:02d}"


def _fetch_lap_data(session: requests.Session, nk_id: str) -> dict | None:
    """netkeibaの走行データAJAXエンドポイントから1着馬のラップタイムを取得。

    Returns:
        {"laps": [12.3, 11.2, ...], "distances": ["200m", "400m", ...]}
        取得失敗時はNone
    """
    try:
        resp = session.get(
            LAP_AJAX_URL,
            params={"id": nk_id, "credit": "1"},
            timeout=10,
        )
        resp.raise_for_status()
        resp.encoding = "EUC-JP"
    except requests.RequestException as e:
        print(f"  [WARN] lap fetch failed for nk_id={nk_id}: {e}", file=sys.stderr, flush=True)
        return None

    if "LapSummary_Table" not in resp.text:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="LapSummary_Table")
    if not table:
        return None

    rows = table.find_all("tr")
    if len(rows) < 3:
        return None

    # Row 1 (index 1): 距離ヘッダー (全体, スタート, 追走, 上がり, 200m, 400m, ...)
    header_cells = [c.get_text(strip=True) for c in rows[1].find_all(["th", "td"])]
    # 距離マーカーを抽出 (数字+m のパターン: "200m", "3C800m" → "800m" etc)
    distances = []
    dist_indices = []
    for i, cell in enumerate(header_cells):
        m = re.search(r'(\d+)m$', cell)
        if m:
            distances.append(cell)
            dist_indices.append(i)

    if not distances:
        return None

    # 1着馬のデータ行を探す（着順=1の行）
    winner_row = None
    for row in rows[2:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        # データ行のフォーマット: ['', 着順, 馬番, 馬名, 指数..., ラップ1, 位置1, ラップ2, 位置2, ...]
        for j, cell in enumerate(cells):
            if cell == "1" and j < 5:
                winner_row = cells
                break
        if winner_row:
            break

    if not winner_row:
        return None

    # ラップタイムを抽出（タイム値と位置値が交互に並ぶ）
    # ヘッダーの距離インデックスに対応するデータ位置を計算
    # ヘッダー: [全体, スタート, 追走, 上がり, 200m, 400m, 600m, ...]
    # データ:   ['', 着順, 馬番, 馬名, 全体指数, スタート指数, 追走指数, 上がり指数, ラップ1, 位置1, ラップ2, 位置2, ...]
    # ヘッダーの最初の距離マーカーの位置を基準にデータのオフセットを計算
    first_dist_header_idx = dist_indices[0]
    # ヘッダーの先頭4列 (全体,スタート,追走,上がり) に対応するデータは先頭8列 (空,着順,馬番,馬名,4つの指数)
    # → data_offset = データの距離ラップ開始位置 - ヘッダーの距離開始位置 × 2 + ヘッダーの距離開始位置
    # 実際にはヘッダーの各距離に対してデータは [タイム, 位置] の2セルなので:
    # データの最初のラップタイム = 4(先頭列) + 4(指数) = 8
    # ヘッダーの最初の距離 = first_dist_header_idx (通常4)
    # data_start = 8 for distances starting at header index 4
    data_start = 8  # 固定: 空+着順+馬番+馬名+全体+スタート+追走+上がり

    laps = []
    for k in range(len(distances)):
        data_idx = data_start + k * 2  # 各距離はタイム+位置の2セル
        if data_idx < len(winner_row):
            time_str = winner_row[data_idx]
            try:
                laps.append(float(time_str))
            except ValueError:
                pass

    if not laps:
        return None

    result = {"laps": laps, "distances": distances}

    # 前半/後半タイムを計算
    half = len(laps) // 2
    if half > 0:
        first_half = sum(laps[:half])
        second_half = sum(laps[half:])
        result["first_half"] = f"{first_half:.1f}"
        result["second_half"] = f"{second_half:.1f}"
        # ペースラベル判定（前半-後半 > 1.0: S, < -1.0: H, else: M）
        diff = first_half - second_half
        if diff > 1.0:
            result["pace_label"] = "S"
        elif diff < -1.0:
            result["pace_label"] = "H"
        else:
            result["pace_label"] = "M"

    return result


def get_race_laps(race_id: str) -> dict:
    """同コース・同距離の直近レースのラップタイムを取得。"""
    try:
        date, course_cd, race_no = parse_race_id(race_id)
    except (IndexError, ValueError):
        return {"error": f"Invalid race_id format: {race_id}"}

    try:
        client = KBDBClient()

        # 当該レースの距離・馬場を取得
        race_rows = client.query(
            f"SELECT DIST, TRACKCD FROM RACEMST "
            f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no};"
        )
        if not race_rows:
            return {"error": f"Race not found: {race_id}"}

        distance = _safe_int(race_rows[0].get("DIST"))
        track_cd = race_rows[0].get("TRACKCD", "")
        surface = _surface_from_trackcd(track_cd)

        if distance == 0:
            return {"error": f"Distance data missing from KBDB for race: {race_id}"}
        if not surface:
            return {"error": f"Track surface could not be determined (TRACKCD={track_cd})"}

        # 6ヶ月前の日付を計算
        race_date = datetime.strptime(date, "%Y%m%d")
        six_months_ago = (race_date - timedelta(days=180)).strftime("%Y%m%d")

        # 同会場・同距離の直近レースを検索（馬場フィルタはPython側で実施）
        similar_rows = client.query(
            f"SELECT OPDT, RCOURSECD, RNO, RNMHON, KAI, NITIME, TRACKCD, "
            f"TSTATCD, DSTATCD, ENTNUM "
            f"FROM RACEMST "
            f"WHERE RCOURSECD='{course_cd}' AND DIST={distance} "
            f"AND OPDT>='{six_months_ago}' AND OPDT<'{date}' "
            f"ORDER BY OPDT DESC;"
        )
    except (RuntimeError, TimeoutError) as e:
        return {"race_id": race_id, "error": f"KBDB query failed: {e}"}

    # 同じ馬場（芝/ダート）でフィルタし、最大10件に制限
    filtered = []
    for row in similar_rows:
        row_surface = _surface_from_trackcd(row.get("TRACKCD", ""))
        if row_surface == surface:
            filtered.append(row)
            if len(filtered) >= 10:
                break

    if not filtered:
        return {
            "race_id": race_id,
            "venue": CODE_TO_VENUE.get(course_cd, course_cd),
            "distance": distance,
            "surface": surface,
            "sample_count": 0,
            "races": [],
        }

    # netkeibaログインセッション作成
    session = _login_session()

    # 各レースのラップタイムを取得
    races = []
    scrape_attempts = 0
    for row in filtered:
        opdt = row.get("OPDT", "").strip()
        rno = _safe_int(row.get("RNO"))
        kai = row.get("KAI", "").strip()
        nichiji = row.get("NITIME", "").strip()
        rc = row.get("RCOURSECD", "").strip()

        if not kai or not nichiji:
            print(f"  [WARN] Missing KAI/NITIME for OPDT={opdt} RNO={rno}, skipping",
                  file=sys.stderr, flush=True)
            continue

        nk_id = _build_netkeiba_id(opdt, rc, kai, nichiji, rno)
        scrape_attempts += 1
        lap_data = _fetch_lap_data(session, nk_id)
        time_mod.sleep(1)  # リクエスト間隔

        if not lap_data:
            continue

        row_trackcd = row.get("TRACKCD", "")[:2]
        row_surface = TRACK_MAP.get(row_trackcd, "")
        if row_surface in ("芝", "障害"):
            condition = CONDITION_MAP.get(row.get("TSTATCD", "").strip(), "")
        else:
            condition = CONDITION_MAP.get(row.get("DSTATCD", "").strip(), "")

        race_entry = {
            "date": opdt,
            "race_name": row.get("RNMHON", "").strip(),
            "condition": condition,
            "entry_count": _safe_int(row.get("ENTNUM")),
            "laps": lap_data.get("laps", []),
        }
        if lap_data.get("first_half"):
            race_entry["first_half"] = lap_data["first_half"]
        if lap_data.get("second_half"):
            race_entry["second_half"] = lap_data["second_half"]
        if lap_data.get("pace_label"):
            race_entry["pace_label"] = lap_data["pace_label"]

        races.append(race_entry)

    if not races:
        return {
            "race_id": race_id,
            "venue": CODE_TO_VENUE.get(course_cd, course_cd),
            "distance": distance,
            "surface": surface,
            "sample_count": 0,
            "races": [],
            "error": f"ラップデータの取得に全件失敗しました ({scrape_attempts}件試行)",
        }

    return {
        "race_id": race_id,
        "venue": CODE_TO_VENUE.get(course_cd, course_cd),
        "distance": distance,
        "surface": surface,
        "sample_count": len(races),
        "races": races,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data/api/race_laps.py <race_id>", file=sys.stderr)
        print("  race_id format: YYYYMMDD_venue_RR (e.g., 20260301_nakayama_11)", file=sys.stderr)
        sys.exit(1)
    race_id = sys.argv[1]
    print(json.dumps(get_race_laps(race_id), ensure_ascii=False, indent=2))
