# fixtures/historical-window 说明（测试专用，不接入正式流程）

本目录为**合成样例**，演示素材移出最新 300 条列表（老化）后的四文件行为。
所有 ID 均以 `fixture-` 开头，与正式数据隔离；**不接入正式 feed、changelog、库存统计与日报**；
**没有为适配样例删除或修改任何正式历史**。

## 三阶段目录（每阶段四文件完整一致，可直接解析）

- **stage-1/**：`changelog.json`（seq1 added，`event_count=1/next_seq=2`）、
  `status.json`（v1 active，`in_latest_feed=false`，`count=1`，完整快照）、
  `feed.json`（最新可用条目，不含该素材）、`retractions.json`（`count=0`）。
  要点：`in_latest_feed=false` 但 `status=active`——移出 ≠ 撤回。
- **stage-2/**：`changelog.json`（seq1+2，`event_count=2/next_seq=3`，seq2 为 `modified`）、
  `status.json`（v2 active，标题修正已同步）、`feed.json`（随时间推进，该素材始终不在其中）、
  `retractions.json`（`count=0`）。
  要点：老化条目的字段变更照常走 ID 不变、版本+1、记事件、`status.json` 同步；`feed.json` 不受影响。
- **stage-3/**：`changelog.json`（seq1+2+3，seq3 为 `retracted`，`event_count=3/next_seq=4`）、
  `status.json`（v3 retracted，`in_latest_feed=false`，完整快照保留）、
  `feed.json`（不含已撤回条目）、`retractions.json`（`count=1`，含撤回事件，为权威停用依据）。

## 旧快照重放（replay/）

- `replay-input.json`：把 stage-1 时期的旧快照（v1 active）重新输入。
- `expected-result.json`：预期判定为 **rejected**（拒绝重新启用），
  判定依据：该 ID 的最大 seq 事件为 seq3 retracted；`retractions.json` 有权威记录；
  重放的 v1 快照版本号低于当前 v3，属过期数据。
  禁止的恢复路径：普通 modified、旧快照重放、重新出现在 feed 中。
  恢复仅能通过显式的 `restored` 事件（更高版本 + 恢复原因 + 关联撤回事件）。

未来出现真实的移出样例时，上游会提供实际 ID，本目录届时仅作形状参考。
