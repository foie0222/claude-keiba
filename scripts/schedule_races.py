"""レーススケジューラ: KBDB APIからレース一覧を取得し、systemd timer/serviceを生成・登録する。

Usage: python scripts/schedule_races.py <date>
  例: python scripts/schedule_races.py 20260307
"""
import subprocess
import sys
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
TRIGGER_MINUTES_BEFORE = 40
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"

sys.path.insert(0, str(PROJECT_DIR / "data" / "api"))
from kbdb_client import KBDBClient
from race_info import CODE_TO_VENUE

SERVICE_TEMPLATE = """\
[Unit]
Description=Keiba Race {date} {venue} {race_no}R

[Service]
Type=oneshot
WorkingDirectory={project_dir}
ExecStart={python} run.py {date} {venue} {race_no}
Environment=PATH={venv_bin}:/usr/bin
TimeoutStartSec=3000
"""

TIMER_TEMPLATE = """\
[Unit]
Description=Keiba Race Timer {date} {venue} {race_no}R

[Timer]
OnCalendar={trigger_time}
AccuracySec=1s
Persistent=false
"""


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
