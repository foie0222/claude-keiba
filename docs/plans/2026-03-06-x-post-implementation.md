# X投稿機能 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 投票処理後に馬券内容をカード画像としてXに自動投稿する。

**Architecture:** `card_image.py`がPillowでカード画像を生成し、`x_poster.py`がtweepy経由でX APIに画像付きツイートを投稿する。orchestratorの投票処理後に呼び出す。

**Tech Stack:** Python 3.12, Pillow (画像生成), tweepy (X API v2), Noto Sans CJK JP (フォント)

---

### Task 1: 依存パッケージのインストール

**Files:**
- Modify: `pyproject.toml`

**Step 1: パッケージをインストール**

```bash
.venv/bin/pip install tweepy Pillow
```

**Step 2: pyproject.tomlのdependenciesにtweepyとPillowを追加**

`pyproject.toml`の`dependencies`リストに以下を追加:
```
"tweepy>=4.14",
"Pillow>=10.0",
```

**Step 3: コミット**

```bash
git add pyproject.toml
git commit -m "chore: tweepyとPillowを依存に追加"
```

---

### Task 2: カード画像生成モジュール

**Files:**
- Create: `src/notifiers/__init__.py`
- Create: `src/notifiers/card_image.py`
- Create: `tests/test_card_image.py`

**Step 1: テストを書く**

`tests/test_card_image.py`:

```python
"""カード画像生成のテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notifiers.card_image import generate_card_image

TYPE_LABEL = {"win": "単勝", "place": "複勝", "quinella": "馬連", "wide": "ワイド"}

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}


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
    # 画像サイズが妥当か
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
```

**Step 2: テストが失敗することを確認**

```bash
.venv/bin/python -m pytest tests/test_card_image.py -v
```

Expected: FAIL (ModuleNotFoundError)

**Step 3: 実装**

`src/notifiers/__init__.py` を空ファイルで作成。

`src/notifiers/card_image.py`:

```python
"""投票内容のカード画像を生成する。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# フォント設定
_FONT_PATH_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_FONT_PATH_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# カラー
_BG_COLOR = (30, 30, 35)
_TEXT_COLOR = (240, 240, 240)
_ACCENT_COLOR = (100, 180, 255)
_MUTED_COLOR = (160, 160, 170)
_PASS_COLOR = (180, 180, 60)

# レイアウト
_CARD_WIDTH = 600
_PADDING = 32
_LINE_HEIGHT_TITLE = 36
_LINE_HEIGHT_BODY = 28

TYPE_LABEL = {"win": "単勝", "place": "複勝", "quinella": "馬連", "wide": "ワイド"}

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}


def _load_font(bold: bool = False, size: int = 24) -> ImageFont.FreeTypeFont:
    path = _FONT_PATH_BOLD if bold else _FONT_PATH_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _horse_name_map(horses: list[dict]) -> dict[int, str]:
    """馬番 → 馬名のマッピングを構築。"""
    return {h["number"]: h["name"] for h in horses}


def _get_condition(race: dict) -> str:
    """馬場状態を取得。芝→turf_condition、ダート→dirt_condition。"""
    surface = race.get("surface", "")
    if "ダート" in surface:
        return race.get("dirt_condition", "")
    return race.get("turf_condition", "")


def generate_card_image(
    race_info: dict,
    bet_decision: dict,
    *,
    output_dir: Path | None = None,
) -> Path:
    """カード画像を生成してPNGファイルパスを返す。"""
    race = race_info.get("race", {})
    horses = race_info.get("horses", [])
    name_map = _horse_name_map(horses)

    venue_jp = VENUE_JP.get(race.get("venue", ""), race.get("venue", ""))
    race_no = race.get("race_number", 0)
    race_name = race.get("name", "")
    distance = race.get("distance", 0)
    surface = race.get("surface", "")
    condition = _get_condition(race)

    bets = bet_decision.get("bets", [])
    is_pass = bet_decision.get("pass_races", False) or not bets
    total_amount = bet_decision.get("total_amount", 0)

    # フォント
    font_title = _load_font(bold=True, size=28)
    font_sub = _load_font(bold=False, size=22)
    font_body = _load_font(bold=False, size=20)
    font_amount = _load_font(bold=True, size=20)
    font_total = _load_font(bold=True, size=24)

    # 行を構築
    lines = []  # (text, font, color, y_offset)

    # ヘッダー
    header = f"{venue_jp}{race_no}R"
    lines.append((header, font_title, _TEXT_COLOR))

    if race_name:
        lines.append((race_name, font_sub, _ACCENT_COLOR))

    detail = f"{surface}{distance}m"
    if condition:
        detail += f" {condition}"
    lines.append((detail, font_sub, _MUTED_COLOR))

    lines.append(("", font_body, _TEXT_COLOR))  # 空行

    if is_pass:
        lines.append(("見送り", font_title, _PASS_COLOR))
    else:
        for bet in bets:
            bet_type = TYPE_LABEL.get(bet["type"], bet["type"])
            horse_nums = bet["horses"]

            if len(horse_nums) == 1:
                h = horse_nums[0]
                name = name_map.get(h, "")
                label = f"{bet_type} {h}番 {name}"
            else:
                nums_str = "-".join(str(h) for h in horse_nums)
                label = f"{bet_type} {nums_str}"

            lines.append((label, font_body, _TEXT_COLOR))

            odds = bet.get("odds", 0)
            ev = bet.get("expected_value", 0)
            amount = bet.get("amount", 0)
            detail_line = f"  {amount:,}円 @{odds} EV{ev:.2f}"
            lines.append((detail_line, font_amount, _MUTED_COLOR))

        lines.append(("", font_body, _TEXT_COLOR))  # 空行
        lines.append((f"計 {total_amount:,}円", font_total, _TEXT_COLOR))

    # 画像サイズ計算
    y = _PADDING
    line_positions = []
    for text, font, color in lines:
        line_positions.append((text, font, color, y))
        if text == "":
            y += 12  # 空行は小さめ
        else:
            bbox = font.getbbox(text)
            y += bbox[3] - bbox[1] + 10
    y += _PADDING

    img = Image.new("RGB", (_CARD_WIDTH, y), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    for text, font, color, ly in line_positions:
        if text:
            draw.text((_PADDING, ly), text, font=font, fill=color)

    # 保存
    race_id = race.get("race_id", "unknown")
    output_dir = output_dir or Path("/tmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{race_id}.png"
    img.save(path)

    return path
```

**Step 4: テストが通ることを確認**

```bash
.venv/bin/python -m pytest tests/test_card_image.py -v
```

Expected: 3 tests PASS

**Step 5: コミット**

```bash
git add src/notifiers/__init__.py src/notifiers/card_image.py tests/test_card_image.py
git commit -m "feat: カード画像生成モジュールを追加"
```

---

### Task 3: X投稿モジュール

**Files:**
- Create: `src/notifiers/x_poster.py`
- Create: `tests/test_x_poster.py`

**Step 1: テストを書く**

`tests/test_x_poster.py`:

```python
"""X投稿モジュールのテスト。"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notifiers.x_poster import post_to_x, build_tweet_text

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}


def test_build_tweet_text_with_bets():
    race_info = {
        "race": {"venue": "hanshin", "race_number": 11, "name": "毎日杯(GII)"},
    }
    text = build_tweet_text(race_info, is_pass=False)
    assert "阪神11R" in text
    assert "毎日杯" in text
    assert "#AI競馬" in text


def test_build_tweet_text_pass():
    race_info = {
        "race": {"venue": "nakayama", "race_number": 5, "name": ""},
    }
    text = build_tweet_text(race_info, is_pass=True)
    assert "中山5R" in text
    assert "見送り" in text
    assert "#AI競馬" in text


def test_post_to_x_skips_when_no_api_key():
    """APIキー未設定時はスキップしてNoneを返す。"""
    env = {
        "X_API_KEY": "",
        "X_API_SECRET": "",
        "X_ACCESS_TOKEN": "",
        "X_ACCESS_TOKEN_SECRET": "",
    }
    with patch.dict(os.environ, env, clear=False):
        result = post_to_x("test", Path("/tmp/dummy.png"))
    assert result is None


@patch("src.notifiers.x_poster.tweepy")
def test_post_to_x_success(mock_tweepy, tmp_path):
    """APIキー設定時は投稿が実行される。"""
    env = {
        "X_API_KEY": "key",
        "X_API_SECRET": "secret",
        "X_ACCESS_TOKEN": "token",
        "X_ACCESS_TOKEN_SECRET": "token_secret",
    }

    # モックのセットアップ
    mock_api = MagicMock()
    mock_media = MagicMock()
    mock_media.media_id = 12345
    mock_api.media_upload.return_value = mock_media
    mock_tweepy.OAuth1UserHandler.return_value = MagicMock()
    mock_tweepy.API.return_value = mock_api

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = {"id": "999"}
    mock_client.create_tweet.return_value = mock_response
    mock_tweepy.Client.return_value = mock_client

    # ダミー画像ファイル
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake png")

    with patch.dict(os.environ, env, clear=False):
        result = post_to_x("test tweet", img_path)

    assert result == "999"
    mock_api.media_upload.assert_called_once_with(filename=str(img_path))
    mock_client.create_tweet.assert_called_once_with(
        text="test tweet", media_ids=[12345]
    )
```

**Step 2: テストが失敗することを確認**

```bash
.venv/bin/python -m pytest tests/test_x_poster.py -v
```

Expected: FAIL (ModuleNotFoundError)

**Step 3: 実装**

`src/notifiers/x_poster.py`:

```python
"""Xに画像付きツイートを投稿する。"""
import os
import sys
from pathlib import Path

import tweepy

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}


def build_tweet_text(race_info: dict, *, is_pass: bool) -> str:
    """ツイート本文を組み立てる。"""
    race = race_info.get("race", {})
    venue_jp = VENUE_JP.get(race.get("venue", ""), race.get("venue", ""))
    race_no = race.get("race_number", 0)
    race_name = race.get("name", "")

    header = f"🏇 {venue_jp}{race_no}R"
    if race_name:
        header += f" {race_name}"

    if is_pass:
        return f"{header} 見送り #AI競馬"
    return f"{header} #AI競馬"


def post_to_x(text: str, image_path: Path) -> str | None:
    """画像付きツイートを投稿する。成功時はtweet_idを返す。

    環境変数 X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET が
    未設定の場合はスキップしてNoneを返す。
    """
    api_key = os.environ.get("X_API_KEY", "")
    api_secret = os.environ.get("X_API_SECRET", "")
    access_token = os.environ.get("X_ACCESS_TOKEN", "")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("  ⚠ X APIキー未設定、投稿スキップ", file=sys.stderr, flush=True)
        return None

    try:
        # v1.1 API でメディアアップロード
        auth = tweepy.OAuth1UserHandler(
            api_key, api_secret, access_token, access_token_secret
        )
        api = tweepy.API(auth)
        media = api.media_upload(filename=str(image_path))

        # v2 Client でツイート投稿
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=text, media_ids=[media.media_id])
        tweet_id = response.data["id"]
        print(f"  ✓ X投稿完了 (tweet_id: {tweet_id})", file=sys.stderr, flush=True)
        return tweet_id

    except Exception as e:
        print(f"  ✗ X投稿エラー: {e}", file=sys.stderr, flush=True)
        return None
```

**Step 4: テストが通ることを確認**

```bash
.venv/bin/python -m pytest tests/test_x_poster.py -v
```

Expected: 4 tests PASS

**Step 5: コミット**

```bash
git add src/notifiers/x_poster.py tests/test_x_poster.py
git commit -m "feat: X投稿モジュールを追加"
```

---

### Task 4: orchestratorにX投稿を組み込む

**Files:**
- Modify: `src/orchestrator.py`

**Step 1: orchestratorの投票処理後にX投稿呼び出しを追加**

`src/orchestrator.py` の `predict_and_bet` メソッド末尾、`return result` の直前に追加:

```python
        # X投稿（本番のみ）
        if live:
            try:
                from src.notifiers.card_image import generate_card_image
                from src.notifiers.x_poster import post_to_x, build_tweet_text

                race_info = prefetch_data.get("race_info", {})
                is_pass = not bets or bet_decision.get("pass_races", False)
                card_path = generate_card_image(race_info, bet_decision)
                tweet_text = build_tweet_text(race_info, is_pass=is_pass)
                tweet_id = post_to_x(tweet_text, card_path)
                result["tweet_id"] = tweet_id
            except Exception as e:
                print(f"  ✗ X投稿処理エラー: {e}", file=sys.stderr, flush=True)
```

**Step 2: 全テストが通ることを確認**

```bash
.venv/bin/python -m pytest tests/ -v -k "not e2e"
```

Expected: ALL PASS

**Step 3: コミット**

```bash
git add src/orchestrator.py
git commit -m "feat: orchestratorにX投稿処理を組み込む"
```
