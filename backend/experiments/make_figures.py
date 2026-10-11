# -*- coding: utf-8 -*-
"""
论文第 4 章图表生成脚本（只读取实测 CSV，不做任何模拟或插值）。

数据来源：
  - backend/runs/violation/yolo11s-helmet-voc-v5-pilot/results.csv      (epoch 1-10)
  - backend/runs/violation/yolo11s-helmet-voc-v5-continue/results.csv   (epoch 11-20)
  - backend/experiments/ablation_results.csv        (表 4.5 消融五组)
  - backend/experiments/resolution_results.csv      (表 4.4 四档分辨率)
  - backend/experiments/sensitivity_results.csv     (表 4.7~4.9 参数扫描)

输出：backend/experiments/figures/fig4_1..fig4_5.png（300 dpi）
"""
from __future__ import annotations

import csv
import io
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# ---------------------------------------------------------------- 全局样式
RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs", "violation")
EXP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(EXP, "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.sans-serif": ["SimHei", "Microsoft YaHei"],
    "font.family": "sans-serif",
    "axes.unicode_minus": False,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 10.5,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "axes.linewidth": 0.8,
    "grid.linewidth": 0.5,
    "grid.alpha": 0.35,
})

# 论文印刷友好配色（色盲安全、明度阶梯清晰）
C_BOX = "#1F5FA9"
C_CLS = "#D1651A"
C_DFL = "#4C9A55"
C_PRIMARY = "#1F5FA9"
C_ACCENT = "#C0392B"
C_MUTED = "#7A7A7A"
GRID_KW = dict(axis="y", linestyle="--", linewidth=0.5, color="#BFBFBF")


def read_csv(path: str) -> list[dict]:
    with io.open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def tidy(ax, ylabel: str | None = None, xlabel: str | None = None) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8A8A8A")
    ax.spines["bottom"].set_color("#8A8A8A")
    ax.grid(**GRID_KW)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)


# =============================================================== 图 4.1 损失
def fig_4_1():
    pilot = read_csv(os.path.join(RUNS, "yolo11s-helmet-voc-v5-pilot", "results.csv"))
    cont = read_csv(os.path.join(RUNS, "yolo11s-helmet-voc-v5-continue", "results.csv"))
    # continue 从 pilot 的 last.pt 续训，epoch 需整体后移 10
    ep = [int(r["epoch"]) for r in pilot] + [int(r["epoch"]) + 10 for r in cont]
    tr_box = [float(r["train/box_loss"]) for r in pilot] + [float(r["train/box_loss"]) for r in cont]
    tr_cls = [float(r["train/cls_loss"]) for r in pilot] + [float(r["train/cls_loss"]) for r in cont]
    tr_dfl = [float(r["train/dfl_loss"]) for r in pilot] + [float(r["train/dfl_loss"]) for r in cont]
    va_box = [float(r["val/box_loss"]) for r in pilot] + [float(r["val/box_loss"]) for r in cont]
    va_cls = [float(r["val/cls_loss"]) for r in pilot] + [float(r["val/cls_loss"]) for r in cont]
    va_dfl = [float(r["val/dfl_loss"]) for r in pilot] + [float(r["val/dfl_loss"]) for r in cont]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    series = [
        (axes[0], tr_box, va_box, C_BOX, "边界框回归损失  box loss"),
        (axes[1], tr_cls, va_cls, C_CLS, "分类损失  cls loss"),
        (axes[2], tr_dfl, va_dfl, C_DFL, "分布焦点回归损失  dfl loss"),
    ]
    for ax, tr, va, color, title in series:
        ax.plot(ep, tr, "-o", color=color, linewidth=1.7, markersize=3.6,
                label="训练集")
        ax.plot(ep, va, "-s", color=color, linewidth=1.5, markersize=3.4,
                linestyle="--", alpha=0.85, label="验证集")
        ax.set_title(title)
        ax.set_xticks([1, 4, 8, 12, 16, 20])
        ax.set_xlim(0.4, 20.6)
        tidy(ax, ylabel="损失值")
    axes[0].set_xlabel("训练轮次  epoch")
    axes[2].set_xlabel("训练轮次  epoch")
    axes[0].legend(frameon=False, loc="upper right")
    axes[0].axvline(10.5, color=C_MUTED, linewidth=0.8, linestyle=":")
    axes[0].annotate("续训起点", xy=(10.5, 0.30), xycoords=("data", "axes fraction"),
                     xytext=(11.0, 0.36), textcoords=("data", "axes fraction"),
                     color=C_MUTED, fontsize=9)
    fig.subplots_adjust(wspace=0.25, top=0.90, bottom=0.15)
    p = os.path.join(OUT, "fig4_1_loss_curves.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


# ========================================================== 图 4.2 验证指标
def fig_4_2():
    pilot = read_csv(os.path.join(RUNS, "yolo11s-helmet-voc-v5-pilot", "results.csv"))
    cont = read_csv(os.path.join(RUNS, "yolo11s-helmet-voc-v5-continue", "results.csv"))
    ep = [int(r["epoch"]) for r in pilot] + [int(r["epoch"]) + 10 for r in cont]
    m50 = [float(r["metrics/mAP50(B)"]) for r in pilot] + [float(r["metrics/mAP50(B)"]) for r in cont]
    m5095 = [float(r["metrics/mAP50-95(B)"]) for r in pilot] + [float(r["metrics/mAP50-95(B)"]) for r in cont]
    prec = [float(r["metrics/precision(B)"]) for r in pilot] + [float(r["metrics/precision(B)"]) for r in cont]
    rec = [float(r["metrics/recall(B)"]) for r in pilot] + [float(r["metrics/recall(B)"]) for r in cont]

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.2))

    ax = axes[0]
    ax.plot(ep, m50, "-o", color=C_PRIMARY, linewidth=1.8, markersize=4, label="mAP@50")
    ax.plot(ep, m5095, "-s", color=C_ACCENT, linewidth=1.8, markersize=4, label="mAP@50:95")
    bi = m5095.index(max(m5095))
    ax.scatter([ep[bi]], [m5095[bi]], s=90, facecolor="none", edgecolor=C_ACCENT, linewidth=1.8, zorder=5)
    ax.annotate(f"最佳轮次 epoch {ep[bi]}（续训段第 9 轮）\nmAP@50 = {m50[bi]:.4f}，mAP@50:95 = {m5095[bi]:.4f}",
                xy=(ep[bi], m5095[bi]), xytext=(3.2, 0.585),
                arrowprops=dict(arrowstyle="->", color=C_ACCENT, linewidth=0.9),
                color=C_ACCENT, fontsize=9.2,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                          edgecolor=C_ACCENT, linewidth=0.6, alpha=0.92))
    ax.set_ylim(0.28, 0.86)
    ax.yaxis.set_major_locator(MultipleLocator(0.1))
    ax.set_xticks([1, 4, 8, 12, 16, 20])
    ax.set_xlim(0.4, 20.6)
    ax.set_title("(a) 平均精度均值随轮次变化")
    ax.legend(frameon=False, loc="lower right")
    tidy(ax, ylabel="mAP")

    ax = axes[1]
    ax.plot(ep, prec, "-o", color="#2E7D32", linewidth=1.7, markersize=4, label="精确率 Precision")
    ax.plot(ep, rec, "-s", color="#8E24AA", linewidth=1.7, markersize=4, label="召回率 Recall")
    ax.set_ylim(0.5, 0.86)
    ax.yaxis.set_major_locator(MultipleLocator(0.05))
    ax.set_xticks([1, 4, 8, 12, 16, 20])
    ax.set_xlim(0.4, 20.6)
    ax.set_title("(b) 精确率与召回率随轮次变化")
    ax.legend(frameon=False, loc="lower right")
    tidy(ax, ylabel="指标值")

    fig.subplots_adjust(wspace=0.25, top=0.90, bottom=0.15)
    p = os.path.join(OUT, "fig4_2_val_metrics.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


# ====================================================== 图 4.3 消融权衡
def fig_4_3():
    rows = read_csv(os.path.join(EXP, "ablation_results.csv"))
    order = ["A", "B", "C", "D", "E"]
    rows.sort(key=lambda r: order.index(r["group"]))
    # 单行短标签：完整机制名称放在图注与正文中，避免多子图 x 轴标签互相粘连
    labels = ["A\n仅检测", "B\n+归属", "C\n+头区", "D\n+置信", "E\n+时序"]
    prec = [float(r["precision"]) for r in rows]
    rec = [float(r["recall"]) for r in rows]
    f1 = [float(r["f1"]) for r in rows]
    fpr = [float(r["false_positive_rate"]) for r in rows]
    fp = [int(r["fp"]) for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.1))

    ax = axes[0]
    x = range(5)
    w = 0.26
    ax.bar([i - w for i in x], prec, w, label="精确率 P", color="#1F5FA9")
    ax.bar(list(x), rec, w, label="召回率 R", color="#D1651A")
    ax.bar([i + w for i in x], f1, w, label="F1", color="#4C9A55")
    for i, (a, b, c) in enumerate(zip(prec, rec, f1)):
        ax.text(i - w, a + 0.006, f"{a:.3f}", ha="center", fontsize=8.2, color="#1F5FA9")
        ax.text(i, b + 0.006, f"{b:.3f}", ha="center", fontsize=8.2, color="#B4560F")
        ax.text(i + w, c + 0.006, f"{c:.3f}", ha="center", fontsize=8.2, color="#2F6B34")
    ax.set_ylim(0.72, 1.02)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title("(a) 精确率、召回率与 F1")
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.30))
    tidy(ax, ylabel="指标值")

    ax = axes[1]
    bars = ax.bar(list(x), [v * 100 for v in fpr], 0.5, color="#C0392B")
    for i, (v, n) in enumerate(zip(fpr, fp)):
        ax.text(i, v * 100 + 0.14, f"{v * 100:.2f}%", ha="center", fontsize=9, color="#8E2A20")
        ax.text(i, v * 100 / 2, f"FP={n}", ha="center", fontsize=8.6,
                color="white", fontweight="bold")
    ax.set_ylim(0, 8.2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title("(b) 误报率（越低越好）")
    tidy(ax, ylabel="误报率 / %")

    ax = axes[2]
    ax.plot(fpr, rec, "-o", color="#1F5FA9", linewidth=1.8, markersize=6)
    # 只标注首末两点：D 与 E 数值完全重合，标注全部点会互相压字
    for i in (0, 3):
        rr = rows[i]
        dx, dy = (0.0026, -0.0060) if i == 0 else (-0.0062, 0.0040)
        ax.annotate(f"组 {rr['group']}", xy=(fpr[i], rec[i]),
                    xytext=(fpr[i] + dx, rec[i] + dy),
                    fontsize=10.5, color="#333333", fontweight="bold")
    ax.annotate("", xy=(fpr[3], rec[3]), xytext=(fpr[0], rec[0]),
                arrowprops=dict(arrowstyle="->", color="#7A7A7A", linewidth=1.0,
                                linestyle="--", shrinkA=8, shrinkB=8))
    ax.text(0.0478, 0.7672, "精确率优先的取舍方向", color="#5A5A5A", fontsize=9)
    ax.set_xlim(0.024, 0.070)
    ax.set_ylim(0.755, 0.830)
    ax.set_title("(c) 精确率—召回率权衡轨迹")
    ax.grid(axis="x", linestyle="--", linewidth=0.5, color="#BFBFBF")
    ax.set_axisbelow(True)
    tidy(ax, xlabel="误报率", ylabel="召回率")

    fig.subplots_adjust(bottom=0.20, top=0.92, wspace=0.30)
    p = os.path.join(OUT, "fig4_3_ablation.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


# ================================================== 图 4.4 分辨率对照
def fig_4_4():
    rows = read_csv(os.path.join(EXP, "resolution_results.csv"))
    rows.sort(key=lambda r: int(r["imgsz"]))
    x = [int(r["imgsz"]) for r in rows]
    p_ = [float(r["box_precision"]) for r in rows]
    r_ = [float(r["box_recall"]) for r in rows]
    f1 = [float(r["box_f1"]) for r in rows]
    dr = [float(r["head_detect_rate"]) for r in rows]
    ms = [float(r["avg_infer_ms"]) for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.1))
    xs = range(len(x))

    ax = axes[0]
    ax.plot(xs, p_, "-o", color="#1F5FA9", linewidth=1.8, markersize=5, label="框精确率")
    ax.plot(xs, r_, "-s", color="#D1651A", linewidth=1.8, markersize=5, label="框召回率")
    ax.plot(xs, f1, "-^", color="#4C9A55", linewidth=1.8, markersize=5, label="框 F1")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([str(v) for v in x])
    ax.set_ylim(0.64, 0.92)
    ax.set_title("(a) 框级 P / R / F1（IoU=0.5）")
    ax.legend(frameon=False, loc="lower right")
    tidy(ax, ylabel="指标值", xlabel="推理输入分辨率 imgsz")

    ax = axes[1]
    ax.plot(xs, f1, "-o", color="#1F5FA9", linewidth=1.8, markersize=5, label="框 F1")
    ax.plot(xs, dr, "-s", color="#8E24AA", linewidth=1.8, markersize=5, label="图像级检出率")
    bi = f1.index(max(f1))
    ax.scatter([bi], [f1[bi]], s=110, facecolor="none", edgecolor=C_ACCENT, linewidth=2.0, zorder=5)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([str(v) for v in x])
    # ylim 必须同时包住 f1(0.769~0.793) 与检出率(0.836~0.902)，否则 annotate 会把画布撑爆
    ax.set_ylim(0.745, 0.925)
    ax.annotate(f"F1 最优拐点\nimgsz = {x[bi]}", xy=(bi, f1[bi]),
                xytext=(bi - 1.35, f1[bi] + 0.052),
                arrowprops=dict(arrowstyle="->", color=C_ACCENT, linewidth=0.9),
                color=C_ACCENT, fontsize=9.5)
    ax.set_title("(b) F1 与检出率：分辨率并非越大越好")
    ax.legend(frameon=False, loc="center left")
    tidy(ax, ylabel="指标值", xlabel="推理输入分辨率 imgsz")

    ax = axes[2]
    bars = ax.bar([str(v) for v in x], ms, 0.5, color="#4A6FA5")
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in ms], padding=3, fontsize=9.5)
    ax.set_ylim(0, 52)
    ax.set_title("(c) 单帧推理耗时（60 张样本实测）\n640 与 960 耗时在噪声内 → 960 无额外代价",
                 fontsize=11)
    tidy(ax, ylabel="耗时 / ms", xlabel="推理输入分辨率 imgsz")

    fig.subplots_adjust(wspace=0.25, top=0.88, bottom=0.15)
    p = os.path.join(OUT, "fig4_4_resolution.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


# ================================================== 图 4.5 参数敏感性
def _sens_rows(param: str) -> list[dict]:
    rows = [r for r in read_csv(os.path.join(EXP, "sensitivity_results.csv"))
            if r["param"] == param and r["group"] == "D"]
    rows.sort(key=lambda r: float(r["value"]))
    return rows


def fig_4_5():
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.1))
    specs = [
        ("RIDER_MAX_FOOT_Y", "(a) $RIDER\\_MAX\\_FOOT\\_Y$（足部锚点下界）", 0.99,
         "0.95 过严，1.00 起引入误报\n0.99 为唯一零代价工作点"),
        ("RIDER_HORIZONTAL_INSET", "(b) $RIDER\\_HORIZONTAL\\_INSET$（水平内缩）", 0.10,
         "0.10~0.12 为平台区\n0.15 开始变差"),
        ("RIDER_MAX_MATCH_SCORE", "(c) $RIDER\\_MAX\\_MATCH\\_SCORE$（匹配代价上限）", 0.82,
         "0.90~1.00 与默认值完全等价\n该阈值当前并非瓶颈"),
    ]
    for ax, (param, title, adopted, note) in zip(axes, specs):
        rows = _sens_rows(param)
        vals = [float(r["value"]) for r in rows]
        f1 = [float(r["f1"]) for r in rows]
        rec = [float(r["recall"]) for r in rows]
        fpr = [float(r["false_positive_rate"]) * 100 for r in rows]
        tp = [int(r["tp"]) for r in rows]
        fp = [int(r["fp"]) for r in rows]

        # 左轴：F1 与召回率。两者量级接近但 F1 变化幅度小得多，
        # 因此以召回率为左轴基准，F1 单独用中间副轴，避免两条线被压成平线。
        lo = min(min(f1), min(rec))
        hi = max(max(f1), max(rec))
        pad = (hi - lo) * 0.35 or 0.01
        ax.set_ylim(lo - pad, hi + pad * 0.6)
        ax.plot(vals, rec, "-s", color="#D1651A", linewidth=1.7, markersize=4.5,
                label="召回率 Recall")
        ax.axhline(0, color="none")

        axf = ax.twinx()
        axf.plot(vals, f1, "-o", color="#1F5FA9", linewidth=1.9, markersize=5,
                 label="F1")
        axf.set_ylim(lo - pad, hi + pad * 0.6)
        axf.set_ylabel("F1", color="#1F5FA9")
        axf.tick_params(axis="y", colors="#1F5FA9")
        axf.spines["top"].set_visible(False)
        axf.spines["right"].set_color("#185FA5")

        ax2 = ax.twinx()
        ax2.spines["right"].set_position(("axes", 1.10))
        ax2.plot(vals, fpr, "-^", color="#C0392B", linewidth=1.6, markersize=4.5,
                 linestyle="--", label="误报率")
        ax2.set_ylabel("误报率 %", color="#C0392B", fontsize=9, rotation=0,
                       ha="left", va="center", labelpad=6)
        ax2.yaxis.set_label_coords(1.02, 1.06)
        ax2.tick_params(axis="y", colors="#C0392B")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_color("#8E2A20")
        ax2.set_ylim(0, max(fpr) * 1.45 + 0.5)

        if adopted in vals:
            i = vals.index(adopted)
            for a in (ax, axf, ax2):
                a.axvline(adopted, color=C_MUTED, linewidth=1.0, linestyle=":")
            axf.scatter([adopted], [f1[i]], s=110, facecolor="none",
                        edgecolor="#1F5FA9", linewidth=2.0, zorder=6)
            # 关键读数直接标在点上：TP / FP 变化比曲线形状更能说明问题
            axf.annotate(f"TP={tp[i]} FP={fp[i]}", xy=(adopted, f1[i]),
                         xytext=(0, 10), textcoords="offset points",
                         ha="center", fontsize=8.8, color="#1F5FA9")

        ax.set_xlim(min(vals) - (max(vals) - min(vals)) * 0.06,
                    max(vals) + (max(vals) - min(vals)) * 0.06)
        ax.set_xticks(vals)
        # foot_y 的 0.97~0.995 区间刻度间距过小，旋转 30° 并右对齐避免粘连
        ax.set_xticklabels([f"{v:g}" for v in vals], rotation=30, ha="right")
        ax.set_title(f"{title}\n（本文采用 {adopted:g}）", fontsize=10.5)
        ax.text(0.5, -0.36, note, transform=ax.transAxes, ha="center", va="top",
                fontsize=8.8, color="#5A5A5A")
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = axf.get_legend_handles_labels()
        h3, l3 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2 + h3, l1 + l2 + l3, frameon=False,
                  loc="upper center", bbox_to_anchor=(0.5, -0.20),
                  fontsize=8.6, ncol=3, columnspacing=1.0, handlelength=1.6)
        tidy(ax, ylabel="召回率", xlabel="参数取值")
        ax.grid(False)

    fig.subplots_adjust(bottom=0.34, top=0.90, wspace=0.72)
    p = os.path.join(OUT, "fig4_5_sensitivity.png")
    fig.savefig(p)
    plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    fig_4_1()
    fig_4_2()
    fig_4_3()
    fig_4_4()
    fig_4_5()
    print("ALL DONE ->", OUT)
