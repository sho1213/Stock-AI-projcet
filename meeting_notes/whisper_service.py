"""Whisperによる音声書き起こしモジュール

faster-whisperを使用して、動画/音声ファイルをテキストに変換する。
"""

import logging

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_MODEL_SIZE = "small"
DEFAULT_LANGUAGE = "ja"


def transcribe(media_path, model_size=DEFAULT_MODEL_SIZE, language=DEFAULT_LANGUAGE):
    """音声/動画ファイルを書き起こしてテキストを返す。

    Args:
        media_path: 音声または動画ファイルのパス
        model_size: Whisperモデルサイズ (tiny/base/small/medium/large-v3)
        language: 言語コード (ja/en等)

    Returns:
        書き起こしテキスト
    """
    logger.info(f"  Whisperモデルをロード中 (サイズ: {model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    logger.info(f"  書き起こし中: {media_path}")
    segments, info = model.transcribe(
        str(media_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    lines = []
    for segment in segments:
        lines.append(segment.text.strip())

    transcript = "\n".join(lines)
    logger.info(
        f"  書き起こし完了: {len(lines)} セグメント, "
        f"検出言語: {info.language} (確率: {info.language_probability:.0%})"
    )
    return transcript
