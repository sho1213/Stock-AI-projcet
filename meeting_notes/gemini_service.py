"""Gemini APIによる議事録生成モジュール

書き起こしテキストからGemini APIで議事録を自動生成する。
動画/音声ファイルの直接アップロードにも対応（フォールバック用）。
"""

import logging
import time

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from google.generativeai.types import (
    BlockedPromptException,
    StopCandidateException,
)

logger = logging.getLogger(__name__)

# リトライ設定
MAX_RETRIES = 3
INITIAL_RETRY_WAIT = 60  # 秒

# 生成設定
FILE_PROCESSING_POLL_INTERVAL = 10  # 秒
MAX_OUTPUT_TOKENS = 8192
TEMPERATURE = 0.3

MEETING_NOTES_PROMPT = """\
あなたは優秀な議事録作成アシスタントです。
以下の会議の書き起こしテキストを読み、詳細な議事録を日本語で作成してください。

## 議事録のフォーマット

以下の構成で議事録を作成してください：

### 会議概要
- 会議名/テーマ（内容から推測）
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
- 書き起こしの誤変換と思われる箇所は文脈から適切に補正してください
- 専門用語はそのまま記載してください
- 時系列に沿って記録してください
"""

MEDIA_MEETING_NOTES_PROMPT = """\
あなたは優秀な議事録作成アシスタントです。
以下の会議の音声/動画を視聴し、詳細な議事録を日本語で作成してください。

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


def generate_meeting_notes_from_transcript(transcript, model_name="gemini-2.0-flash"):
    """書き起こしテキストからGemini APIを使って議事録を生成する。

    Args:
        transcript: Whisper等で生成した書き起こしテキスト
        model_name: 使用するGeminiモデル名

    Returns:
        生成された議事録テキスト
    """
    logger.info(f"  書き起こしテキストから議事録を生成中... (モデル: {model_name})")

    model = genai.GenerativeModel(model_name)
    prompt = MEETING_NOTES_PROMPT + "\n\n## 書き起こしテキスト\n\n" + transcript

    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                ),
            )
            break
        except ResourceExhausted as e:
            if attempt == MAX_RETRIES:
                raise
            wait = INITIAL_RETRY_WAIT * (2 ** attempt)
            logger.warning(
                f"  レート制限に到達。{wait}秒待機後にリトライします "
                f"({attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(wait)
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                wait = INITIAL_RETRY_WAIT * (2 ** attempt)
                logger.warning(
                    f"  レート制限に到達。{wait}秒待機後にリトライします "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait)
            else:
                raise

    try:
        result_text = response.text
    except (BlockedPromptException, StopCandidateException, ValueError) as e:
        raise RuntimeError(
            f"Gemini APIが安全フィルタによりコンテンツをブロックしました: {e}"
        )

    return result_text


def generate_meeting_notes(media_path, model_name="gemini-2.0-flash"):
    """メディアファイル（動画/音声）からGemini APIを使って議事録を生成する。

    Args:
        media_path: 動画または音声ファイルのパス
        model_name: 使用するGeminiモデル名

    Returns:
        生成された議事録テキスト
    """
    logger.info(f"  ファイルをGemini APIにアップロード中: {media_path}")
    uploaded_file = genai.upload_file(str(media_path))

    # ファイルの処理完了を待機
    logger.info("  Gemini APIでファイルを処理中...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(FILE_PROCESSING_POLL_INTERVAL)
        uploaded_file = genai.get_file(uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise RuntimeError(
            f"Gemini APIでのファイル処理に失敗しました: {uploaded_file.name}"
        )

    logger.info(f"  ファイル処理完了。議事録を生成中... (モデル: {model_name})")

    model = genai.GenerativeModel(model_name)

    # リトライ付きで議事録を生成
    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                [uploaded_file, MEDIA_MEETING_NOTES_PROMPT],
                generation_config=genai.GenerationConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                ),
            )
            break
        except ResourceExhausted as e:
            if attempt == MAX_RETRIES:
                _cleanup_file(uploaded_file)
                raise
            wait = INITIAL_RETRY_WAIT * (2 ** attempt)
            logger.warning(
                f"  レート制限に到達。{wait}秒待機後にリトライします "
                f"({attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(wait)
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                wait = INITIAL_RETRY_WAIT * (2 ** attempt)
                logger.warning(
                    f"  レート制限に到達。{wait}秒待機後にリトライします "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait)
            else:
                _cleanup_file(uploaded_file)
                raise

    # アップロードしたファイルを削除
    _cleanup_file(uploaded_file)

    # レスポンスの安全フィルタチェック
    try:
        result_text = response.text
    except (BlockedPromptException, StopCandidateException, ValueError) as e:
        raise RuntimeError(
            f"Gemini APIが安全フィルタによりコンテンツをブロックしました: {e}"
        )

    return result_text


def _cleanup_file(uploaded_file):
    """Gemini APIにアップロードしたファイルを削除する。"""
    try:
        genai.delete_file(uploaded_file.name)
        logger.info("  アップロードファイルを削除しました")
    except Exception as e:
        logger.warning(f"  アップロードファイルの削除に失敗: {e}")
