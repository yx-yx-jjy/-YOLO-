# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import os
import re
import sys
import time
from pathlib import Path


BASE = Path(__file__).resolve().parent
RUN_NAME = "yolo11s-wuhan-clean-v4"
TOTAL_EPOCHS = 50
RUN_DIR = BASE / "runs" / "violation" / RUN_NAME
CSV_PATH = RUN_DIR / "results.csv"
LOG_PATH = BASE / "runs" / "violation" / "wuhan-clean-v4.out.log"
BEST_PATH = RUN_DIR / "weights" / "best.pt"
LAST_PATH = RUN_DIR / "weights" / "last.pt"
REFRESH_SECONDS = 5
STALL_SECONDS = 180

PROGRESS_RE = re.compile(
    rf"(\d+)/{TOTAL_EPOCHS}\s+([\d.]+)G\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
    r"\d+\s+\d+:\s*(\d+)%\|[^|]*\|\s*(\d+)/(\d+)"
)


def enable_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clear() -> None:
    # PyCharm's emulated terminal understands ANSI clear-screen sequences.
    print("\033[2J\033[H", end="")


def read_results() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []
    try:
        with CSV_PATH.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def read_log_tail(size: int = 500_000) -> str:
    if not LOG_PATH.exists():
        return ""
    try:
        with LOG_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - size))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def duration(seconds: float) -> str:
    minutes = max(0, int(seconds)) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours} 小时 {minutes} 分" if hours else f"{minutes} 分"


def render() -> str:
    now = time.time()
    rows = read_results()
    tail = read_log_tail()
    log_age = now - LOG_PATH.stat().st_mtime if LOG_PATH.exists() else None
    progress = None
    for match in PROGRESS_RE.finditer(tail):
        progress = match

    lines = [
        "=" * 82,
        f"  {RUN_NAME}  训练进度监控",
        f"  {time.strftime('%Y-%m-%d %H:%M:%S')}    每 {REFRESH_SECONDS} 秒刷新，Ctrl+C 关闭监控",
        "=" * 82,
        "",
    ]

    if log_age is not None and log_age > STALL_SECONDS:
        lines.append(f"  状态：训练日志已 {duration(log_age)} 没有更新，训练可能已停止")
    elif progress:
        epoch, gpu, box, cls, dfl, percent, batch, batch_total = progress.groups()
        lines.extend(
            [
                f"  状态：正在训练第 {epoch}/{TOTAL_EPOCHS} 轮",
                f"  本轮：{percent}%  ({batch}/{batch_total} batch)",
                f"  loss：box={box}  cls={cls}  dfl={dfl}    显存={gpu}G",
            ]
        )
    elif tail:
        lines.append("  状态：训练进程正在初始化、扫描数据或执行验证")
    else:
        lines.append("  状态：尚未读取到训练日志")

    done = len(rows)
    filled = min(50, int(done / TOTAL_EPOCHS * 50))
    lines.extend(
        [
            f"  已完成：{done}/{TOTAL_EPOCHS} 轮",
            f"  [{'#' * filled}{'-' * (50 - filled)}] {done / TOTAL_EPOCHS * 100:.0f}%",
            "",
        ]
    )

    if rows:
        lines.extend(
            [
                "  最近指标：",
                "   " + "-" * 74,
                f"   {'轮':>4}  {'Precision':>9}  {'Recall':>9}  {'mAP50':>9}  "
                f"{'mAP50-95':>10}  {'val cls':>9}",
                "   " + "-" * 74,
            ]
        )
        for row in rows[-8:]:
            try:
                lines.append(
                    f"   {int(float(row['epoch'])):>4}  "
                    f"{float(row['metrics/precision(B)']):>9.3f}  "
                    f"{float(row['metrics/recall(B)']):>9.3f}  "
                    f"{float(row['metrics/mAP50(B)']):>9.3f}  "
                    f"{float(row['metrics/mAP50-95(B)']):>10.3f}  "
                    f"{float(row['val/cls_loss']):>9.3f}"
                )
            except (KeyError, TypeError, ValueError):
                continue
        best = max(rows, key=lambda row: float(row.get("metrics/mAP50-95(B)") or 0))
        lines.extend(
            [
                "   " + "-" * 74,
                f"   当前最佳：第 {best['epoch']} 轮，"
                f"mAP50={float(best['metrics/mAP50(B)']):.3f}，"
                f"mAP50-95={float(best['metrics/mAP50-95(B)']):.3f}",
            ]
        )

    if LAST_PATH.exists():
        lines.append(
            f"\n  权重更新时间：{time.strftime('%H:%M:%S', time.localtime(LAST_PATH.stat().st_mtime))}"
            f"    best.pt={'存在' if BEST_PATH.exists() else '尚未生成'}"
        )
    lines.extend(["", "  关闭这个监控窗口不会停止后台训练。", "=" * 82])
    return "\n".join(lines)


def main() -> None:
    enable_utf8()
    try:
        while True:
            clear()
            print(render(), flush=True)
            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        print("\n监控已关闭，后台训练不受影响。")


if __name__ == "__main__":
    main()
