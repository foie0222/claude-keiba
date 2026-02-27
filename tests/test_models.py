from src.models import RaceId, AnalysisResult, HorseRanking, CouncilJudgment, BetDecision, Bet

def test_race_id_to_string():
    r = RaceId(date="20260301", venue="nakayama", race_number=11)
    assert str(r) == "20260301_nakayama_11"

def test_analysis_result_validation():
    result = AnalysisResult(
        analyst="bloodline",
        race_id="20260301_nakayama_11",
        analysis="血統分析の結果",
        rankings=[HorseRanking(horse_number=3, score=9.2, reason="父系の適性が高い")],
        confidence=0.75,
        warnings=["初距離"],
    )
    assert result.analyst == "bloodline"
    assert result.rankings[0].score == 9.2

def test_bet_decision_total():
    decision = BetDecision(
        bets=[
            Bet(type="win", horses=[3], amount=3000, expected_value=1.35),
            Bet(type="wide", horses=[3, 7], amount=2000, expected_value=1.22),
        ],
        total_amount=5000,
        reasoning="期待値が高い",
    )
    assert decision.total_amount == 5000
    assert len(decision.bets) == 2
