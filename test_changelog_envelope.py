"""changelog 信封字段回归测试。

覆盖 2026-10-19 事故：追加事件后漏更新 event_count，下游严格校验
event_count == len(events) 失败。

本文件随提交包进入 upstream-repo，在干净克隆中独立运行：
- 所有路径相对本文件所在目录，不依赖外部私有文件；
- 不硬编码任何一轮的具体数字（249/37/99 等），合法的未来追加
  （250/251…）必须正常通过；
- 本文件的前缀测试只检查追加函数自身；跨版本历史审计必须运行
  validate_history.py，对照独立的已发布 Git 基线，不能用当前文件自证。

运行：python3 test_changelog_envelope.py
通过返回 0，任一失败返回非 0 并打印原因。
"""

import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import changelog_utils as u  # noqa: E402

BJ = timezone(timedelta(hours=8))

passed = []
failed = []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"PASS {name}")
    except Exception as e:  # noqa: BLE001
        failed.append(name)
        print(f"FAIL {name}: {e}")


def ev_hash(e):
    return hashlib.sha256(
        json.dumps(e, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def make_fixture(n, stale_count=None):
    events = [
        {
            "event_id": f"evt-20261019-{s:04d}",
            "seq": s,
            "item_id": f"item-{s}",
            "version": 1,
            "type": "added",
            "status": "active",
            "occurred_at": "2026-10-19T09:40:59+08:00",
            "reason": "fixture",
        }
        for s in range(1, n + 1)
    ]
    return {
        "updated_at": "2026-10-17T22:21:24+08:00",
        "event_count": stale_count if stale_count is not None else n,
        "next_seq": n + 1,
        "events": events,
    }


def load_changelog():
    with open(os.path.join(BASE, "changelog.json"), encoding="utf-8") as f:
        return json.load(f)


# --- 单元：统一函数行为 ---
def t_recompute_fixes_stale():
    cl = make_fixture(249, stale_count=228)  # 复现 2026-10-19 事故现场
    try:
        u.assert_envelope(cl)
        raise RuntimeError("断言本应失败却通过了")
    except AssertionError:
        pass  # 预期：旧信封通不过
    u.recompute_envelope(cl, "2026-10-19T13:56:01+08:00")
    u.assert_envelope(cl)
    assert cl["event_count"] == 249 and cl["next_seq"] == 250


def t_recompute_after_append():
    cl = make_fixture(228)
    cl["events"].append(
        {
            "event_id": "evt-20261018-0229",
            "seq": 229,
            "item_id": "new-item",
            "version": 1,
            "type": "added",
            "status": "active",
            "occurred_at": "2026-10-18T09:54:40+08:00",
            "reason": "fixture append",
        }
    )
    u.recompute_envelope(cl, "2026-10-18T09:54:40+08:00")
    u.assert_envelope(cl)
    assert cl["event_count"] == 229 and cl["next_seq"] == 230


def t_assert_catches_gap_and_dupe():
    cl = make_fixture(10)
    bad = copy.deepcopy(cl)
    bad["events"] = [e for e in bad["events"] if e["seq"] != 5]  # 断号
    bad["event_count"] = 9
    try:
        u.assert_envelope(bad)
    except AssertionError:
        pass
    else:
        raise RuntimeError("断号未被发现")
    bad2 = copy.deepcopy(cl)
    bad2["events"][3]["seq"] = 3  # 与 seq=3 重复
    bad2["event_count"] = 10
    try:
        u.assert_envelope(bad2)
    except AssertionError:
        pass
    else:
        raise RuntimeError("重复 seq 未被发现")


# --- 真实文件：通用断言，不硬编码本轮数字 ---
def t_real_changelog_envelope_ok():
    cl = load_changelog()
    u.assert_envelope(cl, label="changelog.json")
    # 信封必须由 events 派生，不允许写死任何数字
    assert cl["event_count"] == len(cl["events"])
    assert cl["next_seq"] == max(e["seq"] for e in cl["events"]) + 1


def t_legal_append_keeps_prefix_hashes():
    """合法追加回归：当前 N 条正确 → 合法追加 1 条 →
    自动得到 N+1 / next N+2，且原 N 条哈希不变（只保护既有前缀）。"""
    cl = load_changelog()
    u.assert_envelope(cl, label="changelog.json")
    n0 = len(cl["events"])
    prefix_hashes = [ev_hash(e) for e in cl["events"]]
    nxt = cl["next_seq"]

    now = datetime.now(BJ).isoformat(timespec="seconds")
    cl["events"].append(
        {
            "event_id": f"evt-20990101-{nxt:04d}",
            "seq": nxt,
            "item_id": "future-legal-item",
            "version": 1,
            "type": "added",
            "status": "active",
            "occurred_at": now,
            "reason": "回归用例：合法追加",
        }
    )
    u.recompute_envelope(cl, now)
    u.assert_envelope(cl, label="changelog.json")
    assert cl["event_count"] == n0 + 1, (cl["event_count"], n0)
    assert cl["next_seq"] == nxt + 1, (cl["next_seq"], nxt)
    assert [ev_hash(e) for e in cl["events"][:n0]] == prefix_hashes, "既有前缀被改动"


def t_cross_file_consistency():
    cl = load_changelog()
    maxseq = max(e["seq"] for e in cl["events"])
    r = json.load(open(os.path.join(BASE, "retractions.json"), encoding="utf-8"))
    assert r["count"] == len(r["events"]), (r["count"], len(r["events"]))
    s = json.load(open(os.path.join(BASE, "status.json"), encoding="utf-8"))
    assert s["count"] == len(s["items"]), (s["count"], len(s["items"]))
    d = json.load(open(os.path.join(BASE, "daily_stats.json"), encoding="utf-8"))
    assert d["last_event_seq"] == maxseq, (d["last_event_seq"], maxseq)
    f = json.load(open(os.path.join(BASE, "feed.json"), encoding="utf-8"))
    assert len(f["items"]) <= 420, len(f["items"])


check("recompute 修复漏更新的信封", t_recompute_fixes_stale)
check("追加后重算 next_seq/event_count", t_recompute_after_append)
check("断言拦截断号与重复 seq", t_assert_catches_gap_and_dupe)
check("真实 changelog.json 信封一致", t_real_changelog_envelope_ok)
check("合法追加后前缀哈希不变", t_legal_append_keeps_prefix_hashes)
check("retractions/status/daily_stats/feed 交叉一致", t_cross_file_consistency)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
