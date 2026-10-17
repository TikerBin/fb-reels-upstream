# FB Reels 视频素材上游 · 接口契约说明（v2，2026-10-13）

本文件面向下游系统，说明字段含义、分类字典、变更事件与同步方式。

## 一、文件一览（仓库根目录）

| 文件 | 内容 | 更新节奏 |
| --- | --- | --- |
| `feed.json` | 最新可用素材列表（JSON Feed 1.1 + 扩展字段），仅含 `active` 条目，按入库时间倒序，最多 420 条 | 每日采集后；有撤回时立即 |
| `feed.xml` | 同上，RSS 2.0 | 同上 |
| `changelog.json` | 全量变更事件（added/modified/retracted/expired/restored），`seq` 全局递增 | 每次变化后 |
| `retractions.json` | 独立撤回列表（只含撤回事件），长期保留 | 有撤回时立即 |
| `status.json` | 全量素材最新状态快照，按 `id` 查询，含完整内容快照（移出最新 420 条的老条目仍可在此查到完整内容），永不裁剪 | 每次变化后 |
| `daily_stats.json` | 最新一天的分分类统计（稳定地址） | 每日 |
| `stats/daily_YYYY-MM-DD.json` | 每日统计归档 | 每日 |

所有时间均为 `Asia/Shanghai`（+08:00）。`seq` 递增排序是唯一排序依据，时间戳仅用于展示。

## 二、feed.json 素材字段

顶层扩展字段 `_verticals`：14 个垂类可用素材总览（数组，按固定顺序；`count` 为 0 的也列出，方便判断缺口）：
`[{"vertical": "科学", "community": "Science Worth Understanding", "count": 8}, ...]`。
判定规则：先看条目的 `community`，同一社群内再按 `category` 拆分子垂类
（Robotics 社群中 `军事/装备`→军事航空装备其余→无人系统；
Science 社群中 `自然/风光`→纯自然风景/野生动物、`自然/海洋生物`→海洋生物/深海其余→科学；
Beyond the Score 社群中 `旅行/户外`→国家公园旅行/户外其余→体育）。
测试条目不计入。

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
| `_recommended_segment` | 可选，`{"start_seconds": n, "end_seconds": m}`，数值型。**坐标系=交付文件自身时间轴**：当交付文件已是自剪精华成品时，区间指成品自身（如整段交付即 `[0, duration]`），禁止填母片坐标；必须满足 `0<=start<end<=duration_s`，否则生成器拒绝构建 |
| `_master_url` | 可选，原始母带地址（当主下载地址为剪辑成品时保留） |
| `_footage_type` | 影像类型：真实拍摄 / 历史影像 / 动画 / 仿真 / AI生成 / 混合（可附组成说明） |
| `_event_date` | 事件日期（YYYY-MM-DD 或 YYYY），未知则空 |
| `_filmed_date` | 拍摄日期，未知则空 |
| `_original_upload_date` | 原始上传日期（来源站发布时间，非入库日期） |
| `_valid_until` | 有效期，空表示长期有效 |
| `_authorization` | 公有领域素材的授权依据对象：`{"evidence_url": "公开权利说明页（HTTPS，无查询参数）", "public_domain_basis": "声明主体、适用原因与已知限制说明", "attribution_required": true/false} `；`attribution_required=true` 表示来源方有强制署名要求（此时 `_attribution` 含完整署名文字），缺省/为 false 表示无强制署名要求；feed.xml 中以 `_authorization_evidence_url` / `_authorization_public_domain_basis` 两个元素表示 |

## 六、测试条目（test fixtures）

联调或演练时可能出现仅供测试的条目：`is_test=true`（feed.json 为 `_is_test`，feed.xml 为 `<_is_test>`）。
测试条目与正式条目隔离：不计入库存统计、不计入每日统计的各分类 valid/added 数，
正式发布流程必须过滤该标记。测试条目的变更事件同样进入 `changelog.json`（带 `is_test` 标记），
以便验证同步、撤回与重放防护流程；其标题会明确标注"联调测试专用"。

## 七、clips/ 目录

母带超过 128 MiB 且官方无可用小文件时，上游可提供自剪的 15–60 秒 720p 成品，
存于仓库 `clips/` 目录，主下载地址指向成品，`_master_url` 保留母带地址。

`_filmed_at`（拍摄日期）、`date_modified`、`_valid_until`（有效期）按素材实际情况填写，未知可空。
`_retracted` 仅出现在撤回事件中，不出现在正常素材条目。

## 三、分类字典（视频）

内容类型严格使用以下 20 个名称（括号内为内部固定编码，下版契约对齐用）：

影视/文化（film_culture）、科技/航天科普（space_science）、科技/安全教育（safety_education）、
科技/财经科普（finance_science）、体育/历史（sports_history）、科技/无人机（drones）、
科技/教育（tech_education）、文化/手工（crafts）、游戏/生活方式（gaming_lifestyle）、
财经/科普（money_education）、科技/创客（makers）、科技/航天（space）、
科技/新闻（tech_news）、体育/建筑（sports_architecture）、文化/艺术（arts）、
游戏/怀旧文化（gaming_history）、自然/风光（nature_scenery）、自然/海洋生物（marine_life）、
旅行/户外（travel_outdoor）、军事/装备（military_equipment）

（2026-10-16 新增后 4 个：自然/风光、自然/海洋生物、旅行/户外、军事/装备，对应新增的 4 个内容垂类。）

目标社群 10 个名称：Screen Stories Brief（screen_stories）、Science Worth Understanding（science）、
Digital Safety Explained（digital_safety）、Crypto Beyond the Price（crypto）、
Beyond the Score Brief（sports）、Robotics and Automation Brief（robotics）、
AI Tools and Everyday Uses（ai_tools）、Design Worth Noticing（design）、
Next Game Brief（gaming）、Everyday News and Money Discussion（news_money）

（2026-10-16 用户确认新垂类社群映射：纯自然风景/野生动物→Science Worth Understanding、
海洋生物/深海→Science Worth Understanding、国家公园旅行/户外→Beyond the Score Brief、
军事航空装备→Robotics and Automation Brief；新垂类条目的 community 字段填所映射的社群名。）

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
3. 老条目完整内容：`feed.json` 只保留最新 420 条可用条目；任何历史条目（含已移出列表、已撤回）的完整内容快照都在 `status.json` 中按 `id` 查询，该文件永不裁剪。
4. 零新增：`changelog.json` 当天无新事件属正常；`daily_stats.json` 的 `update_completed` 为 true 即表示本日更新完成。
5. 游标失效：重新拉取全量快照 + 撤回列表。

## 八、日报（daily_stats.json）

- 地址：`daily_stats.json`（稳定地址，最新一天）；归档 `stats/daily_YYYY-MM-DD.json`。
- `date`：统计日期；`timezone`：`Asia/Shanghai`；统计窗口为该时区自然日 00:00–24:00；
  `stats_until`：本文件计算截止时间；`last_event_seq`：本日报覆盖到的最大事件序号（新增覆盖标识）。
- **即时重算**：日报在每日 08:42 采集后生成；当日若发生临时撤回/修改等变更，
  `daily_stats.json` 会即时重算并推送（`stats_until` 与 `last_event_seq` 同步更新）。
  因此**不要把早间日报当成最新库存**——对账请以 `last_event_seq` 为准，或直接用 `status.json` 全量快照。
- `update_completed`：true = 当日流程完整跑完（含 0 新增）；false = 当日流程未完成（看 `failure_reason`）。
  文件日期未更新 = 当日任务未执行。**不要把 `added=0` 当成失败**，也不要把未完成报成 0。
- `failure_reason`：未完成时写原因；完成时为 null。
- `opening_inventory` / `closing_inventory`：**全量口径**——`status.json` 中 `status=active`
  且非测试条目的数量（不是 `feed.json` 条目数；`feed.json` 只代表最新 420 条窗口，
  当下不足 420 条时两者恰好相等，超过 420 条后不再相等）。
- `total_events_today`：当日非测试变更事件总数（`occurred_at` 落在当日）。
- `categories.<分类>`：`valid`（该分类有效库存，全量口径）、`pending_review`（恒为 0，上游无审核环节）、
  `added` / `modified` / `retracted` / `expired` / `restored`（当日该分类各变化计数）。
- `category_basis`：`LATEST_AT_STATS_UNTIL`——所有分类计数按**统计截止时点各素材的最新分类**归类
  （事件发生时的历史分类不追踪；分类迁移本身记一次 `modified`，`changed_fields` 含 `category`）。
  下游按同一口径比较每分类增减，不要猜测事件发生时分类。
- 计数口径：`added` 仅指新素材首次入库（历史字段补录记 `modified`，不记 `added`）；
  `modified` 按“本日发生该变化的素材身份”去重；同一素材同日多类变化在各列分别计数，不可直接相加；
  测试条目（`is_test`）不计入任何计数；下游按 `seq` 幂等去重。
- 对账口径（全量）：`closing_inventory - opening_inventory` 应等于当日 `added - retracted - expired`；
  `modified` 与分类迁移不改变全量总数；各分类 `valid` 之和应等于 `closing_inventory`。
- 形状样例见 `fixtures/daily-stats-samples/`（0 新增完成 / 未完成各一，均标注为样例，非正式日报）。

## 九、交付约定（上游承诺，下游生产配置另行决定）

以下为上游的交付约定，不代表下游生产配置已上线：

1. 撤回检查建议：每 15 分钟拉一次 `changelog.json`（按 `seq` 游标增量），`retractions.json` 同步检查。
2. 撤回时效：撤回确认后走即时通道（不等每日采集），上游执行并推送；从上游确认执行到文件可见的**最长预期为 30 分钟**（含 raw CDN 缓存）。
3. 停止自动使用建议阈值：连续 6 小时同步失败（拉取失败）则暂停自动选用。零新增（`update_completed=true`）属于同步成功，不触发该阈值。
4. 完整历史快照：`status.json` 含全量条目最新状态 + 完整内容快照，永不裁剪；`feed.json` 只保留最新 420 条可用条目。
   移出最新列表 ≠ 撤回（`status` 保持 `active`）；已撤回条目以 `retractions.json` 为权威停用依据，
   普通 `modified`、`status=active` 的旧快照、重新出现在 feed 中都不能恢复撤回条目。
5. 老化行为样例见 `fixtures/historical-window/`（合成样例，`fixture-` 前缀 ID，不接入正式流程）。
