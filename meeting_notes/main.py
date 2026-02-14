#!/usr/bin/env python3
"""会議動画 → 議事録 自動生成スクリプト

Google Drive共有ドライブの動画をGemini APIで処理し、
議事録をGoogleドキュメントとしてマイドライブに保存する。

使い方:
    python main.py          # 通常実行
    python main.py --dry-run  # 実行せずに対象動画を確認
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import drive_service as ds
import gemini_service as gs

BASE_DIR = Path(__file__).parent
PROCESSED_LOG = BASE_DIR / "processed_videos.json"

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
    """動画ファイル名から議事録のドキュメントタイトルを生成する。"""
    stem = Path(video_name).stem
    return f"【議事録】{stem}"


def run(dry_run=False):
    """メイン処理を実行する。"""
    load_dotenv(BASE_DIR / ".env")

    # 環境変数の読み込み
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
        sys.exit(1)

    shared_drive_name = os.getenv("SHARED_DRIVE_NAME", "Jupiter folder")
    source_folder_name = os.getenv("SOURCE_FOLDER_NAME", "02_録画データ_all")
    target_parent_folder_name = os.getenv("TARGET_PARENT_FOLDER_NAME", "チーム石川")
    target_folder_name = os.getenv("TARGET_FOLDER_NAME", "議事録")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Gemini APIの設定
    gs.configure(gemini_api_key)

    # Google Drive APIの認証
    logger.info("Google Drive APIに接続中...")
    drive_svc, docs_svc = ds.get_services()

    # ソースフォルダを特定（共有ドライブ or 共有アイテム）
    shared_drive_id = None
    if shared_drive_name:
        try:
            logger.info(f"共有ドライブ '{shared_drive_name}' を検索中...")
            shared_drive_id = ds.find_shared_drive(drive_svc, shared_drive_name)
            logger.info(f"ソースフォルダ '{source_folder_name}' を検索中...")
            source_folder_id = ds.find_folder_in_shared_drive(
                drive_svc, source_folder_name, shared_drive_id
            )
        except ValueError:
            logger.info("共有ドライブが見つかりません。共有アイテムから検索します...")
            shared_drive_id = None

    if not shared_drive_id:
        logger.info(f"共有アイテムからフォルダ '{source_folder_name}' を検索中...")
        source_folder_id = ds.find_folder_in_shared_items(
            drive_svc, source_folder_name
        )

    logger.info(f"出力フォルダ '{target_parent_folder_name}/{target_folder_name}' を検索中...")
    parent_folder_id = ds.find_folder_in_my_drive(drive_svc, target_parent_folder_name)
    target_folder_id = ds.find_folder_in_my_drive(
        drive_svc, target_folder_name, parent_id=parent_folder_id
    )

    # 動画ファイルの一覧を取得
    logger.info("動画ファイルを検索中...")
    videos = ds.list_videos_in_folder(drive_svc, source_folder_id, drive_id=shared_drive_id)

    if not videos:
        logger.info("処理対象の動画ファイルが見つかりませんでした。")
        return

    # 処理済み動画の確認（ローカル記録 + Drive上の既存ドキュメント名）
    processed = load_processed()
    existing_docs = ds.list_docs_in_folder(drive_svc, target_folder_id)

    # 未処理の動画をフィルタリング
    unprocessed = []
    for video in videos:
        doc_title = make_doc_title(video["name"])
        if video["id"] in processed:
            logger.info(f"スキップ（処理済み）: {video['name']}")
            continue
        if doc_title in existing_docs:
            logger.info(f"スキップ（ドキュメント存在）: {video['name']}")
            # ローカル記録にも追加
            processed[video["id"]] = {
                "name": video["name"],
                "doc_title": doc_title,
                "processed_at": datetime.now().isoformat(),
                "status": "already_exists",
            }
            continue
        unprocessed.append(video)

    if not unprocessed:
        logger.info("新しい動画はありません。全て処理済みです。")
        save_processed(processed)
        return

    logger.info(f"未処理の動画: {len(unprocessed)} 件")

    if dry_run:
        logger.info("=== ドライラン: 以下の動画が処理対象です ===")
        for v in unprocessed:
            size_mb = int(v.get("size", 0)) / (1024 * 1024)
            logger.info(f"  - {v['name']} ({size_mb:.1f} MB)")
        return

    # 各動画を処理
    success_count = 0
    error_count = 0

    for i, video in enumerate(unprocessed, 1):
        video_name = video["name"]
        video_id = video["id"]
        size_mb = int(video.get("size", 0)) / (1024 * 1024)
        logger.info(
            f"\n{'='*60}\n"
            f"[{i}/{len(unprocessed)}] 処理中: {video_name} ({size_mb:.1f} MB)"
        )

        try:
            # 一時ファイルに動画をダウンロード
            suffix = Path(video_name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp_path = tmp.name

            logger.info(f"  ダウンロード中: {video_name}")
            ds.download_video(drive_svc, video_id, tmp_path)

            # Gemini APIで議事録を生成
            logger.info("  議事録を生成中...")
            notes = gs.generate_meeting_notes(tmp_path, model_name=gemini_model)

            # Googleドキュメントとして保存
            doc_title = make_doc_title(video_name)
            logger.info(f"  Googleドキュメントを作成中: {doc_title}")
            doc_id = ds.create_google_doc(
                drive_svc, docs_svc, doc_title, notes, target_folder_id
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
            success_count += 1
            logger.info(f"  完了: {doc_title}")

        except Exception as e:
            error_count += 1
            logger.error(f"  エラー: {video_name} の処理に失敗しました: {e}")
            processed[video_id] = {
                "name": video_name,
                "processed_at": datetime.now().isoformat(),
                "status": f"error: {str(e)}",
            }
            save_processed(processed)

        finally:
            # 一時ファイルを削除
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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
