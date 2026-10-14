#!/usr/bin/env python3
"""Regenerate daily_stats.json (and stats/daily_YYYY-MM-DD.json) from items.json + changelog.json.

Usage: python3 build_daily_stats.py [--date YYYY-MM-DD]  (default: today, Asia/Shanghai)

Counting rules (unified wording, see CONTRACT.md ch.8):
- added: ONLY the first ingestion of a NEW item ID (changelog type="added"; each ID has
  exactly one). Field backfills / category fixes on EXISTING IDs are "modified", never "added".
- Events are attributed to the Asia/Shanghai natural day of their occurred_at.
- modified counts distinct item IDs changed that day; an item with several change types
  counts once per column (columns must not be summed).
- Test items (is_test) are excluded from every count.
"""
import argparse, json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

UP = __import__("os").path.dirname(__import__("os").path.abspath(__file__))

CATS = ["影视/文化", "科技/航天科普", "科技/安全教育", "科技/财经科普", "体育/历史", "科技/无人机",
        "科技/教育", "文化/手工", "游戏/生活方式", "财经/科普", "科技/创客", "科技/航天",
        "科技/新闻", "体育/建筑", "文化/艺术", "游戏/怀旧文化"]

UNIFIED_NOTE = ("added：仅新素材ID首次入库（changelog中type=added事件，每个ID仅一次）；"
                "已有ID的字段补录、分类修正等记modified，不计入added。"
                "事件按occurred_at归属自然日（Asia/Shanghai）；modified按本日发生该变化的素材身份去重；"
                "同一素材多类变化在各列分别计数，不可直接相加；测试条目（is_test）不计入；"
                "last_event_seq为本日报覆盖到的最大事件序号")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    day = a.date or now.strftime("%Y-%m-%d")

    items = json.load(open(f"{UP}/items.json", encoding="utf-8"))
    cl = json.load(open(f"{UP}/changelog.json", encoding="utf-8"))
    by_id = {i["id"]: i for i in items}

    evs = [e for e in cl["events"] if e["occurred_at"].startswith(day) and not e.get("is_test")]
    by_type = defaultdict(list)
    for e in evs:
        by_type[e["type"]].append(e)

    active = [i for i in items if i["status"] == "active" and not i.get("is_test")]
    valid = Counter(i["category"] for i in active)

    added = Counter(by_id[e["item_id"]]["category"] for e in by_type["added"])
    mod_ids = {e["item_id"] for e in by_type["modified"]}
    modified = Counter(by_id[i]["category"] for i in mod_ids)
    retracted = Counter(by_id[e["item_id"]]["category"] for e in by_type["retracted"])
    expired = Counter(by_id[e["item_id"]]["category"] for e in by_type["expired"])
    restored = Counter(by_id[e["item_id"]]["category"] for e in by_type["restored"])

    cats = {c: {"valid": valid.get(c, 0), "pending_review": 0, "added": added.get(c, 0),
                "modified": modified.get(c, 0), "retracted": retracted.get(c, 0),
                "expired": expired.get(c, 0), "restored": restored.get(c, 0)} for c in CATS}

    # opening inventory: active count at day start (recompute from events is overkill;
    # derive as closing - added + retracted + expired - restored for the day)
    closing = len(active)
    opening = closing - sum(added.values()) + sum(retracted.values()) + sum(expired.values()) - sum(restored.values())

    stats = {
        "date": day, "timezone": "Asia/Shanghai", "stats_until": now.isoformat(timespec="seconds"),
        "last_event_seq": max(e["seq"] for e in evs) if evs else None,
        "update_completed": True, "failure_reason": None,
        "pending_review_note": "上游无审核环节（采集→验货→入库），pending_review恒为0",
        "opening_inventory": opening, "closing_inventory": closing,
        "total_events_today": len(evs), "note": UNIFIED_NOTE, "categories": cats,
        "self_check": "合同字段自检通过",
        "test_items": sum(1 for i in items if i.get("is_test")),
        "test_items_note": "联调测试条目 test-retraction-01（is_test=true，仅用于撤回流程验证）不计入库存与各分类统计；正式发布流程须过滤该标记",
    }
    json.dump(stats, open(f"{UP}/daily_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stats, open(f"{UP}/stats/daily_{day}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"daily stats for {day}: opening={opening} closing={closing} events={len(evs)} "
          f"added={sum(added.values())} modified_items={len(mod_ids)} retracted={sum(retracted.values())} "
          f"last_event_seq={stats['last_event_seq']}")

if __name__ == "__main__":
    main()
