from __future__ import annotations
import json
from pathlib import Path


class RaceLogger:
    """レースごとの全推論ログを保存する"""

    def __init__(self, base_dir: Path = Path("logs")):
        self.base_dir = base_dir

    def _race_dir(self, race_id: str) -> Path:
        parts = race_id.split("_", 1)
        date_str = parts[0]
        rest = parts[1] if len(parts) > 1 else "unknown"
        return self.base_dir / date_str / rest

    def save(self, race_id: str, data: dict) -> Path:
        d = self._race_dir(race_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "full_result.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_agent_log(self, race_id: str, agent_name: str, data: dict) -> Path:
        d = self._race_dir(race_id) / "agents"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{agent_name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_result(self, race_id: str, result: dict) -> Path:
        d = self._race_dir(race_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "race_result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
