"""TOONファイルから該当馬のデータのみ抽出するフィルタ。

prefetch完了後にローカルファイルを読み込んでフィルタリングし、
レース出走馬に関連する種牡馬・母父の産駒成績のみを返す。
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]


def parse_toon(path: Path) -> tuple[str, list[str], list[list[str]]]:
    """TOONファイルをパース → (block_name, columns, rows)

    TOON形式:
        block_name[N]{col1,col2,...}:
        val1,val2,...
        val1,val2,...
    """
    text = path.read_text(encoding="utf-8")
    lines = text.strip().split("\n")
    if not lines:
        return ("", [], [])

    header = lines[0]
    # "sire_stats[123]{name,s,d,runs,wins,top3}:" をパース
    bracket = header.index("[")
    brace_open = header.index("{")
    brace_close = header.index("}")
    block_name = header[:bracket]
    columns = header[brace_open + 1:brace_close].split(",")

    rows = []
    for line in lines[1:]:
        if line.strip():
            rows.append(line.split(","))
    return block_name, columns, rows


def _build_toon(block_name: str, columns: list[str], rows: list[list[str]]) -> str:
    """フィルタ済みデータからTOON文字列を組み立てる。"""
    lines = [f"{block_name}[{len(rows)}]{{{','.join(columns)}}}:"]
    for row in rows:
        lines.append(",".join(row))
    return "\n".join(lines)


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

    parts = []

    # sire_stats.toon — name列(index 0)でフィルタ
    sire_path = DATA_DIR / "sire_stats.toon"
    if sire_path.exists() and sire_names:
        block_name, columns, rows = parse_toon(sire_path)
        filtered = [r for r in rows if r[0] in sire_names]
        if filtered:
            parts.append(_build_toon(block_name, columns, filtered))

    # bms_stats.toon — name列(index 0)でフィルタ
    bms_path = DATA_DIR / "bms_stats.toon"
    if bms_path.exists() and bms_names:
        block_name, columns, rows = parse_toon(bms_path)
        filtered = [r for r in rows if r[0] in bms_names]
        if filtered:
            parts.append(_build_toon(block_name, columns, filtered))

    # nicks.toon — sire列(index 0) AND bms列(index 1)でフィルタ
    nicks_path = DATA_DIR / "nicks.toon"
    if nicks_path.exists() and sire_names and bms_names:
        block_name, columns, rows = parse_toon(nicks_path)
        filtered = [r for r in rows if r[0] in sire_names and r[1] in bms_names]
        if filtered:
            parts.append(_build_toon(block_name, columns, filtered))

    return "\n\n".join(parts)
