"""领域异常（services 层抛出，main.py 的全局处理器映射为 HTTP 状态码）。"""
from __future__ import annotations


class ServiceError(Exception):
    status_code = 400
    code = "BAD_REQUEST"
    default_hint: str | None = None

    def __init__(self, message: str, code: str | None = None, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        # hint 仅在显式提供（或子类设置 default_hint）时输出，避免改动既有错误的 detail 结构
        self.hint = hint if hint is not None else self.default_hint

    def to_detail(self) -> dict:
        detail = {"code": self.code, "message": self.message}
        if self.hint:
            detail["hint"] = self.hint
        return detail


class ValidationError(ServiceError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotFoundError(ServiceError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(ServiceError):
    """状态机冲突（如对 pending 记录再 revoke）。"""
    status_code = 409
    code = "STATE_CONFLICT"


class UnauthorizedError(ServiceError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(ServiceError):
    status_code = 403
    code = "FORBIDDEN"
