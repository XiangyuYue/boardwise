# 548P129 — stage4 post-joint 完整失败捕获（仅一次）

> 状态：**已捕获，built=False，无候选，生产未改**。证据 `evidence/548P129/README.md`。
> 下一步只捕获joint成功后的path-first首拒，见 `tasks/548p130_path_first_refusal.md`。

## 已有证据

- stage4反钉joint成功：chain=8、U1.3=5、GND 4/2，planRefusals为空。
- 全局注入会在service binder阶段C2失座，不能用于生产。
- F1其他组最便宜候选作墙：chain/U1.3均无完整座，不能采用。
- stage7 post-joint使用stage4的247节点后没有生成LayoutPlan，`built=False`；随后报告因tuple键
  JSON序列化失败，详细下游首拒未保存。该工具错误不得写成页面拒因。

生产保持：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。

## 唯一完成条件

1. 复制 `.tmp_548p128/stage7_stage4_full.py` 到 `.tmp_548p129/`，仅把 `chosen` 改为
   `[[net, group, owner], ...]` 等JSON安全结构，并在 `_build_candidate` 返回后立即打印/落盘
   `built/failure/violations/repairs`，即使后续报告失败也保留真实返回。不得改生产或搜索参数。
2. 同一P126输入、同一stage4墙、同一variant，**最多运行一次**，前台给明确timeout；若转后台，
   只能有一个任务，完成/取消都收集。不得再开第二轮凑不同结果。
3. 若 `built=False`：记录真实首拒并停止，不实施生产、不做视觉；下一批只针对该首拒。
4. 若 `built=True`：保存LayoutPlan，独立逐脚/readability并渲染，主代理亲看长干线/far旗位；
   机器成功不代替视觉。未过视觉仍不实施生产。
5. 报告生产/输入SHA、实际耗时、命令与原始返回；无Git写、全量、真机、apply、移动或删除。
