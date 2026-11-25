# 563：共享网表查询与可回验电路语义（首批）

> 日期：2026-11-24。状态：563A/B 实现与聚焦验收完成（246 passed）。
> 当前 HEAD `f508328` 已含 563A 与 563B 主体；最终闭环修复、测试与本文档仍属后续工作树改动，未提交、未推送。
> 来源：路线图的「AI 电路语义编译层」现在启动；绘制线工作树在
> `engines/drawlint.py` 新增了 `NetlistPin/NetlistPart/Netlist`、
> `read_netlist_document()`、`pin_nets()`、`pin_count()`。本批以其为输入，
> 不另造第三份解析器，也不把字符串换格式冒充电路理解。

## 1. 首批完成定义

两个串行小批：

- **563A shared 解析与查询**：把薄解析器移入 `core/netlist.py`；保留 drawlint
  原有公开别名与 L12 行为；`core/candidate.py` 改为消费同一解析器；
  增加带实例身份的 `PinRef` 和 `NetlistView`，回答精确的引脚、网络成员、
  邻居、器件网络与未连接引脚查询。`core/connectivity.py` 可复用其网络成员读取，
  但既有 `component_net/pin_company/nc_violation` 行为不得变化。
- **563B 语义投影**：新增纯函数 `compile_semantics(NetlistView)`，输出版本化
  `boardwise.circuitSemantics/1` 结构及确定性的类 C 文本；结构包含完整原始事实、
  派生关系与歧义/未证明项，并能用结构化结果重新编译对拍。C 文本是投影，
  **本批不写 C 文本解析器**。

公开 Python API 即可，不新增 CLI、bridge、Connector、DSH 工具或 Rust 主流程。
这批不是自动审查规则，也不改变 finding/severity/verdict、布局、网表成员或报告。

## 2. 数据与身份合同

- 原始 `sch.netlist` 的 `{type:"EasyEDA",text:...}` 包装和已解码
  `{version,components}` 都走 `read_netlist_document()`；垃圾、空模型、未知结构
  明确拒绝，不把不可读解释成「没有连接」。
- `NetlistPin/NetlistPart/Netlist` 保留薄读取器既有字段与方法。为统一 candidate
  可增加 `source_id`、`key`、`props` 等附加元数据，但不得改变 drawlint 的
  `parts/designator/pins/number/name/net` 读数。
- `PinRef(designator, number, source_id="", pin_key="")` 是不可变值对象；`ref` 为
  `DESIGNATOR.NUMBER`，解析用户字符串时在**最后一个点**分割。`source_id`
  是 host components 条目的 key；`pin_key` 是 host `pinInfoMap` 的 key。
  同名多单元/重复位号按实例寻址；同一实例的同脚号不同 pin key 也不得被折叠或
  first-wins。没有足够身份字段判断多单元还是重复放置时，只能称「同名实例」。
- `NetlistView` 可由 `Netlist` 或既有 `DesignModel` 构造：
  - `members(net)` 保留来源模型成员顺序与重复实例，不按名字合并；
  - `net_of(designator, number, source_id=None)` 在无名查询命中多个实例时抛
    `AmbiguousPinError`，不得任选第一个；指定完整实例/脚 key 后精确回答；
  - `neighbors(...)` 只回答同一 net 的其他引脚，不把单脚自动网说成连接；
  - `nets_of(designator, source_id=None)` 按器件引脚顺序去重，空网不返回；
  - `unconnected()` 只列空网引脚；有名字的单脚网不属于空网；
  - `duplicate_designators()` 只披露同名实例，不擅自按 MPN/value 合并；
    另有 `ambiguous_designators()` 供语义层同时排除 `cross_page_designators`。
- `from_model()` 的成员表以 `model.nets` 为准，器件引脚以 `model.components`
  为准；模型已丢弃的实例不得编造回来。`model.unproven_nets` 必须进入语义层的
  unknowns，不得参与 parallel/series 派生。
- candidate 的历史投影保持：值/封装/LCSC/MPN 等字段、entry 顶层或 props 内的
  `Unique ID`、`R?` 跳过、重复位号披露、后实例覆盖 component、所有实例仍贡献
  net members、按原 map key 的 `len(key)` 排引脚、空 net→`None`、raw 四个尾段，
  以及 `NetlistFormatError` 对外类型。不借统一解析器修复或改变 552 的文件侧
  多单元语义。

## 3. 语义函数：只编译拓扑事实

首批只有以下语句；所有数组顺序确定，JSON 可 canonical 对拍：

- `part(...)` / `pin(...)` / `net(...)`：完整保留原始器件、引脚与网络成员事实，
  包括重复实例和单成员网。它们是回验底座，不只是给人看的摘要。
- `unconnected(...)`：空网引脚；不等于「设计错误」。
- `ambiguous(...)` / `unproven(...)`：重复位号、未证明网或无法线性化的环等，
  只披露原因，不猜结论。
- `two_pin(part, pins=[...])`：恰好两条引脚的**唯一位号**器件；保留脚号、脚名和
  各自 net，不表示电流方向，不推断电阻/电容/二极管类型。
- `parallel(parts, between)`：至少两个合格的 two-pin 器件，其两个非空、不同
  网络组成同一无序对；每组恰好一条。两端 net 排序只用于规范化，不表示方向。
- `series(parts, nets)`：合格 two-pin 器件通过仅含两个不同器件引脚的内部网
  串成极大简单链。`nets` 必须包含**两个端网与全部内部网**，所以数量为
  `len(parts)+1`；端网不是这种二度网，空端网原样保留。链不可重复器件或网，
  **两个端网相同也算重复并形成闭环**：≥3 器件时记 cycle，不输出 series；
  两器件两端同网仍只按 parallel 表达。闭环某个网上另有第三脚也不能把它变成串联。
  纯环不强行选起点，记 unknown，不输出 series。`nets` 顺序是链的拓扑顺序，
  不代表电压或信号流；正逆规范化时必须同步反转 parts 与 nets。
  `to_c()` 的 two_pin 脚表示也必须带 pin_key，不能让同号不同 key 在文本里折叠。

明确禁止从网表名字或形状推断：`decap`、`filter`、`driver`、`opamp`、
`power_path`、地/电源功能、信号方向、跨板同名相连。后续语义必须另立证据合同。

`SemanticProgram.as_dict()` 至少含 `schema`、`parts`、`pins`、`nets`、`relations`、
`unknowns`；`to_c()` 输出 `// boardwise.circuitSemantics/1` 与对应函数调用。
`verify_semantics(view, program)` 重新编译并比较完整结构化程序；`roundtrip_members`
对拍原始与程序中的逐脚网络事实。任一成员、NC、unknown 或 relation 被改都必须失败。

## 4. 必须钉住的反例

1. `U15` 两个 host 实例：无名 `net_of("U15","1")` 必须歧义拒绝；按 source_id
   可分别回答。不得把同名实例静默合并，也不得把多单元当成两颗同编码料报错。
2. `R1` 与 `R2` 经 `MID` 串联，但 `MID` 再有第三脚时不得输出该 series。
3. 两个 two-pin 器件端网相同才可 parallel；只有一端相同不可。
4. 同名跨页/跨板 `unproven_nets` 不得生成 parallel/series；同名不等于相连。
5. 重复位号器件不参与 two_pin/parallel/series 的功能化投影，原始 net/pin 仍完整。
6. 空网进 unconnected；单脚命名网不进入 unconnected，也不产生空名 net。
7. 位号含点时按最后一个点解析；`U9.3` 不得借用 `U9.33` 的脚名或身份。
8. 纯 two-pin 环不得任意选起点输出 series；unknown 必须说明。
9. 从程序删除一脚、改一个 net、删一条 unknown 或删一条 relation，verify 必须红。
10. 既有 drawlint L12、candidate diff、review-read netlist 与 connectivity 读数不变。

## 5. 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| host EasyEDA JSON | wrapper/raw、普通件、重复实例、NC、合成拓扑 | Protel/PADS 等未校准格式 |
| `.epro2` / `.eprj2` / `.eprj3` | 解析器未改；`from_model` 的合成模型与既有邻域 | 不声称新做三种真实容器兼容验收 |
| V3 / V4 host | 同一 JSON 读取合同；不碰宿主动作 | 不声称完成新真机 V3/V4 验收 |
| 在线 / 离线 | 纯内存查询；既有 candidate/drawlint/review-read 消费者 | 不新增在线入口，不读 EDA，不写设计 |
| 单 / 多板 | 单一 NetlistView；模型 unproven 保守阻断 | 不把跨板同名合并，不启动 041 S3/S4 |
| 普通件 / 多单元 / CBB | 普通件与同名实例身份；CBB 内部展开未覆盖 | 不声称 CBB 内部语义完成 |
| 重复 PCB / 分歧库 | 本批不改容器合流 | 不借用 038P1 的绿代替本批验证 |

## 6. 文件域、验证与回退

- 563A：新增 `core/netlist.py`、`tests/test_563_netlist_view.py`；必要修改
  `core/candidate.py`、`core/connectivity.py`、`engines/drawlint.py` 的薄函数段、
  `contracts/module-owners.json`。不动 drawlint 的其他未提交绘制改动。
- 563B：新增 `core/circuitsemantics.py`、`tests/test_563_circuit_semantics.py`、
  `docs/circuit-semantics.md`；只补 owner 与本任务/台账，不改 563A 业务代码，
  除非主代理复验给出具体拒因。
- 每批开工先 `cp` 备份所有将改文件并记 SHA-256；绘制线工作树为混合未提交状态，
  禁止 git restore/checkout。测试只跑聚焦：`test_563_*`、`test_candidate_draw.py`、
  `test_lock_p1_delivery_gates.py`、`test_537d_review_read_netlist.py`、
  `test_540_shared_connectivity.py`（若实际文件名不同先定位）、owner/layer/doc claims。
- 每批至少两项因果变异，先红后 `cp` 恢复并核对 SHA-256；563A 至少覆盖「歧义不再拒绝」
  与「candidate 不再保留重复实例成员」，563B 至少覆盖「三脚中间网误产 series」
  与「unknown 不参与对拍」。无效变异必须报告，不能凑数。
- 当前基线：上述 candidate + drawlint + review-read + owner 为 **109 passed**。
  当前关键文件 SHA-256：candidate `c267cb004124d60c313709c7f24eddc8fcc083381831ab5a9781120504a47f09`；
  drawlint `26721d59fdd65841866a9286990694c5a9b099200db95cd59f2fffd1c5ec3886`；
  reviewread `b1ee09fb83c84e23ed91e6f59f3b61e6e4585a589c4e537107758580bf92e8ba`。
- 零 git 写、零 push/release、零删除、零真机、零全量。版本不 bump。
  回退只经 cp 恢复本批文件，不能覆盖其他线改动。


## 7. 验收记录（2026-11-24）

最终主代理聚焦命令：

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest \
  tests/test_563_circuit_semantics.py tests/test_563_netlist_view.py \
  tests/test_candidate_draw.py tests/test_lock_p1_delivery_gates.py \
  tests/test_537d_review_read_netlist.py tests/test_540_shared_connectivity.py \
  tests/test_owner_rules.py tests/test_layer_rules.py tests/test_doc_claims.py \
  tests/test_540_cli_draw.py tests/test_540_cli_review.py tests/test_540_cli_shared.py \
  -q -n 4 --dist loadfile --basetemp=.tmp_pt_563_final
```

汇总：**246 passed in 17.79s，0 failed / 0 errors**。
563A 独立邻域 **141 passed**；563B 语义与 view/owner/layer **60 passed**；
563B 原影响面 **107 passed**。这些是聚焦读数，不是全量。

主代理独立变异：

| 因果项 | 变异结果 | 恢复 |
|---|---|---|
| `core/netlist.py` 去掉 pin key 身份 | **5 failed / 5 passed** | cp 后 SHA `29f3c670…65f6b8`，10 passed |
| `core/candidate.py` 去 entry UID 回退 | **1 failed / 9 passed** | cp 后 SHA `591d777d…1e23d6`，10 passed |
| `core/circuitsemantics.py` series 只留内部网 | **5 failed / 21 passed** | cp 后 SHA `9a5aecea…c02e5ecc7a1` |
| 允许同名端网闭环进入 series | **1 failed / 25 passed** | cp 后 SHA 同上；最终 246 passed |

审查返修还覆盖了：candidate 顶层 UID 回退、同号不同 pin key 不折叠、
不把同名实例猜成多单元、series 必须带两个端网、C 文本 two_pin 必须带 pin key、
同名端网加第三脚仍是闭环。无键 C 文本分支使用直接清空 key 的真实投影测试，
不是恒绿断言。

实现期文件域外没有绘制算法、CLI/DSH/bridge、fixtures 或真实工程改动。
未跑全量、Connector、DSH、Rust 或真机；无 git 写、推送、发布或文件删除。
