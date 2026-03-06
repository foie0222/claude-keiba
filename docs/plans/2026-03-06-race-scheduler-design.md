# レーススケジューラ設計書

## 概要

レースごとに独立したジョブとして予想・投票を実行するスケジューリングシステム。
1つのレースがクラッシュしても他のレースに影響しない耐障害性を実現する。

## 方式

**systemd user timer + oneshot service** をローカルPC上で使用。

- コスト: 0円（既存PCのみ）
- root権限不要（systemd --user）
- 外出先からはTailscale SSH経由でコード変更・状況確認可能

## アーキテクチャ

```
毎朝8:00 (cron)
    │
    ▼
schedule_races.py <date>
    │
    ├── 前日分のkeiba-*タイマー/サービスを停止・削除
    ├── KBDB APIで全会場・全レースの発走時刻を取得
    ├── 各レースごとにsystemd timer + serviceを生成
    │     keiba-<date>-<venue>-<race_no>.timer
    │     keiba-<date>-<venue>-<race_no>.service
    ├── ~/.config/systemd/user/ に配置
    ├── systemctl --user daemon-reload
    └── 全timerをstart

各レース発走40分前
    │
    ▼
systemd が oneshot service を起動
    │
    ▼
run.py <date> <venue> <race_number>
    │  (独立プロセス・他のレースに影響なし)
    ▼
予想 → 投票 → ログ保存 → プロセス終了
```

## ファイル構成

### 新規ファイル

```
scripts/
├── schedule_races.py         # レース取得 → systemd timer/service生成・登録
└── templates/
    ├── keiba-race.service    # systemd serviceテンプレート
    └── keiba-race.timer      # systemd timerテンプレート
```

## systemd テンプレート

### service

```ini
[Unit]
Description=Keiba Race {date} {venue} {race_no}R
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/home/inoue-d/dev/claude-keiba
ExecStart=/home/inoue-d/dev/claude-keiba/.venv/bin/python run.py {date} {venue} {race_no}
Environment=PATH=/home/inoue-d/dev/claude-keiba/.venv/bin:/usr/bin
TimeoutStartSec=2400
```

### timer

```ini
[Unit]
Description=Keiba Race Timer {date} {venue} {race_no}R

[Timer]
OnCalendar={発走40分前の時刻}
AccuracySec=1s
Persistent=false
```

## schedule_races.py 処理フロー

1. 前日分のkeiba-*タイマーを停止、service/timerファイルを削除（クリーンアップ）
2. KBDB APIで指定日の全会場・全レース発走時刻を取得
3. レースが0件なら何もせず終了
4. 各レースごとにservice/timerファイルを生成 → `~/.config/systemd/user/` に配置
5. `systemctl --user daemon-reload`
6. 全timerを `systemctl --user start`
7. 登録結果をログ出力

冪等性: 何度実行しても同じ結果（既存を削除してから再生成）。

## cron設定

```cron
# 毎朝8:00に実行。レースがなければ何もしない。
0 8 * * * cd /home/inoue-d/dev/claude-keiba && .venv/bin/python scripts/schedule_races.py $(date +\%Y\%m\%d)
```

## エラーハンドリング

| 障害パターン | 挙動 |
|---|---|
| schedule_races.py失敗（API障害等） | timerが0件 → 投票は発生しない（安全側） |
| 個別レースのrun.py失敗 | systemdジャーナルに記録。他レースには影響なし |
| タイムアウト（40分超過） | systemdが強制終了。IPAT APIも発走後は投票拒否 |
| PCシャットダウン | timerが発火しない。次回起動時にPersistent=falseなので過去分は実行されない |

自動リトライは行わない（発走時刻を過ぎたら投票不可、APIコスト節約）。

## ログ確認

```bash
# 当日の全レースのタイマー状況
systemctl --user list-timers 'keiba-*'

# 特定レースのログ
journalctl --user -u keiba-20260307-hanshin-11.service

# 失敗したレースだけ
systemctl --user --failed 'keiba-*'
```

アプリログは従来通り `logs/<date>/<venue>_<race>/` にJSON保存。

## クリーンアップ

schedule_races.py実行時に前日分を自動削除。常に当日分のtimer/serviceのみが存在する。

## 運用規模

- 最大3会場 × 12R = 36レース/日
- 各レース独立プロセス、30分間隔で同時並行実行あり
- 実行時間: 約36分/レース
