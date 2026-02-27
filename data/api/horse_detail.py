"""出走馬の血統情報を取得。

Usage: python data/api/horse_detail.py <race_id>
  race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

race_info.pyで取得したBLDNOを使い、HORSEテーブルから4代血統を取得する。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient
from race_info import parse_race_id

SEX_MAP = {"1": "牡", "2": "牝", "3": "セン"}


def get_horse_details(race_id: str) -> dict:
    date, course_cd, race_no = parse_race_id(race_id)
    client = KBDBClient()

    # 出走馬のBLDNO一覧を取得
    detail_rows = client.query(
        f"SELECT UMANO, BLDNO, HSNM FROM RACEDTL "
        f"WHERE OPDT='{date}' AND RCOURSECD='{course_cd}' AND RNO={race_no} ORDER BY UMANO;"
    )
    if not detail_rows:
        return {"error": f"Race not found: {race_id}"}

    bldnos = [r["BLDNO"].strip() for r in detail_rows if r.get("BLDNO", "").strip()]
    bldno_list = ",".join(f"'{b}'" for b in bldnos)

    # HORSEテーブルから血統情報取得
    horse_rows = client.query(
        f"SELECT * FROM HORSE WHERE BLDNO IN ({bldno_list});"
    )
    horse_map = {r["BLDNO"].strip(): r for r in horse_rows}

    # 父母のBRDNOを集めてBRDテーブルから血統名を取得
    parent_brdnos = set()
    for h in horse_rows:
        for key in ["FBRDNO", "MBRDNO", "MFBRDNO", "MMBRDNO"]:
            val = h.get(key, "").strip()
            if val and val != "0000000000":
                parent_brdnos.add(val)

    brd_map = {}
    if parent_brdnos:
        brdno_list = ",".join(f"'{b}'" for b in parent_brdnos)
        brd_rows = client.query(
            f"SELECT BRDNO, HSNM, FBRDNO, MBRDNO FROM BRD WHERE BRDNO IN ({brdno_list});"
        )
        brd_map = {r["BRDNO"].strip(): r for r in brd_rows}

    horses = []
    for rd in detail_rows:
        bldno = rd["BLDNO"].strip()
        h = horse_map.get(bldno, {})

        pedigree = _build_pedigree(h, brd_map)

        horses.append({
            "number": int(rd.get("UMANO", 0)),
            "name": rd.get("HSNM", "").strip(),
            "bldno": bldno,
            "sex": SEX_MAP.get(h.get("SEXCD", "").strip(), ""),
            "birth_date": h.get("BTHDT", "").strip(),
            "pedigree": pedigree,
        })

    return {"race_id": race_id, "horses": horses}


def _build_pedigree(h: dict, brd_map: dict) -> dict:
    """HORSEレコードとBRDマップから血統を構築する。"""
    def _horse_field(key: str) -> str:
        return h.get(key, "").strip() or ""

    def _brd_name(brdno: str) -> str:
        b = brd_map.get(brdno, {})
        return b.get("HSNM", "").strip() or ""

    def _brd_parent(brdno: str, field: str) -> str:
        b = brd_map.get(brdno, {})
        parent_brdno = b.get(field, "").strip()
        if parent_brdno:
            return _brd_name(parent_brdno)
        return ""

    sire_brdno = _horse_field("FBRDNO")
    dam_brdno = _horse_field("MBRDNO")

    return {
        "sire": _horse_field("FHSNM") or _brd_name(sire_brdno),
        "dam": _horse_field("MHSNM") or _brd_name(dam_brdno),
        "sire_sire": _horse_field("FFHSNM") or _brd_parent(sire_brdno, "FBRDNO"),
        "sire_dam": _horse_field("FMHSNM") or _brd_parent(sire_brdno, "MBRDNO"),
        "dam_sire": _horse_field("MFHSNM") or _brd_name(_horse_field("MFBRDNO")),
        "dam_dam": _horse_field("MMHSNM") or _brd_name(_horse_field("MMBRDNO")),
    }


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_horse_details(race_id), ensure_ascii=False, indent=2))
