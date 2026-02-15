"""Whisperを使った日本語書き起こしモジュール。"""

from __future__ import annotations

import logging
import os
import sys

# Windows: nvidia-cublas-cu12 等の pip パッケージに含まれる DLL を
# ctranslate2 が見つけられるよう PATH と add_dll_directory に登録する
if sys.platform == "win32":
    import glob
    import sysconfig

    _site = sysconfig.get_path("platlib") or ""
    _added: set[str] = set()
    for _pattern in ("cublas*.dll", "cudnn*.dll", "cublasLt*.dll"):
        for _dll in glob.glob(
            os.path.join(_site, "nvidia", "**", _pattern), recursive=True
        ):
            _d = os.path.dirname(_dll)
            if _d not in _added:
                _added.add(_d)
                os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(_d)

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


def render_meeting_notes(video_name: str, segments) -> str:
    """書き起こし結果を議事録向けテキストに整形する。"""
    lines = [
        f"# 議事録（自動書き起こし）: {video_name}",
        "",
        "## 書き起こし全文（日本語）",
    ]

    if not segments:
        lines.append("- （音声が検出できませんでした）")
        return "\n".join(lines)

    for seg in segments:
        text = seg.text.strip() if seg.text else "（聞き取り不明）"
        lines.append(f"- {text}")

    return "\n".join(lines)
