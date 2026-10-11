"""全量逐条对账：**原始 JS 算法（demo_dataset_reference.js） vs 库内数据**。

用于验证 seed_ledger.py 的移植忠实度 + 复核时间 clamp 修正的正确性。

用法（backend 目录、backend/.venv）：
    python scripts/seed_ledger.py --reset --now "2026-10-03 15:00:00"
    python scripts/reconcile_seed.py      --now "2026-10-03 15:00:00"

两侧必须用**同一个 now**（脚本无法从库里反推生成时刻），否则「今日未来抓拍」的过滤
与边界样本时间会对不齐。

判定逻辑：
  1. node 参考实现（--clamp）产出期望集合；库内每条经生产序列化器读出的 Record 与之逐字段比对。
  2. 额外用未 clamp 的参考实现，验证「受影响的行数」= 库里 review_time 被 clamp 到 now 的行数。
  3. 断言：库里不存在 review_time > now 的记录（缺陷已消除）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.db import engine as db_engine  # noqa: E402
from app.db.models import ReviewHistory, ViolationRecord  # noqa: E402
from app.services import record_view  # noqa: E402

JS_REFERENCE = Path(__file__).with_name("demo_dataset_reference.js")

SCALAR_FIELDS = [
    "capture_time", "camera_id", "violation_type", "category",
    "status", "reviewer", "review_time", "review_remark",
]
DETAIL_FIELDS = ["helmet_status", "consecutive_frames", "plate_or_vehicle"]
DISP_FIELDS = ["status", "method", "notified_at", "disposed_at", "handler", "remark"]


def run_reference(now_str: str, clamp: bool) -> dict:
    node = os.getenv("NODE_BIN", "node")
    cmd = [node, str(JS_REFERENCE), now_str]
    if clamp:
        cmd.append("--clamp")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"node 参考实现执行失败：{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _num_equal(a, b) -> bool:
    return abs(float(a) - float(b)) < 1e-9


def compare_record(js: dict, api: dict) -> list[str]:
    diffs: list[str] = []
    for field in SCALAR_FIELDS:
        if js.get(field) != api.get(field):
            diffs.append(f"{field}: js={js.get(field)!r} db={api.get(field)!r}")
    if str(js.get("track_id")) != str(api.get("track_id")):
        diffs.append(f"track_id: js={js.get('track_id')!r} db={api.get('track_id')!r}")
    if not _num_equal(js.get("confidence"), api.get("confidence")):
        diffs.append(f"confidence: js={js.get('confidence')!r} db={api.get('confidence')!r}")

    js_details = js.get("details") or {}
    api_details = api.get("details") or {}
    for field in DETAIL_FIELDS:
        if js_details.get(field) != api_details.get(field):
            diffs.append(f"details.{field}: js={js_details.get(field)!r} db={api_details.get(field)!r}")

    js_disp = js.get("disposition") or {}
    api_disp = api.get("disposition") or {}
    for field in DISP_FIELDS:
        if (js_disp.get(field) or None) != (api_disp.get(field) or None):
            diffs.append(f"disposition.{field}: js={js_disp.get(field)!r} db={api_disp.get(field)!r}")
    js_hist = js_disp.get("history") or []
    api_hist = api_disp.get("history") or []
    if len(js_hist) != len(api_hist):
        diffs.append(f"disposition.history.length: js={len(js_hist)} db={len(api_hist)}")
    else:
        for index, (js_item, api_item) in enumerate(zip(js_hist, api_hist)):
            for field in ("action", "operator", "remark", "time"):
                if js_item.get(field) != api_item.get(field):
                    diffs.append(
                        f"disposition.history[{index}].{field}: "
                        f"js={js_item.get(field)!r} db={api_item.get(field)!r}"
                    )
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="原始 JS 算法 vs 库内数据 全量逐条对账")
    parser.add_argument("--now", required=True, help="与 seed --now 完全一致的生成时刻")
    parser.add_argument("--max-diff-print", type=int, default=10)
    args = parser.parse_args()

    now_str = args.now
    print(f"[reconcile] now = {now_str}")

    expected = run_reference(now_str, clamp=True)
    unclamped = run_reference(now_str, clamp=False)
    js_records = expected["records"]
    js_by_id = {r["id"]: r for r in js_records}
    unclamped_by_id = {r["id"]: r for r in unclamped["records"]}

    db_engine.init_db()
    if not db_engine.db_state.ready:
        print(f"[error] 数据库不可用：{db_engine.db_state.message}")
        return 1

    with db_engine.session_scope() as session:
        rows = list(session.execute(select(ViolationRecord)).scalars())
        api_by_id = {row.id: record_view.full_record(session, row) for row in rows}
        review_map: dict[str, list] = {}
        for row in session.execute(select(ReviewHistory)).scalars():
            review_map.setdefault(row.violation_id, []).append(row)

    print(f"[reconcile] JS 期望 {len(js_by_id)} 条 / 库内 {len(api_by_id)} 条")

    # 1) 集合一致性
    missing = sorted(set(js_by_id) - set(api_by_id))
    extra = sorted(set(api_by_id) - set(js_by_id))
    if missing:
        print(f"  ✗ 库内缺失 {len(missing)} 条：{missing[:5]}")
    if extra:
        print(f"  ✗ 库内多出 {len(extra)} 条：{extra[:5]}")

    # 2) 逐条字段对账
    mismatches: list[tuple[str, list[str]]] = []
    for record_id, js in js_by_id.items():
        api = api_by_id.get(record_id)
        if api is None:
            continue
        diffs = compare_record(js, api)
        if diffs:
            mismatches.append((record_id, diffs))

    print(f"[reconcile] 字段逐条对账：不一致 {len(mismatches)} 条")
    for record_id, diffs in mismatches[: args.max_diff_print]:
        print(f"  ✗ {record_id}")
        for diff in diffs:
            print(f"      - {diff}")

    # 3) review_history ≡ seedReviewHistory（老记录用 reviewer/review_remark 补一条轨迹）
    history_mismatch = 0
    for record_id, js in js_by_id.items():
        rows = sorted(review_map.get(record_id, []), key=lambda r: r.seq)
        if js["status"] == "pending":
            expected_len = 0
        else:
            expected_len = 1
        if len(rows) != expected_len:
            history_mismatch += 1
            continue
        if expected_len == 1:
            row = rows[0]
            exp_action = "approve" if js["status"] == "approved" else "reject"
            if not (
                row.action == exp_action
                and row.reviewer == js["reviewer"]
                and row.remark == (js["review_remark"] or "")
                and row.event_time == js["review_time"]
            ):
                history_mismatch += 1
    print(f"[reconcile] review_history 与 seedReviewHistory 语义：不一致 {history_mismatch} 条")

    # 4) clamp 报告 + 「无未来复核时间」断言
    future_in_db = [(rid, api.get("review_time")) for rid, api in api_by_id.items()
                    if api.get("review_time") and api["review_time"] > now_str]
    clamped_js = [
        rid for rid, js in unclamped_by_id.items()
        if js.get("review_time") and js["review_time"] > now_str
    ]
    actually_clamped = [
        rid for rid in clamped_js
        if api_by_id.get(rid, {}).get("review_time") == now_str
    ]
    print(f"[reconcile] 未 clamp 的 JS 中 review_time>now 的行：{len(clamped_js)} 条")
    print(f"[reconcile] 其中被 clamp 到 now（库内 review_time==now）：{len(actually_clamped)} 条")
    print(f"[reconcile] 库内仍存在 review_time>now 的行：{len(future_in_db)} 条")
    for rid, value in future_in_db[: args.max_diff_print]:
        print(f"  ✗ {rid} review_time={value}")

    ok = (
        not missing and not extra and not mismatches and not history_mismatch
        and not future_in_db and len(clamped_js) == len(actually_clamped)
    )
    print("\n[reconcile] 结果：" + ("PASS ✓（库内数据与原始 JS 算法逐条一致，且无未来复核时间）" if ok else "FAIL ✗"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
