"""出走馬の過去走成績を取得。

Usage: python data/api/past_results.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

各出走馬の直近10走の成績をRACEDTLから取得し、レース情報をRACEMSTと結合して返す。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id, CODE_TO_VENUE, TRACK_MAP, CONDITION_MAP, WEATHER_MAP


def get_past_results(race_id: str) -> dict:
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    # 出走馬一覧を取得
    entry_rows = client.query(
        f"SELECT UMANO, BLDNO, HSNM FROM RACEDTL "
        f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no} ORDER BY UMANO;"
    )
    if not entry_rows:
        return {"error": f"Race not found: {race_id}"}

    bldnos = [r["BLDNO"].strip() for r in entry_rows if r.get("BLDNO", "").strip()]
    bldno_list = ",".join(f"'{b}'" for b in bldnos)

    # 全出走馬の過去走を一括取得（当該レースより前の日付のみ）
    past_rows = client.query(
        f"SELECT D.BLDNO, D.OPDT, D.RCOURSECD, D.RNO, D.UMANO, D.WAKNO, "
        f"D.FIXPLC, D.RUNTM, D.FTNWGHT, D.WGHT, D.ZOGENSIGN, D.ZOGENDIFF, "
        f"D.JKYNM4, D.TANODDS, D.TANNINKI, D.ABNMLCD, D.SH3FL, D.DIFFTM, "
        f"M.RNMHON, M.DIST, M.TRACKCD, M.TSTATCD, M.DSTATCD, M.WEATHERCD, M.ENTNUM "
        f"FROM RACEDTL D "
        f"JOIN RACEMST M ON D.OPDT=M.OPDT AND D.RCOURSECD=M.RCOURSECD AND D.RNO=M.RNO "
        f"WHERE D.BLDNO IN ({bldno_list}) AND D.OPDT<'{date}' "
        f"ORDER BY D.BLDNO, D.OPDT DESC;"
    )

    # BLDNOごとにグルーピング
    past_by_horse: dict[str, list] = {}
    for r in past_rows:
        bldno = r["BLDNO"].strip()
        past_by_horse.setdefault(bldno, []).append(r)

    horses = []
    for entry in entry_rows:
        bldno = entry["BLDNO"].strip()
        past = past_by_horse.get(bldno, [])[:10]  # 直近10走

        past_races = []
        for p in past:
            track_cd = p.get("TRACKCD", "")[:2] if p.get("TRACKCD") else ""
            venue_cd = p.get("RCOURSECD", "").strip()
            past_races.append({
                "date": p.get("OPDT", "").strip(),
                "venue": CODE_TO_VENUE.get(venue_cd, venue_cd),
                "race_name": p.get("RNMHON", "").strip(),
                "distance": int(p.get("DIST", 0)),
                "surface": TRACK_MAP.get(track_cd, ""),
                "condition": CONDITION_MAP.get(p.get("TSTATCD", "").strip(), "")
                    if TRACK_MAP.get(track_cd, "") in ("芝", "障害") else CONDITION_MAP.get(p.get("DSTATCD", "").strip(), ""),
                "entry_count": int(p.get("ENTNUM", 0)),
                "gate": int(p.get("WAKNO", 0)),
                "number": int(p.get("UMANO", 0)),
                "result": int(p.get("FIXPLC", 0)) if p.get("FIXPLC", "").strip() else None,
                "finish_time": int(p.get("RUNTM", 0)) if p.get("RUNTM", "").strip() else None,
                "last_3f": int(p.get("SH3FL", 0)) if p.get("SH3FL", "").strip() else None,
                "margin": p.get("DIFFTM", "").strip(),
                "weight_carried": int(p.get("FTNWGHT", 0)) / 10 if p.get("FTNWGHT", "").strip() else None,
                "body_weight": int(p.get("WGHT", 0)) if p.get("WGHT", "").strip() else None,
                "jockey": p.get("JKYNM4", "").strip(),
                "odds": int(p.get("TANODDS", 0)) / 10 if p.get("TANODDS", "").strip() else None,
                "popularity": int(p.get("TANNINKI", 0)) if p.get("TANNINKI", "").strip() else None,
            })

        horses.append({
            "number": int(entry.get("UMANO", 0)),
            "name": entry.get("HSNM", "").strip(),
            "bldno": bldno,
            "past_race_count": len(past_races),
            "past_races": past_races,
        })

    return {"race_id": race_id, "horses": horses}


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_past_results(race_id), ensure_ascii=False, indent=2))
