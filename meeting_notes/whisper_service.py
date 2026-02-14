"""ローカルWhisper (faster-whisper) による音声書き起こしモジュール

faster-whisper の large-v3 モデルを使用して、動画/音声ファイルから
高精度な日本語書き起こしを生成する。
"""

import logging

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# 日本語の書き起こし精度を向上させるための初期プロンプト
INITIAL_PROMPT = "これは日本語の会議の音声です。"

_model = None


def load_model(model_size="large-v3", device="auto", compute_type="int8"):
    """Whisperモデルをロードする（初回のみ）。

    Args:
        model_size: モデルサイズ ("large-v3", "medium", "small" など)
        device: 推論デバイス ("auto", "cpu", "cuda")
        compute_type: 計算精度 ("int8", "float16", "float32")
            - CPU使用時: "int8" を推奨（メモリ効率が良い）
            - GPU使用時: "float16" を推奨（高速）
    """
    global _model
    if _model is not None:
        return _model

    logger.info(
        f"Whisperモデルをロード中: {model_size} "
        f"(device={device}, compute_type={compute_type})"
    )
    _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info("Whisperモデルのロード完了")
    return _model


def transcribe(audio_path, model_size="large-v3", device="auto",
               compute_type="int8"):
    """音声/動画ファイルを書き起こす。

    Args:
        audio_path: 音声または動画ファイルのパス
        model_size: Whisperモデルサイズ
        device: 推論デバイス
        compute_type: 計算精度

    Returns:
        タイムスタンプ付きの書き起こしテキスト
    """
    model = load_model(model_size, device, compute_type)

    logger.info(f"  書き起こし開始: {audio_path}")

    segments, info = model.transcribe(
        audio_path,
        language="ja",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        initial_prompt=INITIAL_PROMPT,
        condition_on_previous_text=True,
    )

    logger.info(
        f"  検出言語: {info.language} (確率: {info.language_probability:.2f})"
    )

    lines = []
    for segment in segments:
        start_ts = _format_timestamp(segment.start)
        end_ts = _format_timestamp(segment.end)
        text = segment.text.strip()
        if text:
            lines.append(f"[{start_ts} - {end_ts}] {text}")

    transcription = "\n".join(lines)
    logger.info(f"  書き起こし完了: {len(lines)} セグメント")

    return transcription


def _format_timestamp(seconds):
    """秒数を HH:MM:SS 形式に変換する。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
