#!/usr/bin/env python3
"""Google OAuth2認証ヘルパー

ステップ1: python auth.py          → 認証URLを表示
ステップ2: python auth.py <コード>  → トークンを生成・保存
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import Flow

BASE_DIR = Path(__file__).parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

REDIRECT_URI = "http://localhost"


def _create_flow():
    """OAuth2 Flowオブジェクトを作成する。"""
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def step1_show_url():
    """認証URLを表示する。"""
    flow = _create_flow()
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\n" + "=" * 60)
    print("以下のURLをブラウザで開いてGoogleアカウントでログインしてください:")
    print(f"\n{auth_url}\n")
    print("ログイン後、ブラウザのアドレスバーに表示されるURLから")
    print("「code=」の後の文字列（&の前まで）をコピーしてください。")
    print("")
    print("例: http://localhost/?code=4/0AanRR... → 4/0AanRR... の部分")
    print("")
    print("次に以下を実行してください:")
    print(f"  python auth.py <コピーしたコード>")
    print("=" * 60)


def step2_fetch_token(code):
    """認証コードからトークンを取得して保存する。"""
    flow = _create_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n認証成功! トークンを保存しました: {TOKEN_PATH}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        step1_show_url()
    else:
        step2_fetch_token(sys.argv[1])
