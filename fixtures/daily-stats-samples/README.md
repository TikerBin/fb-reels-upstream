# fixtures/daily-stats-samples 说明

本目录为**日报形状样例（fixtures）**，仅用于下游适配解析逻辑，**不是正式日报**。

- `daily_stats_zero_new.sample.json` —— “0新增但更新完成”：`update_completed=true`、`failure_reason=null`、各列计数全 0。下游不要把 `added=0` 当成失败。
- `daily_stats_incomplete.sample.json` —— “更新未完成”：`update_completed=false`、`failure_reason` 写明原因。下游判断未完成请看这两个字段。

正式日报地址（稳定）：`https://raw.githubusercontent.com/TikerBin/fb-reels-upstream/main/daily_stats.json`
归档：`stats/daily_YYYY-MM-DD.json`

字段说明见 CONTRACT.md “日报（daily_stats.json）”章节。
