"""設定読み込みユーティリティ。"""

import os
import sys
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

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
        sys.exit(1)

    return {
        "gemini_api_key": gemini_api_key,
        "shared_drive_name": _get_env_str("SHARED_DRIVE_NAME", ""),
        "source_folder_name": _get_env_str("SOURCE_FOLDER_NAME", "録画データ_all"),
        "target_parent_folder_name": _get_env_str("TARGET_PARENT_FOLDER_NAME", "チーム石川"),
        "target_folder_name": _get_env_str("TARGET_FOLDER_NAME", "議事録"),
        "gemini_model": _get_env_str("GEMINI_MODEL", "gemini-2.0-flash"),
        "request_interval": _get_env_int("REQUEST_INTERVAL", 30, logger),
        "max_videos": _get_env_int("MAX_VIDEOS_PER_RUN", 50, logger),
    }
