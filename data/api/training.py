"""調教データ取得スタブ。Usage: python data/api/training.py <race_id>"""
import json
import sys

def get_training(race_id: str) -> dict:
    return {
        "race_id": race_id,
        "horses": [
            {
                "number": i,
                "name": f"テストホース{i}",
                "recent_training": [
                    {"date": "20260225", "location": "美浦", "course": "坂路", "time": f"5{i}.{i}", "condition": "良", "evaluation": "好調"},
                    {"date": "20260222", "location": "美浦", "course": "ウッド", "time": f"6{i}.{i}", "condition": "良", "evaluation": "普通"},
                ],
            }
            for i in range(1, 9)
        ],
    }

if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_training(race_id), ensure_ascii=False))
