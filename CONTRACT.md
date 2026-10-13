# FB Reels 视频素材上游 · 接口契约说明（v2，2026-10-13）

本文件面向下游系统，说明字段含义、分类字典、变更事件与同步方式。

## 一、文件一览（仓库根目录）

| 文件 | 内容 | 更新节奏 |
| --- | --- | --- |
| `feed.json` | 最新可用素材列表（JSON Feed 1.1 + 扩展字段），最多 300 条 | 每日采集后；有撤回时立即 |
| `feed.xml` | 同上，RSS 2.0 | 同上 |
| `changelog.json` | 全量变更事件（added/modified/retracted/expired/restored），`seq` 全局递增 | 每次变化后 |
| `retractions.json` | 独立撤回列表（只含撤回事件），长期保留 | 有撤回时立即 |
| `status.json` | 全量素材最新状态快照，按 `id` 查询 | 每次变化后 |
| `daily_stats.json` | 最新一天的分分类统计（稳定地址） | 每日 |
| `stats/daily_YYYY-MM-DD.json` | 每日统计归档 | 每日 |

所有时间均为 `Asia/Shanghai`（+08:00）。`seq` 递增排序是唯一排序依据，时间戳仅用于展示。

## 二、feed.json 素材字段

| 字段 | 含义 |
| --- | --- |
| `id` | 素材稳定身份，修改不换 ID |
| `_version` | 版本号，v1 起，每次有效变化 +1 |
| `title` / `summary` | 标题与内容摘要（写实，不推测） |
| `content_text` | 完整中文说明：内容总结、内容类型、对应社群、许可证、Reels 角度、热点挂钩、规格 |
| `url` | 原始来源页面地址（作者页/机构页，非下载地址） |
| `attachments[].url` | 直接可下载的 HTTPS 文件地址 |
| `attachments[].mime_type` / `size_in_bytes` / `duration_in_seconds` | 类型、字节数、时长 |
| `tags` | [内容类型, 对应社群, 热点挂钩] |
| `date_published` | 素材入库日期（北京时间） |
| `_author` | 作者或权利主体（CC 素材必填，已核实；未知则不填，不编造） |
| `_source_url` | 原始发布页面地址（同 `url`） |
| `_license` | 许可证名称，如 `Public domain`、`CC BY 3.0`、`CC BY-SA 4.0` |
| `_license_url` | 许可证页面地址（CC 素材必填） |
| `_attribution` | 署名要求：CC 素材为"发帖时在描述中注明作者、来源链接和许可证链接：<许可证地址>"；Public domain 为"无需署名" |
| `_recommended_segment` | 可选，`{"start_seconds": n, "end_seconds": m}`，母带推荐截取区间（数值型） |
| `_master_url` | 可选，原始母带地址（当主下载地址为剪辑成品时保留） |
| `_footage_type` | 影像类型：真实拍摄 / 历史影像 / 动画 / 仿真 / AI生成 / 混合（可附组成说明） |
| `_event_date` | 事件日期（YYYY-MM-DD 或 YYYY），未知则空 |
| `_filmed_date` | 拍摄日期，未知则空 |
| `_original_upload_date` | 原始上传日期（来源站发布时间，非入库日期） |
| `_valid_until` | 有效期，空表示长期有效 |

## 六、clips/ 目录

母带超过 128 MiB 且官方无可用小文件时，上游可提供自剪的 15–60 秒 720p 成品，
存于仓库 `clips/` 目录，主下载地址指向成品，`_master_url` 保留母带地址。

`_filmed_at`（拍摄日期）、`date_modified`、`_valid_until`（有效期）按素材实际情况填写，未知可空。
`_retracted` 仅出现在撤回事件中，不出现在正常素材条目。

## 三、分类字典（视频）

内容类型严格使用以下 16 个名称（括号内为内部固定编码，下版契约对齐用）：

影视/文化（film_culture）、科技/航天科普（space_science）、科技/安全教育（safety_education）、
科技/财经科普（finance_science）、体育/历史（sports_history）、科技/无人机（drones）、
科技/教育（tech_education）、文化/手工（crafts）、游戏/生活方式（gaming_lifestyle）、
财经/科普（money_education）、科技/创客（makers）、科技/航天（space）、
科技/新闻（tech_news）、体育/建筑（sports_architecture）、文化/艺术（arts）、
游戏/怀旧文化（gaming_history）

目标社群 10 个名称：Screen Stories Brief（screen_stories）、Science Worth Understanding（science）、
Digital Safety Explained（digital_safety）、Crypto Beyond the Price（crypto）、
Beyond the Score Brief（sports）、Robotics and Automation Brief（robotics）、
AI Tools and Everyday Uses（ai_tools）、Design Worth Noticing（design）、
Next Game Brief（gaming）、Everyday News and Money Discussion（news_money）

## 四、变更事件（changelog.json）

```json
{
  "event_id": "evt-20261013-0035",
  "seq": 35,
  "item_id": "c2-sdo-x54-flare",
  "version": 2,
  "type": "modified",
  "status": "active",
  "occurred_at": "2026-10-13T09:40:00+08:00",
  "reason": "分类修正为约定名称；补齐原始来源地址",
  "changed_fields": ["category", "source_url"]
}
```

类型：`added`（首次入库）、`modified`（同 ID 改字段，注明 changed_fields）、
`retracted`（撤回，带原因/时间/影响范围）、`expired`（过期，不计入撤回）、
`restored`（误撤回恢复，关联原撤回 event_id）。
撤回事件同时写入 `retractions.json`，确认后立即推送，不等待每日采集。

## 五、同步方式

1. 初次：拉 `feed.json`（快照）+ `changelog.json`（历史事件）+ `retractions.json`（撤回）。
2. 增量：按 `changelog.json` 的 `seq` 游标读取新事件；`status.json` 按 `id` 查最新状态。
3. 零新增：`changelog.json` 当天无新事件属正常；`daily_stats.json` 的 `update_completed` 为 true 即表示本日更新完成。
4. 游标失效：重新拉取全量快照 + 撤回列表。
