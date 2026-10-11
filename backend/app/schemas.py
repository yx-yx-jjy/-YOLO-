"""请求体 Pydantic 模型（仅覆盖 POST/PATCH 的 body，query 用 FastAPI Query 校验）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewPayload(BaseModel):
    action: str = Field(..., description="approve | reject | revoke")
    reviewer: str = Field(..., description="复核人署名")
    badge: str | None = None
    remark: str | None = None
    category_override: str | None = None


class DispositionPayload(BaseModel):
    action: str = Field(..., description="notify | dispose | archive")
    operator: str = Field(..., description="承办人")
    method: str | None = None
    remark: str | None = None


class BatchReviewPayload(BaseModel):
    action: str = Field(..., description="approve | reject | notify")
    ids: list[str]
    reviewer: str
    badge: str | None = None
    remark: str | None = None


class LoginPayload(BaseModel):
    username: str
    password: str


class CreateUserPayload(BaseModel):
    username: str
    real_name: str
    badge_number: str
    role: str = "officer"
    department: str = ""
    password: str | None = None


class StatusPayload(BaseModel):
    status: str | None = None
    action: str | None = None
