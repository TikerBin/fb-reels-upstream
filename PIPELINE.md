# FB Reels 每日素材上游 — 管线说明

## 目标
每天搜集 3–5 条适合发 Facebook Reels 的**合法免费**视频素材（公有领域 / CC BY / CC BY-SA），
写入 `upstream/items.json`，重新生成 `feed.xml`（RSS 2.0）与 `feed.json`（JSON Feed 1.1），
用户系统通过固定 URL 拉取这两个文件获取素材信息（含原始下载地址）。

## 采集量规则（2026-10-12 更新：每垂类每天尽量 1 条）

- 10 个垂类（新闻/财经、AI、加密资产、无人系统、科学、网络安全、游戏、影视、体育、艺术设计）**每个尽量每天出 1 条**，每天最多 10 条。
- 宁缺毋滥：某垂类当天没有合格素材就空缺，不硬凑；极端情况下全天可 0 条（feed 不变，日志注明原因）。
- feed 上限从 150 条提高到 300 条（约 1 个月留存），由 worker 在更新 items.json 时执行淘汰。

## 目录
- `items.json` — 数据源（也是去重依据，按 download_url 去重），新条目插到最前面，最多保留 150 条
- `build_feed.py` — 由 items.json 生成 feed.xml + feed.json + status.json（`--base-url` 为托管地址）
- `build_daily_stats.py` — 由 items.json + changelog.json 重算 daily_stats.json 与 stats/daily_YYYY-MM-DD.json（`--date` 指定日期，默认当天）；计数口径见 CONTRACT.md 第八章
- `collect.py` — 搜索助手（Wikimedia Commons / archive.org / NASA），注意 Commons API 必须带 User-Agent 否则 403
- `feed.xml` / `feed.json` — 对外发布的成品（RSS enclosure 指向**原始下载地址**，不转存视频字节）
- `UPLOAD.md` — 上传目标配置（待用户确认后填写）

## 新鲜度规则（2026-10-12 新增，解决"素材偏旧"问题）

背景：版权硬门槛（只收 PD / CC BY / CC BY-SA）天然偏向档案库——老新闻片、版权过期老片、NASA 历史影像。
新鲜爆款（影视切片、游戏实机、赛事集锦）几乎全是版权的，不能碰。所以"话题新、素材旧"是结构性现状，
本规则只能在合规范围内尽量拉新，做不到"搬运今天的爆款原片"（那会直接被下架/限流）。

执行顺序（每天）：
1. **先找新的**：archive.org 用 `addeddate desc` 找近 30 天上传的 PD 素材；
   Commons 用 `commons_search(..., sort="newest")` 或 `commons_recent_videos(keyword=...)` 扫最新上传；
   航天类直接查 NASA API（看 date_created，优先本周发布）。
   Commons 还有按年分的 `Category:Videos of 2026` 可翻。
2. **新闻类优先 PD 时政影像**：VOA、美军 / 白宫公开影像是公有领域且天天更新，
   搜 Commons 上的 VOA 上传或 archive.org 的政府公开影像。
3. **实在没有新的才用档案**：候选质量相当时永远选上传日期新的（`uploaded` 字段已加入搜索结果）。
4. 档案素材必须配**新鲜的话题挂钩**（trend_hook 写清关联的本周新闻），不能为发而发。
5. 注意：archive.org 按 addeddate 排前面多是各国电视台录播（版权），license_ok() 挡掉，只收明确 PD/CC 的。

## 每日流程（cron worker 遵循）
1. 看当天热点：`browser.search`（news vertical）查美国当日/当周趋势；结合 10 个社群垂类轮换选题。
   10 社群：Everyday News and Money Discussion（新闻/财经）、AI Tools and Everyday Uses（AI）、
   Crypto Beyond the Price（加密资产）、Robotics and Automation Brief（无人系统）、
   Science Worth Understanding（科学）、Digital Safety Explained（网络安全）、
   Next Game Brief（游戏）、Screen Stories Brief（影视）、Beyond the Score Brief（体育）、
   Design Worth Noticing（艺术设计）。
2. 用 collect.py 在 Commons / archive.org / NASA 搜候选（`filetype:video` 类查询；archive.org 用 advancedsearch）。
   Pexels/Pixabay/Mixkit 的直链被 Cloudflare 挡，**不要用**。
3. 版权红线：只收 Public domain / CC BY / CC BY-SA（用 `license_ok()` 初筛，再看文件页确认）。
   影视正片切片、游戏实机、职业赛事画面一律不要。
4. 去重：download_url 已在 items.json 中则跳过。
5. 下载到 /tmp 验货：ffprobe 看时长分辨率，ffmpeg 抽 3 帧缩略图并**亲眼看**确认内容与描述一致，
   再写中文总结（内容总结 / 内容类型 / 对应社群 / 许可证与署名要求 / Reels 角度 / 热点挂钩）。
6. 合同字段自检（2026-10-13 起固定步骤，入库并重建 feed 后、上传前必做）：对本轮新入库条目逐条核对
   CONTRACT.md 必填字段——`_footage_type`、`_event_date`、`_filmed_date`（不确定可空，但不能标 unknown 了事）、
   `_original_upload_date`；超 60 秒的必须有数值型 `_recommended_segment`；超 128 MiB 的必须已换小文件/自剪成品；
   CC 条目必须有 author/source_url/license_url，PD 条目必须有 source_url；分类名必须在 16 个约定名称之内；
   许可证名统一为 `Public domain`。缺失的按来源站原文查证补齐，补齐后 bump version 并在 changelog 记 modified。
   自检通过后再上传。

## 分类字典（2026-10-13 起严格执行，不许自创）

内容类型只能用以下 16 个约定名称：影视/文化、科技/航天科普、科技/安全教育、科技/财经科普、体育/历史、科技/无人机、科技/教育、文化/手工、游戏/生活方式、财经/科普、科技/创客、科技/航天、科技/新闻、体育/建筑、文化/艺术、游戏/怀旧文化。

注意：普通 AI 公司新闻不能仅因公司涉及技术就归入财经/科普类。

## 版本与变更（2026-10-13 起）

- 每条素材有稳定 ID（`id`），修改不换 ID；`version` 从 1 起，每次有效变化 +1；`status` 为 active/retracted/expired。
- 每次变化在 `changelog.json` 记一笔：唯一 `event_id`、全局递增 `seq`（从 `next_seq` 续）、类型 added/modified/retracted/expired/restored、原因；修改注明 `changed_fields`。
- `status.json` 全量最新状态（`in_latest_feed` 标记是否在最新列表）；`retractions.json` 独立撤回列表，长期保留。
- 撤回立即推送，不等次日采集。过期记 expired，不计入撤回。旧料不许换新 ID 复活。
- 许可证名称统一为 `Public domain`（不加 NASA/VOA 后缀）。

## 署名信息规范（2026-10-12 新增）
- 每个 CC 协议（CC BY / CC BY-SA）条目必须填写 `author`（去文件页核实真实作者名）、`source_url`（文件页地址）、`license_url`（creativecommons.org 许可证地址）。
- `attribution` 统一写"发帖时在描述中注明作者、来源链接和许可证链接：<license_url>"；Public domain 条目写"无需署名"。
- 不确定的作者名宁可空着也不要编造。

## 结构化字段（2026-10-13 新增，新条目必填）
- `_footage_type`：真实拍摄 / 历史影像 / 动画 / 仿真 / AI生成 / 混合（可附组成说明）。
- `_event_date`：事件日期（YYYY-MM-DD 或 YYYY），不确定可空，不许编。
- `_original_upload_date`：去来源站核实的原始上传日期（Commons 文件页 / archive.org metadata / NASA date_created）。
- `_valid_until`：有效期，空表示长期有效。
- `_recommended_segment`：超 60 秒的素材必须看片后给 15–60 秒精华窗口（数值型起止秒）。
- 母带超 128 MiB：必须另给小文件或自剪 15–60 秒 720p 成品放仓库 `clips/`（主下载指向成品，`_master_url` 保留母带）。

## 上传（2026-10-12 起：git 自动推送）
- 本地仓库：`~/workspace/goals/fb-reels/upstream-repo`（origin 已配带 token 的 HTTPS 地址，直接 push，无需确认）。
- 流程：`git pull --rebase` → 复制 feed.xml/feed.json/changelog.json/retractions.json/status.json/daily_stats.json（+ stats/daily_YYYY-MM-DD.json）→ commit → `git push origin main` → curl 验证 raw 地址（注意 raw 有几分钟 CDN 缓存）。
- ⚠️ feed.xml/feed.json 是生成文件，不要直接在 GitHub 网页上改它们——下次推送会覆盖。如需修正，先改 `upstream/items.json`（数据源），再重新生成推送。
   单文件超过 ~150MB 的优先找小尺寸衍生版（如 archive.org 的 `*_512kb.mp4`）。
6. 每天 3–5 条，宁缺毋滥；实在找不到合格的，当天可 0 条（feed 不变，日志注明原因）。
7. 更新 items.json（新条目在前，pub_date 用当天北京时间），跑 `build_feed.py --base-url <UPLOAD.md 中的地址>`。
8. 按 UPLOAD.md 上传 feed.xml + feed.json；未配置上传目标时跳过此步。
9. 在 `../hidden_files/upstream-daily.log` 追加一行：日期、新增条数、备注。不碰 MEMORY.md。
