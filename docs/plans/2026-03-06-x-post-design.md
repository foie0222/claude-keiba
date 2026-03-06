# X投稿機能 設計書

## 概要

投票処理完了後に、投票内容をカード画像としてXに投稿する。自分用のログとして記録を残す目的。

## 投稿タイミング

- 投票成功時: 馬券詳細のカード画像を投稿
- 見送り時: 見送りカード画像を投稿
- バックテスト時: 投稿しない（`live=True`のときのみ）

## 投稿内容

### ツイート本文

```
🏇 阪神11R 毎日杯(GII) #AI競馬
```

短いテキスト+ハッシュタグのみ。詳細は画像に載せる。

### カード画像（購入時）

```
┌─────────────────────────┐
│  🏇 阪神11R             │
│  毎日杯(GII)            │
│  ダート1800m 良          │
│                         │
│  単勝 5番 グランドブリッツ │
│    1,600円 @4.2 EV2.31  │
│  ワイド 3-5             │
│    1,200円 @8.5 EV1.87  │
│                         │
│  計 2,800円             │
└─────────────────────────┘
```

Pillow生成。ダーク背景+白テキスト。日本語フォントはNoto Sans JP。

### カード画像（見送り時）

```
┌─────────────────────────┐
│  🏇 阪神11R             │
│  毎日杯(GII)            │
│  ダート1800m 良          │
│                         │
│  見送り                  │
└─────────────────────────┘
```

## アーキテクチャ

### ファイル構成

```
src/notifiers/
├── __init__.py
├── card_image.py    # カード画像生成（Pillow）
└── x_poster.py      # X API投稿（tweepy）
```

### 呼び出しフロー

```
orchestrator.predict_and_bet()
  → 予想・合議・投票
  → notify_x(result, race_info)
      → generate_card_image(result, race_info) → PNG画像
      → post_to_x(text, image_path) → X API v2
```

### データの流れ

投稿に必要なデータは全て`predict_and_bet`の戻り値とprefetchデータから取得:

- レース情報: `prefetch_data["race_info"]` → 会場、レース番号、レース名、距離、馬場
- 馬名: `prefetch_data["race_info"]["horses"]` → 馬番→馬名マッピング
- 馬券: `result["bet_decision"]["bets"]` → 馬券種、馬番、金額、オッズ、EV
- 見送り: `result["bet_decision"]["pass_races"]`

## API認証

環境変数から取得:

```
X_API_KEY
X_API_SECRET
X_ACCESS_TOKEN
X_ACCESS_TOKEN_SECRET
```

未設定の場合は投稿をスキップし、stderrにwarning出力。

## エラーハンドリング

| 障害パターン | 挙動 |
|---|---|
| APIキー未設定 | スキップ（warning出力） |
| 画像生成失敗 | スキップ（エラーログ出力） |
| X API投稿失敗 | スキップ（エラーログ出力） |
| レート制限 | スキップ（エラーログ出力） |

全て投票処理には影響させない。

## 依存追加

- `tweepy` — X API v2クライアント
- `Pillow` — 画像生成
- Noto Sans JP フォント — 日本語テキスト描画用
