"""機械的なケリー基準ベッティング。

LLMを使わず、judgeの評価結果とオッズから決定論的に馬券を算出する。
スコアからの勝率推定には softmax を使用。
"""
from __future__ import annotations

import math
from pathlib import Path

import toon


MIN_BALANCE = 1000
MAX_BET_RATIO = 0.07  # 残高の7%
MIN_BET_UNIT = 100
MIN_AGREEMENT_SCORE = 0.60
MIN_EXPECTED_VALUE = 1.5
KELLY_FRACTION = 0.5  # ハーフケリー


def _softmax_probs(evaluations: list[dict]) -> dict[int, float]:
    """全馬のoverall_scoreからsoftmaxで勝率を推定する。

    Returns: {horse_number: win_probability}
    """
    scores = [(e["horse_number"], e["overall_score"]) for e in evaluations]
    max_score = max(s for _, s in scores)
    # overflow防止のためmax_scoreを引く
    exps = [(num, math.exp(score - max_score)) for num, score in scores]
    total = sum(e for _, e in exps)
    return {num: e / total for num, e in exps}


def _place_prob(win_prob: float, num_horses: int) -> float:
    """単勝勝率から複勝的中率を近似推定する。

    Harvilleモデルの簡易近似: 3着以内率 ≈ 1 - (1 - win_prob)^3 を
    出走頭数で調整。8頭以上は3着まで、7頭以下は2着まで。
    """
    if num_horses <= 7:
        return 1 - (1 - win_prob) ** 2
    return 1 - (1 - win_prob) ** 3


def _wide_prob(prob_a: float, prob_b: float, num_horses: int) -> float:
    """2頭が両方3着以内に入る確率を近似推定する。"""
    place_a = _place_prob(prob_a, num_horses)
    place_b = _place_prob(prob_b, num_horses)
    # 独立近似に相関補正（同時に3着以内は独立より低い）
    return place_a * place_b * 0.85


def _quinella_prob(prob_a: float, prob_b: float) -> float:
    """2頭が1着2着を占める確率を近似推定する。"""
    return 2 * prob_a * prob_b


def _kelly_bet(prob: float, odds: float, balance: int) -> int | None:
    """ハーフケリーで賭け金を計算。期待値不足やゼロの場合はNone。"""
    ev = prob * odds
    if ev <= MIN_EXPECTED_VALUE:
        return None
    if odds <= 1.0:
        return None
    kelly = (prob * odds - 1) / (odds - 1)
    if kelly <= 0:
        return None
    half_kelly = kelly * KELLY_FRACTION
    amount = int(balance * half_kelly)
    amount = (amount // MIN_BET_UNIT) * MIN_BET_UNIT
    if amount < MIN_BET_UNIT:
        return None
    return amount


def compute_bet_decision(judge: dict, odds_data: dict, balance: int) -> dict:
    """judgeの評価とオッズから機械的に馬券を決定する。

    Args:
        judge: council.judgeの出力 (evaluations, recommended_top, race_assessment)
        odds_data: odds.toonの内容
        balance: 現在の残高

    Returns: bet_decisionのdict (bets, total_amount, reasoning, pass_races, etc.)
    """
    result = {
        "balance": balance,
        "max_bet_for_race": (balance * MAX_BET_RATIO // MIN_BET_UNIT) * MIN_BET_UNIT,
        "bets": [],
        "total_amount": 0,
        "reasoning": "",
        "pass_races": False,
    }

    if balance < MIN_BALANCE:
        result["pass_races"] = True
        result["reasoning"] = f"残高{balance:,}円が最低残高{MIN_BALANCE:,}円未満のため見送り"
        return result

    evaluations = judge.get("evaluations", [])
    if not evaluations:
        result["pass_races"] = True
        result["reasoning"] = "評価データなし"
        return result

    win_odds = odds_data.get("win", {})
    place_odds = odds_data.get("place", {})
    wide_odds_list = odds_data.get("wide", [])
    quinella_odds_list = odds_data.get("quinella", [])

    if not win_odds:
        result["pass_races"] = True
        result["reasoning"] = "オッズデータなし"
        return result

    # 勝率推定
    win_probs = _softmax_probs(evaluations)
    num_horses = len(evaluations)
    max_bet = result["max_bet_for_race"]

    # agreement_scoreでフィルタ
    candidates = [
        e for e in evaluations
        if e.get("agreement_score", 0) >= MIN_AGREEMENT_SCORE
    ]

    bets = []

    # 単勝
    for e in candidates:
        h = e["horse_number"]
        odds_entry = win_odds.get(str(h))
        if not odds_entry or not odds_entry.get("odds"):
            continue
        odds_val = odds_entry["odds"]
        prob = win_probs.get(h, 0)
        amount = _kelly_bet(prob, odds_val, balance)
        if amount:
            bets.append({
                "type": "win",
                "horses": [h],
                "amount": amount,
                "estimated_win_prob": round(prob, 4),
                "odds": odds_val,
                "expected_value": round(prob * odds_val, 3),
                "reasoning": f"{h}番 単勝: 推定勝率{prob:.1%}×オッズ{odds_val}=EV{prob*odds_val:.2f}",
            })

    # 複勝
    for e in candidates:
        h = e["horse_number"]
        odds_entry = place_odds.get(str(h))
        if not odds_entry:
            continue
        o_min = odds_entry.get("odds_min")
        o_max = odds_entry.get("odds_max")
        if o_min is None:
            continue
        # 期待値計算には中央値を使う
        odds_val = (o_min + o_max) / 2 if o_max else o_min
        prob = _place_prob(win_probs.get(h, 0), num_horses)
        amount = _kelly_bet(prob, odds_val, balance)
        if amount:
            bets.append({
                "type": "place",
                "horses": [h],
                "amount": amount,
                "estimated_win_prob": round(prob, 4),
                "odds": odds_val,
                "expected_value": round(prob * odds_val, 3),
                "reasoning": f"{h}番 複勝: 推定的中率{prob:.1%}×オッズ{odds_val:.1f}=EV{prob*odds_val:.2f}",
            })

    # ワイド（candidates同士の組み合わせ）
    wide_odds_map = {e["combination"]: e for e in wide_odds_list}
    for i, e1 in enumerate(candidates):
        for e2 in candidates[i + 1:]:
            h1, h2 = sorted([e1["horse_number"], e2["horse_number"]])
            combo_key = f"{h1}-{h2}"
            odds_entry = wide_odds_map.get(combo_key)
            if not odds_entry or not odds_entry.get("odds"):
                continue
            odds_val = odds_entry["odds"]
            prob = _wide_prob(
                win_probs.get(h1, 0), win_probs.get(h2, 0), num_horses,
            )
            amount = _kelly_bet(prob, odds_val, balance)
            if amount:
                bets.append({
                    "type": "wide",
                    "horses": [h1, h2],
                    "amount": amount,
                    "estimated_win_prob": round(prob, 4),
                    "odds": odds_val,
                    "expected_value": round(prob * odds_val, 3),
                    "reasoning": f"{h1}-{h2} ワイド: 推定的中率{prob:.1%}×オッズ{odds_val}=EV{prob*odds_val:.2f}",
                })

    # 馬連（candidates上位同士の組み合わせ）
    quinella_odds_map = {e["combination"]: e for e in quinella_odds_list}
    for i, e1 in enumerate(candidates):
        for e2 in candidates[i + 1:]:
            h1, h2 = sorted([e1["horse_number"], e2["horse_number"]])
            combo_key = f"{h1}-{h2}"
            odds_entry = quinella_odds_map.get(combo_key)
            if not odds_entry or not odds_entry.get("odds"):
                continue
            odds_val = odds_entry["odds"]
            prob = _quinella_prob(
                win_probs.get(h1, 0), win_probs.get(h2, 0),
            )
            amount = _kelly_bet(prob, odds_val, balance)
            if amount:
                bets.append({
                    "type": "quinella",
                    "horses": [h1, h2],
                    "amount": amount,
                    "estimated_win_prob": round(prob, 4),
                    "odds": odds_val,
                    "expected_value": round(prob * odds_val, 3),
                    "reasoning": f"{h1}-{h2} 馬連: 推定的中率{prob:.1%}×オッズ{odds_val}=EV{prob*odds_val:.2f}",
                })

    if not bets:
        result["pass_races"] = True
        result["reasoning"] = "期待値が1.0を超える馬券なし"
        return result

    # EV降順でソート
    bets.sort(key=lambda b: b["expected_value"], reverse=True)

    # 合計が上限を超える場合は比例縮小
    total = sum(b["amount"] for b in bets)
    if total > max_bet:
        ratio = max_bet / total
        for b in bets:
            b["amount"] = (int(b["amount"] * ratio) // MIN_BET_UNIT) * MIN_BET_UNIT
        bets = [b for b in bets if b["amount"] >= MIN_BET_UNIT]

    total = sum(b["amount"] for b in bets)
    if total == 0:
        result["pass_races"] = True
        result["reasoning"] = "比例縮小後に有効な馬券なし"
        return result

    result["bets"] = bets
    result["total_amount"] = total
    result["reasoning"] = (
        f"ケリー基準(機械的算出): {len(bets)}点 合計{total:,}円 "
        f"(上限{max_bet:,}円)"
    )
    return result


def compute_from_prefetch(judge: dict, prefetch_path: Path, balance: int) -> dict:
    """prefetchキャッシュからoddsを読んでbet_decisionを返す。"""
    odds_path = prefetch_path / "odds.toon"
    if odds_path.exists():
        odds_data = toon.decode(odds_path.read_text(encoding="utf-8"))
    else:
        odds_data = {}
    return compute_bet_decision(judge, odds_data, balance)
