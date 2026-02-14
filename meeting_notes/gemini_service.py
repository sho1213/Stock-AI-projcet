"""互換用の空モジュール。

このプロジェクトは Gemini API 依存を廃止し、
`transcription_service.py` の faster-whisper を利用します。
"""

raise RuntimeError(
    "gemini_service.py は廃止されました。main.py を利用してください。"
)
