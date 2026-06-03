import json
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_JSON,
    GOOGLE_TOKEN_PATH,
)


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _write_secret_file(path, content):
    if not content:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _load_token_scopes(token_path):
    if not os.path.exists(token_path):
        return []

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            token_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    scopes = token_data.get("scopes")
    if isinstance(scopes, list):
        return [scope.strip() for scope in scopes if scope and scope.strip()]

    scope_value = token_data.get("scope")
    if isinstance(scope_value, str):
        return [scope.strip() for scope in scope_value.split() if scope.strip()]

    return []


def _ensure_required_scopes(token_path):
    token_scopes = _load_token_scopes(token_path)
    if not token_scopes:
        return

    missing_scopes = [scope for scope in SCOPES if scope not in token_scopes]
    if not missing_scopes:
        return

    raise RuntimeError(
        "Google OAuth token scopes do not match the scopes required by this app.\n"
        f"Required scopes: {SCOPES}\n"
        f"Token scopes: {token_scopes}\n"
        "Recreate token.json locally with `python refresh_google_token.py` and "
        "update the GitHub secret `GOOGLE_TOKEN_JSON` with the new file contents."
    )


def _ensure_credentials_files():
    _write_secret_file(GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON)
    _write_secret_file(GOOGLE_TOKEN_PATH, GOOGLE_TOKEN_JSON)

    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Google credentials file not found: {GOOGLE_CREDENTIALS_PATH}\n"
            "Set GOOGLE_CREDENTIALS_PATH or GOOGLE_CREDENTIALS_JSON first."
        )


def _build_invalid_scope_message(token_path):
    token_scopes = _load_token_scopes(token_path)
    return (
        "Google OAuth refresh failed because the stored refresh token was issued "
        "for different scopes.\n"
        f"Required scopes: {SCOPES}\n"
        f"Token scopes: {token_scopes or 'unknown'}\n"
        "Run `python refresh_google_token.py` locally, then update the GitHub "
        "secret `GOOGLE_TOKEN_JSON` with the newly generated token.json."
    )


def get_google_creds():
    _ensure_credentials_files()
    _ensure_required_scopes(GOOGLE_TOKEN_PATH)

    creds = None
    if os.path.exists(GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                if "invalid_scope" in str(exc):
                    raise RuntimeError(_build_invalid_scope_message(GOOGLE_TOKEN_PATH)) from exc
                raise
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def refresh_google_token():
    _ensure_credentials_files()

    flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return GOOGLE_TOKEN_PATH
