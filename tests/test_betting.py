from src.betting.executor import BettingExecutor
from src.models import BetDecision, Bet

def test_executor_dry_run():
    executor = BettingExecutor(dry_run=True)
    decision = BetDecision(
        bets=[Bet(type="win", horses=[3], amount=3000, expected_value=1.35)],
        total_amount=3000,
        reasoning="test",
    )
    result = executor.execute(decision)
    assert result["status"] == "dry_run"
    assert result["bets_placed"] == 1
