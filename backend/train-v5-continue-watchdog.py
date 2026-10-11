# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
from pathlib import Path


BASE = Path(__file__).resolve().parent
os.environ.update(
    YOLO_RUN_NAME="yolo11s-helmet-voc-v5-continue",
    YOLO_INITIAL=str(
        BASE
        / "runs"
        / "violation"
        / "yolo11s-helmet-voc-v5-pilot"
        / "weights"
        / "best.pt"
    ),
    YOLO_LOG_NAME="helmet-voc-v5-continue.out.log",
    YOLO_LOCK_NAME=".training-v5-continue-watchdog.lock",
    YOLO_TOTAL_EPOCHS="10",
    YOLO_PATIENCE="5",
    YOLO_MOSAIC="0.0",
    YOLO_LR0="0.01",
    YOLO_LRF="0.01",
    YOLO_WARMUP_EPOCHS="3.0",
    YOLO_CLOSE_MOSAIC="0",
)
runpy.run_path(str(BASE / "train-v5-pilot-watchdog.py"), run_name="__main__")
