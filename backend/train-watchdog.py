# -*- coding: utf-8 -*-
"""
训练看门狗：自动续训 yolo11s-wuhan-manual-v3，直到跑满 100 轮。

为什么需要它：
  本机提交内存（commit）几乎被其他程序占满（56.7 GB 限额只剩几 GB），
  训练进程在第 8 轮做 mosaic 增强时连 10.5 MiB 都分配不出来而崩掉。
  这种崩溃会反复发生，而 Ultralytics 的 last.pt 每次都是完整的，
  所以崩溃后直接从 last.pt 续训即可，代价只是重跑崩掉的那一轮。

行为：
  · 每一轮都从 runs/violation/yolo11s-wuhan-manual-v3/weights/last.pt 续训
  · 子进程输出**追加**写入 runs/violation/wuhan-manual-v3-resume.out.log
  · 崩溃后等 30 秒再试（给系统回收内存留时间）
  · 如果连续 3 次都在 90 秒内就崩（说明不是偶发内存问题），直接放弃并报错
  · results.csv 达到 101 行（表头 + 100 轮）即视为完成，退出

用法：backend/start-training.bat
"""

import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(BASE, "runs", "violation", "yolo11s-wuhan-manual-v3")
CSV_PATH = os.path.join(RUN_DIR, "results.csv")
CKPT = os.path.join(RUN_DIR, "weights", "last.pt")
LOG_PATH = os.path.join(BASE, "runs", "violation", "wuhan-manual-v3-resume.out.log")
LOCK_PATH = os.path.join(BASE, "runs", "violation", ".training-watchdog.lock")
DATA = os.path.join(os.path.dirname(BASE), "data", "wuhan-manual-yolo", "combined-dataset.yaml")
PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
TRAIN = os.path.join(BASE, "training", "train.py")

TOTAL_EPOCHS = 100
RETRY_WAIT_SECONDS = 30
FAST_FAIL_SECONDS = 90
# 本机提交内存长期紧张，快速失败是常态而不是异常，所以这里给足重试次数
MAX_CONSECUTIVE_FAST_FAILS = 40
MAX_ATTEMPTS = 80
# 开一轮训练之前，系统至少要有这么多剩余「提交内存」（commit）配额。
# 实测训练崩在 cv2.warpAffine 分配 2.76 MB 失败 / numpy 分配 10.5 MB 失败，
# 都是因为别的程序把 commit 占满了 —— 物理内存还剩 6 GB 也没用。
MIN_COMMIT_HEADROOM_MB = 4096


def commit_headroom_mb():
    """系统剩余提交内存配额，单位 MB（测不到时返回一个大数，不拦事）。"""
    try:
        import ctypes

        class MS(ctypes.Structure):
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

        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPageFile / 1048576.0
    except Exception:
        return 999999.0


def log(msg):
    line = f"[watchdog {time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("\n" + line + "\n")
    except Exception:
        pass


def epochs_done():
    if not os.path.exists(CSV_PATH):
        return 0
    try:
        with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except Exception:
        return 0


def pid_alive(pid):
    """安全地探测进程是否存活。

    注意：Windows 上不要用 os.kill(pid, 0) 做探测 —— CPython 在 win32 下对
    非 CTRL_C_EVENT 的信号会走 TerminateProcess，有把进程真的杀掉的风险。
    这里用 OpenProcess 只申请查询权限，拿得到句柄说明进程还在。
    """
    if not pid:
        return False
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        # 探测本身出错时保守认为是活着的，避免并发写同一份 results.csv
        return True


def acquire_lock():
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r", encoding="utf-8") as fh:
                pid = int(fh.read().strip() or 0)
        except Exception:
            pid = 0
        if pid_alive(pid):
            return False, pid
        # 陈旧锁，继续
    with open(LOCK_PATH, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    return True, os.getpid()


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def main():
    ok, pid = acquire_lock()
    if not ok:
        log(f"已有另一个看门狗在跑（PID {pid}），本次退出。")
        return 1

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    log("=" * 70)
    log("看门狗启动")
    log(f"  目标    : {TOTAL_EPOCHS} 轮")
    log(f"  当前进度: {epochs_done()} 轮")
    log(f"  检查点  : {CKPT}")
    log("=" * 70)

    fast_fails = 0

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            done = epochs_done()
            if done >= TOTAL_EPOCHS:
                log(f"✅ 已完成 {done}/{TOTAL_EPOCHS} 轮，看门狗收工。")
                return 0

            if not os.path.exists(CKPT):
                log(f"❌ 找不到检查点 {CKPT}，无法续训。")
                return 1

            cmd = [
                PY, TRAIN,
                "--data", DATA,
                "--resume", CKPT,
                "--batch", "1",
                "--imgsz", "960",
                "--device", "0",
                "--workers", "0",
            ]

            # 先确认系统有足够的提交内存，否则一开就崩在数据增强上
            # （实测崩在 cv2.warpAffine 分不出 2.76 MB / numpy 分不出 10.5 MB）
            headroom = commit_headroom_mb()
            if headroom < MIN_COMMIT_HEADROOM_MB:
                log(
                    f"⏳ 剩余提交内存只有 {headroom:.0f} MB，低于门槛 "
                    f"{MIN_COMMIT_HEADROOM_MB} MB，暂不启动训练（启动也必崩）。"
                )
                while commit_headroom_mb() < MIN_COMMIT_HEADROOM_MB:
                    log(
                        "   等 60 秒后再看……请关掉占内存的程序腾地方："
                        "Edge 浏览器 / 微信 / QQ / ChatGPT / 哔哩哔哩客户端"
                    )
                    time.sleep(60)
                log(f"✅ 提交内存已回升到 {commit_headroom_mb():.0f} MB，继续。")

            log(f"--- 第 {attempt} 次尝试，从第 {done + 1} 轮继续 ---")
            started = time.time()
            with open(LOG_PATH, "ab") as fh:
                fh.write(
                    f"\n\n===== [watchdog] attempt {attempt} "
                    f"resume from epoch {done + 1} "
                    f"at {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n".encode("utf-8")
                )
                fh.flush()
                proc = subprocess.run(cmd, cwd=BASE, env=env, stdout=fh, stderr=subprocess.STDOUT)
            lasted = time.time() - started

            done_after = epochs_done()
            log(
                f"第 {attempt} 次结束：返回码 {proc.returncode}，"
                f"运行 {lasted / 60:.1f} 分钟，进度 {done} → {done_after} 轮"
            )

            if done_after >= TOTAL_EPOCHS:
                log(f"✅ 已完成 {done_after}/{TOTAL_EPOCHS} 轮，看门狗收工。")
                return 0

            if proc.returncode == 0:
                log("训练正常退出但轮数不足，可能提前触发了早停（patience）。停止重试。")
                return 0

            if lasted < FAST_FAIL_SECONDS:
                fast_fails += 1
                log(f"⚠️ 快速失败计数 {fast_fails}/{MAX_CONSECUTIVE_FAST_FAILS}")
                if fast_fails >= MAX_CONSECUTIVE_FAST_FAILS:
                    log("❌ 连续快速失败，判定为环境问题而非偶发内存不足，停止重试。")
                    log("   建议：关掉一些占内存的程序（PyCharm / 浏览器 / 微信）后重新启动看门狗。")
                    return 1
            else:
                fast_fails = 0

            log(f"等 {RETRY_WAIT_SECONDS} 秒后重试……")
            time.sleep(RETRY_WAIT_SECONDS)

        log("❌ 达到最大重试次数，停止。")
        return 1
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
