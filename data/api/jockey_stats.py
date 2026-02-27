"""出走馬の騎手成績統計を取得。

Usage: python data/api/jockey_stats.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

各出走馬の騎手の直近1年の成績をRACEDTLから集計して返す。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id, CODE_TO_VENUE


def get_jockey_stats(race_id: str) -> dict:
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    # 出走馬の騎手コード取得
    entry_rows = client.query(
        f"SELECT UMANO, HSNM, JKYCD, JKYNM4 FROM RACEDTL "
        f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no} ORDER BY UMANO;"
    )
    if not entry_rows:
        return {"error": f"Race not found: {race_id}"}

    jky_codes = list({r["JKYCD"].strip() for r in entry_rows if r.get("JKYCD", "").strip()})
    jky_list = ",".join(f"'{c}'" for c in jky_codes)

    # 直近1年の成績を集計
    year_ago = str(int(date) - 10000)  # 簡易的に1年前
    stats_rows = client.query(
        f"SELECT JKYCD, RCOURSECD, FIXPLC, ABNMLCD FROM RACEDTL "
        f"WHERE JKYCD IN ({jky_list}) AND OPDT>='{year_ago}' AND OPDT<'{date}' AND ABNMLCD='0';"
    )

    # 騎手ごとに集計
    jky_stats: dict[str, dict] = {}
    for r in stats_rows:
        jcd = r["JKYCD"].strip()
        ccd = r["RCOURSECD"].strip()
        plc = int(r["FIXPLC"]) if r.get("FIXPLC", "").strip() else 99

        if jcd not in jky_stats:
            jky_stats[jcd] = {"total": 0, "win": 0, "top2": 0, "top3": 0, "by_course": {}}
        s = jky_stats[jcd]
        s["total"] += 1
        if plc == 1:
            s["win"] += 1
        if plc <= 2:
            s["top2"] += 1
        if plc <= 3:
            s["top3"] += 1

        # コース別集計
        if ccd not in s["by_course"]:
            s["by_course"][ccd] = {"total": 0, "win": 0, "top3": 0}
        bc = s["by_course"][ccd]
        bc["total"] += 1
        if plc == 1:
            bc["win"] += 1
        if plc <= 3:
            bc["top3"] += 1

    jockeys = []
    for entry in entry_rows:
        jcd = entry["JKYCD"].strip()
        s = jky_stats.get(jcd, {"total": 0, "win": 0, "top2": 0, "top3": 0, "by_course": {}})
        total = s["total"] or 1

        course_stats = s["by_course"].get(course_cd)
        course_info = None
        if course_stats:
            ct = course_stats["total"] or 1
            course_info = {
                "venue": CODE_TO_VENUE.get(course_cd, course_cd),
                "races": course_stats["total"],
                "win_rate": round(course_stats["win"] / ct, 3),
                "top3_rate": round(course_stats["top3"] / ct, 3),
            }

        jockeys.append({
            "number": int(entry.get("UMANO", 0)),
            "horse_name": entry.get("HSNM", "").strip(),
            "jockey_code": jcd,
            "jockey_name": entry.get("JKYNM4", "").strip(),
            "year_stats": {
                "races": s["total"],
                "wins": s["win"],
                "top2": s["top2"],
                "top3": s["top3"],
                "win_rate": round(s["win"] / total, 3),
                "top3_rate": round(s["top3"] / total, 3),
            },
            "course_stats": course_info,
        })

    return {"race_id": race_id, "jockeys": jockeys}


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_jockey_stats(race_id), ensure_ascii=False, indent=2))
