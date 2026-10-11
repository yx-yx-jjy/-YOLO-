"""数据库持久化层（SQLite + SQLAlchemy 2.x）。

分层依赖方向（架构稿 §1.2 铁律）：
    routers → services → repositories → models/engine
    writer 只依赖 models/config，被 camera 与 router 共同依赖，不反向依赖 services。
"""
