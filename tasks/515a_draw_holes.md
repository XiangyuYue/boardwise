# 任务书：515A — v0.5.15 发版前绘制引擎修洞（挖洞闸缝1/缝2 的高危与中危）

- 批号：**515A**　日期：2026-10-17　来源：挖洞 swarm 缝1/缝2 报告（探针在 `.tmp_hole515_s1/`、`.tmp_hole515_2/`——**先复现再修**，探针转回归测试）。
- 前置：**201C 已踢出 v0.5.15**（150 落地页回归实锤；其改动备份在 `.tmp_201c_hold/`，`router.py`/`drawcompiler.py` 的布线部分均为 HEAD 状态）。本批在 HEAD（v0.5.15 已发，tree tip 含发版收尾）上做，**不碰 `router.py`**。

## 必修（高危）

1. **多模块页双地同符号**（缝1#2，probe_page_domains.py）：`_ground_domains`（drawcompiler.py:5594 一带）按**模块本地**电路数域，多模块页每模块只看到自己那颗地网 → 域数恒 1 → PGND 和 SEC_GND 都画成 PWR-GND，违反「绝不并地」。修：域判定改读**整页**（pagecompiler 把全页电路的地网域下发给模块编译，或页级 `_flag_profile` 用整页输入）。回归：双模块页（a=PGND、b=SEC_GND，库里有 PWR-PGND/PWR-SEC_GND）→ 两颗不同的字。
2. **拓扑轮没有关系闸**（缝2#1，pb4_e2e.py / pb3_gate.py）：`_topology_placement` 把关系当软代价，带着 miss 也返回，compile 照样 ok=True。修：返回前跑一次关系闸（用合一后的 `placement.relation_holds` 那把尺），miss 非空 → 该档按 GrammarFailure 拒绝（与阶梯同口径）。回归：注入互斥关系的 power_entry 探针，拓扑轮必须拒。
3. **拓扑轮不读 userLocks 坐标**（缝2#2，pc2_locks.py）：PlacementPart 没有坐标字段，锁定件被搜索挪走 → 必然 user-lock-violated。修：锁坐标作为硬锚进 PlacementInput（钉死原点、豁免吸附/平移/旋转），readability 的锁校验仍逐字比。

## 必修（中危，都是小改）

4. **路由失败降级 label 时不写回 expressions**（缝1#1，probe_gnd_label_forced.py）：地网降级后旗标 pass 仍当它是 wire，挂了唯一地符号还写下「pads are joined by the rail」的假话。修：写回 `expressions[net_id]`；note 改成由实际绘制结果推出（有轨道才写 joined by the rail）。同函数 12 行外 `_flag_wire_fallback` 有同类修正先例。
5. **关系尺边界不一致**（缝2#3，pa_boundary.py）：`relation_miss`（<=）与 `relation_holds`（<）在边界上答案不同。修：四个严格序 + adjacent 改成严格同号式；补边界参数化用例。
6. **旗位预留与实际落旗脚不是一把尺**（缝1#4/缝2#4）：`_flag_seats` 的 gnd 分支改调 `_flag_seat_pins` 取首档；预留框把引脚坐标算进去（别只围元件原点）。
7. **stall 计数在 continue 路径不累计**（缝2#5）：全锁件输入时 6000 次空转。修：continue 也计 stall，或全锁短路返回种子。
8. **页级框归属盲区**（缝1#3，probe_page_crossmodule.py）：`geometry-outside-frames` 只问「在某个框里」不问「在自己的框里」。修：readability 页级补 membership 判定（对象 ∈ 自己模块的框）。

## 纪律

- 地盘：engines/drawcompiler.py、engines/placement.py、engines/readability.py、engines/pagecompiler.py（如需）、grammar/flyback.py。不碰 router.py（201C 刚动完，除非必读）。不碰 tools/、packaging/、.githooks/、dsh-plugin/（515B 在做）。
- 改了 rules/** 才重钉指纹（本批大概率不碰）。
- 零移动闸动了就前后对比重钉（201A/B 同流程）。
- 全量绿 `--basetemp=.tmp_pt_515a -n 4 --dist loadfile`（test_193 槽位红单跑确认）。变异 ≥2 组。
- 企业名零出现；不动 git；不 rm（回收站）；不碰真机/bridge。
- 证据 outputs/515a/evidence.md；PROGRESS.md append 一行；不要 commit。约 100 分钟。

## 543H 当前基线核销与修复（2026-11-06）

- 先只读逐项复现，未照单全收旧问题。①多模块双地、②拓扑轮关系闸、③拓扑轮userLocks、
  ④降级expressions/note、⑤关系尺边界、⑦全锁stall短路均有当前实现与测试证据：
  `tests/test_515a_draw_holes.py`、页级域下发、离格点锁、4820次边界对拍等。
- ⑥旗位预留/落旗曾实锤不同脚：opamp预留C1.2、实际U1.11。现 `_flag_seats` 保留
  `_flag_seat_pins` 的**全部候选**，实际落旗脚必属预留集合，且不再为无供电脚电源网
  按member-id预留。新增成图引线回溯与预留盒断言；四个可出图样本digest不变。
- ⑧页框归属曾实锤错位不报：现part必须完整落在自家模块框或attach宿主框，未分配件仍
  走旧判，合法attach正例与无attach反例分开。错位器件点名 `geometry-outside-module-frames`。
- 主代理：第⑧ **20 passed**、第⑥ **21 passed**；两组frame变异与两组flag变异均先红后
  字节还原。执行者邻域：第⑧100 passed/1 skipped，第⑥73+46+45+1 passed；P38合同未回退。
- 证据 `.tmp_543h_515a/`、`evidence/543g/main_515a_*.log`。全量回归在目标收尾批执行，
  本段不声称真机或全量已通过。
- **全量兼容续修**：首轮出现6条旧反激回归，根因是全部候选被placement逐条叠加成本。
  现 `_priced_seats` 以每网首档计价、全集继续用于覆盖，旧拓扑19件位姿逐项一致。
  六条主代理复跑 **29 passed**；去掉首档去重的变异使成本合同立即变红并已还原。
  证据 `.tmp_543h_515a/flag_cost/`、`evidence/543h/regression_after.log`。
