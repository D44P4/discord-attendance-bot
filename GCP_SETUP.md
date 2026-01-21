# GCP Cloud Runデプロイガイド

DiscordボットをGCP Cloud Runにデプロイする手順です。

## 0. 前提条件

- Google Cloud Platform（GCP）アカウント
- GCPプロジェクトの作成権限
- GitHubアカウント（自動デプロイ用）
- Discord Botトークン（Discord Developer Portalから取得）

## 1. GCPプロジェクトの作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクト選択ドロップダウンから「新しいプロジェクト」をクリック
3. プロジェクト名を入力（例: `discord-attendance-bot`）
4. 「作成」をクリック
5. プロジェクトが作成されたら、そのプロジェクトを選択

## 2. 必要なAPIの有効化

以下のAPIを有効化します：

1. **Cloud Run API**
   - [Cloud Run API](https://console.cloud.google.com/apis/library/run.googleapis.com)にアクセス
   - 「有効にする」をクリック

2. **Cloud Build API**
   - [Cloud Build API](https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com)にアクセス
   - 「有効にする」をクリック

3. **Artifact Registry API**
   - [Artifact Registry API](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com)にアクセス
   - 「有効にする」をクリック

## 3. Artifact Registryリポジトリの作成

Dockerイメージを保存するためのリポジトリを作成します。

1. [Artifact Registry](https://console.cloud.google.com/artifacts)にアクセス
2. 「リポジトリを作成」をクリック
3. 以下の設定を入力：
   - **名前**: `discord-bot`
   - **形式**: Docker
   - **モード**: 標準
   - **リージョン**: `asia-northeast1`（東京）
4. 「作成」をクリック

## 4. Cloud Runサービスの初回作成（手動）

初回は手動でCloud Runサービスを作成し、環境変数を設定します。

### 4.1. gcloud CLIのインストール（オプション）

コマンドラインから操作する場合は、[gcloud CLI](https://cloud.google.com/sdk/docs/install)をインストールしてください。

### 4.2. 初回デプロイ（手動）

以下のいずれかの方法で初回デプロイを行います：

#### 方法A: Cloud Consoleからデプロイ

1. [Cloud Run](https://console.cloud.google.com/run)にアクセス
2. 「サービスの作成」をクリック
3. 「コンテナイメージをビルドしてデプロイ」を選択
4. 以下の設定を入力：
   - **サービス名**: `discord-attendance-bot`
   - **リージョン**: `asia-northeast1`
   - **認証**: 「未認証の呼び出しを許可」を選択
   - **コンテナイメージURL**: 後で設定（先にイメージをビルドする必要があります）
5. 「次へ」をクリック
6. 「コンテナ、変数、シークレット、接続」セクションで環境変数を設定（後述）
7. 「次へ」をクリック
8. 「最小インスタンス数**: `1`（常時起動のため）
9. 「最大インスタンス数**: `1`
10. 「CPUスロットリングを無効にする」: チェック
11. 「作成」をクリック

#### 方法B: gcloud CLIからデプロイ

```bash
# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# Dockerイメージをビルド（ローカルで実行する場合）
docker build -t asia-northeast1-docker.pkg.dev/YOUR_PROJECT_ID/discord-bot/discord-attendance-bot:latest .

# Artifact Registryに認証
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# イメージをプッシュ
docker push asia-northeast1-docker.pkg.dev/YOUR_PROJECT_ID/discord-bot/discord-attendance-bot:latest

# Cloud Runにデプロイ
gcloud run deploy discord-attendance-bot \
  --image asia-northeast1-docker.pkg.dev/YOUR_PROJECT_ID/discord-bot/discord-attendance-bot:latest \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 1 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 3600 \
  --no-cpu-throttling \
  --set-env-vars "DISCORD_TOKEN=YOUR_TOKEN,GUILD_ID=YOUR_GUILD_ID,CHANNEL_ID=YOUR_CHANNEL_ID"
```

## 5. 環境変数の設定

Cloud Runサービスに環境変数を設定します。

### 5.1. Cloud Consoleから設定

1. [Cloud Run](https://console.cloud.google.com/run)にアクセス
2. `discord-attendance-bot`サービスをクリック
3. 「編集と新しいリビジョンをデプロイ」をクリック
4. 「変数とシークレット」タブを開く
5. 「変数を追加」をクリックして以下の環境変数を追加：

#### 必須環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `DISCORD_TOKEN` | `YOUR_DISCORD_BOT_TOKEN` | Discord Botトークン（Discord Developer Portalから取得） |

#### 推奨環境変数

| 環境変数名 | 値 | 説明 |
|----------|-----|------|
| `GUILD_ID` | `YOUR_GUILD_ID` | サーバー（ギルド）ID |
| `CHANNEL_ID` | `YOUR_CHANNEL_ID` | 手動コマンド用チャンネルID |
| `AUTO_SEND_CHANNEL_ID` | `YOUR_AUTO_SEND_CHANNEL_ID` | 自動送信用チャンネルID |

#### オプション環境変数（デフォルト値で動作）

| 環境変数名 | デフォルト値 | 説明 |
|----------|------------|------|
| `SEND_TIME` | `20:00` | メッセージ送信時刻（HH:MM形式） |
| `SUMMARY_TIME` | `22:00` | 集計結果送信時刻（HH:MM形式） |
| `WEEKDAYS` | `[4,5]` | 送信する曜日（JSON形式、0=月曜日, 4=金曜日, 5=土曜日） |
| `SEND_BEFORE_HOLIDAYS` | `true` | 祝前日に送信するかどうか（`true`または`false`） |

6. 「デプロイ」をクリック

### 5.2. Secret Managerを使用する方法（推奨）

機密情報（Discordトークンなど）はSecret Managerを使用することを推奨します。

1. [Secret Manager](https://console.cloud.google.com/security/secret-manager)にアクセス
2. 「シークレットを作成」をクリック
3. シークレット名を入力（例: `discord-token`）
4. シークレット値を入力（Discord Botトークン）
5. 「作成」をクリック
6. Cloud Runサービスの「変数とシークレット」タブで「シークレットを追加」をクリック
7. 作成したシークレットを選択し、環境変数名を設定（例: `DISCORD_TOKEN`）

## 6. Cloud Buildトリガーの設定（GitHub連携）

GitHubにプッシュすると自動的にデプロイされるように設定します。

### 6.1. GitHub接続の作成

1. [Cloud Buildトリガー](https://console.cloud.google.com/cloud-build/triggers)にアクセス
2. 「接続を作成」をクリック
3. 「GitHub（Cloud Build GitHub App）」を選択
4. 「続行」をクリック
5. GitHubアカウントで認証
6. リポジトリを選択（`D44P4/discord-attendance-bot`）
7. 「接続」をクリック

### 6.2. トリガーの作成

1. 「トリガーを作成」をクリック
2. 以下の設定を入力：
   - **名前**: `discord-bot-deploy`
   - **イベント**: プッシュイベント
   - **ソース**: `D44P4/discord-attendance-bot`
   - **ブランチ**: `^main$`（mainブランチのみ）
   - **設定タイプ**: Cloud Build設定ファイル（yaml または json）
   - **場所**: `cloudbuild.yaml`
3. 「作成」をクリック

### 6.3. Cloud Buildサービスアカウントの権限設定

Cloud BuildがCloud Runにデプロイできるように権限を付与します。

1. [IAM](https://console.cloud.google.com/iam-admin/iam)にアクセス
2. Cloud Buildサービスアカウント（`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`）を検索
3. 「編集」をクリック
4. 「ロールを追加」をクリック
5. 以下のロールを追加：
   - `Cloud Run Admin`
   - `Service Account User`
6. 「保存」をクリック

## 7. デプロイの確認

### 7.1. 初回デプロイの確認

1. [Cloud Run](https://console.cloud.google.com/run)にアクセス
2. `discord-attendance-bot`サービスをクリック
3. 「ログ」タブを開く
4. 以下のメッセージが表示されれば成功：
   - `Bot がログインしました`
   - `コマンドを同期しました`

### 7.2. 自動デプロイの確認

1. GitHubリポジトリに変更をプッシュ
2. [Cloud Build履歴](https://console.cloud.google.com/cloud-build/builds)でビルドが開始されることを確認
3. ビルドが成功すると、自動的にCloud Runにデプロイされます

## 8. ボットの動作確認

1. Discordでボットがオンラインになっていることを確認
2. `/send_question`コマンドが使用できることを確認
3. `/show_summary`コマンドが使用できることを確認
4. 定期メッセージ送信が正常に動作することを確認

## 9. Koyebからの移行手順

### 9.1. 環境変数の移行

Koyebで設定していた環境変数をGCPに移行：

1. Koyebダッシュボードで「Environment Variables」を確認
2. 設定されている環境変数をメモまたはコピー
3. GCP Cloud Runの「変数とシークレット」に同じ環境変数を設定（手順5を参照）

### 9.2. デプロイの確認

1. GCPでデプロイが成功することを確認
2. Discordでボットが正常に動作することを確認
3. 定期メッセージ送信が正常に動作することを確認

### 9.3. Koyebサービスの停止

1. GCPでの動作確認が完了したら、Koyebダッシュボードでサービスを停止または削除
2. これにより、Koyebの課金を停止できます

## トラブルシューティング

### デプロイが失敗する

**エラーメッセージ**: "Build failed" または "Deployment failed"

**解決方法**:
1. [Cloud Build履歴](https://console.cloud.google.com/cloud-build/builds)でビルドログを確認
2. `Dockerfile`が正しく設定されているか確認
3. `requirements.txt`が正しく設定されているか確認
4. Artifact Registryリポジトリが正しく作成されているか確認

### ボットが起動しない

**解決方法**:
1. Cloud Runの「ログ」タブでエラーメッセージを確認
2. 環境変数が正しく設定されているか確認
3. `DISCORD_TOKEN`が正しいか確認
4. Discord Developer Portalでボットのトークンが有効か確認

### コマンドが表示されない

**解決方法**:
1. ボットがサーバーに招待されているか確認
2. ボットに「applications.commands」スコープが付与されているか確認
3. Cloud Runのログに「コマンドを同期しました」と表示されているか確認

### メッセージが送信されない

**解決方法**:
1. `AUTO_SEND_CHANNEL_ID`が正しく設定されているか確認
2. ボットが指定されたチャンネルにアクセス権限を持っているか確認
3. Cloud Runのログでエラーメッセージを確認

### インスタンスがスリープする

**解決方法**:
1. Cloud Runサービスの設定で「最小インスタンス数」が`1`に設定されているか確認
2. 「CPUスロットリングを無効にする」が有効になっているか確認

### データが失われる

**注意**: Cloud Runの一時ストレージに保存されたデータ（`data/responses.json`、`data/holidays.json`）は、再起動時に失われる可能性があります。

**解決方法**:
- 必要に応じて、Cloud Storageにデータを保存するようにコードを修正
- または、Cloud SQLやFirestoreなどの永続ストレージを使用

## コスト見積もり

Cloud Runの料金は以下の通りです：

- **CPU**: 常時起動（最小インスタンス数1）の場合、24時間稼働で約$0.00002400/秒
- **メモリ**: 512Mi使用で約$0.00000250/秒
- **リクエスト**: 無料枠あり（月200万リクエストまで無料）

**月額見積もり（最小インスタンス数1、512Miメモリ）**:
- CPU: 約$2.07/月
- メモリ: 約$0.22/月
- **合計**: 約$2.29/月（リクエストは無料枠内）

## 補足情報

- データファイル（`data/responses.json`、`data/holidays.json`）はCloud Runの一時ストレージに保存されます
- ログはCloud Loggingから確認できます
- 環境変数を変更した場合は、新しいリビジョンがデプロイされます
- GitHubにプッシュすると自動的に再デプロイされます
- Cloud Runは自動スケーリングに対応していますが、Discordボットの場合は最小インスタンス数1で固定することを推奨します

## 参考リンク

- [Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [Cloud Build ドキュメント](https://cloud.google.com/build/docs)
- [Artifact Registry ドキュメント](https://cloud.google.com/artifact-registry/docs)
- [Secret Manager ドキュメント](https://cloud.google.com/secret-manager/docs)
