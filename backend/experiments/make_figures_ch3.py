# -*- coding: utf-8 -*-
"""
第 3 章示意图（图 3-2 / 图 3-3）：把 3.3 节最抽象的三处机制画出来。

  图 3-2  骑乘归属判定：足部锚点 + 三条几何约束 + 代价函数
  图 3-3  头盔归属与置信度融合：头部区域约束 + 三态仲裁 + min 融合

设计原则：论文插图用矢量输出，打印清晰。禁用手写 ax.text 顶部标签
（多子图下会把 bbox 撑爆），一律用 bar_label 或直接画在 axes 坐标内。
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

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
    "axes.linewidth": 0.8,
})

# 配色（与第 4 章图表保持一致）
C_PERSON = "#1F5FA9"
C_VEHICLE = "#8A8A8A"
C_HELMET = "#4C9A55"
C_BARE = "#C0392B"
C_ZONE = "#B5D4F4"
C_ANCHOR = "#D1651A"
C_DIM = "#9A9A9A"


def box(ax, x, y, w, h, fc, ec, lw=1.2, ls="solid", z=2):
    """画一个矩形框。"""
    p = Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                  linewidth=lw, linestyle=ls, zorder=z)
    ax.add_patch(p)
    return (x, y, w, h)


def label(ax, x, y, s, fontsize=10, color="#333333", ha="center",
          va="center", weight="normal", style="normal"):
    ax.text(x, y, s, fontsize=fontsize, color=color, ha=ha, va=va,
            zorder=6, fontweight=weight, fontstyle=style)


# ======================================================= 图 3-2 骑乘归属
def fig_3_2():
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.6))
    axes = axes.ravel()
    for ax in axes:
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")

    # ---------- (a) 足部锚点 ----------
    ax = axes[0]
    box(ax, 12, 8, 58, 78, "#F7F7F7", C_VEHICLE, 1.4)
    label(ax, 41, 90, "车辆框", 10.5, C_VEHICLE)
    box(ax, 22, 30, 22, 52, "#E6F1FB", C_PERSON, 1.4)          # 人体框
    label(ax, 33, 68, "人体框", 9.5, C_PERSON)
    box(ax, 25, 76, 16, 12, "#FAECE7", C_ANCHOR, 1.2)           # 头部
    label(ax, 33, 82, "头", 9, C_ANCHOR)

    # 足部锚点
    fx, fy = 33, 30
    ax.plot([fx], [fy], marker="o", markersize=9, color=C_ANCHOR, zorder=8)
    ax.add_patch(FancyArrowPatch((fx + 26, fy - 9), (fx + 1, fy + 0.5),
                                 arrowstyle="->", color=C_ANCHOR, linewidth=1.4,
                                 mutation_scale=13))
    label(ax, fx + 27, fy - 12, "足部锚点\n（底边中点）", 9.5, C_ANCHOR, ha="left")
    label(ax, 50, 4, "(a) 以脚的位置判断骑乘，而非\n用身体中心做重叠度",
          9.8, "#555555")

    # ---------- (b) 三条约束 ----------
    ax = axes[1]
    box(ax, 10, 10, 62, 76, "#F7F7F7", C_VEHICLE, 1.4)
    # 车框内允许区域（水平 10%~90%，垂直 0~99%）
    box(ax, 10 + 62 * 0.10, 10, 62 * 0.80, 76 * 0.99, "#EAF3DE", "#639922", 1.0, ":")
    label(ax, 41, 12, "允许的骑乘区域", 9, "#3B6D11")
    box(ax, 28, 34, 20, 46, "#E6F1FB", C_PERSON, 1.4)
    label(ax, 38, 70, "人体框", 9, C_PERSON)
    box(ax, 31, 74, 14, 10, "#FAECE7", C_ANCHOR, 1.1)
    ax.plot([38], [34], marker="o", markersize=8, color=C_ANCHOR, zorder=8)

    # 三个被排除的目标
    box(ax, 76, 40, 9, 42, "#F2F2F2", C_DIM, 1.0, "--")
    label(ax, 80.5, 86, "车旁人", 8.6, "#666666")
    ax.plot([80.5], [40], marker="x", markersize=7, color=C_DIM, zorder=8)

    box(ax, 1, 40, 8, 42, "#F2F2F2", C_DIM, 1.0, "--")
    label(ax, 5, 86, "车旁人", 8.6, "#666666")
    ax.plot([5], [40], marker="x", markersize=7, color=C_DIM, zorder=8)

    box(ax, 60, 2, 10, 22, "#F2F2F2", C_DIM, 1.0, "--")
    label(ax, 65, 26.5, "推行者", 8.6, "#666666")
    ax.plot([65], [2], marker="x", markersize=7, color=C_DIM, zorder=8)

    label(ax, 50, 90, "三条约束把「不像骑车的人」挡在外面", 10.2, C_VEHICLE)
    label(ax, 50, -2, "(b) 脚须落在车框中间、不得低于车底、允许少量抖动余量",
          9.8, "#555555")

    # ---------- (c) 代价函数三项 ----------
    ax = axes[2]
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    items = [
        ("① 水平间隙  ×2.0", "脚有没有往车外偏", C_ANCHOR),
        ("② 纵向距离  ×1.0", "脚踩的位置对不对", "#639922"),
        ("③ 中心距    ×0.35", "脚是不是踩在车中间", C_VEHICLE),
    ]
    y = 93
    for head, desc, col in items:
        label(ax, 3, y, head, 10.5, col, ha="left", weight="500")
        y -= 8
        label(ax, 7, y, desc, 9.4, "#666666", ha="left")
        y -= 11
    box(ax, 3, 12, 94, 15, "#F5F5F5", "#D8D8D8", 0.8)
    label(ax, 50, 22, "三项相加 = 匹配代价（越小越可信）", 10, "#333333")
    label(ax, 50, 15.5, "若最小代价仍 > 0.82，则判为非骑乘者", 9.4, "#666666")
    label(ax, 50, 3, "(c) 权重按「区分力」设定：水平最关键", 9.8, "#555555")

    fig.subplots_adjust(wspace=0.06, top=0.96, bottom=0.04)
    p = os.path.join(OUT, "fig3_2_rider_assignment.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


# ============================================ 图 3-3 头盔归属与置信度融合
def fig_3_3():
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.4))
    axes = axes.ravel()
    for ax in axes:
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")

    # ---------- (a) 头部区域约束 ----------
    ax = axes[0]
    # 人体框：下边界 y=16，高 80 → 顶边 y=96
    box(ax, 20, 16, 40, 80, "#E6F1FB", C_PERSON, 1.4)
    label(ax, 40, 94, "人体框", 9.8, C_PERSON)
    # 头部候选区域：左右外扩 0.2w，上移 0.08h，下探至人体顶下方 0.42h
    pw, ph, py = 40.0, 80.0, 16.0
    zx1 = 20 - 0.2 * pw
    zy_top = py + ph + 0.08 * ph
    zw = pw * 1.4
    zh = 0.50 * ph
    box(ax, zx1, zy_top - zh, zw, zh, C_ZONE, "#185FA5", 1.0, "--")
    label(ax, zx1 + zw / 2, zy_top + 3.5, "头部候选区域", 9.4, "#185FA5")
    # 头盔与裸头两个框都落在区域内
    box(ax, 30, zy_top - zh + 6, 13, 12, "#EAF3DE", C_HELMET, 1.3)
    label(ax, 36.5, zy_top - zh + 12, "盔", 9, C_HELMET)
    box(ax, 52, zy_top - zh + 7, 12, 11, "#FCEBEB", C_BARE, 1.3)
    label(ax, 58, zy_top - zh + 12.5, "裸", 9, C_BARE)

    # 区域外的人头被排除
    box(ax, 66, 26, 13, 12, "#F2F2F2", C_DIM, 1.0, "--")
    label(ax, 72.5, 21, "区域外", 8.4, "#999999")
    label(ax, 72.5, 31, "远处人头", 8.4, "#666666")
    ax.plot([72.5], [32], marker="x", markersize=7, color=C_DIM, zorder=8)
    label(ax, 40, 6, "两框均落入区域 → 进入置信度仲裁", 9.2, "#555555")
    label(ax, 44, 1, "(a) 先按区域硬约束过滤，再在候选中择优", 9.8, "#555555")

    # ---------- (b) 三态仲裁 ----------
    ax = axes[1]
    label(ax, 50, 94, "佩戴状态的三态仲裁", 10.6, "#333333", weight="500")
    cases = [
        ("裸头置信 ≥ 头盔置信", "判定：未戴头盔", C_BARE),
        ("仅有头盔框", "判定：已戴头盔", C_HELMET),
        ("两者都没认领到", "判定：状态未知 → 转人工", C_ANCHOR),
    ]
    y = 78
    for cond, res, col in cases:
        box(ax, 8, y - 9, 84, 11, "#FFFFFF", "#D0D0D0", 0.9)
        label(ax, 13, y - 3.5, cond, 9.4, "#444444", ha="left")
        label(ax, 87, y - 3.5, res, 9.4, col, ha="right")
        y -= 15
    label(ax, 50, 12, "仲裁规则：两个框都认领时，置信度高者胜出", 9.4, "#555555")
    label(ax, 50, 4, "(b) 故佩戴类与未佩戴类须分别独立认领", 9.6, "#555555")

    # ---------- (c) 置信度取最小值 ----------
    ax = axes[2]
    label(ax, 50, 94, "置信度瓶颈融合", 10.6, "#333333", weight="500")
    items = [("车辆检测", 0.95, C_VEHICLE), ("骑手检测", 0.91, C_PERSON),
             ("裸头检测", 0.42, C_BARE)]
    y = 80
    for name, v, col in items:
        label(ax, 12, y + 5, name, 9.4, "#444444", ha="left")
        box(ax, 12, y - 3, 62, 6, "#F0F0F0", "#D0D0D0", 0.7)
        box(ax, 12, y - 3, 62 * v, 6, col, col, 0.7)
        label(ax, 78, y, f"{v:.2f}", 9.4, col, ha="left")
        y -= 13
    label(ax, 43, y + 2, "↓  取三者最小值", 10, C_BARE, weight="500")
    box(ax, 12, y - 16, 62, 8, C_BARE, C_BARE, 0.9)
    label(ax, 43, y - 12, "最终置信度 = 0.42", 10.4, "white", weight="500")
    label(ax, 50, 6, "(c) 链条最弱一环决定结论，避免高置信度\n为低置信度环节背书",
          9.4, "#555555")

    fig.subplots_adjust(wspace=0.10, top=0.96, bottom=0.04)
    p = os.path.join(OUT, "fig3_3_helmet_attribution.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    fig_3_2()
    fig_3_3()
    print("ALL DONE ->", OUT)
