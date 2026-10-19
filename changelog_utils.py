"""changelog.json 信封字段统一维护。

根因（2026-10-19）：10-18 / 10-19 的入库脚本追加事件后只更新了 next_seq，
漏掉了 event_count（及 updated_at），导致下游严格校验 event_count == len(events)
失败（228 != 249），第二、三批视频被拦。

规则：
- 只追加新事件，不得修改既有已分发事件；追加后必须调用 recompute_envelope()。
- event_count / next_seq / updated_at 都是派生字段，永远由 events 数组重算，
  禁止手写、禁止沿用旧值。
- 上传（git commit/push）之前必须调用 assert_envelope()，不通过则中断发布。

已分发事件（seq 1..N）本身不可改写：本模块只动信封字段，不碰 events 数组。
"""

import json


def recompute_envelope(cl, now_iso):
    """追加/修改事件后调用：从 events 数组重算全部派生字段。"""
    events = cl.get("events", [])
    seqs = [e["seq"] for e in events]
    cl["event_count"] = len(events)
    cl["next_seq"] = max(seqs) + 1 if seqs else 1
    cl["updated_at"] = now_iso
    return cl


def assert_envelope(cl, label="changelog.json"):
    """发布前断言：信封字段必须与 events 数组一致。违规则抛错中断发布。"""
    events = cl.get("events", [])
    n = len(events)
    if cl.get("event_count") != n:
        raise AssertionError(
            f"{label}: event_count={cl.get('event_count')} != len(events)={n}，"
            "发布前必须先调用 recompute_envelope() 重算"
        )
    seqs = [e["seq"] for e in events]
    expect_next = max(seqs) + 1 if seqs else 1
    if cl.get("next_seq") != expect_next:
        raise AssertionError(
            f"{label}: next_seq={cl.get('next_seq')} != max(seq)+1={expect_next}"
        )
    if seqs != list(range(1, n + 1)):
        raise AssertionError(f"{label}: seq 不连续或有重复/断号（共 {n} 条）")
    eids = [e["event_id"] for e in events]
    if len(eids) != len(set(eids)):
        raise AssertionError(f"{label}: event_id 有重复")
    if not cl.get("updated_at"):
        raise AssertionError(f"{label}: updated_at 缺失")
    return True


def load_and_assert(path):
    with open(path, encoding="utf-8") as f:
        cl = json.load(f)
    assert_envelope(cl, label=path)
    return cl
