"""Live console monitor for the currently running YOLO training job."""

from __future__ import annotations

import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = PROJECT_ROOT / "backend" / "runs" / "violation" / "yolo11s-wuhan-manual-v3"
RESULTS_FILE = RUN_DIR / "results.csv"
TOTAL_EPOCHS = 100
REFRESH_SECONDS = 3


def read_rows() -> list[dict[str, str]]:
    if not RESULTS_FILE.exists():
        return []
    with RESULTS_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def training_processes() -> list[tuple[int, str]]:
    try:
        import psutil
    except ImportError:
        if sys.platform != "win32":
            return []
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -eq 'python.exe' -and "
            "$_.CommandLine -like '*train.py*' -and "
            "$_.CommandLine -like '*yolo11s-wuhan-manual-v3*' } | "
            "Select-Object -ExpandProperty ProcessId"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return []
        return [
            (int(pid), "python")
            for pid in result.stdout.splitlines()
            if pid.strip().isdigit()
        ]

    matches: list[tuple[int, str]] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or [])
            if "train.py" in command and "yolo11s-wuhan-manual-v3" in command:
                matches.append((process.info["pid"], process.info.get("name") or "python"))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return matches


def gpu_status() -> str:
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "GPU status unavailable"
    return result.stdout.strip()


def metric(row: dict[str, str], name: str) -> str:
    try:
        return f"{float(row[name]):.4f}"
    except (KeyError, TypeError, ValueError):
        return "-"


def render(rows: list[dict[str, str]]) -> None:
    processes = training_processes()
    status = "正在训练" if processes else "已完成或已停止"
    pids = ", ".join(str(pid) for pid, _ in processes) or "-"

    print("\n" + "=" * 72, flush=True)
    print(f"YOLO 头盔检测模型 - 实时训练进度    {datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)
    print(f"训练状态：{status}    进程：{pids}", flush=True)
    print(f"GPU（使用率、已用显存、总显存、温度）：{gpu_status()}", flush=True)

    if not rows:
        print(f"正在等待训练结果：{RESULTS_FILE}", flush=True)
        return

    latest = rows[-1]
    epoch_text = latest.get("epoch", "0").strip()
    try:
        epoch = int(float(epoch_text))
    except ValueError:
        epoch = 0
    percent = epoch / TOTAL_EPOCHS * 100
    completed_blocks = min(30, round(percent / 100 * 30))
    progress = "#" * completed_blocks + "-" * (30 - completed_blocks)
    print("", flush=True)
    print(f"总进度：[{progress}] {percent:5.1f}%", flush=True)
    print(
        f"轮次：已完成 {epoch}/{TOTAL_EPOCHS} 轮，剩余 {max(0, TOTAL_EPOCHS - epoch)} 轮",
        flush=True,
    )
    print(
        "本轮成绩：准确率 {precision}  召回率 {recall}  "
        "mAP50 {map50}  综合mAP {map5095}".format(
            precision=metric(latest, "metrics/precision(B)"),
            recall=metric(latest, "metrics/recall(B)"),
            map50=metric(latest, "metrics/mAP50(B)"),
            map5095=metric(latest, "metrics/mAP50-95(B)"),
        ),
        flush=True,
    )
    best = max(rows, key=lambda row: float(row.get("metrics/mAP50-95(B)", 0)))
    print(
        "历史最好：第 {epoch} 轮，mAP50 {map50}，综合mAP {map5095}".format(
            epoch=best.get("epoch", "-").strip(),
            map50=metric(best, "metrics/mAP50(B)"),
            map5095=metric(best, "metrics/mAP50-95(B)"),
        ),
        flush=True,
    )
    print("\n最近 8 轮明细", flush=True)
    print("轮次   准确率   召回率   mAP50   综合mAP", flush=True)
    for row in rows[-8:]:
        print(
            f"{row.get('epoch', '-').strip():>5}  "
            f"{metric(row, 'metrics/precision(B)'):>9}  "
            f"{metric(row, 'metrics/recall(B)'):>6}  "
            f"{metric(row, 'metrics/mAP50(B)'):>5}  "
            f"{metric(row, 'metrics/mAP50-95(B)'):>9}",
            flush=True,
        )


def main() -> None:
    print(f"正在监控：{RUN_DIR}", flush=True)
    print("点击 PyCharm 红色方块只会关闭监控，不会停止后台训练。", flush=True)
    while True:
        render(read_rows())
        if not training_processes():
            break
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()
