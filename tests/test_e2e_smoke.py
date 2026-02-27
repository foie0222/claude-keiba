# tests/test_e2e_smoke.py
"""
E2Eスモークテスト。実際にclaude-agent-sdkを呼ぶため、
CI環境ではスキップし、手動実行で確認する。
"""
import pytest
import asyncio
from pathlib import Path
from src.orchestrator import Orchestrator

@pytest.mark.skipif(
    not Path.home().joinpath(".claude").exists(),
    reason="Claude Code CLI not available"
)
@pytest.mark.asyncio
async def test_e2e_single_race():
    """1レースの全フローが通ることを確認（スタブデータ）"""
    orchestrator = Orchestrator(
        prompts_dir=Path("agents/prompts"),
        logs_dir=Path("logs/test"),
    )
    result = await orchestrator.predict_and_bet("20260301", "nakayama", 11)

    assert "analyses" in result
    assert "council" in result
    assert "bet_decision" in result

    # ログが保存されていること
    log_dir = Path("logs/test/20260301/nakayama_11")
    assert log_dir.exists()
