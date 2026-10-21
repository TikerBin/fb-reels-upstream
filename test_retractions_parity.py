#!/usr/bin/env python3
"""撤回事件对等性回归测试：retractions.json 中每个事件必须与 changelog.json
中同 seq 的权威事件逐字段 deep-equal（含 _retracted 块）。2026-10-21 seq327/328
出生即分叉（changelog 副本缺 _retracted）导致下游 VIDEO_EVENT_CONFLICT 后新增。"""
import json, os, sys

UP = os.path.dirname(os.path.abspath(__file__))

def main():
    cl = {e["seq"]: e for e in json.load(open(os.path.join(UP, "changelog.json")))["events"]}
    rt = json.load(open(os.path.join(UP, "retractions.json")))
    fails = []
    if rt["count"] != len(rt["events"]):
        fails.append(f"retractions count={rt['count']} != events {len(rt['events'])}")
    for e in rt["events"]:
        s = e["seq"]
        if s not in cl:
            fails.append(f"seq{s} 在 changelog 中不存在")
        elif e != cl[s]:
            only_r = {k for k in e if cl[s].get(k) != e[k]}
            only_c = {k for k in cl[s] if e.get(k) != cl[s][k]}
            fails.append(f"seq{s} 与 changelog 不一致: retractions独有/不同 {only_r}, changelog独有/不同 {only_c}")
        if e["type"] == "retracted" and "_retracted" not in e:
            fails.append(f"seq{s} 撤回事件缺 _retracted 块")
    if fails:
        print(f"{len(fails)} failed:")
        [print(" -", f) for f in fails]
        return 1
    print(f"{len(rt['events'])} retraction events parity-checked, 0 failed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
