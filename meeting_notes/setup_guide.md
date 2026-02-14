# 会議動画 → 議事録 自動化セットアップ（Whisper版）

この仕組みは次を満たします。
- 共有アイテムの `録画データ_all` から動画を取得
- 日本語で高精度に書き起こし（faster-whisper / 無料）
- マイドライブ `チーム石川/議事録` にGoogleドキュメント保存
- 1日1回の定期実行（GitHub Actions または cron）
- すでに処理済み動画はスキップ

## 1. 必須準備

- Google Cloud で Drive API / Docs API を有効化
- OAuth クライアントを作成して `meeting_notes/credentials.json` を配置
- `python auth.py` で `meeting_notes/token.json` を作成
- ffmpeg をインストール（音声抽出・Whisper実行のため推奨）

## 2. 環境変数

`meeting_notes/.env.example` を `.env` にコピーし、必要なら調整。

- `SOURCE_FOLDER_NAME=録画データ_all`
- `TARGET_PARENT_FOLDER_NAME=チーム石川`
- `TARGET_FOLDER_NAME=議事録`
- Whisperモデルは `large-v3` を固定で使用（精度優先）

## 3. 実行

```bash
cd meeting_notes
python main.py --dry-run  # 対象確認
python main.py            # 本実行
```

## 4. 定期実行

### GitHub Actions（推奨）
`.github/workflows/meeting-notes.yml` は `0 21 * * *`（JST 06:00）で毎日実行。

Secrets:
- `GOOGLE_CREDENTIALS_JSON`
- `GOOGLE_TOKEN_JSON`
- `SHARED_DRIVE_NAME`（共有アイテム運用なら空文字）
- `SOURCE_FOLDER_NAME`
- `TARGET_PARENT_FOLDER_NAME`
- `TARGET_FOLDER_NAME`

Variables（任意）:
- `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`
- `REQUEST_INTERVAL`, `MAX_VIDEOS_PER_RUN`

### cron
`meeting_notes/cron_setup.sh` を実行すると毎日6時実行のcronを作成。

## 5. スキップ仕様

以下は再生成しません。
- `processed_videos.json` に成功済み記録がある動画
- 同名議事録（`【議事録】<動画名>`）がすでに保存済みの動画

## 6. 精度と処理時間

- モデルは精度優先の `large-v3` 固定です。
- 長時間動画が多い場合、1日あたり件数は `MAX_VIDEOS_PER_RUN` で制御してください。
- CPU性能に応じて `WHISPER_COMPUTE_TYPE` を調整してください（例: `int8`）。
