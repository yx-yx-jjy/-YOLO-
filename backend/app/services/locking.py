"""写操作串行锁。

为什么需要：system_logs.prev_hash 依赖上一条的 entry_hash，而写日志的请求来自
FastAPI 线程池。若两条日志并发读取同一个 prev_hash，链就会分叉（DB 的
idx_system_logs_prev_hash_unique 会报 UNIQUE 错，但设计上就不该并发写）。
故所有"会写 system_logs"的写操作（复核 / 处置 / 登录 / 用户管理）统一持此锁，
把"读 prev_hash → INSERT → commit"串行化。单机毕设并发极低，代价可忽略。
"""
from __future__ import annotations

import threading

WRITE_LOCK = threading.RLock()
