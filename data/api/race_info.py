"""レース情報取得スタブ。Usage: python data/api/race_info.py <race_id>"""
import json
import sys

def get_race_info(race_id: str) -> dict:
    parts = race_id.split("_")
    return {
        "race": {
            "race_id": race_id,
            "date": parts[0] if len(parts) > 0 else "",
            "venue": parts[1] if len(parts) > 1 else "",
            "race_number": int(parts[2]) if len(parts) > 2 else 0,
            "name": "スタブレース",
            "distance": 2000,
            "surface": "芝",
            "condition": "良",
            "weather": "晴",
        },
        "horses": [
            {
                "number": i,
                "name": f"テストホース{i}",
                "age": 3,
                "sex": "牡",
                "weight": 57.0,
                "jockey": f"騎手{i}",
                "trainer": f"調教師{i}",
                "sire": f"父馬{i}",
                "dam_sire": f"母父{i}",
                "past_races": [
                    {"date": "20260201", "venue": "中山", "distance": 2000, "result": i % 5 + 1, "time": f"2:0{i}.{i}"},
                    {"date": "20260101", "venue": "中山", "distance": 1800, "result": (i + 1) % 5 + 1, "time": f"1:5{i}.{i}"},
                ],
            }
            for i in range(1, 9)
        ],
    }

if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(get_race_info(race_id), ensure_ascii=False))
