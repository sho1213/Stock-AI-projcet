"""Gemini APIによる議事録生成モジュール

動画ファイルをGemini APIにアップロードし、議事録を自動生成する。
"""

import logging
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

MEETING_NOTES_PROMPT = """\
あなたは優秀な議事録作成アシスタントです。
以下の会議動画を視聴し、詳細な議事録を日本語で作成してください。

## 議事録のフォーマット

以下の構成で議事録を作成してください：

### 会議概要
- 会議名/テーマ（動画の内容から推測）
- 参加者（識別できる場合）
- 会議の目的

### 議題と討議内容
各議題について以下を記録：
- 議題のタイトル
- 討議の要点
- 発言者ごとの主な意見（識別できる場合）

### 決定事項
- 会議で合意・決定された事項を箇条書きで記載

### アクションアイテム
- 誰が、何を、いつまでに行うか（識別できる場合）

### 備考・補足
- その他重要な発言や補足情報

---

注意事項：
- 正確性を重視し、推測で発言を捏造しないでください
- 聞き取れない部分は「（聞き取り不明）」と記載してください
- 専門用語はそのまま記載してください
- 時系列に沿って記録してください
"""


def configure(api_key):
    """Gemini APIの設定。"""
    genai.configure(api_key=api_key)


def generate_meeting_notes(video_path, model_name="gemini-2.0-flash"):
    """動画ファイルからGemini APIを使って議事録を生成する。

    Args:
        video_path: 動画ファイルのパス
        model_name: 使用するGeminiモデル名

    Returns:
        生成された議事録テキスト
    """
    logger.info(f"  動画をGemini APIにアップロード中: {video_path}")
    video_file = genai.upload_file(str(video_path))

    # ファイルの処理完了を待機
    logger.info("  Gemini APIで動画を処理中...")
    while video_file.state.name == "PROCESSING":
        time.sleep(10)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise RuntimeError(
            f"Gemini APIでの動画処理に失敗しました: {video_file.name}"
        )

    logger.info(f"  動画処理完了。議事録を生成中... (モデル: {model_name})")

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        [video_file, MEETING_NOTES_PROMPT],
        generation_config=genai.GenerationConfig(
            max_output_tokens=8192,
            temperature=0.3,
        ),
    )

    # アップロードしたファイルを削除
    try:
        genai.delete_file(video_file.name)
        logger.info("  アップロードファイルを削除しました")
    except Exception as e:
        logger.warning(f"  アップロードファイルの削除に失敗: {e}")

    return response.text
