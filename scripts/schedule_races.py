"""レーススケジューラ: KBDB APIからレース一覧を取得し、systemd timer/serviceを生成・登録する。

Usage: python scripts/schedule_races.py <date>
  例: python scripts/schedule_races.py 20260307
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data" / "api"))
from kbdb_client import KBDBClient
from race_info import CODE_TO_VENUE


def fetch_race_schedule(date: str) -> list[dict]:
    """指定日の全レース(会場,レース番号,発走時刻)を取得する。"""
    client = KBDBClient()
    rows = client.query(
        f"SELECT RCOURSECD, RNO, POSTTM FROM RACEMST WHERE OPDT='{date}' ORDER BY POSTTM;"
    )
    races = []
    for row in rows:
        venue = CODE_TO_VENUE.get(row["RCOURSECD"].strip())
        if venue is None:
            continue
        races.append({
            "venue": venue,
            "race_no": int(row["RNO"]),
            "post_time": row["POSTTM"].strip(),
        })
    return races
