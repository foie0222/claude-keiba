"""種牡馬・母父・ニックスの産駒成績を集計しTOON形式で出力する。

Usage:
    python data/api/generate_sire_stats.py

出力:
    data/bloodline/sire_stats.toon  — 種牡馬 × 芝ダート × 距離帯
    data/bloodline/bms_stats.toon   — 母父(BMS) × 芝ダート × 距離帯
    data/bloodline/nicks.toon       — 父×母父ニックス（10走以上）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import toon

DATA_DIR = Path(__file__).resolve().parents[1] / "bloodline"

# 種牡馬 × 芝ダート × 距離帯
SQL_SIRE = """
SELECT H.FHSNM,
  CASE WHEN M.TRACKCD LIKE '1%' THEN 'T' ELSE 'D' END AS SURFACE,
  CASE WHEN M.DIST <= 1400 THEN 'sprint' WHEN M.DIST <= 1800 THEN 'mile'
       WHEN M.DIST <= 2200 THEN 'middle' ELSE 'long' END AS DISTCAT,
  COUNT(*) AS RUNS,
  SUM(CASE WHEN D.FIXPLC='01' THEN 1 ELSE 0 END) AS WINS,
  SUM(CASE WHEN D.FIXPLC IN ('01','02','03') THEN 1 ELSE 0 END) AS TOP3
FROM RACEDTL D, HORSE H, RACEMST M
WHERE D.BLDNO = H.BLDNO
  AND D.OPDT = M.OPDT AND D.RCOURSECD = M.RCOURSECD AND D.RNO = M.RNO
  AND H.FHSNM <> '' AND D.FIXPLC <> '00' AND D.ABNMLCD = '0'
GROUP BY H.FHSNM, SURFACE, DISTCAT
""".strip()

# 母父(BMS) × 芝ダート × 距離帯
SQL_BMS = """
SELECT H.MFHSNM,
  CASE WHEN M.TRACKCD LIKE '1%' THEN 'T' ELSE 'D' END AS SURFACE,
  CASE WHEN M.DIST <= 1400 THEN 'sprint' WHEN M.DIST <= 1800 THEN 'mile'
       WHEN M.DIST <= 2200 THEN 'middle' ELSE 'long' END AS DISTCAT,
  COUNT(*) AS RUNS,
  SUM(CASE WHEN D.FIXPLC='01' THEN 1 ELSE 0 END) AS WINS,
  SUM(CASE WHEN D.FIXPLC IN ('01','02','03') THEN 1 ELSE 0 END) AS TOP3
FROM RACEDTL D, HORSE H, RACEMST M
WHERE D.BLDNO = H.BLDNO
  AND D.OPDT = M.OPDT AND D.RCOURSECD = M.RCOURSECD AND D.RNO = M.RNO
  AND H.MFHSNM <> '' AND D.FIXPLC <> '00' AND D.ABNMLCD = '0'
GROUP BY H.MFHSNM, SURFACE, DISTCAT
""".strip()

# 父×母父ニックス（10走以上）
SQL_NICKS = """
SELECT H.FHSNM, H.MFHSNM,
  CASE WHEN M.TRACKCD LIKE '1%' THEN 'T' ELSE 'D' END AS SURFACE,
  CASE WHEN M.DIST <= 1400 THEN 'sprint' WHEN M.DIST <= 1800 THEN 'mile'
       WHEN M.DIST <= 2200 THEN 'middle' ELSE 'long' END AS DISTCAT,
  COUNT(*) AS RUNS,
  SUM(CASE WHEN D.FIXPLC='01' THEN 1 ELSE 0 END) AS WINS,
  SUM(CASE WHEN D.FIXPLC IN ('01','02','03') THEN 1 ELSE 0 END) AS TOP3
FROM RACEDTL D, HORSE H, RACEMST M
WHERE D.BLDNO = H.BLDNO
  AND D.OPDT = M.OPDT AND D.RCOURSECD = M.RCOURSECD AND D.RNO = M.RNO
  AND H.FHSNM <> '' AND H.MFHSNM <> '' AND D.FIXPLC <> '00' AND D.ABNMLCD = '0'
GROUP BY H.FHSNM, H.MFHSNM, SURFACE, DISTCAT
HAVING COUNT(*) >= 10
""".strip()


_LOWER_KEYS = {"SURFACE", "DISTCAT"}


def _normalize_rows(rows: list[dict], col_map: dict[str, str]) -> list[dict]:
    """KBDBのカラム名をTOON用キーにリネームし、値を正規化する。"""
    result = []
    for row in rows:
        d = {}
        for toon_key, db_key in col_map.items():
            v = row.get(db_key, "").strip()
            if db_key in _LOWER_KEYS:
                v = v.lower()
            d[toon_key] = int(v) if v.isdigit() else v
        result.append(d)
    return result


def _write_toon(path: Path, rows: list[dict]) -> int:
    """python-toonでファイルに書き出す。書き出した行数を返す。"""
    path.write_text(toon.encode(rows), encoding="utf-8")
    return len(rows)


def main():
    client = KBDBClient()

    # Q1: 種牡馬
    print("  種牡馬成績を集計中...", file=sys.stderr, flush=True)
    sire_rows = _normalize_rows(
        client.query(SQL_SIRE),
        {"name": "FHSNM", "s": "SURFACE", "d": "DISTCAT", "runs": "RUNS", "wins": "WINS", "top3": "TOP3"},
    )
    n = _write_toon(DATA_DIR / "sire_stats.toon", sire_rows)
    print(f"  ✓ sire_stats.toon ({n}行)", file=sys.stderr, flush=True)

    # Q2: 母父(BMS)
    print("  母父成績を集計中...", file=sys.stderr, flush=True)
    bms_rows = _normalize_rows(
        client.query(SQL_BMS),
        {"name": "MFHSNM", "s": "SURFACE", "d": "DISTCAT", "runs": "RUNS", "wins": "WINS", "top3": "TOP3"},
    )
    n = _write_toon(DATA_DIR / "bms_stats.toon", bms_rows)
    print(f"  ✓ bms_stats.toon ({n}行)", file=sys.stderr, flush=True)

    # Q3: ニックス
    print("  ニックス成績を集計中...", file=sys.stderr, flush=True)
    nicks_rows = _normalize_rows(
        client.query(SQL_NICKS),
        {"sire": "FHSNM", "bms": "MFHSNM", "s": "SURFACE", "d": "DISTCAT", "runs": "RUNS", "wins": "WINS", "top3": "TOP3"},
    )
    n = _write_toon(DATA_DIR / "nicks.toon", nicks_rows)
    print(f"  ✓ nicks.toon ({n}行)", file=sys.stderr, flush=True)

    print("完了", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
