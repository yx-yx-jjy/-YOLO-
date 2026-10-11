"""全局数据库可用性状态。

作用：DB 不可用时**后端仍要能启动**（实时流/推理接口继续可用），
台账类读接口据此外返回 503 + 结构化 detail，而不是 200 + 空数组（消灭静默失败）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DbState:
    ready: bool = False
    reason: str | None = None
    message: str | None = None


# 进程级单例：由 engine.init_db() 在启动时写入，由 /api/health 与请求依赖读取。
db_state = DbState()


class DbUnavailableError(Exception):
    """数据库不可用。由 main.py 的异常处理统一转成 HTTP 503 + 结构化 detail。"""

    code = "DB_UNAVAILABLE"

    def __init__(self, message: str, hint: str | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code:
            self.code = code

    def to_detail(self) -> dict:
        detail: dict = {"code": self.code, "message": self.message}
        if self.hint:
            detail["hint"] = self.hint
        return detail
