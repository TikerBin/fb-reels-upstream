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
    """追加事件后调用：从 events 数组重算全部派生字段。"""
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


def assert_history_unchanged(published, candidate):
    """与独立的已发布基线比较；历史事件任何字段都不可改写，只能追加。"""
    for label, document in (("published", published), ("candidate", candidate)):
        if not isinstance(document, dict) or not isinstance(document.get("events"), list):
            raise AssertionError(f"{label}: events 必须为数组，不能省略历史基线")
        assert_envelope(document, label=label)
        if any(type(e["seq"]) is not int for e in document["events"]):
            raise AssertionError(f"{label}: seq 必须为整数")
    old, new = published["events"], candidate["events"]
    if len(new) < len(old):
        raise AssertionError(f"历史事件被删除：已发布 {len(old)} 条，候选仅 {len(new)} 条")

    def encode(value):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    for previous, current in zip(old, new):
        # JSON 规范化忽略键顺序/排版，但区分 true/1、缺失/null，包含未知字段及嵌套数据。
        if encode(previous) != encode(current):
            fields = sorted(
                key for key in previous.keys() | current.keys()
                if key not in previous or key not in current
                or encode(previous[key]) != encode(current[key])
            )
            raise AssertionError(
                f"历史事件不可改写：seq={previous['seq']}，字段={','.join(fields)}；"
                "更正必须追加新 seq/event_id，不得修改原事件"
            )
    return True
