from __future__ import annotations
from pydantic import BaseModel

class RaceId(BaseModel):
    date: str
    venue: str
    race_number: int

    def __str__(self) -> str:
        return f"{self.date}_{self.venue}_{self.race_number}"

class HorseRanking(BaseModel):
    horse_number: int
    score: float
    reason: str

class AnalysisResult(BaseModel):
    analyst: str
    race_id: str
    analysis: str
    rankings: list[HorseRanking]
    confidence: float
    warnings: list[str] = []

class HorseEvaluation(BaseModel):
    horse_number: int
    overall_score: float
    summary: str
    dissenting_views: list[str] = []

class CouncilJudgment(BaseModel):
    evaluations: list[HorseEvaluation]
    recommended_top: list[int]
    race_assessment: str

class Bet(BaseModel):
    type: str
    horses: list[int]
    amount: int
    expected_value: float

class BetDecision(BaseModel):
    bets: list[Bet]
    total_amount: int
    reasoning: str
    pass_races: bool = False
