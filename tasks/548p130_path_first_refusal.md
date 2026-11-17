# 548P130 — joint 成功后的 path-first 首拒捕获

> 状态：**已捕获path-first-terminal首拒，生产未改**。证据 `evidence/548P130/README.md`。
> 下一步仅反证信号与标签走廊，见 `tasks/548p131_signal_corridors.md`。

## 已有事实

- post-joint修复3次均为chain 17→8、ok=true、expansions 10→6；
- 同一 `_build_candidate` 最终built=False，返回service C2房间/宿主线拒绝，violations=[]；
- 断层在 `_service_flag_room_ok` / path-first验收及宿主退休循环，不在“chain无候选”。

生产与输入不得改：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`，P125/P126规格。

## 唯一问题

joint成功后，`_service_flag_room_ok` 的哪一步先失败：

1. `_seat_first_channel_terminal`；
2. `_seat_first_path_first_terminal`；
3. `_path_first_plan`；
4. `_path_first_audit`。

用只读包装记录每个阶段的返回值和首个refusal，定位为什么成功joint最终又进入C2退休失败。
探针必须在首个有效下游拒绝处停止，不能再跑368秒陪完整个退休循环。

## 文件域与停止线

仅 `.tmp_548p130/`、`evidence/548P130/`。不得改生产/tests/docs/tasks/输入、shared/review/bridge、
P43/WiFi/P128/P129证据。不得调reach/GAP/预算/排列/页框、强制共旗、扩大搜索或恢复P124实验。
不移动删除、不Git写、不bridge/apply/真机/全量。

交卷必须含实际阶段、原始refusal、对应seat/path/flag对象和下一最小动作；若捕获不到，
报告实际经过的阶段，不猜。只有出现ok=True候选才做逐脚和视觉。
