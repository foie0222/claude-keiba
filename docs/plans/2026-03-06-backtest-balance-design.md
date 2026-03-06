# バックテスト残高追跡 設計書

## 概要

バックテスト時に仮想残高（初期100,000円）を追跡し、レースごとに投入額・払戻額を反映して残高を更新する。bettingエージェントが参照する`balance.toon`を上書きすることで、残高に応じた賭け金計算を実現する。

## 変更対象

`scripts/backtest.py` のみ。orchestrator・エージェント側の変更は不要。

## 仕組み

1. バックテスト開始時に `balance = 100,000` を初期化
2. 各レース実行前に、prefetchキャッシュの `balance.toon` をシミュレーション残高で上書き
3. 各レース実行後に残高を更新: `balance = balance - stake + payout`
4. サマリーに残高推移を表示

## balance.toon の上書き内容

```python
{
    "buy_limit_money": balance,
    "day_buy_money": 0,
    "total_buy_money": 0,
    "day_refund_money": 0,
    "total_refund_money": 0,
    "buy_possible_count": 99,
}
```

## 残高がゼロ以下になった場合

bettingエージェントの既存ルール（残高1,000円未満 → pass_races=true）に従い見送りとなるが、バックテスト自体は続行する。
