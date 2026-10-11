# -*- coding: utf-8 -*-
"""图 3-1 五层架构图。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.sans-serif": ["SimHei", "Microsoft YaHei"],
    "font.family": "sans-serif",
    "axes.unicode_minus": False,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 10,
})


def fig_3_1():
    fig, ax = plt.subplots(figsize=(9.6, 10.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    layers = [
        # (层名, 技术, 职责, 底色, 字色)
        ("应用层", "Vue 3 + Element Plus",
         "实时监测页　违规台账页　态势研判大屏　系统管理页", "#E6F1FB", "#185FA5"),
        ("服务层", "FastAPI + MJPEG",
         "视频流分发　接口编排　令牌鉴权　证据静态挂载", "#EAF3DE", "#3B6D11"),
        ("数据层", "SQLite + SQLAlchemy",
         "证据落盘　台账持久化　复核处置留痕　哈希链防篡改", "#FAEEDA", "#854F0B"),
        ("决策层", "自研推理引擎（rules.py）",
         "骑乘归属　头盔归属　佩戴状态三态仲裁　置信度瓶颈融合", "#FCEBEB", "#A32D2D"),
        ("感知层", "YOLO11 + ByteTrack",
         "视频解码　双检测器推理　目标轨迹关联", "#EEEDFE", "#534AB7"),
    ]

    h = 12.6
    gap = 3.4
    y0 = 14.0
    tops = []

    # 自下而上绘制：感知层在最下，应用层在最上
    for i, (name, tech, duty, fc, tc) in enumerate(layers):
        y = y0 + i * (h + gap)
        tops.append(y)
        ax.add_patch(FancyBboxPatch(
            (8, y), 84, h, boxstyle="round,pad=0.6,rounding_size=1.6",
            facecolor=fc, edgecolor=tc, linewidth=1.3))
        ax.text(12, y + h / 2 + 2.2, name, fontsize=12.5, color=tc,
                ha="left", va="center", fontweight="500")
        ax.text(12, y + h / 2 - 2.6, tech, fontsize=9.4, color="#555555",
                ha="left", va="center")
        ax.text(33, y + h / 2, duty, fontsize=9.6, color="#333333",
                ha="left", va="center")

    # 层间双向箭头
    for i in range(len(layers) - 1):
        y_top = tops[i] + h
        y_bot = tops[i + 1]
        ax.add_patch(FancyArrowPatch(
            (52, y_bot + 0.4), (52, y_top - 0.4),
            arrowstyle="-|>", mutation_scale=12,
            color="#8A8A8A", linewidth=1.1, zorder=5))
        ax.add_patch(FancyArrowPatch(
            (44, y_top - 0.4), (44, y_bot + 0.4),
            arrowstyle="-|>", mutation_scale=12,
            color="#B8B8B8", linewidth=1.0, zorder=5))

    # 底部输入
    ax.add_patch(FancyBboxPatch(
        (8, 6.0), 84, 5.6, boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor="#F2F2F2", edgecolor="#8A8A8A", linewidth=1.0))
    ax.text(50, 8.8, "输入：卡口监控视频流　/　上传的图片与视频",
            fontsize=10, color="#444444", ha="center", va="center")

    # 左侧：数据自下而上
    ax.annotate("", xy=(4.4, tops[-1] + h / 2), xytext=(4.4, tops[0] + h / 2),
                arrowprops=dict(arrowstyle="-|>", color="#7A7A7A", linewidth=1.4))
    ax.text(2.0, (tops[0] + tops[-1]) / 2 + h / 2, "数\n据\n流",
            fontsize=10, color="#7A7A7A", ha="center", va="center", linespacing=1.6)

    # 右侧：请求自上而下
    ax.annotate("", xy=(95.6, tops[0] + h / 2), xytext=(95.6, tops[-1] + h / 2),
                arrowprops=dict(arrowstyle="-|>", color="#7A7A7A", linewidth=1.4))
    ax.text(98, (tops[0] + tops[-1]) / 2 + h / 2, "请\n求\n流",
            fontsize=10, color="#7A7A7A", ha="center", va="center", linespacing=1.6)

    # 决策层侧注（layers 顺序为 应用/服务/数据/决策/感知，自下而上绘制，故决策层是 tops[3]）
    dy = tops[3]
    ax.text(50, dy - 1.4, "▲ 本文方法层的工作集中于此层（3.3 节）",
            fontsize=9.4, color="#A32D2D", ha="center", va="top")

    ax.text(50, 96, "各层职责单一，依赖单向：上层可依赖下层，下层不反向依赖上层",
            fontsize=10.0, color="#555555", ha="center", va="center")

    fig.subplots_adjust(top=0.99, bottom=0.01)
    p = os.path.join(OUT, "fig3_1_architecture.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    fig_3_1()
    print("ALL DONE ->", OUT)
