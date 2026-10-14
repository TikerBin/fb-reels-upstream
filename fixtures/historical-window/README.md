# fixtures/historical-window 说明（测试专用，不接入正式流程）

本目录为**合成样例**，演示素材移出最新 300 条列表（老化）后的四文件行为。
所有 ID 均以 `fixture-` 开头、序号使用 9001+，与正式数据永不冲突。
**不接入正式 feed、changelog、库存统计与日报。**

## 场景

`fixture-agedout-01` 是一条很久以前入库的素材，后来 active 条目超过 300 条，
它被移出了最新列表，但状态仍为 active。

### 1. 移出后仍可查到完整内容（status.sample.json）

```json
{
  "id": "fixture-agedout-01",
  "status": "active",
  "version": 2,
  "date_modified": "2026-01-15T10:00:00+08:00",
  "in_latest_feed": false,
  "retract_reason": "",
  "title": "合成样例：已移出最新列表的历史素材",
  "download_url": "https://example.invalid/fixture-agedout-01.mp4",
  "...": "其余完整快照字段与正式 status.json 条目相同"
}
```

要点：`in_latest_feed=false` 但 `status=active`，完整内容快照保留。
移出 ≠ 撤回。

### 2. 移出后仍可正常修改（changelog.sample.json 的 seq 9002）

老化条目的字段变更照常走：ID 不变、版本号+1、记 `modified` 事件（`changed_fields` 注明）、
`status.json` 同步更新。`feed.json` 不变（它本来就不在最新列表里）。

### 3. 撤回后旧 ACTIVE 快照重放（replay-check.sample.json）

- seq 9003：该条目被撤回（`type=retracted`，同步写入 `retractions.sample.json`）。
- 下游把 seq 9001 时期的旧快照（`status=active`）重新输入测试系统。
- 正确行为：以**该 ID 的最大 seq 事件**为准（9003 retracted），且 `retractions.json` 为权威撤回依据，
  该条目**不得**被重新启用。普通 `modified`、`status=active` 或重新出现在 feed 里都不能恢复撤回。

未来出现真实的移出样例时，上游会提供实际 ID，本目录样例届时仅作形状参考。
