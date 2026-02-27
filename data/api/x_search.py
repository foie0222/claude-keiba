"""X(Twitter)検索。Chrome MCP経由で事前取得したキャッシュを読む。

Usage:
  python data/api/x_search.py <race_id>

race_id format: YYYYMMDD_venue_RR  (例: 20260301_nakayama_11)

キャッシュは orchestrator が Chrome MCP 経由で事前に保存する。
キャッシュが無い場合は検索URLを返す（手動/自動で取得が必要）。
"""
import json
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}

JST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / ".cache" / "x_search"


def _cache_path(race_id: str) -> Path:
    return CACHE_DIR / f"{race_id}.json"


def build_search_url(venue_en: str, race_no: int, start_dt: datetime, end_dt: datetime) -> str:
    """X検索URLを構築する。"""
    venue_jp = VENUE_JP.get(venue_en, venue_en)
    since_str = start_dt.astimezone(JST).strftime("%Y-%m-%d_%H:%M:%S_JST")
    until_str = end_dt.astimezone(JST).strftime("%Y-%m-%d_%H:%M:%S_JST")
    query = f"{venue_jp}{race_no}R パドック since:{since_str} until:{until_str}"
    return f"https://x.com/search?q={urllib.parse.quote(query)}&src=typed_query&f=live"


def build_query(venue_en: str, race_no: int, start_dt: datetime, end_dt: datetime) -> str:
    """X検索クエリ文字列を構築する。"""
    venue_jp = VENUE_JP.get(venue_en, venue_en)
    since_str = start_dt.astimezone(JST).strftime("%Y-%m-%d_%H:%M:%S_JST")
    until_str = end_dt.astimezone(JST).strftime("%Y-%m-%d_%H:%M:%S_JST")
    return f"{venue_jp}{race_no}R パドック since:{since_str} until:{until_str}"


def save_cache(race_id: str, data: dict) -> None:
    """キャッシュを保存する（orchestratorから呼ばれる）。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(race_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_race_time_info(race_id: str, *, cutoff_minutes: int = 0) -> dict:
    """race_idからレース情報・検索パラメータを取得する。

    Args:
        cutoff_minutes: 発走何分前までを検索対象にするか。
            0 = 発走時刻まで (本番用)
            10 = 発走10分前まで (テスト用: 直前ツイートは取得不可のため)
    """
    from race_info import get_race_info

    info = get_race_info(race_id)
    if "error" in info:
        return {"error": info["error"]}

    race = info["race"]
    date_str = race["date"]
    post_time_str = race["post_time"]

    hh, mm = int(post_time_str[:2]), int(post_time_str[2:])
    post_dt = datetime(
        int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]),
        hh, mm, tzinfo=JST,
    )
    end_dt = post_dt - timedelta(minutes=cutoff_minutes)
    start_dt = post_dt - timedelta(hours=1)

    return {
        "venue": race["venue"],
        "race_number": race["race_number"],
        "post_dt": post_dt,
        "end_dt": end_dt,
        "start_dt": start_dt,
    }


# --- Chrome MCP用 JavaScript スニペット ---

SCRAPE_JS = """
(() => {
  const articles = document.querySelectorAll('article[data-testid="tweet"]');
  const posts = [];
  const seen = new Set();
  articles.forEach(article => {
    const textEl = article.querySelector('div[data-testid="tweetText"]');
    const text = textEl ? textEl.innerText.trim() : '';
    if (!text || seen.has(text)) return;
    seen.add(text);
    let user = '';
    const userEl = article.querySelector('div[data-testid="User-Name"]');
    if (userEl) {
      for (const span of userEl.querySelectorAll('span')) {
        if (span.innerText.startsWith('@')) { user = span.innerText; break; }
      }
    }
    const timeEl = article.querySelector('time');
    const createdAt = timeEl ? timeEl.getAttribute('datetime') : '';
    posts.push({ user, text, created_at: createdAt });
  });
  return JSON.stringify(posts);
})()
""".strip()


def search_x(race_id: str, *, cutoff_minutes: int = 0) -> dict:
    """キャッシュからX検索結果を読む。無い場合は検索URLを返す。"""
    cached = _cache_path(race_id)
    if cached.exists():
        return json.loads(cached.read_text())

    time_info = get_race_time_info(race_id, cutoff_minutes=cutoff_minutes)
    if "error" in time_info:
        return {"race_id": race_id, "posts": [], "error": time_info["error"]}

    end_dt = time_info["end_dt"]
    url = build_search_url(
        time_info["venue"], time_info["race_number"],
        time_info["start_dt"], end_dt,
    )
    query = build_query(
        time_info["venue"], time_info["race_number"],
        time_info["start_dt"], end_dt,
    )

    return {
        "race_id": race_id,
        "query": query,
        "search_url": url,
        "post_count": 0,
        "posts": [],
        "error": "キャッシュなし。Chrome MCP経由で事前に検索結果を取得してください。",
    }


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    cutoff = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(search_x(race_id, cutoff_minutes=cutoff), ensure_ascii=False, indent=2))
