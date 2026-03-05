"""同コース・同距離の直近レースからラップタイムを取得。

Usage: python data/api/race_laps.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

同じ会場・同じ距離・同じ馬場（芝/ダート）の直近レースを最大10件取得し、
netkeibaのレース結果ページからラップタイム（1ハロンごと）をスクレイピングする。
"""
import json
import re
import sys
import time as time_mod
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id, CODE_TO_VENUE, TRACK_MAP, CONDITION_MAP

RESULT_URL = "https://race.netkeiba.com/race/result.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}


def _surface_from_trackcd(trackcd: str) -> str:
    """TRACKCDの先頭2桁から馬場種別を返す。"""
    prefix = trackcd[:2] if trackcd else ""
    return TRACK_MAP.get(prefix, "")


def _build_netkeiba_id(opdt: str, course_cd: str, kai: str, nichiji: str, rno: int) -> str:
    """KBDB情報からnetkeiba race_id (12桁) を構築。"""
    year = opdt[:4]
    return f"{year}{course_cd}{kai.strip().zfill(2)}{nichiji.strip().zfill(2)}{rno:02d}"


def _scrape_lap_times(nk_id: str) -> dict | None:
    """netkeibaのレース結果ページからラップタイムをスクレイピング。

    Returns:
        {"laps": [12.3, 11.2, ...], "first_half": "59.9", "second_half": "57.0", "pace_label": "S"}
        取得失敗時はNone
    """
    try:
        resp = requests.get(RESULT_URL, params={"race_id": nk_id}, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        resp.encoding = "EUC-JP"
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    # ラップタイムセクションを探す（複数のクラス名に対応）
    lap_section = (
        soup.find(class_="RapTime_HalopaceTable")
        or soup.find(class_="Race_HalopaceTable")
    )
    if not lap_section:
        # フォールバック: RaceResult_Box内を探す
        box = soup.find(class_="RaceResult_Box")
        if box:
            lap_section = box

    if not lap_section:
        return None

    # "ラップ" ラベルを含む行からタイム配列を取得
    for tr in lap_section.find_all("tr"):
        th = tr.find("th")
        if th and "ラップ" in th.get_text():
            td = tr.find("td")
            if td:
                lap_text = td.get_text()
                lap_matches = re.findall(r'(\d{1,2}\.\d)', lap_text)
                if lap_matches:
                    result["laps"] = [float(x) for x in lap_matches]
            break

    # テーブル構造でなかった場合、テキストからラップを探す
    if "laps" not in result:
        full_text = lap_section.get_text()
        # "ラップ" の後に続く数値列を探す
        rap_match = re.search(r'ラップ[^\d]*(([\d]{1,2}\.\d[\s\-−]+)+[\d]{1,2}\.\d)', full_text)
        if rap_match:
            lap_matches = re.findall(r'(\d{1,2}\.\d)', rap_match.group(1))
            if lap_matches:
                result["laps"] = [float(x) for x in lap_matches]

    if "laps" not in result:
        return None

    # ペース情報を探す: "S(59.9-57.0)" or "M(58.5-58.0)" 形式
    for tr in lap_section.find_all("tr"):
        th = tr.find("th")
        if th and "ペース" in th.get_text():
            td = tr.find("td")
            if td:
                pace_text = td.get_text()
                pace_match = re.search(
                    r'([SMH])\s*[\(（]?\s*(\d+\.?\d*)\s*[-\-ー]\s*(\d+\.?\d*)',
                    pace_text,
                )
                if pace_match:
                    result["pace_label"] = pace_match.group(1)
                    result["first_half"] = pace_match.group(2)
                    result["second_half"] = pace_match.group(3)
            break

    # ペース情報がテーブル外にある場合のフォールバック
    if "pace_label" not in result:
        full_text = lap_section.get_text()
        pace_match = re.search(
            r'([SMH])\s*[\(（]\s*(\d+\.?\d*)\s*[-\-ー]\s*(\d+\.?\d*)',
            full_text,
        )
        if pace_match:
            result["pace_label"] = pace_match.group(1)
            result["first_half"] = pace_match.group(2)
            result["second_half"] = pace_match.group(3)

    return result


def get_race_laps(race_id: str) -> dict:
    """同コース・同距離の直近レースのラップタイムを取得。"""
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    # 当該レースの距離・馬場を取得
    race_rows = client.query(
        f"SELECT DIST, TRACKCD FROM RACEMST "
        f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no};"
    )
    if not race_rows:
        return {"error": f"Race not found: {race_id}"}

    distance = int(race_rows[0].get("DIST", 0))
    track_cd = race_rows[0].get("TRACKCD", "")
    surface = _surface_from_trackcd(track_cd)

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

    # 各レースのラップタイムをスクレイピング
    races = []
    for row in filtered:
        opdt = row.get("OPDT", "").strip()
        rno = int(row.get("RNO", 0))
        kai = row.get("KAI", "").strip()
        nichiji = row.get("NITIME", "").strip()
        rc = row.get("RCOURSECD", "").strip()

        nk_id = _build_netkeiba_id(opdt, rc, kai, nichiji, rno)
        lap_data = _scrape_lap_times(nk_id)
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
            "entry_count": int(row.get("ENTNUM", 0)),
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
            "error": "ラップデータの取得に全件失敗しました",
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
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_race_laps(race_id), ensure_ascii=False, indent=2))
