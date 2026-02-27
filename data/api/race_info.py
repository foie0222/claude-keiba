"""レース基本情報+出走馬一覧を取得。

Usage: python data/api/race_info.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient

VENUE_TO_CODE = {
    "sapporo": "01", "hakodate": "02", "fukushima": "03", "niigata": "04",
    "tokyo": "05", "nakayama": "06", "chukyo": "07", "kyoto": "08",
    "hanshin": "09", "kokura": "10",
}
CODE_TO_VENUE = {v: k for k, v in VENUE_TO_CODE.items()}

TRACK_MAP = {"10": "芝", "11": "芝", "12": "芝", "13": "芝",
             "17": "障害", "18": "障害", "19": "障害",
             "20": "ダート", "21": "ダート", "22": "ダート", "23": "ダート"}
WEATHER_MAP = {"1": "晴", "2": "曇", "3": "雨", "4": "小雨", "5": "雪", "6": "小雪"}
CONDITION_MAP = {"0": "良", "1": "良", "2": "稍重", "3": "重", "4": "不良"}
SEX_MAP = {"1": "牡", "2": "牝", "3": "セン"}


def parse_race_id(race_id: str) -> tuple[str, str, int]:
    parts = race_id.split("_")
    return parts[0], VENUE_TO_CODE.get(parts[1], parts[1]), int(parts[2])


def get_race_info(race_id: str) -> dict:
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    race_rows = client.query(
        f"SELECT * FROM RACEMST WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no};"
    )
    if not race_rows:
        return {"error": f"Race not found: {race_id}"}
    rm = race_rows[0]

    detail_rows = client.query(
        f"SELECT * FROM RACEDTL WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no} ORDER BY UMANO;"
    )

    track_cd = rm.get("TRACKCD", "")[:2] if rm.get("TRACKCD") else ""
    surface = TRACK_MAP.get(track_cd, track_cd)

    race = {
        "race_id": race_id,
        "date": date,
        "venue": CODE_TO_VENUE.get(course_cd, course_cd),
        "venue_code": course_cd,
        "race_number": race_no,
        "name": rm.get("RNMHON", "").strip(),
        "distance": int(rm.get("DIST", 0)),
        "surface": surface,
        "track_code": rm.get("TRACKCD", "").strip(),
        "weather": WEATHER_MAP.get(rm.get("WEATHERCD", "").strip(), ""),
        "turf_condition": CONDITION_MAP.get(rm.get("TSTATCD", "").strip(), ""),
        "dirt_condition": CONDITION_MAP.get(rm.get("DSTATCD", "").strip(), ""),
        "post_time": rm.get("POSTTM", "").strip(),
        "entry_count": int(rm.get("ENTNUM", 0)),
        "run_count": int(rm.get("RUNNUM", 0)),
    }

    horses = []
    for rd in detail_rows:
        horse = {
            "number": int(rd.get("UMANO", 0)),
            "gate": int(rd.get("WAKNO", 0)),
            "name": rd.get("HSNM", "").strip(),
            "bldno": rd.get("BLDNO", "").strip(),
            "sex": SEX_MAP.get(rd.get("SEXCD", "").strip(), ""),
            "age": int(rd.get("AGE", 0)),
            "weight_carried": int(rd.get("FTNWGHT", 0)) / 10,
            "jockey_code": rd.get("JKYCD", "").strip(),
            "jockey": rd.get("JKYNM4", "").strip(),
            "trainer_code": rd.get("TRNRCD", "").strip(),
            "trainer": rd.get("TRNRNM4", "").strip(),
            "body_weight": int(rd.get("WGHT", 0)) if rd.get("WGHT", "").strip() else None,
            "weight_diff": rd.get("ZOGENSIGN", "").strip() + rd.get("ZOGENDIFF", "").strip(),
            "abnormal": int(rd.get("ABNMLCD", 0)),
        }
        # 確定着順がある場合（レース終了後）
        if rd.get("FIXPLC", "").strip():
            horse["result"] = int(rd.get("FIXPLC", 0))
            horse["finish_time"] = int(rd.get("RUNTM", 0))
        horses.append(horse)

    return {"race": race, "horses": horses}


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_race_info(race_id), ensure_ascii=False, indent=2))
