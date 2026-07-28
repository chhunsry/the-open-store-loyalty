import os
import secrets
import time

import bcrypt
from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.database import connect

COOKIE_NAME = "openstore_admin"
EPHEMERAL_SECRET = secrets.token_urlsafe(48)


def serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("APP_SECRET")
    if not secret or len(secret) < 32:
        secret = EPHEMERAL_SECRET
    return URLSafeTimedSerializer(secret, salt="openstore-admin-v1")


def hash_password(password: str) -> bytes:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))


def verify_password(password: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed)
    except (ValueError, TypeError):
        return False


def ensure_default_admin() -> None:
    username = os.getenv("DEFAULT_ADMIN_USERNAME", "").strip()
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    if not username or not password:
        return
    with connect() as db:
        exists = db.execute(
            "SELECT 1 FROM admins WHERE username = ?", (username,)
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )


def authenticate(username: str, password: str):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM admins WHERE username = ?", (username.strip(),)
        ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "username": row["username"]}
    return None


def make_session(admin: dict) -> str:
    return serializer().dumps(
        {"id": admin["id"], "username": admin["username"], "nonce": secrets.token_hex(8)}
    )


def current_admin(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        hours = int(os.getenv("SESSION_HOURS", "12"))
        data = serializer().loads(token, max_age=hours * 3600)
        return {"id": int(data["id"]), "username": str(data["username"])}
    except (BadSignature, KeyError, ValueError):
        return None


def csrf_token(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME, "public")
    return serializer().dumps({"session": token[-32:]})


def valid_csrf(request: Request, token: str) -> bool:
    try:
        data = serializer().loads(token, max_age=24 * 3600)
        session = request.cookies.get(COOKIE_NAME, "public")
        return secrets.compare_digest(data["session"], session[-32:])
    except (BadSignature, KeyError, TypeError):
        return False
