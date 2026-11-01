#!/usr/bin/env python3
"""回归测试：build_jsonfeed 不得让已发布同版本表示漂移（2026-11-01 修正）。

背景：10b9e95 曾给全部 420 条同版本条目补上 date_modified，导致下游
对已接收旧版本 raw 哈希判 384 条 VIDEO_EVENT_CONFLICT（仅 date_modified
差异）。正确的规则是按上一已发布 feed 以 (id, version) 保留该字段的
存在性与值；无基线时不给旧条目擅自新增字段。

断言：
1. 同版本旧条目：基线无 date_modified 时，即使 items.json 有该值，
   输出也不得补上（不漂移）；
2. Artemis：基线 (v2) 有 date_modified=2026-10-31T21:24:22+08:00 时，
   输出原值保留、_version 仍为 2；
3. 新条目：基线中无该 (id, version)，按规范输出 items.json 的值；
4. 升版条目：基线只有 v1、现为 v2 时，按规范输出新值；
5. 无基线：旧条目（pub_date 非北京时间当天）不新增字段，
   当天新条目按规范输出；
6. 不动点：以上一轮输出作基线再生成，结果逐字节一致（下轮不漂移）。

用法：PYTHONDONTWRITEBYTECODE=1 python3 test_feed_preserves_date_modified.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_feed  # noqa: E402

BJ = timezone(timedelta(hours=8))


def _fixture(item_id, version, date_modified, pub_date):
    it = {
        "id": item_id,
        "download_url": "https://example.invalid/video.mp4",
        "title": "fixture",
        "summary_cn": "fixture summary",
        "category": "文化/艺术",
        "community": "Design Worth Noticing",
        "license": "Public domain",
        "attribution": "无需署名",
        "reels_angle": "fixture angle",
        "trend_hook": "fixture hook",
        "duration_s": 30.0,
        "width": 1920,
        "height": 1080,
        "bytes": 1000000,
        "mime": "video/mp4",
        "pub_date": pub_date,
        "status": "active",
        "version": version,
    }
    if date_modified is not None:
        it["date_modified"] = date_modified
    return it


def _baseline_entry(item_id, version, date_modified):
    e = {"id": item_id, "_version": version}
    if date_modified is not None:
        e["date_modified"] = date_modified
    return e


def _out(items, baseline):
    return json.loads(build_feed.build_jsonfeed(items, "https://example.invalid", baseline))


def main():
    today = datetime.now(BJ).date().isoformat()
    yesterday = (datetime.now(BJ).date() - timedelta(days=1)).isoformat()
    old_pub = yesterday + "T09:00:00+08:00"
    new_pub = today + "T09:00:00+08:00"

    baseline = {"items": [
        _baseline_entry("old-no-field", 1, None),
        _baseline_entry("art-artemis-flyby-viz-20261031", 2, "2026-10-31T21:24:22+08:00"),
        _baseline_entry("bump-item", 1, None),
    ]}
    items = [
        _fixture("old-no-field", 1, "2026-10-30T10:00:00+08:00", old_pub),
        _fixture("art-artemis-flyby-viz-20261031", 2, "2026-10-31T21:24:22+08:00", "2026-10-31T09:34:49+08:00"),
        _fixture("brand-new", 1, "2026-11-01T10:00:00+08:00", new_pub),
        _fixture("bump-item", 2, "2026-11-01T11:00:00+08:00", old_pub),
    ]
    by_id = {x["id"]: x for x in _out(items, baseline)["items"]}

    # 1. 同版本旧条目不漂移
    assert "date_modified" not in by_id["old-no-field"], "old same-version item must NOT gain date_modified"
    assert by_id["old-no-field"]["_version"] == 1
    # 2. Artemis 原值保留
    assert by_id["art-artemis-flyby-viz-20261031"].get("date_modified") == "2026-10-31T21:24:22+08:00"
    assert by_id["art-artemis-flyby-viz-20261031"]["_version"] == 2
    # 3. 新条目按规范输出
    assert by_id["brand-new"].get("date_modified") == "2026-11-01T10:00:00+08:00"
    # 4. 升版按规范输出新值
    assert by_id["bump-item"].get("date_modified") == "2026-11-01T11:00:00+08:00"
    assert by_id["bump-item"]["_version"] == 2

    # 5. 无基线：旧条目不新增，当天新条目按规范
    by_id2 = {x["id"]: x for x in _out([
        _fixture("old-no-baseline", 1, "2026-10-30T10:00:00+08:00", old_pub),
        _fixture("new-no-baseline", 1, "2026-11-01T10:00:00+08:00", new_pub),
    ], None)["items"]}
    assert "date_modified" not in by_id2["old-no-baseline"], "no baseline: old item must NOT gain date_modified"
    assert by_id2["new-no-baseline"].get("date_modified") == "2026-11-01T10:00:00+08:00"

    # 6. 不动点：以上轮输出作基线再生成，结果一致
    out1 = build_feed.build_jsonfeed(items, "https://example.invalid", baseline)
    out2 = build_feed.build_jsonfeed(items, "https://example.invalid", json.loads(out1))
    assert out1 == out2, "regeneration from its own output as baseline must be byte-identical"
    print("test_feed_preserves_date_modified: PASS (6 groups)")


if __name__ == "__main__":
    main()
