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
以下は再生成しません。
- `processed_videos.json` に成功済み記録がある動画
- 同名議事録（`【議事録】<動画名>`）がすでに保存済みの動画


