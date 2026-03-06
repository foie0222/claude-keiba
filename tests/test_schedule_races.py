"""schedule_races のユニットテスト。"""
import sys
from datetime import time as dtime
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


def test_fetch_race_schedule_skips_unknown_venue():
    rows = [
        _make_race_row("09", 1, "0935"),
        _make_race_row("99", 2, "1005"),  # unknown venue code
    ]
    with patch("schedule_races.KBDBClient") as MockClient:
        MockClient.return_value.query.return_value = rows
        from schedule_races import fetch_race_schedule
        races = fetch_race_schedule("20260307")

    assert len(races) == 1
    assert races[0]["venue"] == "hanshin"


def test_fetch_race_schedule_empty():
    with patch("schedule_races.KBDBClient") as MockClient:
        MockClient.return_value.query.return_value = []
        from schedule_races import fetch_race_schedule
        races = fetch_race_schedule("20260307")

    assert races == []


def test_calc_trigger_time_normal():
    from schedule_races import calc_trigger_time
    # 発走10:00 → 40分前 = 09:20
    assert calc_trigger_time("1000") == dtime(9, 20)


def test_calc_trigger_time_early():
    from schedule_races import calc_trigger_time
    # 発走09:35 → 40分前 = 08:55
    assert calc_trigger_time("0935") == dtime(8, 55)


def test_generate_units():
    from schedule_races import generate_units
    race = {"venue": "hanshin", "race_no": 11, "post_time": "1540"}
    service, timer = generate_units("20260307", race)

    assert "run.py 20260307 hanshin 11" in service
    assert "TimeoutStartSec=2400" in service
    assert "OnCalendar=2026-03-07 15:00:00" in timer
    assert "AccuracySec=1s" in timer
