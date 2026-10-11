"""FastAPI 依赖：写接口的登录校验（签名令牌）。

设计取舍（刻意的，不是漏做）：
  · **只给"会改动数据"的 6 个接口挂鉴权**；只读接口（台账/统计/用户读/日志/卡口）与
    实时链路（`/api/camera/*`、`/api/detections`、`/api/health`）**不校验**。
  · 原因：答辩要现场演示实时视频流，鉴权一旦把 `/api/camera/stream` 打断就是演示事故。
  · 令牌复用 `security.create_token/verify_token`，有效期走 `auth_token_ttl_seconds`，
    不另造一套。

错误响应沿用项目结构化风格（与 `DB_UNAVAILABLE` 一致）：
    {"detail": {"code": "UNAUTHORIZED", "message": "...", "hint": "..."}}
  前端可按 `detail.code == "UNAUTHORIZED"` 稳定区分"该重新登录"与其它错误。
"""
from __future__ import annotations

from fastapi import Request

from .security import verify_token
from .services.errors import UnauthorizedError

_UNAUTHORIZED_HINT = "请先登录，或检查令牌是否过期"


def require_auth(request: Request) -> dict:
    """校验 `Authorization: Bearer <token>`。

    缺失 / 格式不对 / 签名不通过 / 过期 → 401（统一 code=UNAUTHORIZED）。
    校验通过返回令牌声明（user_id / username / role），当前不用于推导操作人。
    """
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("未提供有效登录凭证", hint=_UNAUTHORIZED_HINT)
    claims = verify_token(token.strip())
    if claims is None:
        raise UnauthorizedError("未提供有效登录凭证", hint=_UNAUTHORIZED_HINT)
    return claims
