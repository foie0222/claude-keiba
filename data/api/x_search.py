"""X(Twitter)検索スタブ。Usage: python data/api/x_search.py <race_id>"""
import json
import sys

def search_x(race_id: str) -> dict:
    return {
        "race_id": race_id,
        "posts": [
            {"user": "予想家A", "text": "3番テストホース3が本命。血統的に中山向き。", "likes": 150, "retweets": 30},
            {"user": "予想家B", "text": "7番テストホース7の調教が良い。穴で狙える。", "likes": 80, "retweets": 15},
            {"user": "記者C", "text": "1番テストホース1は馬場が合えば。重馬場なら評価アップ。", "likes": 45, "retweets": 8},
            {"user": "データ分析D", "text": "今回はペースが流れそう。差し馬有利の展開予想。", "likes": 200, "retweets": 50},
        ],
        "trending": ["#スタブレース", "#テストホース3"],
    }

if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print(json.dumps(search_x(race_id), ensure_ascii=False))
