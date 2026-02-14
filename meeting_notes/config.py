"""設定読み込みユーティリティ。"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _get_env_str(name, default):
    """環境変数を文字列として取得し、空文字ならデフォルトを返す。"""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_env_int(name, default, logger):
    """環境変数を整数として取得し、不正値ならデフォルトを返す。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "%s の値 '%s' は整数ではないため、デフォルト値 %d を使用します。",
            name,
            raw,
            default,
        )
        return default


def load_config(base_dir: Path, logger):
    """環境変数を読み込み、設定辞書を返す。"""
    load_dotenv(base_dir / ".env")

    return {
        # Google Drive 設定
        "shared_drive_name": _get_env_str("SHARED_DRIVE_NAME", ""),
        "source_folder_name": _get_env_str("SOURCE_FOLDER_NAME", "録画データ_all"),
        "target_parent_folder_name": _get_env_str("TARGET_PARENT_FOLDER_NAME", "チーム石川"),
        "target_folder_name": _get_env_str("TARGET_FOLDER_NAME", "議事録"),
        # Whisper 設定
        "whisper_model_size": _get_env_str("WHISPER_MODEL_SIZE", "large-v3"),
        "whisper_device": _get_env_str("WHISPER_DEVICE", "auto"),
        "whisper_compute_type": _get_env_str("WHISPER_COMPUTE_TYPE", "int8"),
        # 実行制御
        "request_interval": _get_env_int("REQUEST_INTERVAL", 5, logger),
        "max_videos": _get_env_int("MAX_VIDEOS_PER_RUN", 50, logger),
    }
