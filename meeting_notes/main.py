#!/usr/bin/env python3
"""会議動画 → 書き起こし 自動生成スクリプト

Google Drive共有アイテムの動画をローカルWhisper (faster-whisper) で書き起こし、
結果をGoogleドキュメントとしてマイドライブに保存する。

使い方:
    python main.py          # 通常実行
    python main.py --dry-run  # 実行せずに対象動画を確認
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import drive_service as ds
import whisper_service as ws
from config import load_config

BASE_DIR = Path(__file__).parent
PROCESSED_LOG = BASE_DIR / "processed_videos.json"
MB = 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "meeting_notes.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_processed():
    """処理済み動画IDの記録を読み込む。"""
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_processed(processed):
    """処理済み動画IDの記録を保存する。"""
    with open(PROCESSED_LOG, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)


def make_doc_title(video_name):
    """動画ファイル名から書き起こしのドキュメントタイトルを生成する。"""
    stem = Path(video_name).stem
    return f"【議事録】{stem}"


def extract_audio(video_path):
    """動画ファイルからWAV音声を抽出する（Whisperの入力に最適化）。

    Args:
        video_path: 動画ファイルのパス

    Returns:
        WAVファイルのパス。変換失敗時はNoneを返す。
    """
    wav_path = video_path.rsplit(".", 1)[0] + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
             "-y", wav_path],
            check=True,
            capture_output=True,
            text=True,
        )
        video_size = os.path.getsize(video_path) / MB
        wav_size = os.path.getsize(wav_path) / MB
        logger.info(
            f"  音声抽出完了: {video_size:.1f}MB → {wav_size:.1f}MB"
        )
        return wav_path
    except FileNotFoundError:
        logger.warning(
            "  ffmpegが見つかりません。動画ファイルのまま書き起こしを行います。"
        )
        return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"  音声抽出に失敗しました。動画のまま処理します: {e.stderr}")
        return None


def _find_source_folder(drive_svc, shared_drive_name, source_folder_name):
    """ソースフォルダを検索し、(folder_id, drive_id)を返す。"""
    shared_drive_id = None
    if shared_drive_name:
        try:
            logger.info(f"共有ドライブ '{shared_drive_name}' を検索中...")
            shared_drive_id = ds.find_shared_drive(drive_svc, shared_drive_name)
            logger.info(f"ソースフォルダ '{source_folder_name}' を検索中...")
            source_folder_id = ds.find_folder_in_shared_drive(
                drive_svc, source_folder_name, shared_drive_id
            )
            return source_folder_id, shared_drive_id
        except ValueError:
            logger.info("共有ドライブが見つかりません。共有アイテムから検索します...")

    logger.info(f"共有アイテムからフォルダ '{source_folder_name}' を検索中...")
    source_folder_id = ds.find_folder_in_shared_items(
        drive_svc, source_folder_name
    )
    return source_folder_id, None


def _filter_unprocessed(videos, processed, existing_docs):
    """未処理の動画をフィルタリングして返す。"""
    unprocessed = []
    for video in videos:
        doc_title = make_doc_title(video["name"])
        if video["id"] in processed:
            entry = processed[video["id"]]
            # エラーだった動画は再処理対象に含める
            if entry.get("status", "").startswith("error"):
                logger.info(f"再処理（前回エラー）: {video['name']}")
                unprocessed.append(video)
                continue
            logger.info(f"スキップ（処理済み）: {video['name']}")
            continue
        if doc_title in existing_docs:
            logger.info(f"スキップ（ドキュメント存在）: {video['name']}")
            processed[video["id"]] = {
                "name": video["name"],
                "doc_title": doc_title,
                "processed_at": datetime.now().isoformat(),
                "status": "already_exists",
            }
            continue
        unprocessed.append(video)
    return unprocessed


def _process_video(video, drive_svc, docs_svc, target_folder_id,
                   config, has_ffmpeg, processed):
    """1件の動画を処理する（ダウンロード→音声抽出→書き起こし→保存）。

    Returns:
        True: 成功, False: エラー
    """
    video_name = video["name"]
    video_id = video["id"]
    tmp_path = None
    wav_path = None

    try:
        # 一時ファイルに動画をダウンロード
        suffix = Path(video_name).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        logger.info(f"  ダウンロード中: {video_name}")
        ds.download_video(drive_svc, video_id, tmp_path)

        # 音声を抽出（ffmpegが利用可能な場合）
        media_path = tmp_path
        if has_ffmpeg:
            logger.info("  音声を抽出中...")
            wav_path = extract_audio(tmp_path)
            if wav_path:
                media_path = wav_path
                # 動画の一時ファイルを先に削除（ディスク節約）
                try:
                    os.unlink(tmp_path)
                    tmp_path = None
                except OSError:
                    pass

        # Whisperで書き起こし
        logger.info("  書き起こし中（Whisper large-v3）...")
        transcription = ws.transcribe(
            media_path,
            model_size=config["whisper_model_size"],
            device=config["whisper_device"],
            compute_type=config["whisper_compute_type"],
        )

        # Googleドキュメントとして保存
        doc_title = make_doc_title(video_name)
        logger.info(f"  Googleドキュメントを作成中: {doc_title}")
        doc_id = ds.create_google_doc(
            drive_svc, docs_svc, doc_title, transcription, target_folder_id
        )

        # 処理済みとして記録
        processed[video_id] = {
            "name": video_name,
            "doc_title": doc_title,
            "doc_id": doc_id,
            "processed_at": datetime.now().isoformat(),
            "status": "success",
        }
        save_processed(processed)
        logger.info(f"  完了: {doc_title}")
        return True

    except Exception as e:
        logger.error(f"  エラー: {video_name} の処理に失敗しました: {e}")
        processed[video_id] = {
            "name": video_name,
            "processed_at": datetime.now().isoformat(),
            "status": f"error: {str(e)}",
        }
        save_processed(processed)
        return False

    finally:
        # 一時ファイルを削除
        for path in [tmp_path, wav_path]:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def run(dry_run=False):
    """メイン処理を実行する。"""
    config = load_config(BASE_DIR, logger)

    # ffmpegの有無を確認
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if has_ffmpeg:
        logger.info("ffmpeg検出: 動画から音声を抽出してWhisperに入力します")
    else:
        logger.warning(
            "ffmpegが見つかりません。動画ファイルのまま処理します。"
            "ffmpegのインストールを推奨します（音声抽出で処理が高速化されます）。"
        )

    # Whisperモデルを事前にロード
    logger.info(
        f"Whisperモデル: {config['whisper_model_size']} "
        f"(device={config['whisper_device']}, "
        f"compute_type={config['whisper_compute_type']})"
    )
    if not dry_run:
        ws.load_model(
            config["whisper_model_size"],
            config["whisper_device"],
            config["whisper_compute_type"],
        )

    # Google Drive認証
    logger.info("Google Drive APIに接続中...")
    drive_svc, docs_svc = ds.get_services()

    # ソースフォルダ・出力フォルダを特定
    source_folder_id, shared_drive_id = _find_source_folder(
        drive_svc, config["shared_drive_name"], config["source_folder_name"]
    )

    logger.info(
        f"出力フォルダ '{config['target_parent_folder_name']}"
        f"/{config['target_folder_name']}' を検索中..."
    )
    parent_folder_id = ds.find_folder_in_my_drive(
        drive_svc, config["target_parent_folder_name"]
    )
    target_folder_id = ds.find_folder_in_my_drive(
        drive_svc, config["target_folder_name"], parent_id=parent_folder_id
    )

    # 動画ファイルの一覧を取得
    logger.info("動画ファイルを検索中...")
    videos = ds.list_videos_in_folder(
        drive_svc, source_folder_id, drive_id=shared_drive_id
    )
    if not videos:
        logger.info("処理対象の動画ファイルが見つかりませんでした。")
        return

    # 未処理の動画をフィルタリング
    processed = load_processed()
    existing_docs = ds.list_docs_in_folder(drive_svc, target_folder_id)
    unprocessed = _filter_unprocessed(videos, processed, existing_docs)

    if not unprocessed:
        logger.info("新しい動画はありません。全て処理済みです。")
        save_processed(processed)
        return

    # 処理上限の適用
    max_videos = config["max_videos"]
    if max_videos > 0 and len(unprocessed) > max_videos:
        logger.info(
            f"未処理の動画: {len(unprocessed)} 件 "
            f"（今回は最大 {max_videos} 件を処理）"
        )
        unprocessed = unprocessed[:max_videos]
    else:
        logger.info(f"未処理の動画: {len(unprocessed)} 件")

    if dry_run:
        logger.info("=== ドライラン: 以下の動画が処理対象です ===")
        for video in unprocessed:
            size_mb = int(video.get("size", 0)) / MB
            logger.info(f"  - {video['name']} ({size_mb:.1f} MB)")
        return

    # 各動画を処理
    success_count = 0
    error_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 3
    request_interval = config["request_interval"]

    for i, video in enumerate(unprocessed, 1):
        size_mb = int(video.get("size", 0)) / MB
        logger.info(
            f"\n{'='*60}\n"
            f"[{i}/{len(unprocessed)}] 処理中: {video['name']} ({size_mb:.1f} MB)"
        )

        ok = _process_video(
            video, drive_svc, docs_svc, target_folder_id,
            config, has_ffmpeg, processed,
        )
        if ok:
            success_count += 1
            consecutive_errors = 0
        else:
            error_count += 1
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                logger.error(
                    f"{max_consecutive_errors} 件連続でエラーが発生したため処理を中断します。"
                )
                break

        # 次の処理まで待機
        if i < len(unprocessed) and request_interval > 0:
            logger.info(f"  次の処理まで {request_interval} 秒待機...")
            time.sleep(request_interval)

    logger.info(
        f"\n{'='*60}\n"
        f"処理完了: 成功 {success_count} 件, エラー {error_count} 件"
    )


def main():
    parser = argparse.ArgumentParser(
        description="会議動画から書き起こしを自動生成"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実行せずに処理対象の動画を確認する",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
