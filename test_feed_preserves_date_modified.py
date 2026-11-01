#!/usr/bin/env python3
"""回归测试：build_jsonfeed 必须保留已发布的 date_modified 字段。

背景（2026-11-01）：art-artemis-flyby-viz-20261031 的 v2 修改（事件
evt-20261031-0658，date_modified=2026-10-31T21:24:22+08:00）在 status.json
中有该字段，但 build_jsonfeed 的输出字段白名单里没有 date_modified，
导致 feed.json 的同版本表示缺字段，下游同版本内容哈希检查判
VIDEO_EVENT_CONFLICT，游标卡在 658。

断言：
1. 源条目有 date_modified 时，feed 条目必须原值保留；
2. 源条目没有 date_modified 时，feed 条目不得凭空捏造该字段；
3. 同源连续两次生成结果必须逐字节一致（重跑不丢字段）。

用法：PYTHONDONTWRITEBYTECODE=1 python3 test_feed_preserves_date_modified.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_feed  # noqa: E402


def _fixture(item_id, version, date_modified):
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
        "pub_date": "2026-10-31T09:34:49+08:00",
        "status": "active",
        "version": version,
    }
    if date_modified is not None:
        it["date_modified"] = date_modified
    return it


def main():
    v2 = _fixture("art-artemis-flyby-viz-20261031", 2, "2026-10-31T21:24:22+08:00")
    v1 = _fixture("fixture-v1-no-modified", 1, None)
    out1 = build_feed.build_jsonfeed([v2, v1], "https://example.invalid")
    feed = json.loads(out1)
    by_id = {x["id"]: x for x in feed["items"]}
    assert by_id[v2["id"]].get("date_modified") == "2026-10-31T21:24:22+08:00", (
        "v2 feed entry lost date_modified: %r" % (by_id[v2["id"]].get("date_modified"),)
    )
    assert by_id[v2["id"]].get("_version") == 2, "v2 _version must stay 2"
    assert "date_modified" not in by_id[v1["id"]], (
        "must not invent date_modified for an item that has none"
    )
    out2 = build_feed.build_jsonfeed([v2, v1], "https://example.invalid")
    assert out1 == out2, "regeneration from the same source must be byte-identical"
    print("test_feed_preserves_date_modified: PASS (3 assertions)")


if __name__ == "__main__":
    main()
