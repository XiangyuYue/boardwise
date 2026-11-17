# 548J：共享上拉/服务支路联合座位（下一独立批）

## 前提证据

`evidence/548D/full-page/BLOCKED.md` 与 `.tmp_548D/probe_spacing/`：WiFi三颗上拉R4/R5/R6由 `_share_one_bay` 的真实盒+四边GAP膨胀规则排成50节距；R4另被C8顶55。pinGap只服务电容，bottom/1列panelGroups对R6/IO0无合法座位。40/35虽过机器闸但省不够41.5，30穿旗，25/整簇右移55视觉废。不得把本批写成调GAP或pinGap。

## 一个缺口

同类上拉/服务支路的**座位—宿主引线—终端旗—文字**没有共同完整结果。现有bay逐支路外推，后续旗/文字被动选择，可能让页框和视觉同时退化。需要先定义小型可验证合同，再决定实现点，禁止先调共享常数。

## 建议合同

1. 输入只读真实电路、文档声明的同类关系、profile/pose；不按R4/R5/R6、WiFi、坐标或网名硬编码。
2. 一组同类支路共享阅读方向和合法节距；候选外框包含器件文字、host path、终端旗及引线。节距不是全局GAP，也不靠缩小文字/旗。
3. 联合生成有限座位/旗位候选，每个都过真实器件/文字/外来针/异网导体尺；共同供电可各挂本地旗，不拉全板母线，不改GND/power语义。
4. C8/C9与上拉支路共同参与合法座位，不能先摆电容再把电阻顶出去。真实pinGap语义不扩展给电阻。
5. base/topology/最终回放同一BoundPlan；不可满足时具名拒绝，不静默保留散姿或靠readability收尾。
6. 默认不写新声明时旧行为不变；CH34、P43、三岛与既有bay基线逐项核对。

## 小批顺序与验收

- 先做3颗同类上拉+1电容的最小合成夹具：证明同向、逐脚、无穿体/穿旗、文字完整、旗阵一致；加入C8冲突与不可满足负例。
- 再测WiFi真实模块，必须同时报告机器三关、实际frame和主代理视觉，不能只报宽度。若WiFi可读但整页仍差尺寸，下一批再处理页级组合，不在这批强行调页。
- 若需改placement/shared合同，先走 `tasks/shared-platform.md` 集成锁；若只改 `_share_one_bay`，必须证明534/CH343既有页不退化，不能用共享GAP当调参口。
- 至少两项主代理独立变异、CH34/P43邻域、全量四线。真机/git写逐次经岳批准。

## 明确不做

不改页框、不降40、不扩max_nodes、不改near/reach/排名/硬闸、不缩字、不拆buzzer或更多功能岛、不用参考坐标/userLocks、不把25/整簇右移55的视觉退化当答案。

## 人工对照页（2026-11-13 实测，未落图）

- 离线切片复核通过：`pagecompiler._module_view` 派生的 wifi 单岛经标准 `draw compile` 复现已验收几何
  （无 page-box 时 `ecb1c019b217…`，layout 与 `offline/wifi-island.cand1.layout.json` 逐字节同）。
- 真机 test V4 建 P44 `6fb7a1f1f245008e`（空白，只有图幅件），随后 `draw plan` **两候选都 exit 5
  `cannot_build_plan`**：ESP_RST 的 J2 端标签四面被 J5 本体 / GND 导线 / ESP_EN 交叉 / ESP_IO0 端封死，
  排不出名字桩（099d 短路保护）。**没有 ChangePlan，apply 未运行，页未落图，未删任何页。**
- 结论：本批已知的「ESP_RST 降级成两端标签」不是观感问题，它是落图硬阻塞；解阻需生产侧让该支路成对走线
  （或给单模块视图的 pin-tip 标签留座），不在本次授权内。证据 `evidence/548J/wifi-canvas/`。

- 追加（同日第二跳）：按裁决给临时单岛派生件只加一条 `directWiringObligations{nets:["ESP_RST"]}`，`draw compile` 通过且
  ESP_RST 确实成线（该网 0 标签、`labelFallbacks=[]`、逐脚 7 网全对、仅 `J2.8`=NC 悬空）；但 `draw plan` 两候选仍 exit 5，
  卡点转移到单脚跨岛网 **ESP_RXD 的名字桩**（右 J5 本体 / 上 3V3 导线 / 左压 J2 位号文字 / 下 RST 导线端）。
  即单岛视图缺的是页面级标签座位，不是 ESP_RST 一条网。未 apply、P44 仍空白、未 lint/render。
  证据 `evidence/548J/wifi-canvas/` §7。

- 追加（同日第三跳，页级编译路径）：以最初切片为底仅在 `modules[0]` 加 `"grammarRef":"ic-periphery"`，
  `draw compile --page-box 0,0,1170,825` 产出 2 个 `boardwise-page-layout-plan` 候选，模块内部几何
  `ecb1c019b217…` 与已验收候选一致，逐脚 7 网全对、仅 `J2.8`=NC 悬空；但 `draw plan --page 6fb7a1f1f245008e`
  仍 exit 5，卡点回到 **ESP_RST 脚端标签无名字桩**（单模块页无跨岛端口可承接）。未 apply、P44 仍空白、
  未 lint/render。三条合法路径（单模块视图 / RST 直连 / 模块 grammarRef）停在同一条标签座位缺口，
  证据 `evidence/548J/wifi-canvas/` §8。**未完成 548J 算法。**

- 追加（同日第四跳，收尾）：底件用 RST 直连派生件，只改 `partTexts` 两个有限变体。`{"J2":"below"}` 编译通过且
  RST 是导线，但 `draw plan` 仍 exit 5（ESP_RXD 脚端标签无桩，左向名字行改压 3V3 旗 name row）；
  `{"J2":"above"}` 编译即 `layout-unsat`（J2.3V3 的 3V3 旗无处可挂，0 候选）。按裁决两变体皆失败即停，
  **未 apply、P44 仍空白、未 lint/render、无 refdes**。四次合法尝试（单模块视图 / RST 直连 / 模块 grammarRef /
  RST 直连+J2 文字边）同停在 J2 脚端标签座位缺口，需生产侧改动，展示键已用尽。证据 `evidence/548J/wifi-canvas/` §9，
  该 README 首部已标明落图专用衍生件≠冻结规格逐字节重放。**未完成 548J 算法。**

- 追加（同日第五跳，agent-adjusted 收尾）：按授权把 RST 直连 + J2 below 候选的 `LayoutPlan.labels` 清空（实去 TXD/RXD，
  RST 本来 0 标签）、导线与 net 全留、器件零移动，再用 `readability/derive_netlist` 复核：7 网仍单节点，但
  **J2.3/J2.4 变成无任何附着物的空脚**，`required-pin-not-connected` 两条硬违例。可见网名正是这两条单脚网唯一的附着物，
  删名字等于断连——这是连通闸，不是桩/几何问题。按「不绕连通闸、构造器或 apply 拒绝即停」，**未调用 module_plan、
  未建 ChangePlan、未 apply**；下游网表腿同样会红并留下孤儿器件，故不发起。P44 仍空白、无 refdes、未 lint/render。
  五条路径（单模块视图 / RST 直连 / 模块 grammarRef / RST 直连+J2 文字边 / agent-adjusted）全部如实失败，
  剩下只能靠生产侧（脚端标签留座或跨岛具名端口）。证据 `evidence/548J/wifi-canvas/` §10。**未完成 548J 算法。**

- 追加（同日第六跳，agent-adjusted + 5 单位具名短端）：在 labels 清空的派生件上给 J2.TXD/J2.RXD 各加一段 5 单位真实导线
  `(335,685)→(330,685)`（ESP_TXD）、`(335,675)→(330,675)`（ESP_RXD），非标签桩、不消费 stubMin、不加可见标签、器件零移动。
  预检：7 网单一分区、**17/18 脚 connected（唯一悬空 J2.8=NC）**，`required-pin-not-connected` 已满足；但
  `readability` 报两条 `dangling-wire-end` 硬违例——单脚开放网必须有 label/port 才算成立。据此立即停：
  **未调用 module_plan、无 ChangePlan、未 apply、P44 仍空白**。三条机器规则在本机构成闭合矛盾：有名无桩→plan 拒；
  有导体无名→dangling 拒；无名无导体→not-connected 拒。解只能在生产侧（脚端留座 / 开放口端口承接 / 对声明开放网豁免
  dangling 规则）。证据 `evidence/548J/wifi-canvas/` §11。**未完成 548J 算法，未落图。**

- 追加（同日第七跳，标签语义 + 5 单位具名短端）：保留 TXD/RXD 的 `LayoutLabel`，anchor 移到短端自由端
  `(330,685)/(330,675)`、bbox 同移 −5，另加两条 5 单位真实导线。预检：`required-pin-not-connected` 与
  `dangling-wire-end` 均解决（17/18 脚 connected，唯一悬空 J2.8=NC；7 网单一分区），但 `readability` 新增两条
  `text-overlap`——**具名导线自己的 name row 由段自身推导**（`332.5…365`），J2 本体自 `x=345` 起，5 单位短端让名字行
  压在连接器本体上；要避开需约 35 单位左侧净空，超出本跳授权。按「预检不过立即停、不遮」：未调 `module_plan`、
  无 ChangePlan、未 apply、P44 仍空白。三闸几何预算互斥：5 单位解连通不解避让，40 单位解避让却无空位。
  证据 `evidence/548J/wifi-canvas/` §12。**未完成 548J 算法，未落图。**

- 追加（同日第八跳，局部旗位恢复）：新候选 powerSymbols[0] 的 3V3 旗引线起点 (305,705) 经 `derive_netlist` 证明是 **C8.1**，
  按早期 page-box 候选把这一枚旗与其引线恢复为 `(305,765)` rot0 / `(305,705)→(305,765)`，其余几何不动。预检
  `readability.ok=True`（hard 空）、17/18 脚 connected（J2.8=NC）、7 网单一分区。公开 `module_plan(label_stubs=True)`
  随即**通过**：6 件 C25/C26/J5/R16/R17/R18、15 线，TXD/RXD 的 50 单位名字桩自动生成——桩阻塞确实解除。
  但 `draw apply` 在写完全部器件与值后，**引脚回读处 exit 3**：宿主那颗 ESP-01S 是 2×4 双列（脚尖 x=330/400），
  冻结 profile 是单侧 8 脚（x=335），偏差 -5/-25 与 +65；未拉线、未保存。**P44 现有 6 件未保存器件，未清理**。
  根因是 SKILL §3 的「`--profiles` 必须真机实测」——这份 547 冻结库不是本机符号几何。证据 `evidence/548J/wifi-canvas/` §13。
  **未完成 548J 算法，未落成可交付对照页。**

- 追加（同日第九跳，真机校准）：冻结库 `ESP01S-8P` 自述 “NOT measured on the live editor”。按真机 `sch.component_pins`
  （P44 J5 `62c0691e96237abb`，uuid `4662283d21c94f9c9db85d9f8446e5ea`：2×4，左列 x=−35 GND/IO2/IO0/RXD，
  右列 x=+35 TXD/EN/RST/VCC，len 10，body [−25,−25,25,25]）与 `evidence/547/g4/facts/symbol-pins.json` 的 `esp-01s`
  两路互证一致，生成临时 `calibrated.library.json`（只改该 profile 几何/方向/真实 pin 名/source，其它 profile 不动、不宣称已校准）
  与 `calibrated-wifi-island.circuit.json`（只把 `J2.3V3`→`J2.VCC`）。标准 `draw compile --page-box 0,0,1170,825` **通过**：
  1 候选 `51ea23c42e7b…`，bends 9、crossings 0、wire_length 970，J2 在 (215,690)，7 网单一分区、17/18 脚 connected
  （唯一悬空 J2.2=IO2/NC）、J2.8(VCC) 落在 3V3。但标准 `draw plan --page P45=22d51b7d8e39974b` 仍 exit 5：
  **ESP_EN 脚端标签无桩**（右交叉 ESP_RST 竖段、上 ESP_RST 线端、左穿 J2 本体、下穿 J2.5 脚尖）。按「标签仍拒即停、
  不再绕行」未建 plan、未 apply、未建 P46。**P44 保留第八跳 6 件未保存器件（未动未删）；P45 仍空白**。
  证据 `evidence/548J/wifi-canvas/` §14。**未完成 548J 算法，未落成可交付对照页。**

- 追加（同日第十跳，EN+RST 成对直连）：在 calibrated circuit+library 上给 presentation 再加一条
  `directWiringObligations{ESP_EN}`（保留 ESP_RST，note 写明 R4/EN 与 R5/RST 同属 ESP 本地配置上拉），其它键一律未动。
  `draw compile` 几何仍过闸（1 候选 `7925df5a2c9c…`、bends 9、crossings 0、wire_length 970），但 **EN 没有拉成线**：
  `labelFallbacks` 明写 "promised a wire … no free run between (250,685) and (430,685)"，派生 layout 里 ESP_EN 仍是
  0 段导线 + 2 个标签；RST 为导线、TXD/RXD 保留标签。因此本跳验收条件（EN/RST 都成线、无两端 fallback）**未达成**。
  标准 `draw plan --page P45` 同处 exit 5（EN 标签无桩），按「plan 仍拒即停、不改参数」未建 plan、未 apply、未建 P46。
  **P44 六件残留未动未删；P45 仍空白**。证据 `evidence/548J/wifi-canvas/` §15。
  **未完成 548J 算法，未落成可交付对照页。**

- 追加（同日第十一跳，回归干净路径）：去掉 EN/RST 的 directWiringObligations、模块 grammarRef、旧单侧 layout/旗位/短端，
  只保留 **真机校准 profile + `J2.3V3→J2.VCC` + `partTexts={"J2":"below"}`**（逐键比对只有 `partTexts` 变）。
  标准 `draw compile --page-box` 通过且 **`labelFallbacks=[]`**：1 候选 `f4f1c58c00ee…`、bends 9、crossings 0、
  wire_length 890、verdict pass；同类上拉自然一致——EN 成导线、RST 走两端名字；逐脚 7 网全对、17/18 connected
  （悬空 J2.2=IO2/NC）、J2.8(VCC) 在 3V3。但标准 `draw plan --page P45` 仍 exit 5，阻塞是 **ESP_TXD** 脚端标签：
  右被 EN 导线、上被 3V3 导线、左被 RST 名字桩、下被 RST 标签盒占住（3V3 旗 lead 只是其中一条 rung）。
  因「阻塞不止 C8.1 局部旗因」，按裁决停：未改旗、未建 plan、未 apply、未建 P46。**P44 六件残留未动；P45 仍空白**。
  证据 `evidence/548J/wifi-canvas/` §16。**未完成 548J 算法，未落成可交付对照页。**

- 追加（同日第十二跳，原生属性路径）：在 §16 干净件上仅新增顶层 `textPlacement="native-attr"`（P43 用过的宿主属性放名路径，
  可见名字、不隐藏不缩字不降 stubMin、无 obligations、无旧 layout/旗位修正）。标准 `draw compile --page-box`
  **0 候选、exit 5**：`[netlist-partition-mismatch]` —— 判图认为 `ESP_RST`（J2.7/R5.2）与 `3V3` 被放到同一节点，
  即属性名落在了与 3V3 相通的宿主原语上，属未声明短接；7 个变体全部同拒。按「compile/plan 仍拒绝即停、不再换路径」：
  未跑 plan、未建 ChangePlan、未 apply、未 lint/render、未建 P46。**P44 六件残留未动；P45 仍空白**。
  本轮十二次尝试收口：校准是有效成果（干净路径 compile ok、`labelFallbacks=[]`、逐脚 17/18、verdict pass），
  失败全部集中在单岛页脚端名字的座位策略，需生产侧裁决而非继续加规格。
  证据 `evidence/548J/wifi-canvas/` §17。**未完成 548J 算法，未落成可交付对照页。**

- 追加（同日，岳手工版 P44 只读回读）：R1 test V4 / P44 `6fb7a1f1f245008e` 确认后只读采集（doc.list、sch.readback、
  sch.geometry 含 22 个 bbox、6 颗器件的 component_pins、sch.netlist、render PNG+SVG、draw lint），零修改零保存。
  岳把 6 件重新排成 C25(200,675 rot270 mirror) · C26(240,675 rot270 mirror) · R18(290,690) · J5(365,665 未动) ·
  R17(430,690) · R16(465,690)，无增删件；新增 **10 条导线 + 5 枚旗**（VCC×3、GND×2）、0 网标。逐脚按编辑器网表读：
  VCC=C25.1/C26.1/J5.8/R16.1/R17.1/R18.1，GND=C25.2/C26.2/J5.1，$7N2=J5.EN–R16.2，$7N3=J5.RST–R17.2，
  $7N4=J5.IO0–J5.IO2–R18.2，TX=J5.RXD(4) 单脚、RX=J5.TXD(5) 单脚（外端 300,650/430,650 悬空）。
  两处与电路声明不一致如实记录、未恢复：J2.IO2 在电路 `nc[]` 里是 NC 却被连进 $7N4；TX/RX 网名与 TXD/RXD 脚名相反。
  lint 0E/0W/1I（内容占 2.2%），只读不掩饰。证据 `evidence/548J/wifi-canvas/agent-adjusted/`，README §19。

## 岳人工 P44：联合座位判据（读回完成，未生产化）

主代理已亲看 `agent-adjusted/P44-render.png` 全图及原生分辨率局部。完整事实和不变量见
`evidence/548J/wifi-canvas/agent-adjusted/RULES.md`，生产候选必须满足以下关系，而不是复制坐标：

- 上拉按真实宿主脚侧分组，三颗电阻同向、共同底端行；右侧 R17(RST) 在内、R16(EN) 在外，左侧 R18
  接 IO0/IO2。位号序和旧 bay 的 50 节距都不是语义。
- R17/R16/J5.VCC 共用短供电轨与一枚旗；R18 独立本地 VCC 旗；C25/C26 去耦对共享 VCC/GND 各一枚；
  J5.GND 就近独立旗。旗位、宿主路径、支路座位、文字和端口列必须联合生成，不能后补旗再挤死标签。
- EN/RST 等局部直连不重复印名，TX/RX 保留可见、等长的外向短端。不能把隐藏名字当连通。
- 岳已将 IO2 与 IO0 共同上拉，旧 `J2.IO2 NC` 假设不再适用于这张人工版；TX/RX 是对端命名视角，
  与 MCU 侧对账前不判错。后续冻结输入必须先反映这两项人工事实，不能复旧时假设。
- P44 是 `agent-adjusted` 依据页，保留不动。lint 0E/0W/1I 只说明几何，不宣称电气审查或自动算法通过。

下一实现批以“宿主侧支路组”为最小 BoundPlan，联合输出姿态、端子行、宿主路径、共享轨/旗位、
文字、开放端口列和完整 frame；先过最小合成夹具，再用校准后的真实 WiFi 验证。不得把本例 35/40
距离变成新全局 GAP，不得用参考坐标/userLocks 重放人工页。

## 548J-A 公开绘制合同与集成边界（主代理裁决）

`contracts/module-owners.json` 把 `core/presentationspec.py` 明确归为 draw，`tasks/shared-platform.md` §1
也明说 PresentationSpec 不因位于 core 而成为 shared；本批不改 placement、CircuitSpec、ChangePlan、
CLI/connector/DSH/Rust，因此**不触发 shared 集成锁**。新增顶层可选 `serviceGroups`，形状只有：

```json
{"id":"config-pullups","branches":[{"part":"R1","from":"CFG_A","to":"PWR"}]}
```

- 组封闭 `id/branches` 两键，支路封闭 `part/from/to` 三键；至少一条支路，单支路组合法。声明顺序只用于
  稳定遍历和具名拒绝，不承诺几何次序；宿主、脚侧、姿态、端子行、节距、旗位、文字和 frame 均由真实
  CircuitSpec+profile+候选姿态决定。禁止 side/columns/gap/pitch/frame/coordinate 字段。
- 组是联合座位与旗域：同组同一终端轨一枚本地旗，组间同网不拉母线；二端均为轨的去耦对共享两端旗。
  组内局部信号用实际导线表达；directWiringObligations 仍是独立的网级声明，不能互相替代。
- part 必须属于同一模块；一个 part 只能落在 seriesBranches/panelGroups/serviceGroups 之一。
  不同模块、不同器件的 panelGroups 与 serviceGroups 允许共存，不做全页互斥。页面切片整组携带或整组省略。
- 缺省或 `[]`：不序列化该键、digest 与旧文档一致、候选逐字节不变。重复 id/part、from==to、未声明或跨模块
  part、空字段/支路、未知键/坐标均具名拒绝。电路两脚、宿主唯一性和几何可满足性由消费方继续判真。

### 小批顺序与兼容矩阵

1. A：解析/roundtrip/页面切片/负例及公开文档，不生成新几何；B：才接联合座位和最小合成/真实WiFi。
2. 离线普通器件为覆盖范围；V3真机、容器 parser、多板、CBB、Rust迁移均**未覆盖、不得声称改变**。
   V4真机另批在 `test V4` 新页验收，P44人工页/P42/P43/Board2不动。
3. negative control：无键及空数组的旧规范JSON/digest不变；CH34/P43/三岛不消费新键；冲突声明具名拒绝，
   不静默择一；声明不可满足时零候选，不回旧散姿。default-off 的两类变异由主代理独立先红后恢复。

### A 批主代理验收（已完成）

- 主代理集成 `201 passed / 1 skipped`；文档钉含在其中。default 强制写出变异=`3 failed / 30 passed`，
  删除 service 器件唯一检查变异=`1 failed / 32 passed`，均事前 cp 备份并恢复为
  `a97adaf869922979ef3abd4edf78d9cf3ae190342a134a4ac1630ecff74c828b`，恢复后44 passed。
  日志 `evidence/548J/contract/`。parser/pagecompiler SHA 分别为上述 a97adaf8… 与
  `1110e626cb54243f046dcf00c0964fe017baea61f1bbdd0e7899e2a7dda06ceb`。
- 两处把声明顺序误写成端子行来源的注释在 B1 修正，行为不变；真实几何仍未实现。

## 548J-B1 最小合成联合座位（原实现批，已停止）

- 文件域：只改 `drawcompiler.py` 和新增 `tests/test_548j_joint_seats.py`；另修正上述两处注释。
  不改 placement/shared/CLI/drawapply/pagecompiler/其它文法/旧fixtures，不真机、不git。
- 夹具：一个真实双侧8脚宿主、三颗同型上拉、至少一颗去耦；右侧两支路一个 serviceGroup，左侧共享
  启动脚的一支路另一个 group，去耦另组。使用通用 HOST/CFG/BOOT/PWR 事实，不把WiFi位号或网名写进引擎。
- 同组二端件同向、共同终端阅读行，成员次序由真实脚位/合法路径决定；共同终端轨以短导线汇聚并每族
  一枚本地旗，跨组不拉母线。去耦两端均轨时两端各一枚共享旗；宿主GND就近。局部信号必须成线，
  开放信号保留可见等长名字桩。所有文字/host path/旗/引线/端口进入最终plan，页级frame由完整plan量出。
- base/topology/最终回放消费同一组级结果；禁止base兜底、二次搬动、另建placement公共合同、参考坐标、
  userLocks、panelGroups复用、native-attr开关、调GAP/pinGap/页框/near/reach/max_nodes/排名/硬闸。
- 验收：derive_netlist逐脚与分区（共享启动脚）、无短路/穿体/穿旗/文字缺失，开放端口可见等长，
  组级旗域及frame完整；不可满足与电容冲突具名拒绝，不回旧散姿；不写serviceGroups逐字节旧行为。
  聚焦跑新测试、548J合同、548D panel/seat-first邻域及CH34；本批不接真实WiFi、不宣称整页或548J完成。

## 548J-B1 停止与交接（2026-11-13，主代理裁决）

**B1 未通过，停止当前独立 builder 路线。** 目标测试虽为22 passed，交接前组合复跑233 passed/1 skipped，
但当前 `evidence/548J/b1/synthetic.png` 的 CFG_A/PWR 大回环由主代理视觉拒收。没有真实WiFi消费、
B1真机、B1独立变异或本批全量四线，不能称548J/548D/548E完成。

- 当前 `drawcompiler=11b2b3b9a9e1acbbad2bc8123b4af3fccf6aad1c75be3c83d77ab05d20ae9f82`，
  B1前基线仍为058a3032…；`test_548j_joint_seats.py=5b004724f9a5d1f13fb5…`。
  B1含独立builder与多轮修复，不在此继续补丁。
- 当前仍为 `row_y=min(host_body, feet)-GAP`；直接改为 `row_y=min(feet)`（不扣body/GAP）及去耦GND行
  的实验均因新拒因回退。`flag-diagnostic.json` 证明PWR外端(150,705)被TX/RX y=715/735横桩及名字盒封堵，
  障碍抽头后又在宿主GND无合法旗柱；没有通过的正例。不得把这些局部拒因写成全局无解。
- A合同可复用，A两项独立变异和恢复已验收；B1没有主代理独立变异。真实WiFi的IO0+IO2共同上拉、
  对端TX/RX命名和2×4校准profile以 `wifi-canvas/agent-adjusted/RULES.md` 为准。
- P44人工页不动，P45空白，P42/P43/Board2不动；daemon已停，证据 `evidence/548J/daemon-stop.txt`。
- 下一任先读 **`evidence/548J/HANDOFF.md`**。继续或清理由岳另裁；清理必须精确反向本批hunks并核对058a，
  禁git restore、禁rm/unlink。若重做，不再造第二套标准build/route/flag/page-anchor，只做组级计划供
  标准链消费，先拿一个无回环的小闭环再谈真实WiFi/整页。
