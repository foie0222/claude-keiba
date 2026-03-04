"""種牡馬・母父・ニックスの産駒成績を集計しTOON形式で出力する。

Usage:
    python data/api/generate_sire_stats.py

出力:
    data/sire_stats.toon  — 種牡馬 × 芝ダート × 距離帯
    data/bms_stats.toon   — 母父(BMS) × 芝ダート × 距離帯
    data/nicks.toon       — 父×母父ニックス（10走以上）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient

DATA_DIR = Path(__file__).resolve().parents[1]

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


def write_toon(path: Path, block_name: str, columns: list[str], rows: list[dict], col_keys: list[str]) -> int:
    """TOON形式でファイルに書き出す。書き出した行数を返す。"""
    lines = [f"{block_name}[{len(rows)}]{{{','.join(columns)}}}:"]
    for row in rows:
        vals = []
        for k in col_keys:
            v = row.get(k, "").strip()
            if k in _LOWER_KEYS:
                v = v.lower()
            vals.append(v)
        lines.append(",".join(vals))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def main():
    client = KBDBClient()

    # Q1: 種牡馬
    print("  種牡馬成績を集計中...", file=sys.stderr, flush=True)
    sire_rows = client.query(SQL_SIRE)
    n = write_toon(
        DATA_DIR / "sire_stats.toon",
        "sire_stats",
        ["name", "s", "d", "runs", "wins", "top3"],
        sire_rows,
        ["FHSNM", "SURFACE", "DISTCAT", "RUNS", "WINS", "TOP3"],
    )
    print(f"  ✓ sire_stats.toon ({n}行)", file=sys.stderr, flush=True)

    # Q2: 母父(BMS)
    print("  母父成績を集計中...", file=sys.stderr, flush=True)
    bms_rows = client.query(SQL_BMS)
    n = write_toon(
        DATA_DIR / "bms_stats.toon",
        "bms_stats",
        ["name", "s", "d", "runs", "wins", "top3"],
        bms_rows,
        ["MFHSNM", "SURFACE", "DISTCAT", "RUNS", "WINS", "TOP3"],
    )
    print(f"  ✓ bms_stats.toon ({n}行)", file=sys.stderr, flush=True)

    # Q3: ニックス
    print("  ニックス成績を集計中...", file=sys.stderr, flush=True)
    nicks_rows = client.query(SQL_NICKS)
    n = write_toon(
        DATA_DIR / "nicks.toon",
        "nicks",
        ["sire", "bms", "s", "d", "runs", "wins", "top3"],
        nicks_rows,
        ["FHSNM", "MFHSNM", "SURFACE", "DISTCAT", "RUNS", "WINS", "TOP3"],
    )
    print(f"  ✓ nicks.toon ({n}行)", file=sys.stderr, flush=True)

    print("完了", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
