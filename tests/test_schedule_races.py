"""schedule_races のユニットテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _make_race_row(course_cd: str, rno: int, posttm: str) -> dict:
    return {"RCOURSECD": course_cd, "RNO": str(rno), "POSTTM": posttm}


def test_fetch_race_schedule_returns_race_list():
    rows = [
        _make_race_row("09", 1, "0935"),
        _make_race_row("09", 2, "1005"),
    ]
    with patch("schedule_races.KBDBClient") as MockClient:
        MockClient.return_value.query.return_value = rows
        from schedule_races import fetch_race_schedule
        races = fetch_race_schedule("20260307")

    assert len(races) == 2
    assert races[0] == {"venue": "hanshin", "race_no": 1, "post_time": "0935"}
    assert races[1] == {"venue": "hanshin", "race_no": 2, "post_time": "1005"}


def test_fetch_race_schedule_empty():
    with patch("schedule_races.KBDBClient") as MockClient:
        MockClient.return_value.query.return_value = []
        from schedule_races import fetch_race_schedule
        races = fetch_race_schedule("20260307")

    assert races == []
