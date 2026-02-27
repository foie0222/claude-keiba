"""出走馬の調教師成績統計を取得。

Usage: python data/api/trainer_stats.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

各出走馬の調教師の直近1年の成績をRACEDTLから集計して返す。
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id, CODE_TO_VENUE


def get_trainer_stats(race_id: str) -> dict:
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    entry_rows = client.query(
        f"SELECT UMANO, HSNM, TRNRCD, TRNRNM4 FROM RACEDTL "
        f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no} ORDER BY UMANO;"
    )
    if not entry_rows:
        return {"error": f"Race not found: {race_id}"}

    trnr_codes = list({r["TRNRCD"].strip() for r in entry_rows if r.get("TRNRCD", "").strip()})
    trnr_list = ",".join(f"'{c}'" for c in trnr_codes)

    dt = datetime.strptime(date, "%Y%m%d")
    year_ago = (dt - timedelta(days=365)).strftime("%Y%m%d")
    stats_rows = client.query(
        f"SELECT TRNRCD, RCOURSECD, FIXPLC, ABNMLCD FROM RACEDTL "
        f"WHERE TRNRCD IN ({trnr_list}) AND OPDT>='{year_ago}' AND OPDT<'{date}' AND ABNMLCD='0';"
    )

    trnr_stats: dict[str, dict] = {}
    for r in stats_rows:
        tcd = r["TRNRCD"].strip()
        ccd = r["RCOURSECD"].strip()
        plc = int(r["FIXPLC"]) if r.get("FIXPLC", "").strip() else 99

        if tcd not in trnr_stats:
            trnr_stats[tcd] = {"total": 0, "win": 0, "top2": 0, "top3": 0, "by_course": {}}
        s = trnr_stats[tcd]
        s["total"] += 1
        if plc == 1:
            s["win"] += 1
        if plc <= 2:
            s["top2"] += 1
        if plc <= 3:
            s["top3"] += 1

        if ccd not in s["by_course"]:
            s["by_course"][ccd] = {"total": 0, "win": 0, "top3": 0}
        bc = s["by_course"][ccd]
        bc["total"] += 1
        if plc == 1:
            bc["win"] += 1
        if plc <= 3:
            bc["top3"] += 1

    trainers = []
    for entry in entry_rows:
        tcd = entry["TRNRCD"].strip()
        s = trnr_stats.get(tcd, {"total": 0, "win": 0, "top2": 0, "top3": 0, "by_course": {}})
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

        trainers.append({
            "number": int(entry.get("UMANO", 0)),
            "horse_name": entry.get("HSNM", "").strip(),
            "trainer_code": tcd,
            "trainer_name": entry.get("TRNRNM4", "").strip(),
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

    return {"race_id": race_id, "trainers": trainers}


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_trainer_stats(race_id), ensure_ascii=False, indent=2))
