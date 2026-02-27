"""オッズ取得スタブ。Usage: python data/api/odds.py <race_id>"""
import json
import sys

def get_odds(race_id: str) -> dict:
    return {
        "race_id": race_id,
        "win": {str(i): round(2.0 + i * 1.5, 1) for i in range(1, 9)},
        "place": {str(i): round(1.2 + i * 0.5, 1) for i in range(1, 9)},
        "quinella": {"3-7": 15.2, "1-3": 8.5, "3-5": 22.0, "1-7": 12.8},
        "wide": {"3-7": 4.5, "1-3": 3.2, "3-5": 7.8, "1-7": 5.1},
    }

if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_odds(race_id), ensure_ascii=False))
