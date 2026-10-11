# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import time


BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
RUN_NAME = "yolo11s-wuhan-clean-v4"
RUN_DIR = os.path.join(BASE, "runs", "violation", RUN_NAME)
CSV_PATH = os.path.join(RUN_DIR, "results.csv")
CKPT = os.path.join(RUN_DIR, "weights", "last.pt")
INITIAL = os.path.join(
    BASE, "runs", "violation", "yolo11s-wuhan-manual-v3", "weights", "best.pt"
)
DATA = os.path.join(
    PROJECT_ROOT, "data", "ebike-helmet-clean-v1", "combined-dataset-v4.yaml"
)
LOG_PATH = os.path.join(BASE, "runs", "violation", "wuhan-clean-v4.out.log")
LOCK_PATH = os.path.join(BASE, "runs", "violation", ".training-v4-watchdog.lock")
PYTHON = os.path.join(BASE, ".venv", "Scripts", "python.exe")
TRAIN = os.path.join(BASE, "training", "train.py")

TOTAL_EPOCHS = 50
RETRY_SECONDS = 30
MAX_ATTEMPTS = 80
MIN_COMMIT_HEADROOM_MB = 4096


def epochs_done() -> int:
    if not os.path.exists(CSV_PATH):
        return 0
    with open(CSV_PATH, encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return True


def acquire_lock() -> bool:
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, encoding="ascii") as handle:
                pid = int(handle.read().strip() or 0)
        except (OSError, ValueError):
            pid = 0
        if pid_alive(pid):
            print(f"Another v4 watchdog is active (PID {pid}).", flush=True)
            return False
    with open(LOCK_PATH, "w", encoding="ascii") as handle:
        handle.write(str(os.getpid()))
    return True


def commit_headroom_mb() -> float:
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullAvailPageFile / 1048576
    except Exception:
        return 999999


def log(message: str) -> None:
    line = f"[v4 watchdog {time.strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def command() -> list[str]:
    common = [
        PYTHON,
        TRAIN,
        "--data",
        DATA,
        "--batch",
        "1",
        "--imgsz",
        "960",
        "--device",
        "0",
        "--workers",
        "0",
    ]
    if os.path.exists(CKPT):
        return common + ["--resume", CKPT]
    return common + [
        "--base",
        INITIAL,
        "--epochs",
        str(TOTAL_EPOCHS),
        "--project",
        os.path.join(BASE, "runs", "violation"),
        "--name",
        RUN_NAME,
        "--exist-ok",
        "--patience",
        "10",
        "--mosaic",
        "0.2",
    ]


def main() -> int:
    for required in (PYTHON, TRAIN, DATA, INITIAL):
        if not os.path.exists(required):
            print(f"Required file does not exist: {required}", flush=True)
            return 1
    if not acquire_lock():
        return 1

    environment = dict(os.environ)
    environment.update(
        PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1"
    )
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            done = epochs_done()
            if done >= TOTAL_EPOCHS:
                log(f"Completed {done}/{TOTAL_EPOCHS} epochs.")
                return 0
            while commit_headroom_mb() < MIN_COMMIT_HEADROOM_MB:
                log("Commit-memory headroom is below 4096 MB; retrying in 60 seconds.")
                time.sleep(60)

            log(f"Attempt {attempt}: starting after {done} completed epochs.")
            with open(LOG_PATH, "ab") as handle:
                result = subprocess.run(
                    command(), cwd=BASE, env=environment, stdout=handle, stderr=subprocess.STDOUT
                )
            after = epochs_done()
            log(f"Attempt {attempt} exited with {result.returncode}; epochs {done} -> {after}.")
            if after >= TOTAL_EPOCHS:
                return 0
            if result.returncode == 0:
                log("Trainer exited normally before the ceiling, likely due to early stopping.")
                return 0
            time.sleep(RETRY_SECONDS)
        log("Maximum restart attempts reached.")
        return 1
    finally:
        try:
            os.remove(LOCK_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
