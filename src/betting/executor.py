from __future__ import annotations
from src.models import BetDecision


class BettingExecutor:
    """馬券購入を実行する。dry_run=Trueで実際には購入しない。"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def execute(self, decision: BetDecision) -> dict:
        if self.dry_run:
            return {
                "status": "dry_run",
                "bets_placed": len(decision.bets),
                "total_amount": decision.total_amount,
                "detail": [b.model_dump() for b in decision.bets],
            }
        raise NotImplementedError("Real betting not implemented yet")
