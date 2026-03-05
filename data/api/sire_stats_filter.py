"""TOONファイルから該当馬のデータのみ抽出するフィルタ。

prefetch完了後にローカルファイルを読み込んでフィルタリングし、
レース出走馬に関連する種牡馬・母父の産駒成績のみを返す。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import toon

DATA_DIR = Path(__file__).resolve().parents[1] / "bloodline"


def filter_for_race(horse_detail: dict) -> str:
    """horse_detailから種牡馬名・母父名を抽出し、3つのTOONファイルをフィルタして結合TOON文字列を返す。"""
    horses = horse_detail.get("horses", [])
    sire_names = set()
    bms_names = set()
    for h in horses:
        pedigree = h.get("pedigree", {})
        sire = pedigree.get("sire", "").strip()
        dam_sire = pedigree.get("dam_sire", "").strip()
        if sire:
            sire_names.add(sire)
        if dam_sire:
            bms_names.add(dam_sire)

    result = {}

    # sire_stats.toon — name列でフィルタ
    sire_path = DATA_DIR / "sire_stats.toon"
    if sire_path.exists() and sire_names:
        rows = toon.decode(sire_path.read_text(encoding="utf-8"))
        filtered = [r for r in rows if r["name"] in sire_names]
        if filtered:
            result["sire_stats"] = filtered

    # bms_stats.toon — name列でフィルタ
    bms_path = DATA_DIR / "bms_stats.toon"
    if bms_path.exists() and bms_names:
        rows = toon.decode(bms_path.read_text(encoding="utf-8"))
        filtered = [r for r in rows if r["name"] in bms_names]
        if filtered:
            result["bms_stats"] = filtered

    # nicks.toon — sire列 AND bms列でフィルタ
    nicks_path = DATA_DIR / "nicks.toon"
    if nicks_path.exists() and sire_names and bms_names:
        rows = toon.decode(nicks_path.read_text(encoding="utf-8"))
        filtered = [r for r in rows if r["sire"] in sire_names and r["bms"] in bms_names]
        if filtered:
            result["nicks"] = filtered

    return toon.encode(result) if result else ""
