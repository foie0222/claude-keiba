import json
from pathlib import Path
from src.logging import RaceLogger

def test_save_and_load(tmp_path):
    logger = RaceLogger(base_dir=tmp_path / "logs")
    race_id = "20260301_nakayama_11"
    data = {"analyses": {"bloodline": {"score": 9.0}}, "bet_decision": {"total_amount": 5000}}
    logger.save(race_id, data)
    log_dir = tmp_path / "logs" / "20260301" / "nakayama_11"
    assert log_dir.exists()
    assert (log_dir / "full_result.json").exists()
    loaded = json.loads((log_dir / "full_result.json").read_text())
    assert loaded["bet_decision"]["total_amount"] == 5000

def test_save_agent_log(tmp_path):
    logger = RaceLogger(base_dir=tmp_path / "logs")
    race_id = "20260301_nakayama_11"
    logger.save_agent_log(race_id, "bloodline", {"analysis": "test"})
    path = tmp_path / "logs" / "20260301" / "nakayama_11" / "agents" / "bloodline.json"
    assert path.exists()
