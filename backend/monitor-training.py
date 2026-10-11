# -*- coding: utf-8 -*-
"""
实时查看 yolo11s-wuhan-manual-v3 的训练进度。

为什么要这个：训练是后台进程，没有窗口，看不到过程。
这个脚本每 5 秒刷新一次，把 results.csv 和训练日志汇总成一块面板。

按 Ctrl+C 退出。
"""

import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(BASE, "runs", "violation", "yolo11s-wuhan-manual-v3")
CSV_PATH = os.path.join(RUN_DIR, "results.csv")
LOG_PATH = os.path.join(BASE, "runs", "violation", "wuhan-manual-v3-resume.out.log")
BEST_PATH = os.path.join(RUN_DIR, "weights", "best.pt")
LAST_PATH = os.path.join(RUN_DIR, "weights", "last.pt")

TOTAL_EPOCHS = 100
REFRESH_SECONDS = 5
STALL_SECONDS = 180  # 日志超过这么久没更新就认为卡住/挂了

PROGRESS_RE = re.compile(
    r"(\d+)/100\s+([\d.]+)G\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+960:\s*"
    r"(\d+)%\|[^|]*\|\s*(\d+)/(\d+)"
)


def enable_utf8_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def read_results():
    if not os.path.exists(CSV_PATH):
        return []
    rows = []
    try:
        with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as fh:
            header = fh.readline().rstrip("\n").split(",")
            for line in fh:
                parts = line.rstrip("\n").split(",")
                if len(parts) != len(header):
                    continue
                rows.append(dict(zip(header, parts)))
    except Exception:
        return rows
    return rows


def read_log_tail(nbytes=400_000):
    if not os.path.exists(LOG_PATH):
        return ""
    try:
        with open(LOG_PATH, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - nbytes))
            return fh.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def fmt_seconds(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} 小时 {m} 分"
    if m:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"


def main():
    enable_utf8_console()
    last_rendered = None

    try:
        while True:
            now = time.time()
            rows = read_results()
            tail = read_log_tail()

            log_age = now - os.path.getmtime(LOG_PATH) if os.path.exists(LOG_PATH) else None
            last_mtime = (
                os.path.getmtime(LAST_PATH) if os.path.exists(LAST_PATH) else None
            )

            # 当前训练轮的进度
            progress = None
            for match in PROGRESS_RE.finditer(tail):
                progress = match
            validating = "Validating" in tail.split("\r")[-1] if tail else False

            done = len(rows)
            lines = []
            lines.append("=" * 78)
            lines.append("  yolo11s-wuhan-manual-v3  训练进度监控")
            lines.append(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}    每 {REFRESH_SECONDS} 秒刷新，Ctrl+C 退出")
            lines.append("=" * 78)
            lines.append("")

            # 状态
            if done == 0:
                lines.append("  状态：还没读到任何完成的轮次")
            elif log_age is not None and log_age > STALL_SECONDS:
                lines.append(
                    f"  ⚠️  状态：疑似已停止 —— 日志已经 {fmt_seconds(log_age)} 没有更新"
                )
                lines.append("      续训请双击：backend\\resume-training.bat")
            elif progress:
                cur_ep = progress.group(1)
                pct = progress.group(7)
                it = progress.group(8)
                total_it = progress.group(9)
                gpu = progress.group(2)
                box_loss = progress.group(3)
                cls_loss = progress.group(4)
                dfl_loss = progress.group(5)
                lines.append(f"  状态：✅ 正在训练")
                if validating:
                    lines.append(f"        第 {cur_ep}/100 轮 —— 正在验证")
                else:
                    lines.append(f"        第 {cur_ep}/100 轮 —— {pct}%  ({it}/{total_it} batch)")
                lines.append(
                    f"        loss: box={box_loss}  cls={cls_loss}  dfl={dfl_loss}"
                    f"   显存={gpu}"
                )
            else:
                lines.append("  状态：训练进程在，但解析不到进度行（可能在做最后的验证/收尾）")

            lines.append(f"  已完成：{done}/100 轮")
            lines.append("")

            # 进度条
            filled = int(done / TOTAL_EPOCHS * 50)
            bar = "#" * filled + "-" * (50 - filled)
            lines.append(f"  [{bar}] {done / TOTAL_EPOCHS * 100:.0f}%")
            lines.append("")

            # 本轮会话速度与 ETA
            if rows:
                try:
                    first_time = float(rows[0]["time"])
                    last_time = float(rows[-1]["time"])
                    per_epoch = last_time / len(rows) if len(rows) == 1 else (last_time - first_time) / (len(rows) - 1)
                    remaining = TOTAL_EPOCHS - done
                    eta = per_epoch * remaining
                    lines.append(
                        f"  平均 {per_epoch:.0f} 秒/轮，"
                        f"已训练 {fmt_seconds(last_time)}"
                    )
                    lines.append(f"  预计剩余 {fmt_seconds(eta)}")
                except Exception:
                    pass
            lines.append("")

            # 指标表
            if rows:
                lines.append("  最近 8 轮指标：")
                lines.append(
                    "   " + "-" * 70
                )
                lines.append(
                    f"   {'轮':>4}  {'精度P':>8}  {'召回R':>8}  {'mAP50':>8}  {'mAP50-95':>9}  {'验证loss':>9}"
                )
                lines.append("   " + "-" * 70)
                for row in rows[-8:]:
                    try:
                        lines.append(
                            f"   {row['epoch']:>4}  {float(row['metrics/precision(B)']):>8.3f}"
                            f"  {float(row['metrics/recall(B)']):>8.3f}"
                            f"  {float(row['metrics/mAP50(B)']):>8.3f}"
                            f"  {float(row['metrics/mAP50-95(B)']):>9.3f}"
                            f"  {float(row['val/cls_loss']):>9.3f}"
                        )
                    except Exception:
                        continue
                lines.append("   " + "-" * 70)

                best = max(
                    rows,
                    key=lambda r: float(r.get("metrics/mAP50(B)") or 0),
                )
                lines.append(
                    f"   目前最好：第 {best['epoch']} 轮，"
                    f"mAP50 = {float(best['metrics/mAP50(B)']):.3f}，"
                    f"mAP50-95 = {float(best['metrics/mAP50-95(B)']):.3f}"
                )

            if last_mtime:
                lines.append("")
                lines.append(
                    f"  权重最后保存：{time.strftime('%H:%M:%S', time.localtime(last_mtime))}"
                    f"    best.pt {'存在' if os.path.exists(BEST_PATH) else '还没有'}"
                )

            lines.append("")
            lines.append("=" * 78)

            render = "\n".join(lines)
            if render != last_rendered:
                clear()
                print(render)
                last_rendered = render

            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        print("\n已退出监控（训练仍在后台继续跑）。")


if __name__ == "__main__":
    main()
