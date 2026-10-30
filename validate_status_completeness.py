#!/usr/bin/env python3
"""推送前门禁：status 快照必须与不可变事件账本全集一致，历史素材不得消失。

2026-10-30 事故：每日入库脚本对 items.json 做 items[:420] 截断（把只属于
feed 窗口的 420 上限错用到库存），导致 13 条最老记录从 status.json 消失，
下游 FBAuto 报 VIDEO_EVENT_SNAPSHOT_INCOMPLETE。本脚本在每次生成后、推送前
运行，任一断言失败即退出非零，禁止推送。

检查（全部针对同一目录下的 changelog.json / status.json / feed.json /
retractions.json；默认取脚本所在目录，可传目录参数）：
  1. status ID 集合 == changelog 唯一 item_id 全集，且无重复；
  2. 每项 version/status == 该项最终事件（最大 seq）；
  3. status count 字段 == 实际条数（禁止只改 count 凑数）；
  4. feed 成员 == in_latest_feed 为真集合 == active 按 pub_date 倒序前 420；
  5. 撤回集合：status 撤回 == 账本撤回 == retractions.json；
  6. 合同字段：每项含 id/status/version/date_modified/title/summary_cn/
     category/community/license/attribution/download_url/pub_date；
     撤回项 retract_reason 非空且与 retractions.json 一致，active 项为空；
  7. feed 不超过 420 条且无重复；不重算、不改写任何文件，只读校验。
用法：python3 validate_status_completeness.py [目录]
"""
import json
import os
import sys

REQUIRED_STATUS_FIELDS = [
    "id", "status", "version", "date_modified", "title", "summary_cn",
    "category", "community", "license", "attribution", "download_url",
    "pub_date",
]
FEED_CAP = 420


def load(directory, name):
    with open(os.path.join(directory, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    directory = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    errors = []

    changelog = load(directory, "changelog.json")
    events = changelog["events"] if isinstance(changelog, dict) else changelog
    final = {}
    for e in sorted(events, key=lambda x: x["seq"]):
        final[e["item_id"]] = e
    ledger_ids = set(final)

    status = load(directory, "status.json")
    sentries = status["items"] if isinstance(status, dict) else status
    if isinstance(status, dict) and status.get("count") != len(sentries):
        errors.append(f"status count 字段={status.get('count')} 与实际条数 {len(sentries)} 不符")
    sids = [s["id"] for s in sentries]
    if len(sids) != len(set(sids)):
        errors.append("status 存在重复 id")
    if set(sids) != ledger_ids:
        errors.append(f"status 缺失账本 id: {sorted(ledger_ids - set(sids))}")
        errors.append(f"status 多余账本外 id: {sorted(set(sids) - ledger_ids)}")

    smap = {s["id"]: s for s in sentries}
    for sid, s in smap.items():
        f = final.get(sid)
        if f is None:
            continue
        if s.get("status") != f["status"] or s.get("version") != f["version"]:
            errors.append(f"{sid}: status/version 与最终事件不符 "
                          f"(status.json {s.get('status')}/v{s.get('version')} vs "
                          f"账本 {f['status']}/v{f['version']}, seq={f['seq']})")
        for fld in REQUIRED_STATUS_FIELDS:
            if not s.get(fld) and s.get(fld) != 0:
                errors.append(f"{sid}: 缺合同字段 {fld}")

    retractions = load(directory, "retractions.json")
    revents = retractions["events"] if isinstance(retractions, dict) else retractions
    rmap = {e["item_id"]: e.get("reason", "") for e in revents}
    ledger_retracted = {i for i, f in final.items() if f["status"] == "retracted"}
    status_retracted = {i for i, s in smap.items() if s.get("status") == "retracted"}
    if status_retracted != ledger_retracted:
        errors.append(f"status 撤回集合与账本不符: 缺 {sorted(ledger_retracted - status_retracted)} "
                      f"多 {sorted(status_retracted - ledger_retracted)}")
    if set(rmap) != ledger_retracted:
        errors.append("retractions.json 与账本撤回集合不符")
    for sid in status_retracted:
        s = smap[sid]
        if not s.get("retract_reason"):
            errors.append(f"{sid}: 已撤回但 retract_reason 为空")
        elif sid in rmap and s["retract_reason"] != rmap[sid]:
            errors.append(f"{sid}: retract_reason 与 retractions.json 不一致")
    for sid, s in smap.items():
        if s.get("status") == "active" and s.get("retract_reason"):
            errors.append(f"{sid}: active 但 retract_reason 非空")

    feed = load(directory, "feed.json")
    fitems = feed["items"] if isinstance(feed, dict) else feed
    fids = [i["id"] for i in fitems]
    if len(fids) != len(set(fids)):
        errors.append("feed 存在重复 id")
    if len(fids) > FEED_CAP:
        errors.append(f"feed {len(fids)} 条超过 {FEED_CAP} 上限")
    in_feed_flag = {i for i, s in smap.items() if s.get("in_latest_feed")}
    if set(fids) != in_feed_flag:
        errors.append(f"feed 成员与 in_latest_feed 不一致: feed 独有 {sorted(set(fids) - in_feed_flag)} "
                      f"标记独有 {sorted(in_feed_flag - set(fids))}")
    active_sorted = sorted(
        (s for s in smap.values() if s.get("status") == "active"),
        key=lambda s: s.get("pub_date", ""), reverse=True,
    )
    expected_feed = {s["id"] for s in active_sorted[:FEED_CAP]}
    if set(fids) != expected_feed:
        errors.append(f"feed 成员与 active 前 {FEED_CAP} 窗口不符: "
                      f"缺 {sorted(expected_feed - set(fids))} 多 {sorted(set(fids) - expected_feed)}")
    for fid in fids:
        if smap.get(fid, {}).get("status") != "active":
            errors.append(f"feed 含非 active 项: {fid}")

    print(f"ledger={len(ledger_ids)} status={len(sentries)} "
          f"feed={len(fids)} retracted={len(ledger_retracted)}")
    if errors:
        print("STATUS COMPLETENESS FAILED:")
        for e in errors:
            print(" - " + e)
        return 1
    print("STATUS COMPLETENESS OK: 历史素材无一消失，版本/状态/撤回/feed 成员全部与账本一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
