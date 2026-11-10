"""Local single-channel OAuth connection with one-use state, PKCE and server-side secrets."""

import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.infrastructure.local_lock import exclusive_lock

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


class ConnectionFailure(ValueError):
    pass


def directory(settings):
    return settings.artifact_dir.resolve().parent / "settings"


def read(name, settings):
    path = directory(settings) / name
    return json.loads(path.read_text()) if path.exists() else {}


def write(name, value, settings):
    root = directory(settings)
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / (secrets.token_hex(12) + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as target:
            json.dump(value, target)
        temporary.replace(root / name)
    finally:
        temporary.unlink(missing_ok=True)


def credentials(settings=None):
    settings = settings or Settings()
    saved = read("youtube.json", settings)
    return {
        "client_id": saved.get("client_id", "") if saved else settings.youtube_client_id,
        "client_secret": saved.get("client_secret", "")
        if saved
        else settings.youtube_client_secret.get_secret_value(),
        "refresh_token": saved.get("refresh_token", "")
        if saved
        else settings.youtube_refresh_token.get_secret_value(),
        "channel": saved.get("channel"),
    }


def configure(client_id, client_secret, settings):
    root = directory(settings)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root / ".youtube.lock"):
        old = credentials(settings)
        secret = client_secret or (old["client_secret"] if client_id == old["client_id"] else "")
        if not client_id or not secret:
            raise ConnectionFailure("Cần Google OAuth client ID và client secret.")
        if client_id != old["client_id"] or secret != old["client_secret"]:
            write("youtube.json", {"client_id": client_id, "client_secret": secret}, settings)
            (root / "youtube-state.json").unlink(missing_ok=True)


def status(settings=None):
    data = credentials(settings)
    return {
        "configured": bool(data["client_id"] and data["client_secret"]),
        "connected": bool(data["client_id"] and data["client_secret"] and data["refresh_token"]),
        "channel": data.get("channel"),
        "platform": "youtube",
    }


def begin(settings):
    data = credentials(settings)
    if not data["client_id"] or not data["client_secret"]:
        raise ConnectionFailure("Lưu Google OAuth client trước khi kết nối.")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    root = directory(settings)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root / ".youtube.lock"):
        write(
            "youtube-state.json",
            {
                "digest": hashlib.sha256(state.encode()).hexdigest(),
                "verifier": verifier,
                "expires": time.time() + 600,
                "client_id": data["client_id"],
            },
            settings,
        )
    return {
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(
            {
                "client_id": data["client_id"],
                "redirect_uri": settings.youtube_redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        ),
        "redirect_uri": settings.youtube_redirect_uri,
    }


def access_token(client, settings=None):
    data = credentials(settings)
    if not all(data[k] for k in ("client_id", "client_secret", "refresh_token")):
        raise ConnectionFailure("Chưa kết nối OAuth YouTube.")
    response = client.post(
        "https://oauth2.googleapis.com/token",
        data={
            **{k: data[k] for k in ("client_id", "client_secret", "refresh_token")},
            "grant_type": "refresh_token",
        },
    )
    if response.status_code != 200:
        raise ConnectionFailure(
            f"OAuth YouTube trả HTTP {response.status_code}; kết nối lại tài khoản."
        )
    return response.json()["access_token"]


def channel(client, token):
    response = client.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": "Bearer " + token},
    )
    if response.status_code != 200 or not response.json().get("items"):
        raise ConnectionFailure("Chưa xác minh được kênh YouTube; kiểm tra API và quyền OAuth.")
    item = response.json()["items"][0]
    return {"id": item["id"], "title": item["snippet"]["title"], "verified_at": time.time()}


def complete(code, state, settings):
    root = directory(settings)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root / ".youtube.lock"):
        pending = read("youtube-state.json", settings)
        data = credentials(settings)
        if (
            not state
            or not pending
            or pending.get("expires", 0) < time.time()
            or not secrets.compare_digest(
                pending.get("digest", ""), hashlib.sha256(state.encode()).hexdigest()
            )
            or pending.get("client_id") != data["client_id"]
        ):
            raise ConnectionFailure("Phiên kết nối hết hạn hoặc không hợp lệ. Bắt đầu lại từ tool.")
        (root / "youtube-state.json").unlink()
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": data["client_id"],
                    "client_secret": data["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.youtube_redirect_uri,
                    "code_verifier": pending["verifier"],
                },
            )
            if response.status_code != 200 or not response.json().get("refresh_token"):
                raise ConnectionFailure(
                    "Google chưa cấp refresh token. Kết nối lại và chấp thuận quyền offline."
                )
            token = response.json()
            verified = channel(client, token["access_token"])
        write(
            "youtube.json",
            {**data, "refresh_token": token["refresh_token"], "channel": verified},
            settings,
        )
        return verified


def verify(settings):
    root = directory(settings)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root / ".youtube.lock"):
        data = credentials(settings)
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            verified = channel(client, access_token(client, settings))
        write("youtube.json", {**data, "channel": verified}, settings)
    return status(settings)
