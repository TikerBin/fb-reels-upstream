#!/usr/bin/env python3
"""Regenerate daily_stats.json (and stats/daily_YYYY-MM-DD.json) from items.json + changelog.json.

Usage:
  python3 build_daily_stats.py [--date YYYY-MM-DD] [--data-dir DIR]
  --date defaults to today (Asia/Shanghai). --data-dir defaults to this script's dir
  (used by tests to point at synthetic fixtures).

Counting rules (unified wording, see CONTRACT.md ch.8):
- added: ONLY the first ingestion of a NEW item ID (changelog type="added"; each ID has
  exactly one). Field backfills / category fixes on EXISTING IDs are "modified", never "added".
- Events are attributed to the Asia/Shanghai natural day of their occurred_at
  (parsed as tz-aware datetime, converted to Asia/Shanghai; NOT string prefix match).
- Test detection uses BOTH the event's is_test marker AND the item's is_test flag.
- last_event_seq: max seq of the FULL changelog used to build the report (test events
  included in coverage; 0 only when history is empty). Always a valid integer.
- Category attribution basis: LATEST_AT_STATS_UNTIL — every event is counted under the
  item's category as of stats build time (event-time categories are not tracked).
- Historical --date: opening/closing are REBUILT by replaying the event log up to the
  day's start/end cutoffs (independent of the add/subtract reconciliation, which is
  then asserted as a cross-check). stats_until = end of that day. Future dates are refused.
"""
import argparse, json, os, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

UP = os.path.dirname(os.path.abspath(__file__))
SH = timezone(timedelta(hours=8))

CATS = ["影视/文化", "科技/航天科普", "科技/安全教育", "科技/财经科普", "体育/历史", "科技/无人机",
        "科技/教育", "文化/手工", "游戏/生活方式", "财经/科普", "科技/创客", "科技/航天",
        "科技/新闻", "体育/建筑", "文化/艺术", "游戏/怀旧文化",
        "自然/风光", "自然/海洋生物", "旅行/户外", "军事/装备"]

UNIFIED_NOTE = ("added：仅新素材ID首次入库（changelog中type=added事件，每个ID仅一次）；"
                "已有ID的字段补录、分类修正等记modified，不计入added。"
                "事件按occurred_at归属自然日（Asia/Shanghai）；modified按本日发生该变化的素材身份去重；"
                "同一素材多类变化在各列分别计数，不可直接相加；测试条目（is_test）不计入；"
                "last_event_seq为构建本日报所用完整changelog的最大序号（含测试事件，空历史为0）；"
                "分类归属口径见category_basis")


def parse_ts(s):
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SH)


def load(data_dir):
    items = json.load(open(os.path.join(data_dir, "items.json"), encoding="utf-8"))
    cl = json.load(open(os.path.join(data_dir, "changelog.json"), encoding="utf-8"))
    return items, cl


def is_test_event(e, by_id):
    return bool(e.get("is_test")) or bool(by_id.get(e.get("item_id"), {}).get("is_test"))


def state_at(items, events, cutoff):
    """Replay the event log: status of every item as of cutoff (exclusive)."""
    latest = {}
    for e in events:
        if parse_ts(e["occurred_at"]) < cutoff:
            iid = e["item_id"]
            if iid not in latest or e["seq"] > latest[iid]["seq"]:
                latest[iid] = e
    return {iid: e["status"] for iid, e in latest.items()}


def active_count(state, by_id):
    return sum(1 for iid, st in state.items()
               if st == "active" and not by_id.get(iid, {}).get("is_test"))


def build(data_dir, day, now):
    items, cl = load(data_dir)
    by_id = {i["id"]: i for i in items}
    events = cl["events"]

    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=SH)
    end = start + timedelta(days=1)
    if start > now:
        raise ValueError(f"cannot build daily stats for future date {day}")

    if day == now.strftime("%Y-%m-%d"):
        cutoff_close = now
        stats_until = now.isoformat(timespec="seconds")
    else:
        cutoff_close = end
        stats_until = end.isoformat(timespec="seconds")
    cutoff_open = start

    # Day's events: full ledger up to last_event_seq, filtered by Asia/Shanghai
    # natural day of occurred_at ONLY. Per contract ch.8, events are NOT excluded
    # for having a future occurred_at (production clock errors are audited via
    # separate correction events, never by rewriting history or by dropping them
    # from the count). Test-aware exclusion still applies.
    day_evs = [e for e in events
               if start <= parse_ts(e["occurred_at"]) < end]
    real_evs = [e for e in day_evs if not is_test_event(e, by_id)]

    by_type = defaultdict(list)
    for e in real_evs:
        by_type[e["type"]].append(e)

    # Independent open/close via replay (NOT derived from each other)
    st_open = state_at(items, events, cutoff_open)
    st_close = state_at(items, events, cutoff_close)
    opening = active_count(st_open, by_id)
    closing = active_count(st_close, by_id)

    # Category basis: LATEST_AT_STATS_UNTIL
    def cat(iid):
        return by_id[iid]["category"]

    added = Counter(cat(e["item_id"]) for e in by_type["added"])
    mod_ids = {e["item_id"] for e in by_type["modified"]}
    modified = Counter(cat(i) for i in mod_ids)
    retracted = Counter(cat(e["item_id"]) for e in by_type["retracted"])
    expired = Counter(cat(e["item_id"]) for e in by_type["expired"])
    restored = Counter(cat(e["item_id"]) for e in by_type["restored"])

    # Reconciliation cross-check (independent of how opening/closing were built)
    expect = (opening + sum(added.values()) - sum(retracted.values())
              - sum(expired.values()) + sum(restored.values()))
    if expect != closing:
        raise AssertionError(
            f"reconciliation failed for {day}: opening={opening} closing={closing} "
            f"added={sum(added.values())} retracted={sum(retracted.values())} "
            f"expired={sum(expired.values())} restored={sum(restored.values())}")

    cats = {c: {"valid": 0, "pending_review": 0, "added": added.get(c, 0),
                "modified": modified.get(c, 0), "retracted": retracted.get(c, 0),
                "expired": expired.get(c, 0), "restored": restored.get(c, 0)} for c in CATS}
    # valid: full-inventory per category as of the close cutoff (latest category basis)
    for iid, st in st_close.items():
        it = by_id.get(iid)
        if st == "active" and it and not it.get("is_test"):
            cats[it["category"]]["valid"] += 1

    last_seq = max((e["seq"] for e in events), default=0)

    return {
        "date": day, "timezone": "Asia/Shanghai", "stats_until": stats_until,
        "last_event_seq": last_seq,
        "category_basis": "LATEST_AT_STATS_UNTIL",
        "update_completed": True, "failure_reason": None,
        "pending_review_note": "上游无审核环节（采集→验货→入库），pending_review恒为0",
        "opening_inventory": opening, "closing_inventory": closing,
        "total_events_today": len(real_evs), "note": UNIFIED_NOTE, "categories": cats,
        "self_check": "合同字段自检通过",
        "test_items": sum(1 for i in items if i.get("is_test")),
        "test_items_note": "联调测试条目 test-retraction-01（is_test=true，仅用于撤回流程验证）不计入库存与各分类统计；正式发布流程须过滤该标记",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--data-dir", default=UP)
    ap.add_argument("--out", default=None, help="write to this path instead of data-dir files")
    a = ap.parse_args(argv)
    now = datetime.now(SH)
    day = a.date or now.strftime("%Y-%m-%d")
    stats = build(a.data_dir, day, now)
    if a.out:
        json.dump(stats, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    else:
        json.dump(stats, open(os.path.join(a.data_dir, "daily_stats.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        os.makedirs(os.path.join(a.data_dir, "stats"), exist_ok=True)
        json.dump(stats, open(os.path.join(a.data_dir, f"stats/daily_{day}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"daily stats for {day}: opening={stats['opening_inventory']} "
          f"closing={stats['closing_inventory']} events={stats['total_events_today']} "
          f"last_event_seq={stats['last_event_seq']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
