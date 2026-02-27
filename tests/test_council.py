import json
from src.agents.council import format_analyses_for_secretary

def test_format_analyses_for_secretary():
    analyses = {
        "bloodline": {"analyst": "bloodline", "analysis": "血統分析結果", "rankings": [{"horse_number": 3, "score": 9.0, "reason": "適性高"}], "confidence": 0.8, "warnings": []},
        "training": {"analyst": "training", "analysis": "調教分析結果", "rankings": [{"horse_number": 3, "score": 8.5, "reason": "好調教"}], "confidence": 0.7, "warnings": []},
    }
    result = format_analyses_for_secretary(analyses)
    assert "bloodline" in result
    assert "training" in result
    assert "血統分析結果" in result
