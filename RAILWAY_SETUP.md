# Railwayデプロイガイド

DiscordボットをRailwayにデプロイする手順です。

## 1. Railwayアカウントの作成

1. [Railway](https://railway.app/)にアクセス
2. 「Start a New Project」または「Login」をクリック
3. GitHubアカウントでログイン

## 2. プロジェクトの作成

1. Railwayダッシュボードで「New Project」をクリック
2. 「Deploy from GitHub repo」を選択
3. `D44P4/discord-attendance-bot`リポジトリを選択して接続
4. リポジトリを選択して「Deploy Now」をクリック

## 3. 環境変数の設定

プロジェクトページで「Variables」タブを開き、以下の環境変数を設定します。

### 必須環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `DISCORD_TOKEN` | `YOUR_DISCORD_BOT_TOKEN` | Discord Botトークン（Discord Developer Portalから取得） |

### 推奨環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `GUILD_ID` | `YOUR_GUILD_ID` | サーバー（ギルド）ID |
| `CHANNEL_ID` | `YOUR_CHANNEL_ID` | 手動コマンド用チャンネルID |
| `AUTO_SEND_CHANNEL_ID` | `YOUR_AUTO_SEND_CHANNEL_ID` | 自動送信用チャンネルID |

### オプション環境変数（デフォルト値で動作）

| 環境変数名 | デフォルト値 | 説明 |
|----------|------------|------|
| `SEND_TIME` | `20:00` | メッセージ送信時刻（HH:MM形式） |
| `WEEKDAYS` | `[4,5]` | 送信する曜日（JSON形式、0=月曜日, 4=金曜日, 5=土曜日） |
| `SEND_BEFORE_HOLIDAYS` | `true` | 祝前日に送信するかどうか（`true`または`false`） |

### 環境変数の設定手順

1. Railwayダッシュボードでプロジェクトを選択
2. 上部の「Variables」タブをクリック
3. 「+ New Variable」ボタンをクリック
4. 「Key」に環境変数名、「Value」に値を入力
5. 「Add」をクリックして保存
6. すべての環境変数を追加したら、「Redeploy」ボタンをクリックして再デプロイ

## 4. デプロイの確認

1. 「Deployments」タブでデプロイ状況を確認
2. 「View Logs」をクリックしてログを確認
3. 以下のメッセージが表示されれば成功：
   - `Bot がログインしました`
   - `コマンドを同期しました`

## 5. ボットの動作確認

1. Discordでボットがオンラインになっていることを確認
2. `/send_question`コマンドが使用できることを確認
3. `/show_summary`コマンドが使用できることを確認

## 6. 自動デプロイ

GitHubリポジトリにプッシュすると、自動的にRailwayで再デプロイされます。

## トラブルシューティング

### "Failed to get private network endpoint" エラー

このエラーは通常、Discordボットの動作には影響しません。Railwayの内部ネットワーク機能に関連するエラーです。

**解決方法：**
1. Railwayダッシュボードで「Settings」タブを開く
2. 「Networking」セクションを確認
3. プライベートネットワークエンドポイントが有効になっている場合は、無効にするか、そのまま無視しても問題ありません
4. ボットが正常に動作しているか（Discordでオンラインになっているか）確認してください

**注意：** Discordボットは外部（Discord API）への接続のみが必要で、Railwayの内部ネットワークエンドポイントは不要です。

### ボットが起動しない

- 環境変数が正しく設定されているか確認
- 「View Logs」でエラーメッセージを確認
- Discord Developer Portalでボットのトークンが有効か確認

### コマンドが表示されない

- ボットがサーバーに招待されているか確認
- ボットに「applications.commands」スコープが付与されているか確認
- ログに「コマンドを同期しました」と表示されているか確認

### メッセージが送信されない

- `AUTO_SEND_CHANNEL_ID`が正しく設定されているか確認
- ボットが指定されたチャンネルにアクセス権限を持っているか確認
- ログでエラーメッセージを確認

## 補足情報

- データファイル（`data/responses.json`、`data/holidays.json`）はRailwayの永続ストレージに保存されます
- ログは「View Logs」から確認できます
- 環境変数を変更した場合は「Redeploy」ボタンをクリックして再デプロイが必要です

