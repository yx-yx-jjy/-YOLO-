"""图像落盘工具（从 camera.py 抽出，供持久化线程复用，避免循环 import）。"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def safe_imwrite(filepath: Path | str, img: np.ndarray, quality: int = 90) -> bool:
    try:
        is_ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if is_ok:
            buf.tofile(str(filepath))
            return True
    except Exception:  # noqa: BLE001 - 落盘失败由调用方决定降级
        pass
    return False
