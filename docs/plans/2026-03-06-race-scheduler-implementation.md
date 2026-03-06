# レーススケジューラ実装計画

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** systemd user timer で各レースを独立ジョブとして発走40分前に自動実行するスケジューラを作る。

**Architecture:** Pythonスクリプト(schedule_races.py)がKBDB APIからレース一覧を取得し、各レースごとにsystemd oneshot service + timer を動的生成。cronで毎朝8:00に自動登録。

**Tech Stack:** Python 3.12, systemd user units, cron, KBDB API (既存KBDBClient)

---

### Task 1: レース一覧取得関数

**Files:**
- Create: `scripts/schedule_races.py`
- Test: `tests/test_schedule_races.py`

**Step 1: Write the failing test**

`tests/test_schedule_races.py` を作成:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schedule_races.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'schedule_races')

**Step 3: Write minimal implementation**

`scripts/schedule_races.py` を作成:

```python
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
        venue = CODE_TO_VENUE.get(row["RCOURSECD"])
        if venue is None:
            continue
        races.append({
            "venue": venue,
            "race_no": int(row["RNO"]),
            "post_time": row["POSTTM"].strip(),
        })
    return races
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schedule_races.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/schedule_races.py tests/test_schedule_races.py
git commit -m "feat: レース一覧取得関数を追加"
```

---

### Task 2: systemd unit ファイル生成関数

**Files:**
- Modify: `scripts/schedule_races.py`
- Modify: `tests/test_schedule_races.py`

**Step 1: Write the failing test**

`tests/test_schedule_races.py` に追加:

```python
from datetime import time as dtime


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schedule_races.py::test_calc_trigger_time_normal -v`
Expected: FAIL (ImportError)

**Step 3: Write minimal implementation**

`scripts/schedule_races.py` に追加:

```python
from datetime import datetime, time as dtime, timedelta

PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
TRIGGER_MINUTES_BEFORE = 40

SERVICE_TEMPLATE = """\
[Unit]
Description=Keiba Race {date} {venue} {race_no}R

[Service]
Type=oneshot
WorkingDirectory={project_dir}
ExecStart={python} run.py {date} {venue} {race_no}
Environment=PATH={venv_bin}:/usr/bin
TimeoutStartSec=2400
"""

TIMER_TEMPLATE = """\
[Unit]
Description=Keiba Race Timer {date} {venue} {race_no}R

[Timer]
OnCalendar={trigger_time}
AccuracySec=1s
Persistent=false
"""


def calc_trigger_time(post_time: str) -> dtime:
    """発走時刻(HHMM)からTRIGGER_MINUTES_BEFORE分前の時刻を返す。"""
    hh, mm = int(post_time[:2]), int(post_time[2:])
    dt = datetime(2000, 1, 1, hh, mm) - timedelta(minutes=TRIGGER_MINUTES_BEFORE)
    return dt.time()


def generate_units(date: str, race: dict) -> tuple[str, str]:
    """1レース分のsystemd service/timerファイル内容を生成する。"""
    trigger = calc_trigger_time(race["post_time"])
    date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    trigger_str = f"{date_fmt} {trigger.strftime('%H:%M:%S')}"

    service = SERVICE_TEMPLATE.format(
        date=date,
        venue=race["venue"],
        race_no=race["race_no"],
        project_dir=PROJECT_DIR,
        python=VENV_PYTHON,
        venv_bin=VENV_PYTHON.parent,
    )
    timer = TIMER_TEMPLATE.format(
        date=date,
        venue=race["venue"],
        race_no=race["race_no"],
        trigger_time=trigger_str,
    )
    return service, timer
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schedule_races.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/schedule_races.py tests/test_schedule_races.py
git commit -m "feat: systemd unit生成関数を追加"
```

---

### Task 3: クリーンアップ・登録・main関数

**Files:**
- Modify: `scripts/schedule_races.py`
- Modify: `tests/test_schedule_races.py`

**Step 1: Write the failing test**

`tests/test_schedule_races.py` に追加:

```python
from unittest.mock import call


def test_cleanup_old_units(tmp_path):
    from schedule_races import cleanup_old_units
    # keiba- で始まるファイルを作成
    (tmp_path / "keiba-20260306-hanshin-11.service").touch()
    (tmp_path / "keiba-20260306-hanshin-11.timer").touch()
    (tmp_path / "other.service").touch()  # 関係ないファイル

    with patch("schedule_races.subprocess.run") as mock_run:
        cleanup_old_units(tmp_path)

    # keiba- ファイルが削除されていること
    assert not (tmp_path / "keiba-20260306-hanshin-11.service").exists()
    assert not (tmp_path / "keiba-20260306-hanshin-11.timer").exists()
    # 関係ないファイルは残っていること
    assert (tmp_path / "other.service").exists()
    # timer停止のコマンドが呼ばれたこと
    mock_run.assert_called()


def test_install_units(tmp_path):
    from schedule_races import install_units
    races = [
        {"venue": "hanshin", "race_no": 11, "post_time": "1540"},
    ]
    with patch("schedule_races.subprocess.run") as mock_run:
        install_units("20260307", races, tmp_path)

    assert (tmp_path / "keiba-20260307-hanshin-11.service").exists()
    assert (tmp_path / "keiba-20260307-hanshin-11.timer").exists()
    # daemon-reload が呼ばれたこと
    reload_calls = [c for c in mock_run.call_args_list if "daemon-reload" in str(c)]
    assert len(reload_calls) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schedule_races.py::test_cleanup_old_units -v`
Expected: FAIL (ImportError)

**Step 3: Write minimal implementation**

`scripts/schedule_races.py` に追加:

```python
import subprocess

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


def unit_name(date: str, race: dict) -> str:
    """keiba-<date>-<venue>-<race_no> の名前を返す。"""
    return f"keiba-{date}-{race['venue']}-{race['race_no']}"


def cleanup_old_units(unit_dir: Path | None = None) -> None:
    """既存のkeiba-*タイマーを停止し、unit ファイルを削除する。"""
    unit_dir = unit_dir or SYSTEMD_USER_DIR
    if not unit_dir.exists():
        return

    timers = list(unit_dir.glob("keiba-*.timer"))
    for timer_file in timers:
        name = timer_file.stem
        subprocess.run(
            ["systemctl", "--user", "stop", f"{name}.timer"],
            capture_output=True,
        )

    for f in unit_dir.glob("keiba-*"):
        f.unlink()


def install_units(date: str, races: list[dict], unit_dir: Path | None = None) -> None:
    """全レースのsystemd unit ファイルを生成・配置・有効化する。"""
    unit_dir = unit_dir or SYSTEMD_USER_DIR
    unit_dir.mkdir(parents=True, exist_ok=True)

    names = []
    for race in races:
        name = unit_name(date, race)
        service_content, timer_content = generate_units(date, race)
        (unit_dir / f"{name}.service").write_text(service_content)
        (unit_dir / f"{name}.timer").write_text(timer_content)
        names.append(name)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)

    for name in names:
        subprocess.run(
            ["systemctl", "--user", "start", f"{name}.timer"],
            check=True,
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/schedule_races.py <date>")
        print("  例: python scripts/schedule_races.py 20260307")
        sys.exit(1)

    date = sys.argv[1]
    print(f"[scheduler] {date} のレースを取得中...")

    cleanup_old_units()
    print("[scheduler] 既存タイマーをクリーンアップしました")

    races = fetch_race_schedule(date)
    if not races:
        print(f"[scheduler] {date} にレースはありません")
        return

    print(f"[scheduler] {len(races)} レースが見つかりました")
    for race in races:
        trigger = calc_trigger_time(race["post_time"])
        print(f"  {race['venue']} {race['race_no']}R "
              f"発走{race['post_time'][:2]}:{race['post_time'][2:]} "
              f"→ トリガー{trigger.strftime('%H:%M')}")

    install_units(date, races)
    print(f"[scheduler] {len(races)} 個のタイマーを登録しました")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schedule_races.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/schedule_races.py tests/test_schedule_races.py
git commit -m "feat: スケジューラのクリーンアップ・登録・main関数を追加"
```

---

### Task 4: systemd lingering 有効化 & cron 登録

**Files:**
- None (OS設定のみ)

**Step 1: systemd user のlinger を有効化**

ログアウト中もuser unitを動作させるために必要:

```bash
loginctl enable-linger $(whoami)
```

**Step 2: systemd user dir を確認**

```bash
mkdir -p ~/.config/systemd/user
```

**Step 3: cron登録**

```bash
crontab -e
```

以下を追加:

```cron
0 8 * * * cd /home/inoue-d/dev/claude-keiba && .venv/bin/python scripts/schedule_races.py $(date +\%Y\%m\%d) >> /home/inoue-d/dev/claude-keiba/logs/scheduler.log 2>&1
```

**Step 4: 動作確認**

```bash
# 手動でスケジュール登録テスト（当日の日付で）
cd /home/inoue-d/dev/claude-keiba
.venv/bin/python scripts/schedule_races.py $(date +%Y%m%d)

# タイマー一覧確認
systemctl --user list-timers 'keiba-*'
```

**Step 5: Commit**

なし（OS設定変更のみ）。

---

### Task 5: 手動実行による統合テスト

**Files:**
- None

**Step 1: テスト日のレースでスケジュール登録**

来週末の開催日で実行:

```bash
python scripts/schedule_races.py <来週の開催日>
```

**Step 2: timer が正しく登録されているか確認**

```bash
systemctl --user list-timers 'keiba-*'
```

全レースのタイマーが表示され、Next の時刻が発走40分前であることを確認。

**Step 3: service ファイルの内容確認**

```bash
cat ~/.config/systemd/user/keiba-<date>-<venue>-<race_no>.service
cat ~/.config/systemd/user/keiba-<date>-<venue>-<race_no>.timer
```

パス・引数・時刻が正しいことを確認。

**Step 4: クリーンアップ確認**

```bash
# もう一度実行して冪等性を確認
python scripts/schedule_races.py <同じ日付>
systemctl --user list-timers 'keiba-*'
```

前回と同じ結果になることを確認。

**Step 5: 不要なタイマーを削除**

テスト目的のタイマーを削除（本番運用日でなければ）:

```bash
python scripts/schedule_races.py 00000000  # レース0件 → クリーンアップのみ実行
```
