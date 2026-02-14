"""Whisperを使った日本語書き起こしモジュール。"""

from __future__ import annotations

import logging
from datetime import timedelta

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class JapaneseTranscriber:
    """faster-whisper ベースの日本語書き起こしクラス。"""

    FIXED_MODEL_SIZE = "large-v3"

    def __init__(
        self,
        compute_type: str = "int8",
        device: str = "cpu",
    ):
        logger.info(
            "Whisperモデルをロード中: model=%s, device=%s, compute_type=%s",
            self.FIXED_MODEL_SIZE,
            device,
            compute_type,
        )
        self.model = WhisperModel(
            self.FIXED_MODEL_SIZE,
            device=device,
            compute_type=compute_type,
        )
        logger.info("Whisperモデルのロード完了")

    def transcribe(
        self,
        media_path: str,
        vad_filter: bool = True,
        beam_size: int = 5,
    ) -> list:
        """音声/動画ファイルを日本語で書き起こす。

        Args:
            media_path: 音声または動画ファイルのパス
            vad_filter: VADフィルタの有効化（無音区間スキップ）
            beam_size: ビームサーチのサイズ

        Returns:
            書き起こしセグメントのリスト
        """
        logger.info("書き起こし開始: %s", media_path)
        segments, info = self.model.transcribe(
            media_path,
            language="ja",
            task="transcribe",
            vad_filter=vad_filter,
            beam_size=beam_size,
            condition_on_previous_text=True,
            temperature=0.0,
        )
        logger.info(
            "言語検出: %s (確率: %.2f)",
            info.language,
            info.language_probability,
        )
        segment_list = list(segments)
        logger.info("書き起こし完了: %d セグメント", len(segment_list))
        return segment_list


def _format_time(seconds: float) -> str:
    td = timedelta(seconds=max(seconds, 0))
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def render_meeting_notes(video_name: str, segments) -> str:
    """書き起こし結果を議事録向けテキストに整形する。"""
    lines = [
        f"# 議事録（自動書き起こし）: {video_name}",
        "",
        "## 注意",
        "- 本文はWhisper (large-v3) による自動書き起こしです。",
        "- 固有名詞や専門用語は誤認識が含まれる場合があります。",
        "",
        "## 書き起こし全文（日本語）",
    ]

    if not segments:
        lines.append("- （音声が検出できませんでした）")
        return "\n".join(lines)

    for seg in segments:
        ts = f"[{_format_time(seg.start)} - {_format_time(seg.end)}]"
        text = seg.text.strip() if seg.text else "（聞き取り不明）"
        lines.append(f"- {ts} {text}")

    return "\n".join(lines)
