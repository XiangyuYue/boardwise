# 548P128 — 同网旁组引脚与旗位通道（先反证）

> 状态：**联合座存在 / 完整构建未闭环，生产未改**。证据 `evidence/548P128/README.md` §7。
> F1无候选，stage7未出LayoutPlan且探针日志失败；下一次仅捕获真实完整返回，见 `tasks/548p129_stage4_full_capture.md`。

## 1. 前因与基线

P126服务落座5/5后，3V3 chain的路径穿过U1.3(y=135)、U1.12(y=45)所在行；
旁组本地旗的所有候选又与这些路径相交。显式同组不被二次拆分后仍为9×13=117/117冲突。
当前 `_seat_first_foreign_tips` 排除本网成员，`_seat_first_paths` 对旁组成员没有组级墙或
合法连接点语义。不能继续改组名，也不能把节点交集直接豁免成连接。

生产基线：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`；
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入 `evidence/548P125/circuit.full.g3c.pinmap.json` +
`evidence/548P126/full.presentation.service-feedback.json`。

## 2. 本批唯一问题

在 `_seat_first_paths` 的真实候选生成中，如何区分：

1. 当前组自己的引脚/座位；
2. 同网但属于另一语义组的引脚——它是需要避开的交叉，还是可显式汇合的连接点；
3. 其他网的引脚——原有foreign wall，不改变。

先做内存反证：只对**当前组之外的同网成员脚**增加组级路径约束，仍用原router/原正交路径，
不得新建第二套路由、扩大预算或豁免碰撞。记录chain与旁组完整候选数、具体首墙和合法路径。
若0候选，交“无完整座”而不是把它包装成修复；若有候选，必须再过原joint/readability。

## 3. 文件域与禁触

侦察只写 `.tmp_548p128/`、`evidence/548P128/`。实现若获得正证据，仅允许draw线必要文件和
一个新测试，并先备份。不得改P126输入、shared/review/bridge/connector/dsh-plugin/fixtures、
P43/WiFi/P127证据。禁止调reach/GAP/预算/排列/页框、强制共旗、恢复P124网格实验或默认新增junction。

## 4. 完成条件与负控

- 先给出三条最小路线及预测：组级引脚墙、显式同网连接点、保持现状并声明无解；实测选一条或停止。
- 新测试基线先红，至少两项变异先红并Copy-Item+SHA恢复；不能仅断言helper被调用。
- P126五服务支路、P43/WiFi geometry及聚焦测试不得退化。
- 只有`ok=True`才逐脚/渲染/视觉；否则交真实首拒和下一最小动作。
- 子代理20分钟/40步，主代理独立复核；不默认全量、真机、apply或Git写。
