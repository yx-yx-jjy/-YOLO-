from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from .camera import camera_manager
from .config import settings
from .db import engine as db_engine
from .db.state import DbUnavailableError
from .db.writer import write_pipeline
from .inference import engine
from .jobs import jobs
from .routers import admin as admin_router
from .routers import auth as auth_router
from .routers import citizen as citizen_router
from .routers import ledger as ledger_router
from .routers import stats as stats_router
from .services.errors import ServiceError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("traffic.main")


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.artifact_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Non-motor Vehicle Violation Detection API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=settings.artifact_dir), name="artifacts")


@app.on_event("startup")
def on_startup() -> None:
    # DB 不可用时后端仍要能启动（实时流 / 推理接口继续可用），故 init_db 不抛穿
    db_engine.init_db()
    write_pipeline.start()


# ---------------------------------------------------------------------------
# 统一错误处理：ServiceError → 对应状态码；DB 不可用 → 503 + 结构化 detail
# ---------------------------------------------------------------------------
@app.exception_handler(ServiceError)
async def _service_error_handler(_request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.to_detail()})


@app.exception_handler(DbUnavailableError)
async def _db_unavailable_handler(_request, exc: DbUnavailableError):
    return JSONResponse(status_code=503, content={"detail": exc.to_detail()})


@app.exception_handler(RequestValidationError)
async def _request_validation_handler(_request, exc: RequestValidationError):
    """FastAPI 默认 422 是 {"detail": [...]} 数组；归一成项目结构化 envelope，状态码仍 422。
    前端靠 code=VALIDATION_ERROR 给用户可读提示。"""
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(part) for part in first.get("loc", []))
        message = f"请求参数校验失败：{loc} — {first.get('msg', '')}".strip()
    else:
        message = "请求参数校验失败"
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "hint": "请检查请求参数的类型与取值范围（如 page>=1、page_size 在 1-100 之间）",
            }
        },
    )


@app.middleware("http")
async def _db_error_middleware(request, call_next):
    """兜底异常映射（原则：**业务违规 ≠ 数据库不可用**）：

      · IntegrityError    —— 业务/数据约束不满足（状态机顺序、唯一性、取值范围）→ 409，**不是** 503；
      · OperationalError  —— 连接/锁/磁盘等运行级故障 → 503；
      · 其它 DatabaseError —— 文件损坏（如 "file is not a database"）仍属"库不可用"范畴 → 503，
                              保住"库不可用 → 503、绝不 200 + 空数组"的红线。

    任何分支都**不把原始异常串透传给客户端**：返回稳定的 code + 面向用户的 message，
    原始栈只写后端日志（exc_info=True）。"""
    try:
        return await call_next(request)
    except IntegrityError as exc:
        logger.error("数据完整性冲突（约束不满足）：%s", exc, exc_info=True)
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "CONSTRAINT_VIOLATION",
                    "message": "操作与数据约束冲突，请检查请求内容或该记录当前状态",
                    "hint": "该操作不满足业务/数据约束（状态机顺序、唯一性或取值范围）",
                }
            },
        )
    except (OperationalError, DatabaseError) as exc:
        logger.error("数据库不可用（连接/文件级）：%s", exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "DB_UNAVAILABLE",
                    "message": "台账数据库暂时不可用",
                    "hint": "请检查 backend/storage/traffic.db 是否被其它程序占用、文件是否损坏，或目录写权限",
                }
            },
        )


# ---------------------------------------------------------------------------
# 新增路由
# ---------------------------------------------------------------------------
app.include_router(ledger_router.router)
app.include_router(stats_router.router)
app.include_router(admin_router.router)
app.include_router(auth_router.router)
# 公众服务端：按登录市民的绑定车牌过滤，与执法后台台账隔离
app.include_router(citizen_router.router)


# ---------------------------------------------------------------------------
# 原有接口（路径 / 方法 / 响应结构一律不动）
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    # 旧字段 service / model 保持不动；新增 db / writer（前端旧代码不受影响）
    return {
        "service": "ok",
        "model": engine.status(),
        "db": db_engine.health(),
        "writer": write_pipeline.stats(),
    }


@app.get("/api/camera/stream")
def camera_stream(
    cam_id: str = "CAM-03",
    show_helmet: bool = True,
):
    return StreamingResponse(
        camera_manager.generate_mjpeg(cam_id, show_helmet),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/camera/status")
def camera_status(cam_id: str = "CAM-03") -> dict:
    return camera_manager.get_status(cam_id)


@app.post("/api/camera/snapshot")
def camera_snapshot(cam_id: str = "CAM-03") -> dict:
    return camera_manager.take_snapshot(cam_id)


@app.get("/api/camera/violations")
def camera_violations() -> list[dict]:
    # 内部继续读 _recent_violations deque（契约不变），不改成读库
    return camera_manager.get_recent_violations()


@app.post("/api/camera/close")
def close_camera() -> dict:
    camera_manager.release_all_cameras()
    return {"status": "ok", "message": "已关闭并释放所有摄像头设备"}


@app.on_event("shutdown")
def on_shutdown():
    # 关闭顺序：先停生产者（不再入队）→ 再停持久化线程排空在途任务
    camera_manager.release_all_cameras()
    leftover = write_pipeline.stop(timeout=5.0)
    if leftover:
        logger.warning("关闭时仍有 %s 个持久化任务未写完", leftover)


@app.post("/api/detections", status_code=202)
async def create_detection(file: UploadFile = File(...)) -> dict:
    original_name = file.filename or "upload"
    extension = Path(original_name).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        media_type = "image"
    elif extension in VIDEO_EXTENSIONS:
        media_type = "video"
    else:
        raise HTTPException(status_code=415, detail="仅支持 JPG、PNG、WEBP、MP4、AVI、MOV、MKV")

    model_status = engine.status()
    if not model_status["ready"]:
        raise HTTPException(status_code=503, detail=model_status)

    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(original_name).stem)[:60] or "upload"
    target = settings.upload_dir / f"{uuid.uuid4().hex}_{safe_stem}{extension}"
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="文件超过上传大小限制")
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return jobs.create(target, media_type, original_name)


@app.get("/api/detections/{job_id}")
def get_detection(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="检测任务不存在或服务已重启")
    return job
