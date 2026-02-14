#!/usr/bin/env python3
"""会議動画 → 議事録 自動生成スクリプト

Google Driveの動画をWhisperで日本語書き起こしし、
議事録をGoogleドキュメントとしてマイドライブに保存する。

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
import transcription_service as ts
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
    if not PROCESSED_LOG.exists():
        return {}

    try:
        with open(PROCESSED_LOG, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("processed_videos.json の形式が不正なため初期化します")
            return {}
    except json.JSONDecodeError:
        logger.warning("processed_videos.json のJSONが壊れているため初期化します")
        return {}


def save_processed(processed):
    """処理済み動画IDの記録を保存する。"""
    with open(PROCESSED_LOG, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)


def make_doc_title(video_name):
    """動画ファイル名から議事録のドキュメントタイトルを生成する。"""
    stem = Path(video_name).stem
    return f"【議事録】{stem}"


def convert_to_mp3(video_path):
    """MP4をMP3に変換して書き起こし処理を軽量化する。

    Args:
        video_path: 動画ファイルのパス

    Returns:
        MP3ファイルのパス。変換失敗時はNoneを返す。
    """
    mp3_path = video_path.rsplit(".", 1)[0] + ".mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
             "-ab", "128k", "-y", mp3_path],
            check=True,
            capture_output=True,
            text=True,
        )
        video_size = os.path.getsize(video_path) / MB
        mp3_size = os.path.getsize(mp3_path) / MB
        reduced_ratio = (mp3_size / video_size * 100) if video_size > 0 else 0
        logger.info(
            f"  MP3変換完了: {video_size:.1f}MB → {mp3_size:.1f}MB "
            f"({reduced_ratio:.0f}%に削減)"
        )
        return mp3_path
    except FileNotFoundError:
        logger.warning(
            "  ffmpegが見つかりません。MP4のまま処理します。"
            "  ffmpegをインストールしてPATHに追加してください。"
        )
        return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"  MP3変換に失敗しました。MP4のまま処理します: {e.stderr}")
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
                   transcriber, has_ffmpeg, processed):
    """1件の動画を処理する（ダウンロード→変換→生成→保存）。

    Returns:
        True: 成功, False: エラー
    """
    video_name = video["name"]
    video_id = video["id"]
    tmp_path = None
    mp3_path = None

    try:
        # 一時ファイルに動画をダウンロード
        suffix = Path(video_name).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        logger.info(f"  ダウンロード中: {video_name}")
        ds.download_video(drive_svc, video_id, tmp_path)

        # MP3に変換（ffmpegが利用可能な場合）
        media_path = tmp_path
        if has_ffmpeg:
            logger.info("  MP3に変換中...")
            mp3_path = convert_to_mp3(tmp_path)
            if mp3_path:
                media_path = mp3_path
                # MP4の一時ファイルを先に削除（ディスク節約）
                try:
                    os.unlink(tmp_path)
                    tmp_path = None
                except OSError:
                    pass

        # Whisperで日本語書き起こしを実行
        logger.info("  日本語書き起こしを実行中...")
        transcribe_start = time.perf_counter()
        segments = transcriber.transcribe(media_path)
        notes = ts.render_meeting_notes(video_name, segments)
        logger.info("  書き起こし完了（%.1f秒）", time.perf_counter() - transcribe_start)

        # Googleドキュメントとして保存
        doc_title = make_doc_title(video_name)
        logger.info(f"  Googleドキュメントを作成中: {doc_title}")
        save_start = time.perf_counter()
        doc_id = ds.create_google_doc(
            drive_svc, docs_svc, doc_title, notes, target_folder_id
        )
        logger.info("  Googleドキュメント保存完了（%.1f秒）", time.perf_counter() - save_start)

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
        for path in [tmp_path, mp3_path]:
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
        logger.info("ffmpeg検出: MP4→MP3変換で書き起こし処理を軽量化します")
    else:
        logger.warning(
            "ffmpegが見つかりません。MP4のまま処理します。"
            "faster-whisperのためffmpegのインストールを推奨します。"
        )

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
    # 既存ドキュメント判定で更新された状態を早めに保存しておく
    save_processed(processed)

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

    logger.info("書き起こしモデルをロードします（初回は数分かかる場合があります）")
    transcriber = ts.JapaneseTranscriber(
        compute_type=config["whisper_compute_type"],
        device=config["whisper_device"],
    )

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
            transcriber, has_ffmpeg, processed,
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
                    "Whisperモデル障害やネットワーク障害の可能性があります。"
                )
                break

        # 次の処理まで待機（レート制限対策）
        if i < len(unprocessed) and request_interval > 0:
            logger.info(f"  次の処理まで {request_interval} 秒待機...")
            time.sleep(request_interval)

    logger.info(
        f"\n{'='*60}\n"
        f"処理完了: 成功 {success_count} 件, エラー {error_count} 件"
    )


def main():
    parser = argparse.ArgumentParser(
        description="会議動画から議事録を自動生成"
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
