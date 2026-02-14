"""Google Drive API操作モジュール

共有ドライブからの動画取得、マイドライブへのGoogleドキュメント作成を担当。
"""

import logging
import os
import sys
from pathlib import Path

import google_auth_httplib2
import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaInMemoryUpload

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

VIDEO_MIME_TYPES = [
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "video/x-ms-wmv",
    "video/mpeg",
]

BASE_DIR = Path(__file__).parent
TOKEN_PATH = BASE_DIR / "token.json"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"


def authenticate():
    """OAuth2認証を行い、credentialsを返す。

    初回はURLを表示し、認証コードを入力してもらう方式。
    以降はtoken.jsonで自動認証。
    """
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json が見つかりません: {CREDENTIALS_PATH}\n"
                    "setup_guide.md を参照してOAuth2クライアントIDを設定してください。"
                )
            # デスクトップ環境（Windows / Linux GUI）ではローカルサーバー方式
            is_desktop = (
                sys.platform == "win32"
                or sys.platform == "darwin"
                or os.environ.get("DISPLAY")
                or os.environ.get("BROWSER")
            )
            if is_desktop:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                creds = flow.run_console()
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def get_services():
    """Google Drive APIとDocs APIのサービスオブジェクトを返す。"""
    creds = authenticate()
    http = google_auth_httplib2.AuthorizedHttp(
        creds,
        http=httplib2.Http(disable_ssl_certificate_validation=True),
    )
    drive = build("drive", "v3", http=http)
    docs = build("docs", "v1", http=http)
    return drive, docs


def find_shared_drive(drive_service, drive_name):
    """共有ドライブをドライブ名で検索し、IDを返す。"""
    results = (
        drive_service.drives()
        .list(q=f"name = '{drive_name}'", fields="drives(id, name)")
        .execute()
    )
    drives = results.get("drives", [])
    if not drives:
        raise ValueError(f"共有ドライブ '{drive_name}' が見つかりません")
    logger.info(f"共有ドライブ発見: {drives[0]['name']} (ID: {drives[0]['id']})")
    return drives[0]["id"]


def find_folder_in_shared_drive(drive_service, folder_name, drive_id):
    """共有ドライブ内のフォルダを名前で検索し、IDを返す。"""
    q = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = (
        drive_service.files()
        .list(
            q=q,
            fields="files(id, name)",
            corpora="drive",
            driveId=drive_id,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = results.get("files", [])
    if not files:
        raise ValueError(
            f"フォルダ '{folder_name}' が共有ドライブ内に見つかりません"
        )
    logger.info(f"ソースフォルダ発見: {files[0]['name']} (ID: {files[0]['id']})")
    return files[0]["id"]


def find_folder_in_shared_items(drive_service, folder_name):
    """共有アイテム内のフォルダを名前で検索し、IDを返す。"""
    q = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false "
        f"and sharedWithMe = true"
    )
    results = (
        drive_service.files()
        .list(
            q=q,
            fields="files(id, name)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = results.get("files", [])
    if not files:
        raise ValueError(
            f"フォルダ '{folder_name}' が共有アイテム内に見つかりません"
        )
    logger.info(f"ソースフォルダ発見（共有アイテム）: {files[0]['name']} (ID: {files[0]['id']})")
    return files[0]["id"]


def find_folder_in_my_drive(drive_service, folder_name, parent_id=None):
    """マイドライブ内のフォルダを名前で検索し、IDを返す。なければ作成。

    Args:
        drive_service: Google Drive APIサービス
        folder_name: フォルダ名
        parent_id: 親フォルダのID（指定時はその中から検索）
    """
    q = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    if parent_id:
        q += f" and '{parent_id}' in parents"
    else:
        q += " and 'me' in owners"

    results = (
        drive_service.files()
        .list(q=q, fields="files(id, name)", spaces="drive")
        .execute()
    )
    files = results.get("files", [])
    if files:
        logger.info(
            f"フォルダ発見: {files[0]['name']} (ID: {files[0]['id']})"
        )
        return files[0]["id"]

    # フォルダが存在しない場合は作成
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]
    folder = (
        drive_service.files()
        .create(body=file_metadata, fields="id, name")
        .execute()
    )
    logger.info(
        f"フォルダを作成: {folder['name']} (ID: {folder['id']})"
    )
    return folder["id"]


def _paginated_file_list(drive_service, q, fields, **extra_kwargs):
    """ページネーション付きでファイル一覧を取得する。"""
    all_files = []
    page_token = None
    while True:
        kwargs = {"q": q, "fields": fields, "pageSize": 100, **extra_kwargs}
        if page_token:
            kwargs["pageToken"] = page_token
        results = drive_service.files().list(**kwargs).execute()
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_files


def list_videos_in_folder(drive_service, folder_id, drive_id=None):
    """指定フォルダ内の全動画ファイルをリストアップ。

    Args:
        drive_service: Google Drive APIサービス
        folder_id: フォルダID
        drive_id: 共有ドライブID（共有アイテムの場合はNone）
    """
    mime_query = " or ".join(
        [f"mimeType = '{mt}'" for mt in VIDEO_MIME_TYPES]
    )
    q = f"'{folder_id}' in parents and ({mime_query}) and trashed = false"

    extra_kwargs = {
        "orderBy": "createdTime",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
    }
    if drive_id:
        extra_kwargs["corpora"] = "drive"
        extra_kwargs["driveId"] = drive_id

    all_files = _paginated_file_list(
        drive_service, q,
        "nextPageToken, files(id, name, mimeType, createdTime, size)",
        **extra_kwargs,
    )
    logger.info(f"動画ファイル {len(all_files)} 件を発見")
    return all_files


def list_docs_in_folder(drive_service, folder_id):
    """指定フォルダ内のGoogleドキュメントの名前一覧を返す（重複チェック用）。"""
    q = (
        f"'{folder_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.document' "
        f"and trashed = false"
    )
    all_docs = _paginated_file_list(
        drive_service, q, "nextPageToken, files(id, name)",
    )
    return {doc["name"] for doc in all_docs}


def download_video(drive_service, file_id, dest_path):
    """動画ファイルをGoogle Driveからダウンロード。"""
    request = drive_service.files().get_media(
        fileId=file_id, supportsAllDrives=True
    )
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.info(f"  ダウンロード進捗: {int(status.progress() * 100)}%")
    logger.info(f"  ダウンロード完了: {dest_path}")


def create_google_doc(drive_service, docs_service, title, content, folder_id):
    """Googleドキュメントを作成し、指定フォルダに配置。"""
    # ドキュメントを作成
    doc = docs_service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # コンテンツを挿入
    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": content,
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()

    # 対象フォルダに移動（rootから移動）
    drive_service.files().update(
        fileId=doc_id,
        addParents=folder_id,
        removeParents="root",
        fields="id, parents",
    ).execute()

    logger.info(f"  Googleドキュメント作成完了: {title} (ID: {doc_id})")
    return doc_id
