"""X投稿モジュールのテスト。"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notifiers.x_poster import post_to_x, build_tweet_text


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

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake png")

    with patch.dict(os.environ, env, clear=False):
        result = post_to_x("test tweet", img_path)

    assert result == "999"
    mock_api.media_upload.assert_called_once_with(filename=str(img_path))
    mock_client.create_tweet.assert_called_once_with(
        text="test tweet", media_ids=[12345]
    )
