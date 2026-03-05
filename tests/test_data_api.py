import subprocess
import sys
import json
import pytest
from pathlib import Path


KBDB_AVAILABLE = Path.home().joinpath(".claude").exists()  # proxy check


@pytest.mark.skipif(not KBDB_AVAILABLE, reason="KBDB API credentials not available")
def test_race_info_real():
    result = subprocess.run(
        [sys.executable, "data/api/race_info.py", "20260222_tokyo_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba",
        timeout=120,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "race" in data
    assert "horses" in data
    assert len(data["horses"]) > 0
    assert data["race"]["name"] == "フェブラリーステークス"


def test_odds_stub():
    result = subprocess.run(
        [sys.executable, "data/api/odds.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "win" in data


def test_training_stub():
    result = subprocess.run(
        [sys.executable, "data/api/training.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "entries" in data


def test_x_search_stub():
    result = subprocess.run(
        [sys.executable, "data/api/x_search.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "posts" in data
