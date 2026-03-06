"""カード画像生成のテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notifiers.card_image import generate_card_image


def _make_race_info():
    return {
        "race": {
            "race_id": "20260307_hanshin_11",
            "venue": "hanshin",
            "race_number": 11,
            "name": "毎日杯(GII)",
            "distance": 1800,
            "surface": "ダート",
            "turf_condition": "",
            "dirt_condition": "良",
        },
        "horses": [
            {"number": 3, "name": "スターライト"},
            {"number": 5, "name": "グランドブリッツ"},
        ],
    }


def _make_bet_decision_with_bets():
    return {
        "bets": [
            {
                "type": "win",
                "horses": [5],
                "amount": 1600,
                "odds": 4.2,
                "expected_value": 2.31,
            },
            {
                "type": "wide",
                "horses": [3, 5],
                "amount": 1200,
                "odds": 8.5,
                "expected_value": 1.87,
            },
        ],
        "total_amount": 2800,
        "pass_races": False,
    }


def _make_bet_decision_pass():
    return {
        "bets": [],
        "pass_races": True,
    }


def test_generate_card_image_with_bets(tmp_path):
    """馬券購入時のカード画像が生成される。"""
    race_info = _make_race_info()
    bet_decision = _make_bet_decision_with_bets()

    path = generate_card_image(race_info, bet_decision, output_dir=tmp_path)

    assert path.exists()
    assert path.suffix == ".png"
    from PIL import Image
    img = Image.open(path)
    assert img.width >= 400
    assert img.height >= 200


def test_generate_card_image_pass(tmp_path):
    """見送り時のカード画像が生成される。"""
    race_info = _make_race_info()
    bet_decision = _make_bet_decision_pass()

    path = generate_card_image(race_info, bet_decision, output_dir=tmp_path)

    assert path.exists()
    assert path.suffix == ".png"


def test_generate_card_image_filename(tmp_path):
    """ファイル名にrace_idが含まれる。"""
    race_info = _make_race_info()
    bet_decision = _make_bet_decision_with_bets()

    path = generate_card_image(race_info, bet_decision, output_dir=tmp_path)

    assert "20260307_hanshin_11" in path.name
