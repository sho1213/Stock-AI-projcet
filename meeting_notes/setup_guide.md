# セットアップガイド

会議動画→議事録自動生成システムの初期設定手順です。

## 1. 前提条件

- Python 3.9以上
- Googleアカウント（Google Drive、共有ドライブへのアクセス権限）

## 2. Python依存パッケージのインストール

```bash
cd meeting_notes
pip install -r requirements.txt
```

## 3. Gemini APIキーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) にアクセス
2. 「APIキーを作成」をクリック
3. 取得したAPIキーをメモ

## 4. Google Drive API用OAuth2認証の設定

### 4-1. Google Cloudプロジェクトの作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 左上のプロジェクト選択 → 「新しいプロジェクト」をクリック
3. プロジェクト名を入力（例: `meeting-notes-generator`）して作成

### 4-2. APIの有効化

1. 左メニュー「APIとサービス」→「ライブラリ」
2. 以下の2つのAPIを検索して有効化：
   - **Google Drive API**
   - **Google Docs API**

### 4-3. OAuth同意画面の設定

1. 左メニュー「APIとサービス」→「OAuth同意画面」
2. ユーザータイプ「外部」を選択（または組織内なら「内部」）
3. 必須項目を入力：
   - アプリ名: `議事録生成ツール`
   - ユーザーサポートメール: 自分のメールアドレス
   - デベロッパーの連絡先メール: 自分のメールアドレス
4. スコープの追加：
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/documents`
5. テストユーザーに自分のGoogleアカウントを追加

### 4-4. OAuth2クライアントIDの作成

1. 左メニュー「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「OAuth クライアントID」
3. アプリケーションの種類: **デスクトップアプリ**
4. 名前: `議事録生成ツール`
5. 「作成」をクリック
6. JSONファイルをダウンロード
7. ダウンロードしたファイルを `meeting_notes/credentials.json` として配置

## 5. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集し、取得したGemini APIキーを設定：

```
GEMINI_API_KEY=ここにAPIキーを貼り付け
```

## 6. 初回実行（認証）

```bash
python main.py --dry-run
```

初回実行時にブラウザが開き、Googleアカウントでのログインが求められます。
ログイン後、`token.json` が自動生成され、以降はブラウザなしで実行できます。

`--dry-run` オプションで、実際に議事録を生成せずに対象動画を確認できます。

## 7. 本番実行

```bash
python main.py
```

## 8. 定期実行の設定

```bash
bash cron_setup.sh
```

毎日午前6時に自動実行するcronジョブが設定されます。
詳細は `cron_setup.sh` を参照してください。

## ファイル構成

```
meeting_notes/
├── .env                  # 環境変数（APIキーなど）※gitに含めない
├── .env.example          # 環境変数のテンプレート
├── credentials.json      # OAuth2認証情報 ※gitに含めない
├── token.json            # 認証トークン（自動生成）※gitに含めない
├── processed_videos.json # 処理済み動画の記録（自動生成）
├── meeting_notes.log     # 実行ログ（自動生成）
├── main.py               # メインスクリプト
├── drive_service.py      # Google Drive API操作
├── gemini_service.py     # Gemini APIによる議事録生成
├── requirements.txt      # Python依存パッケージ
├── setup_guide.md        # このファイル
└── cron_setup.sh         # cron設定スクリプト
```
