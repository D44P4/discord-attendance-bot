# Koyebデプロイガイド

DiscordボットをKoyebにデプロイする手順です。

## 1. Koyebアカウントの作成

1. [Koyeb](https://www.koyeb.com/)にアクセス
2. 「Sign up」または「Get started」をクリック
3. GitHubアカウントでログイン（推奨）またはメールアドレスで登録

## 2. プロジェクトの作成

1. Koyebダッシュボードで「Create App」をクリック
2. 「GitHub」を選択してリポジトリを連携
3. リポジトリを選択（例: `D44P4/discord-attendance-bot`）
4. ブランチを選択（通常は`main`または`master`）

## 3. アプリケーション設定

### 基本設定

- **Name**: アプリケーション名（例: `discord-attendance-bot`）
- **Service Type**: `Worker`を選択（DiscordボットはHTTPサーバーではないため）
- **Build Command**: 空欄（Pythonの場合は自動検出）
- **Run Command**: `python bot.py`

**重要：** 
- Service Typeは`Worker`を選択してください。DiscordボットはHTTPサーバーを提供しないため、`Web Service`ではなく`Worker`が適切です。
- `Procfile`は`web: python bot.py`または`worker: python bot.py`形式で記述できますが、Service Typeを`Worker`に設定している場合は`worker:`形式が推奨されます。

### 環境変数の設定

「Environment Variables」セクションで以下の環境変数を設定します。

#### 必須環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `DISCORD_TOKEN` | `YOUR_DISCORD_BOT_TOKEN` | Discord Botトークン（Discord Developer Portalから取得） |

#### 推奨環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `GUILD_ID` | `532988276840202250` | サーバー（ギルド）ID |
| `CHANNEL_ID` | `1434387080578072696` | 手動コマンド用チャンネルID |
| `AUTO_SEND_CHANNEL_ID` | `1434509700132769792` | 自動送信用チャンネルID |

#### オプション環境変数（デフォルト値で動作）

| 環境変数名 | デフォルト値 | 説明 |
|----------|------------|------|
| `SEND_TIME` | `20:00` | メッセージ送信時刻（HH:MM形式） |
| `WEEKDAYS` | `[4,5]` | 送信する曜日（JSON形式、0=月曜日, 4=金曜日, 5=土曜日） |
| `SEND_BEFORE_HOLIDAYS` | `true` | 祝前日に送信するかどうか（`true`または`false`） |

### 環境変数の設定手順

1. Koyebダッシュボードでアプリケーションを選択
2. 「Settings」タブを開く
3. 「Environment Variables」セクションを開く
4. 「Add Variable」ボタンをクリック
5. 「Key」に環境変数名、「Value」に値を入力
6. 「Save」をクリックして保存
7. すべての環境変数を追加したら、自動的に再デプロイされます

## 4. デプロイの確認

1. 「Deployments」タブでデプロイ状況を確認
2. 「Logs」をクリックしてログを確認
3. 以下のメッセージが表示されれば成功：
   - `Bot がログインしました`
   - `コマンドを同期しました`

## 5. ボットの動作確認

1. Discordでボットがオンラインになっていることを確認
2. `/send_question`コマンドが使用できることを確認
3. `/show_summary`コマンドが使用できることを確認

## 6. 自動デプロイ

GitHubリポジトリにプッシュすると、自動的にKoyebで再デプロイされます。

## Railwayからの移行手順

### 1. 環境変数の移行

Railwayで設定していた環境変数をKoyebに移行：

1. Railwayダッシュボードで「Variables」タブを開く
2. 設定されている環境変数をメモまたはコピー
3. Koyebダッシュボードで「Environment Variables」に同じ環境変数を設定

### 2. デプロイの確認

1. Koyebでデプロイが成功することを確認
2. Discordでボットが正常に動作することを確認
3. 定期メッセージ送信が正常に動作することを確認

### 3. Railwayサービスの停止

1. Koyebでの動作確認が完了したら、Railwayダッシュボードでサービスを停止または削除
2. これにより、Railwayの課金を停止できます

## トラブルシューティング

### デプロイが失敗する（起動コマンドが認識されない）

**エラーメッセージ：** "The command to launch your application is not defined"

**原因：** Koyebが`Procfile`の`worker:`形式を認識していない可能性があります。

**解決方法：**
1. Koyebダッシュボードでアプリケーションを選択
2. 「Settings」タブを開く
3. 「General」セクションで「Run Command」を確認
4. `python bot.py`が設定されているか確認（設定されていない場合は入力）
5. 「Save」をクリックして再デプロイ

### ヘルスチェックに失敗する

**エラーメッセージ：** "TCP health check failed on port 8000" または "Your application failed to pass the initial health checks"

**原因：** Service Typeを`Web Service`に設定している場合、KoyebはデフォルトでHTTPヘルスチェックを行いますが、DiscordボットはHTTPサーバーではないため応答できません。

**解決方法：**
1. **推奨：** Service Typeを`Worker`に変更する（ヘルスチェックが不要になります）
   - Koyebダッシュボードでアプリケーションを選択
   - 「Settings」タブを開く
   - 「General」セクションで「Service Type」を`Worker`に変更
   - 「Save」をクリックして再デプロイ

2. **代替方法：** Service Typeを`Web Service`のまま使用する場合
   - 「Settings」タブの「Health Checks」セクションを開く
   - 「Disable Health Checks」を有効化（またはカスタムヘルスチェックを設定）
   - 「Save」をクリックして再デプロイ

**注意：** Service Typeを`Worker`に設定すると、ヘルスチェックが不要になり、Discordボットに最適な設定になります。

### ボットが起動しない

- 環境変数が正しく設定されているか確認
- 「Logs」でエラーメッセージを確認
- Discord Developer Portalでボットのトークンが有効か確認
- `Procfile`が正しく設定されているか確認（`web: python bot.py`）

### コマンドが表示されない

- ボットがサーバーに招待されているか確認
- ボットに「applications.commands」スコープが付与されているか確認
- ログに「コマンドを同期しました」と表示されているか確認

### メッセージが送信されない

- `AUTO_SEND_CHANNEL_ID`が正しく設定されているか確認
- ボットが指定されたチャンネルにアクセス権限を持っているか確認
- ログでエラーメッセージを確認

### アプリケーションがスリープする（無料プラン）

Koyebの無料プランでは、一定時間アクセスがないとアプリケーションがスリープする可能性があります。

**解決方法：**
- 有料プランにアップグレード（常時起動）
- 外部のpingサービスを使用して定期的にアクセス（推奨）
- スリープからの復帰には数秒かかる場合があります

### デプロイが失敗する

- `requirements.txt`が正しく設定されているか確認
- Pythonのバージョンが適切か確認（Koyebは自動検出）
- ログでエラーメッセージを確認

## 補足情報

- データファイル（`data/responses.json`、`data/holidays.json`）はKoyebの永続ストレージに保存されます
- ログは「Logs」から確認できます
- 環境変数を変更した場合は自動的に再デプロイされます
- Koyebの無料プランには制限があります（スリープ、リソース制限など）

## Koyebの無料プラン制限

- **スリープ**: 一定時間アクセスがないとスリープする可能性
- **リソース**: CPU/メモリに制限あり
- **帯域幅**: 月間帯域幅に制限あり

Discordボットは常時起動が必要なため、無料プランではスリープする可能性があります。本番環境では有料プランの検討を推奨します。
