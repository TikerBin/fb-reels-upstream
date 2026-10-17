#!/usr/bin/env python3
"""Build feed.xml (RSS 2.0) and feed.json (JSON Feed 1.1) from upstream/items.json.

Usage: python3 build_feed.py [--base-url https://host/path]
The base URL is where feed.xml will be hosted; used for channel link/self links.
"""
import argparse, json, os
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape

UP = os.path.dirname(os.path.abspath(__file__))

def load_items():
    with open(os.path.join(UP, "items.json"), encoding="utf-8") as f:
        return json.load(f)

def rfc2822(iso):
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)

def build_verticals(items):
    """14 垂类可用素材总览（供下游判断当前有哪些类型的视频素材；含 0 的也列出）。
    判定规则：先看 community；同一社群下再按 category 拆分子垂类。"""
    VERTICALS = [
        ("新闻/财经", "Everyday News and Money Discussion"),
        ("AI", "AI Tools and Everyday Uses"),
        ("加密资产", "Crypto Beyond the Price"),
        ("无人系统", "Robotics and Automation Brief"),
        ("军事航空装备", "Robotics and Automation Brief"),
        ("科学", "Science Worth Understanding"),
        ("纯自然风景/野生动物", "Science Worth Understanding"),
        ("海洋生物/深海", "Science Worth Understanding"),
        ("网络安全", "Digital Safety Explained"),
        ("游戏", "Next Game Brief"),
        ("影视", "Screen Stories Brief"),
        ("体育", "Beyond the Score Brief"),
        ("国家公园旅行/户外", "Beyond the Score Brief"),
        ("艺术设计", "Design Worth Noticing"),
    ]

    def vertical_of(it):
        comm, cat = it.get("community"), it.get("category")
        if comm == "Robotics and Automation Brief":
            return "军事航空装备" if cat == "军事/装备" else "无人系统"
        if comm == "Science Worth Understanding":
            if cat == "自然/风光":
                return "纯自然风景/野生动物"
            if cat == "自然/海洋生物":
                return "海洋生物/深海"
            return "科学"
        if comm == "Beyond the Score Brief":
            return "国家公园旅行/户外" if cat == "旅行/户外" else "体育"
        for v, c in VERTICALS:
            if c == comm:
                return v
        return None

    counts = {v: 0 for v, _ in VERTICALS}
    for it in items:
        if it.get("is_test"):
            continue
        v = vertical_of(it)
        if v in counts:
            counts[v] += 1
    return [{"vertical": v, "community": c, "count": counts[v]} for v, c in VERTICALS]


def build_rss(items, base_url):
    now = format_datetime(datetime.now(timezone.utc))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0">', '<channel>']
    parts.append("<title>" + escape("FB Reels 每日素材上游") + "</title>")
    parts.append("<link>" + escape(base_url) + "</link>")
    parts.append("<description>" + escape("每日更新的 Facebook Reels 可用视频素材：下载地址、内容总结、内容类型、许可证。全部为公有领域或 CC 协议合法素材。") + "</description>")
    parts.append("<language>zh-CN</language>")
    parts.append("<lastBuildDate>" + now + "</lastBuildDate>")
    for it in items:
        desc = (
            "【内容总结】" + it["summary_cn"] + "<br/>"
            "【内容类型】" + it["category"] + "<br/>"
            "【对应社群】" + it["community"] + "<br/>"
            "【许可证】" + it["license"] + "（" + it["attribution"] + "）<br/>"
            "【Reels角度】" + it["reels_angle"] + "<br/>"
            "【热点挂钩】" + it["trend_hook"] + "<br/>"
            "【规格】" + str(it["duration_s"]) + "秒，" + str(it["width"]) + "x" + str(it["height"]) + "，约%.1fMB" % (it["bytes"] / 1048576)
        )
        parts.append("<item>")
        parts.append("<title>" + escape(it["title"]) + "</title>")
        parts.append("<link>" + escape(it["download_url"]) + "</link>")
        parts.append('<guid isPermaLink="false">' + escape(it["id"]) + "</guid>")
        parts.append("<pubDate>" + rfc2822(it["pub_date"]) + "</pubDate>")
        parts.append("<category>" + escape(it["category"]) + "</category>")
        parts.append("<category>" + escape(it["community"]) + "</category>")
        parts.append('<enclosure url="' + escape(it["download_url"]) + '" length="' + str(it["bytes"]) + '" type="' + escape(it["mime"]) + '"/>')
        parts.append("<description><![CDATA[" + desc + "]]></description>")
        parts.append("<_license>" + escape(it["license"]) + "</_license>")
        parts.append("<_attribution>" + escape(it["attribution"]) + "</_attribution>")
        if it.get("author"):
            parts.append("<_author>" + escape(it["author"]) + "</_author>")
        parts.append("<_source_url>" + escape(it.get("source_url") or "") + "</_source_url>")
        if it.get("_authorization"):
            parts.append("<_authorization_evidence_url>" + escape(it["_authorization"].get("evidence_url") or "") + "</_authorization_evidence_url>")
            parts.append("<_authorization_public_domain_basis>" + escape(it["_authorization"].get("public_domain_basis") or "") + "</_authorization_public_domain_basis>")
        if it.get("is_test"):
            parts.append("<_is_test>true</_is_test>")
        if it.get("license_url"):
            parts.append("<_license_url>" + escape(it.get("license_url")) + "</_license_url>")
        parts.append("</item>")
    parts += ["</channel>", "</rss>"]
    return "\n".join(parts) + "\n"

def build_jsonfeed(items, base_url):
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "FB Reels 每日素材上游",
        "home_page_url": base_url,
        "feed_url": base_url.rstrip("/") + "/feed.json",
        "description": "每日更新的 Facebook Reels 可用视频素材：下载地址、内容总结、内容类型、许可证。",
        "language": "zh-CN",
        "_verticals": build_verticals(items),
        "items": [],
    }
    for it in items:
        feed["items"].append({
            "id": it["id"],
            "url": it["download_url"],
            "title": it["title"],
            "summary": it["summary_cn"],
            "content_text": (
                "内容总结：" + it["summary_cn"] + "\n内容类型：" + it["category"] + "\n"
                "对应社群：" + it["community"] + "\n许可证：" + it["license"] + "（" + it["attribution"] + "）\n"
                "Reels角度：" + it["reels_angle"] + "\n热点挂钩：" + it["trend_hook"] + "\n"
                "规格：" + str(it["duration_s"]) + "秒，" + str(it["width"]) + "x" + str(it["height"]) + "，约%.1fMB" % (it["bytes"] / 1048576)
            ),
            "date_published": it["pub_date"],
            "tags": [it["category"], it["community"], it["trend_hook"]],
            "attachments": [{
                "url": it["download_url"],
                "mime_type": it["mime"],
                "size_in_bytes": it["bytes"],
                "duration_in_seconds": it["duration_s"],
            }],
            "_license": it["license"],
            "_attribution": it["attribution"],
            "_version": it.get("version", 1),
        })
        if it.get("is_test"):
            feed["items"][-1]["_is_test"] = True
        if it.get("author"):
            feed["items"][-1]["_author"] = it["author"]
        feed["items"][-1]["_source_url"] = it.get("source_url")
        if it.get("license_url"):
            feed["items"][-1]["_license_url"] = it.get("license_url")
        if it.get("_master_url"):
            feed["items"][-1]["_master_url"] = it["_master_url"]
        for _f in ("_footage_type", "_event_date", "_filmed_date", "_original_upload_date", "_valid_until", "_recommended_segment"):
            if it.get(_f) is not None:
                feed["items"][-1][_f] = it[_f]
        if it.get("_authorization") is not None:
            feed["items"][-1]["_authorization"] = it["_authorization"]
    return json.dumps(feed, ensure_ascii=False, indent=1) + "\n"

STATUS_SNAPSHOT_FIELDS = [
    "title", "summary_cn", "category", "community", "license", "license_url",
    "author", "source_url", "download_url", "attribution", "reels_angle",
    "trend_hook", "duration_s", "width", "height", "bytes", "mime",
    "pub_date", "is_test", "_footage_type", "_event_date", "_filmed_date",
    "_original_upload_date", "_valid_until", "_recommended_segment", "_master_url",
    "_authorization",
]

def load_retractions():
    p = os.path.join(UP, "retractions.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for e in data.get("events", []):
        out[e["item_id"]] = e.get("reason", "")
    return out

def build_status(items, feed_ids):
    """Full latest-status snapshot for every known item (never trimmed).
    Additive: keeps the old status fields and adds a full content snapshot,
    so aged-out items remain queryable by id."""
    retract_reasons = load_retractions()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    entries = []
    for it in items:
        e = {
            "id": it["id"],
            "status": it.get("status", "active"),
            "version": it.get("version", 1),
            "date_modified": it.get("date_modified", ""),
            "in_latest_feed": it["id"] in feed_ids,
            "retract_reason": retract_reasons.get(it["id"], ""),
        }
        if it.get("is_test"):
            e["is_test"] = True
        for f in STATUS_SNAPSHOT_FIELDS:
            if it.get(f) is not None:
                e[f] = it[f]
        entries.append(e)
    return {
        "updated_at": now,
        "count": len(entries),
        "note": "全量最新状态快照，按 id 查询。条目含完整内容快照，移出最新列表的老条目仍可在此查到完整内容。",
        "items": entries,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://example.invalid/fb-reels-upstream",
                    help="Public base URL where feed.xml will be hosted")
    a = ap.parse_args()
    items = load_items()
    # The public list carries only usable items: active status, newest first, cap 420
    # (14 verticals x ~30 days retention).
    feed_items = [i for i in items if i.get("status") == "active"]
    feed_items.sort(key=lambda i: i.get("pub_date", ""), reverse=True)
    feed_items = feed_items[:420]
    with open(os.path.join(UP, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(build_rss(feed_items, a.base_url))
    with open(os.path.join(UP, "feed.json"), "w", encoding="utf-8") as f:
        f.write(build_jsonfeed(feed_items, a.base_url))
    status = build_status(items, {i["id"] for i in feed_items})
    with open(os.path.join(UP, "status.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(status, ensure_ascii=False, indent=1) + "\n")
    print("built feed.xml + feed.json from %d active items, status.json for %d items (base=%s)"
          % (len(feed_items), len(items), a.base_url))

if __name__ == "__main__":
    main()
