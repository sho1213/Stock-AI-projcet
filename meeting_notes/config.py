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
            name, raw, default,
        )
        return default


def load_config(base_dir: Path, logger):
    """環境変数を読み込み、設定辞書を返す。"""
    load_dotenv(base_dir / ".env")

    request_interval = _get_env_int("REQUEST_INTERVAL", 5, logger)
    if request_interval < 0:
        logger.warning(
            "REQUEST_INTERVAL の値 %d は負数のため、デフォルト値 5 を使用します。",
            request_interval,
        )
        request_interval = 5

    max_videos = _get_env_int("MAX_VIDEOS_PER_RUN", 80, logger)
    if max_videos < 0:
        logger.warning(
            "MAX_VIDEOS_PER_RUN の値 %d は負数のため、デフォルト値 80 を使用します。",
            max_videos,
        )
        max_videos = 80

    return {
        "shared_drive_name": _get_env_str("SHARED_DRIVE_NAME", ""),
        "source_folder_name": _get_env_str("SOURCE_FOLDER_NAME", "録画データ_all"),
        "target_parent_folder_name": _get_env_str("TARGET_PARENT_FOLDER_NAME", "チーム石川"),
        "target_folder_name": _get_env_str("TARGET_FOLDER_NAME", "議事録"),
        "whisper_device": _get_env_str("WHISPER_DEVICE", "cpu"),
        "whisper_compute_type": _get_env_str("WHISPER_COMPUTE_TYPE", "int8"),
        "request_interval": request_interval,
        "max_videos": max_videos,
    }
