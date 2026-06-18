from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent common directory to path
COMMON_DIR = Path(__file__).resolve().parents[2] / "common"
sys.path.insert(0, str(COMMON_DIR))

from feishu.http import post_json

ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = ROOT / "runtime" / "oauth" / "feishu_user_token.json"
FEISHU_ENDPOINT = os.environ.get("FEISHU_ENDPOINT", "https://open.feishu.cn").rstrip("/")


def exchange_code(app_id: str, app_secret: str, code: str) -> dict:
    return post_json(
        f"{FEISHU_ENDPOINT}/open-apis/authen/v1/access_token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "app_id": app_id,
            "app_secret": app_secret,
        },
    )


def refresh_token(app_id: str, app_secret: str, refresh_token_value: str) -> dict:
    return post_json(
        f"{FEISHU_ENDPOINT}/open-apis/authen/v1/refresh_access_token",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
            "app_id": app_id,
            "app_secret": app_secret,
        },
    )


def save_token_file(data: dict) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_saved_refresh_token() -> str:
    if not TOKENS_PATH.exists():
        return ""
    payload = json.loads(TOKENS_PATH.read_text(encoding="utf-8") or "{}")
    return str(payload.get("refresh_token") or "").strip()


def sanitize_output(data: dict) -> dict:
    return {
        "ok": True,
        "token_type": data.get("token_type"),
        "expires_in": data.get("expires_in"),
        "has_access_token": bool(data.get("access_token")),
        "has_refresh_token": bool(data.get("refresh_token")),
        "scope": data.get("scope"),
        "saved_to": str(TOKENS_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Get or refresh Feishu user_access_token")
    parser.add_argument("--code", help="OAuth authorization code")
    parser.add_argument("--refresh-token", help="Refresh token; if omitted, tries saved token file")
    args = parser.parse_args()

    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        print(json.dumps({
            "ok": False,
            "error": "missing FEISHU_APP_ID or FEISHU_APP_SECRET",
        }, ensure_ascii=False, indent=2))
        return 1

    try:
        if args.code:
            resp = exchange_code(app_id, app_secret, args.code)
            data = resp.get("data", {}) if isinstance(resp, dict) else {}
            save_token_file(data)
            print(json.dumps(sanitize_output(data), ensure_ascii=False, indent=2))
            return 0

        refresh_value = (args.refresh_token or "").strip() or load_saved_refresh_token()
        if not refresh_value:
            print(json.dumps({
                "ok": False,
                "error": "missing auth code and no refresh_token available",
                "hint": "Run once with --code <authorization_code> first, then refresh can reuse saved token file.",
            }, ensure_ascii=False, indent=2))
            return 2

        resp = refresh_token(app_id, app_secret, refresh_value)
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        save_token_file(data)
        print(json.dumps(sanitize_output(data), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "saved_to": str(TOKENS_PATH),
        }, ensure_ascii=False, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
