#!/usr/bin/env python3
"""Tests for build_daily_stats.py. Uses synthetic fixtures in /tmp only.
Never touches the real 139-event history.
Run: python3 test_build_daily_stats.py
"""
import json, os, sys, tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_daily_stats import build, SH, parse_ts

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail and not cond else ""))


def write_fixture(d, items, events):
    json.dump(items, open(os.path.join(d, "items.json"), "w"), ensure_ascii=False)
    json.dump({"event_count": len(events), "next_seq": max(e["seq"] for e in events) + 1 if events else 1,
               "events": events},
              open(os.path.join(d, "changelog.json"), "w"), ensure_ascii=False)


def item(iid, cat, status="active", is_test=False):
    it = {"id": iid, "category": cat, "status": status, "title": "t"}
    if is_test:
        it["is_test"] = True
    return it


def ev(seq, iid, typ, status, occurred_at, version=1, is_test=False):
    e = {"event_id": f"evt-test-{seq:04d}", "seq": seq, "item_id": iid, "version": version,
         "type": typ, "status": status, "occurred_at": occurred_at,
         "reason": "test", "changed_fields": None}
    if is_test:
        e["is_test"] = True
    return e


def now_at(s):
    return parse_ts(s)


# ---------- 1. zero-new completed day ----------
d = tempfile.mkdtemp()
write_fixture(d,
    [item("a1", "科技/新闻"), item("a2", "影视/文化")],
    [ev(1, "a1", "added", "active", "2026-10-10T10:00:00+08:00"),
     ev(2, "a2", "added", "active", "2026-10-10T11:00:00+08:00")])
s = build(d, "2026-10-11", now_at("2026-10-12T09:00:00+08:00"))
check("zero-new: update_completed true", s["update_completed"] is True)
check("zero-new: all counts 0",
      s["total_events_today"] == 0 and all(v["added"] == 0 and v["modified"] == 0 for v in s["categories"].values()))
check("zero-new: last_event_seq is valid int", isinstance(s["last_event_seq"], int) and s["last_event_seq"] == 2,
      f"got {s['last_event_seq']!r}")
check("zero-new: opening==closing==2", s["opening_inventory"] == 2 and s["closing_inventory"] == 2)

# ---------- 2. test-only day ----------
d = tempfile.mkdtemp()
write_fixture(d,
    [item("a1", "科技/新闻"), item("t1", "科技/新闻", "retracted", True)],
    [ev(1, "a1", "added", "active", "2026-10-10T10:00:00+08:00"),
     ev(2, "t1", "added", "active", "2026-10-11T10:00:00+08:00", is_test=True),
     # retraction WITHOUT event-level marker: item-level is_test must still exclude it
     ev(3, "t1", "retracted", "retracted", "2026-10-11T11:00:00+08:00")])
s = build(d, "2026-10-11", now_at("2026-10-12T09:00:00+08:00"))
check("test-only: counts 0", s["total_events_today"] == 0 and s["closing_inventory"] == 1,
      f"events={s['total_events_today']} closing={s['closing_inventory']}")
check("test-only: last_event_seq covers test events", s["last_event_seq"] == 3,
      f"got {s['last_event_seq']!r}")

# ---------- 3. UTC midnight crossing (Shanghai) ----------
d = tempfile.mkdtemp()
write_fixture(d,
    [item("a1", "科技/新闻"), item("a2", "科技/新闻")],
    [ev(1, "a1", "added", "active", "2026-10-14T15:59:59+00:00"),   # = 10-14 23:59:59+08:00
     ev(2, "a2", "added", "active", "2026-10-14T23:30:00+00:00")])  # = 10-15 07:30:00+08:00
s14 = build(d, "2026-10-14", now_at("2026-10-16T09:00:00+08:00"))
s15 = build(d, "2026-10-15", now_at("2026-10-16T09:00:00+08:00"))
check("utc-cross: 15:59:59Z -> 10-14", s14["categories"]["科技/新闻"]["added"] == 1,
      f"got {s14['categories']['科技/新闻']['added']}")
check("utc-cross: 23:30:00Z -> 10-15", s15["categories"]["科技/新闻"]["added"] == 1,
      f"got {s15['categories']['科技/新闻']['added']}")

# ---------- 4. historical date rebuild ----------
d = tempfile.mkdtemp()
write_fixture(d,
    [item("a1", "科技/新闻"), item("a2", "影视/文化", "retracted"), item("a3", "科技/新闻")],
    [ev(1, "a1", "added", "active", "2026-10-10T10:00:00+08:00"),
     ev(2, "a2", "added", "active", "2026-10-11T10:00:00+08:00"),
     ev(3, "a2", "retracted", "retracted", "2026-10-12T10:00:00+08:00"),
     ev(4, "a3", "added", "active", "2026-10-13T10:00:00+08:00")])
s = build(d, "2026-10-12", now_at("2026-10-14T09:00:00+08:00"))
check("historical: opening==2 (a1,a2 active at 10-12 00:00)", s["opening_inventory"] == 2,
      f"got {s['opening_inventory']}")
check("historical: closing==1 (a2 retracted during day)", s["closing_inventory"] == 1,
      f"got {s['closing_inventory']}")
check("historical: retracted counted", s["categories"]["影视/文化"]["retracted"] == 1)
check("historical: stats_until == end of day",
      s["stats_until"] == "2026-10-13T00:00:00+08:00", f"got {s['stats_until']}")
check("historical: reconciliation 2-1==1", s["closing_inventory"] - s["opening_inventory"] == -1)

# ---------- 5. same-ID multiple modified dedup ----------
d = tempfile.mkdtemp()
write_fixture(d,
    [item("a1", "科技/新闻")],
    [ev(1, "a1", "added", "active", "2026-10-10T10:00:00+08:00"),
     ev(2, "a1", "modified", "active", "2026-10-11T10:00:00+08:00", version=2),
     ev(3, "a1", "modified", "active", "2026-10-11T15:00:00+08:00", version=3)])
s = build(d, "2026-10-11", now_at("2026-10-12T09:00:00+08:00"))
check("dedup: one ID two modifieds -> count 1",
      s["categories"]["科技/新闻"]["modified"] == 1,
      f"got {s['categories']['科技/新闻']['modified']}")

# ---------- 6. future date refused ----------
d = tempfile.mkdtemp()
write_fixture(d, [item("a1", "科技/新闻")],
              [ev(1, "a1", "added", "active", "2026-10-10T10:00:00+08:00")])
try:
    build(d, "2026-10-20", now_at("2026-10-12T09:00:00+08:00"))
    check("future date refused", False, "no error raised")
except ValueError:
    check("future date refused", True)

# ---------- 7. empty history ----------
d = tempfile.mkdtemp()
write_fixture(d, [], [])
s = build(d, "2026-10-11", now_at("2026-10-12T09:00:00+08:00"))
check("empty history: last_event_seq==0", s["last_event_seq"] == 0, f"got {s['last_event_seq']!r}")
check("empty history: inventories 0", s["opening_inventory"] == 0 and s["closing_inventory"] == 0)

print()
failed = [r for r in results if r[0] == FAIL]
print(f"{len(results)-len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
