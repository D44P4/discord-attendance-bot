# Code Project

このプロジェクトはデータ分析と可視化を行うためのコードベースです。

## Discordボット

参加可否を確認するDiscordボットが実装されています。

## プロジェクト構成

### Discordボット関連
- `bot.py` - Discordボットのメインファイル
- `config.json` - ボット設定ファイル
- `utils/` - ユーティリティモジュール
  - `scheduler.py` - スケジュール管理
  - `data_manager.py` - データ管理
  - `holidays.py` - 祝日管理
- `data/` - データファイル
  - `responses.json` - 回答データ
  - `holidays.json` - 祝日データ
- `commands/` - コマンドモジュール

### その他
- `scripts/` - Pythonスクリプト
- `sql/` - SQLクエリファイル
- `docs/` - ドキュメント・レポート
- `results/` - 分析結果データ（CSV等）
- `pics/` - 可視化画像

## Discordボットのセットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの編集

`config.json`を編集して以下の情報を設定してください：

```json
{
  "token": "YOUR_BOT_TOKEN",
  "guild_id": "YOUR_GUILD_ID",
  "channel_id": "YOUR_CHANNEL_ID",
  "send_time": "20:00",
  "weekdays": [4, 5],
  "send_before_holidays": true
}
```

- `token`: Discord Botトークン（Discord Developer Portalから取得）
- `guild_id`: サーバー（ギルド）ID
- `channel_id`: メッセージを送信するチャンネルID
- `send_time`: メッセージ送信時刻（HH:MM形式）
- `weekdays`: 送信する曜日（0=月曜日, 4=金曜日, 5=土曜日）
- `send_before_holidays`: 祝前日に送信するかどうか

### 3. ボットの起動

```bash
python bot.py
```

## ボットの機能

### 定期メッセージ送信
- 設定された曜日（デフォルト: 金曜日、土曜日）の20時に参加可否を問うメッセージを自動送信
- 日本の祝日の前日にも自動送信（設定で有効化）

### 参加可否の回答
- 「参加可能」「参加不可」ボタンで回答
- 参加可能な場合、開始時刻と終了時刻を選択式で入力

### スラッシュコマンド
- `/send_question` - 手動で質問メッセージを送信
- `/show_summary` - 集計結果を表示

### データ管理
- 回答は`data/responses.json`に保存
- ユーザーID、参加可否、時刻情報を記録

## Koyebへのデプロイ

### 1. Koyebアカウントの作成
1. [Koyeb](https://www.koyeb.com/)にアクセス
2. 「Sign up」または「Get started」をクリック
3. GitHubアカウントでログイン（推奨）

### 2. プロジェクトの作成
1. Koyebダッシュボードで「Create App」をクリック
2. 「GitHub」を選択してリポジトリを連携
3. リポジトリを選択（例: `D44P4/discord-attendance-bot`）
4. ブランチを選択（通常は`main`または`master`）

### 3. アプリケーション設定

**重要：** Service Typeは`Worker`を選択してください。DiscordボットはHTTPサーバーを提供しないため、`Web Service`ではなく`Worker`が適切です。

- **Name**: アプリケーション名（例: `discord-attendance-bot`）
- **Service Type**: `Worker`を選択
- **Run Command**: `python bot.py`

### 4. 環境変数の設定

Koyebダッシュボードの「Environment Variables」セクションで以下の環境変数を設定：

**必須環境変数：**
- `DISCORD_TOKEN`: Discord Botトークン（Discord Developer Portalから取得）

**推奨環境変数：**
- `GUILD_ID`: サーバー（ギルド）ID
- `CHANNEL_ID`: 手動コマンド用チャンネルID
- `AUTO_SEND_CHANNEL_ID`: 自動送信用チャンネルID

**オプション環境変数（デフォルト値で動作）：**
- `SEND_TIME`: メッセージ送信時刻（デフォルト: `20:00`）
- `SUMMARY_TIME`: 集計結果送信時刻（デフォルト: `22:00`）
- `WEEKDAYS`: 送信する曜日（デフォルト: `[4,5]`、JSON形式）
- `SEND_BEFORE_HOLIDAYS`: 祝前日に送信するか（デフォルト: `true`）

### 5. 自動デプロイ
GitHubにプッシュすると自動的にKoyebで再デプロイされます。

### 6. ログの確認
Koyebダッシュボードの「Logs」タブでログを確認できます。

詳細な手順は[KOYEB_SETUP.md](./KOYEB_SETUP.md)を参照してください。

## その他のセットアップ

1. Python仮想環境の作成と有効化
2. 必要なパッケージのインストール
3. BigQuery認証情報の設定

## Git設定

このプロジェクトはGitでバージョン管理されています。

### 初回設定（必要な場合）

```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 基本的な操作

```bash
# ステータス確認
git status

# 変更を追加
git add .

# コミット
git commit -m "コミットメッセージ"

# リモートリポジトリに追加（初回のみ）
git remote add origin <repository-url>

# プッシュ
git push -u origin main
```

