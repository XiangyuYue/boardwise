# 548P126 — localSeats 支路顺序与宿主脚反馈（单独集成批）

> 状态：**机制通过 / 当前MCU页面未通过**；最终验收 `evidence/548P126/README.md`。
> 真实MCU五条服务支路已按显式语义达到5/5落座，被拒绝支路的已选宿主脚已进入后续反馈。
> 不宣称完整MCU/整页通过；3V3联合旗位由 `tasks/548p127_rail_joint_seats.md` 另批处理。

## 1. 前因与行为基线

- P125已按547G3C恢复 `C3.1=NRST、R1.1=BOOT0`，保持30件/31网/4NC/114成员。
- G3C + `localSeats:true` 下，C1/C2都选host 13；声明顺序BZ1先座，后续C1/C2/C3被拒。
- `_service_seats_in_flag_room` 只从最终声明计划退休宿主脚；拒绝计划没有cells，已选host 13未进入bans。
- 原binder反向实验：顺序C1→C3→BZ1→C2→R1且C2=host 1，5/5服务支路合法落座；
  C2=host 3仍失败。完整variant另有GND固定终端共席与3V3联合旗位冲突，不在本批掩盖。

当前生产基线：drawcompiler `2348a1401ce6e988119cdbcfd55549c54ac7e28b5aed869d8a071be4326d7a68`，
placement `af5413f991b3c289b8ec81f1e09b888af8640c94c413a66d1ae6aee4be617b2b`。
混合工作树保留，禁止Git写/restore和直接删除。

## 2. 公开行为合同与调用方

1. **显式顺序**：`localSeats` 页面若模块已有 `branchOrder`，服务模板必须按该顺序消费；
   未写 `branchOrder` 的页面保持现有声明顺序和低/高行序，不增加排列或预算。
   本例语义顺序为 C1（供电去耦）→C3（NRST）→BZ1→C2（外侧bulk）→R1（右侧BOOT0），
   不写任何坐标、userLock或宿主脚绝对位置。
2. **拒绝反馈**：每个被拒绝服务计划已实际选择的宿主脚必须能以内部只读方式返回给现有
   `_service_seats_in_flag_room` 退休逻辑；不得靠解析拒绝文案恢复。该脚也必须进入`seen`键，
   否则拒绝计划在换脚前就会被误判重复。只退休已试脚，不禁止未试脚，文档明确指定的host token
   仍不可被替换。发生落座失败时只退休**失败支路**的已试脚，已成功支路保持原位；全部落座后
   若下游旗房检查失败，才保留现有全组退休行为。
3. **内部兼容**：不新增PresentationSpec/CircuitSpec字段，不改LayoutPlan/ChangePlan/CLI/DSH JSON。
   若内部计划增加宿主审计字段，必须缺省兼容旧构造调用，且不进入任何序列化计划。
4. **合法旗分组**：C1/C2为独立供电支路，GND不得被两个固定终端共席；只许声明电路真实成员，
   不得复活P124的U1.31/47/63。分组语义先于距离，不把独立支路强制共旗。

调用方至少两个：drawcompiler constructive/base 与 topology 的同一 `placement.bind_service_plans`
接缝；P43是既有成功消费者，WiFi serviceGroups与未启用localSeats页面是兼容消费者。

## 3. 文件域与回退

- 集成实现仅 `src/boardwise/engines/placement.py` 与必要的
  `src/boardwise/engines/drawcompiler.py` 消费接缝；先备份并记录SHA。
- 新测试 `tests/test_548p126_service_host_feedback.py`；证据 `evidence/548P126/`、
  探针 `.tmp_548p126/`。不得改shared/review/bridge/connector/dsh-plugin/fixtures。
- 输入从 `evidence/548P125/circuit.full.g3c.pinmap.json` 与
  `full.presentation.g3c-local-seats.json` 派生；保留P120/P123/P124。
- 回退只能Copy-Item+SHA-256恢复；不得顺手修改near/reach/GAP/预算/排列上限/页框。
- 若证明需要新增第二套builder/router、扩大搜索排列或改公开文档字段，立即停止，不实施。

## 4. 验收与负控

1. 新测试先在基线红：显式branchOrder被原样消费；拒绝计划的已选host可退休且进入seen键；
   落座失败只退休失败支路。同一失败输入应保持C1=host 13，让C2按13→3→1推进并达到
   5/5服务支路落座。不能只断言helper被调用。
2. 两项独立变异：禁拒绝宿主反馈应复现C1/C2重复host 13；禁branchOrder消费应复现BZ1先座冲突。
   主代理亲自复跑并Copy-Item+SHA恢复。
3. P43精确输入保持1候选和原geometry；WiFi P118 geometry不变；LED/P122与P54/P55/P6/P64/P70
   聚焦无新增红。pytest独立basetemp、`-n 4 --dist loadfile`，不默认全量。
4. 完整variant若仍拒，必须分别报告GND固定终端分组与3V3联合旗位，不得拿5/5落座冒充候选。
5. 只有出现`ok=True`候选才做逐脚和渲染视觉；否则交“机制通过/页面未通过”。

## 5. 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| 未写branchOrder | 合成与P43 | 声明顺序、低/高行序、调用次数与几何不变 |
| 显式host token | 合成负控 | bans不得替换文档指定脚 |
| localSeats成功页 | P43精确输入 | 原1候选与geometry不变 |
| serviceGroups非localSeats | P118 WiFi | 原geometry与路线不变 |
| base/topology消费者 | 各自真实入口 | 同一宿主选择和拒绝反馈，不两套语义 |
| V3/V4、在线/离线 | 仅离线算法 | 不改宿主/bridge，不声称真机兼容已完成 |
| `.epro2/.eprj2/.eprj3` | 未覆盖 | parser未改，不声称容器兼容变化 |
| 单/多板、普通器件/CBB | 单MCU普通器件；其余未覆盖 | 不以本批推称多板或CBB支持 |
| shared/review | owner/layer聚焦 | 零新增跨线依赖、零review行为变化 |

## 6. 预算与交卷

一个实现子代理，20分钟/40步；主代理负责diff、两项变异、真实输入复验和必要视觉。
交卷带命令→汇总行→差异、最终SHA、未解决首拒；禁止全量/真机/apply/Git写。
