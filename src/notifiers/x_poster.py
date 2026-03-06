"""Xに画像付きツイートを投稿する。"""
import os
import sys
from pathlib import Path

import tweepy
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def post_to_x(image_path: Path) -> str | None:
    """画像のみのツイートを投稿する。成功時はtweet_idを返す。

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
        response = client.create_tweet(text="", media_ids=[media.media_id])
        tweet_id = response.data["id"]
        print(f"  ✓ X投稿完了 (tweet_id: {tweet_id})", file=sys.stderr, flush=True)
        return tweet_id

    except Exception as e:
        print(f"  ✗ X投稿エラー: {e}", file=sys.stderr, flush=True)
        return None
