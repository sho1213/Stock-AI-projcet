# セットアップガイド

会議動画→書き起こし自動生成システムの初期設定手順です。

## 1. 前提条件

- Python 3.9以上
- ffmpeg（音声抽出に必要。なくても動作しますがインストール推奨）
- Googleアカウント（Google Drive、共有ドライブへのアクセス権限）
- 十分なディスク容量（Whisper large-v3モデル: 約3GB）
- メモリ: 4GB以上（CPU / int8実行時）

## 2. Python依存パッケージのインストール

```bash
cd meeting_notes
pip install -r requirements.txt
```

### ffmpegのインストール

```bash
# Ubuntu/Debian
sudo apt-get install -y ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

## 3. Whisperモデルについて

本システムは [faster-whisper](https://github.com/SYSTRAN/faster-whisper) を使用し、
OpenAI Whisper large-v3 モデルで高精度な日本語書き起こしを行います。

- **APIキー不要**（完全ローカル実行、無料）
- モデルは初回実行時に自動ダウンロードされます（約3GB）
- GPU (CUDA) があれば自動検出して高速処理
- CPUのみでも動作（int8量子化でメモリ効率化）

### モデルサイズの目安

| モデル | VRAM/RAM | 精度 | 速度（1時間動画・CPU） |
|---|---|---|---|
| `large-v3` | ~3GB | 最高 | 約2-3時間 |
| `medium` | ~1.5GB | 高 | 約1時間 |
| `small` | ~0.5GB | 中 | 約20分 |

**推奨: `large-v3`**（デフォルト設定）

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

`.env` ファイルを編集（通常はデフォルト値のまま使用可能）：

```
# 必要に応じて変更
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=int8
```

## 6. 初回実行（認証）

```bash
python main.py --dry-run
```

初回実行時にブラウザが開き、Googleアカウントでのログインが求められます。
ログイン後、`token.json` が自動生成され、以降はブラウザなしで実行できます。

`--dry-run` オプションで、実際に書き起こしを生成せずに対象動画を確認できます。

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

## 9. GitHub Actionsでのクラウド実行（オプション）

ローカルPCを使わず、GitHub Actions上で自動実行・手動実行できます。

**注意**: GitHub ActionsではCPU実行のため、書き起こしに時間がかかります。
1時間の動画で約2-3時間かかる場合があります（タイムアウト: 6時間）。
長時間の動画が多い場合はローカル実行（cron）を推奨します。

### 9-1. 前提条件

- ローカルで初回認証が完了していること（`token.json` が生成済み）
- OAuth同意画面の公開ステータスが「本番」または「内部」に設定されていること
  - 「テスト」のままだとリフレッシュトークンが**7日で期限切れ**になります
  - Google Cloud Console →「APIとサービス」→「OAuth同意画面」→「アプリを公開」

### 9-2. GitHub Secretsの設定

GitHubリポジトリの **Settings → Secrets and variables → Actions → Secrets** に以下を登録：

| Secret名 | 内容 |
|---|---|
| `GOOGLE_CREDENTIALS_JSON` | `credentials.json` の中身をそのまま貼り付け |
| `GOOGLE_TOKEN_JSON` | `token.json` の中身をそのまま貼り付け |
| `SHARED_DRIVE_NAME` | 共有ドライブ名（`.env` の `SHARED_DRIVE_NAME` の値） |
| `SOURCE_FOLDER_NAME` | ソースフォルダ名（例: `録画データ_all`） |
| `TARGET_PARENT_FOLDER_NAME` | 出力親フォルダ名 |
| `TARGET_FOLDER_NAME` | 出力フォルダ名 |

**Secretsの登録方法:**

```bash
# credentials.json の中身をコピー
cat meeting_notes/credentials.json
# → 出力をコピーして GOOGLE_CREDENTIALS_JSON に貼り付け

# token.json の中身をコピー
cat meeting_notes/token.json
# → 出力をコピーして GOOGLE_TOKEN_JSON に貼り付け
```

### 9-3. GitHub Variables（オプション）

**Settings → Secrets and variables → Actions → Variables** に必要に応じて設定：

| Variable名 | デフォルト値 | 説明 |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `large-v3` | Whisperモデルサイズ |
| `REQUEST_INTERVAL` | `5` | 動画間の待機秒数 |
| `MAX_VIDEOS_PER_RUN` | `50` | 1回の実行で処理する最大件数 |

### 9-4. 動作確認

1. GitHubリポジトリの **Actions** タブを開く
2. 左メニューから「Meeting Notes Generator」を選択
3. 「Run workflow」ボタンをクリック
4. 「ドライラン」にチェックを入れて実行
5. ログを確認し、対象動画が正しく検出されることを確認

### 9-5. 自動実行

ワークフローは毎日 **6:00 AM（日本時間）** に自動実行されます。
手動でいつでも GitHub の Actions タブから実行することもできます。

### 9-6. トラブルシューティング

- **認証エラー**: `token.json` のリフレッシュトークンが期限切れの可能性があります。ローカルで `python auth.py` を再実行し、新しい `token.json` の内容で `GOOGLE_TOKEN_JSON` Secretを更新してください
- **メモリ不足**: `WHISPER_MODEL_SIZE` を `medium` に変更してください
- **タイムアウト**: `MAX_VIDEOS_PER_RUN` を小さくするか、ローカル実行に切り替えてください
- **二重作成を防ぎたい**: 既存の書き起こしドキュメント（`【議事録】動画名`）があれば自動スキップされます

### 9-7. この要件向けの推奨設定

以下の設定で：
- 共有アイテム内の `録画データ_all` から動画を取得
- Whisper large-v3 で高精度に日本語書き起こし
- マイドライブ `チーム石川/議事録` へ保存
- 毎日1回自動実行

が実現できます。

- `SHARED_DRIVE_NAME`: 空文字（共有ドライブを使わず共有アイテムを検索）
- `SOURCE_FOLDER_NAME`: `録画データ_all`
- `TARGET_PARENT_FOLDER_NAME`: `チーム石川`
- `TARGET_FOLDER_NAME`: `議事録`
- GitHub Actions の `schedule` は `0 21 * * *`（JSTで毎日6:00）

## ファイル構成

```
meeting_notes/
├── .env                  # 環境変数 ※gitに含めない
├── .env.example          # 環境変数のテンプレート
├── credentials.json      # OAuth2認証情報 ※gitに含めない
├── token.json            # 認証トークン（自動生成）※gitに含めない
├── processed_videos.json # 処理済み動画の記録（自動生成）
├── meeting_notes.log     # 実行ログ（自動生成）
├── main.py               # メインスクリプト
├── config.py             # 環境変数の読み込み・デフォルト処理
├── drive_service.py      # Google Drive API操作
├── whisper_service.py    # Whisperによる書き起こし
├── requirements.txt      # Python依存パッケージ
├── setup_guide.md        # このファイル
└── cron_setup.sh         # cron設定スクリプト

.github/workflows/
└── meeting-notes.yml     # GitHub Actionsで日次実行
```
