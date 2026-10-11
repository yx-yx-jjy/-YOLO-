"""认证与凭据：密码哈希 + 轻量签名令牌（仅标准库）。

设计取舍（架构稿 §5 安全 / 决策 4）：
  · 密码用 **标准库 hashlib.pbkdf2_hmac('sha256', ...) + 每用户随机 salt**，
    不引入 passlib / bcrypt（本机安全策略会拦原生 DLL）。
  · 令牌用 **标准库 hmac + hashlib** 自签，不引入 JWT 库。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from .config import settings

_PBKDF2_ITERATIONS = 100_000
_HASH_PREFIX = "pbkdf2_sha256"


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_HASH_PREFIX}${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        prefix, iterations, salt_hex, digest_hex = stored.split("$")
        if prefix != _HASH_PREFIX:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(derived.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _sign(payload: str) -> str:
    return hmac.new(settings.auth_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_token(user_id: int, username: str, role: str) -> str:
    expires = int(time.time()) + settings.auth_token_ttl_seconds
    payload = f"{user_id}:{username}:{role}:{expires}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{encoded}.{_sign(encoded)}"


def verify_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(encoded), signature):
        return None
    try:
        payload = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        user_id, username, role, expires = payload.split(":")
    except (ValueError, UnicodeDecodeError):
        return None
    if int(expires) < int(time.time()):
        return None
    return {"user_id": int(user_id), "username": username, "role": role}
