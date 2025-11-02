# Code Project

このプロジェクトはデータ分析と可視化を行うためのコードベースです。

## プロジェクト構成

- `scripts/` - Pythonスクリプト
- `sql/` - SQLクエリファイル
- `docs/` - ドキュメント・レポート
- `results/` - 分析結果データ（CSV等）
- `pics/` - 可視化画像

## セットアップ

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

