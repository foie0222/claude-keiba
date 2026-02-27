import subprocess
import json

def test_race_info_stub():
    result = subprocess.run(
        ["python", "data/api/race_info.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "race" in data
    assert "horses" in data
    assert len(data["horses"]) > 0

def test_odds_stub():
    result = subprocess.run(
        ["python", "data/api/odds.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "win" in data

def test_training_stub():
    result = subprocess.run(
        ["python", "data/api/training.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "horses" in data

def test_x_search_stub():
    result = subprocess.run(
        ["python", "data/api/x_search.py", "20260301_nakayama_11"],
        capture_output=True, text=True,
        cwd="/home/inoue-d/dev/claude-keiba"
    )
    data = json.loads(result.stdout)
    assert "posts" in data
