# 548D3D-P1：path-first 宿主侧端口列

## 缺陷与已核实接点

H6 的真实64脚候选 `evidence/548D/host-binding/h6/out/h6.svg` 机器检查为空，但主代理放大视觉拒收：KEY1–4在右脚33–36原点，LED1/2在左脚17/18，plan没有标签短桩，KEY文字压预览脚号，LED名字错列。不是六个label bbox互相重叠。

只读证据 `evidence/548D/host-binding/port-column/`：path-first 在 `_seat_first_path_first_terminal` 调 `_seat_first_label_map` → 裸 `_label_for`，从未调用 `_local_label_carriers`；`_path_first_plan` 只消费labels和signals，因此没有segment。`_reserve_label_stubs` 的seats本身不产生segment。

## 一个缺口的完成条件

对 `localLabelObligations` 中且最终为label-style的网，path-first 必须生成完整结果：原始脚点key → 可见LayoutSegment（脚点到far）→ LayoutLabel（anchor=far，真实box）。同一 `(host part, 实际出脚方向)` 的声明端口共同选一直桩长度/阅读列；先尝试文档 `labelPolicy.stubMin` 首选值，再沿既有 `LOCAL_LABEL_RUNGS/grid` 有限档位整组换档。不得逐脚偶然错列，不得按KEY/LED网名或坐标硬编码。脚距不足时的扇出不属本批。

复用 `_local_label_candidate` / `_local_label_carriers` / `_local_label_trial_box` 的真实碰撞与文字梯，不发明第二套盒尺。carrier规划必须避开当前path-first的器件、文字、旗、服务通道和已预飞线；`_local_label_carriers` 负责最终box与segment，不能再退回pin上的裸label。最终labels仍按原脚点key入terminal，carrier segments可并入terminal.signals.segments/walls由 `_path_first_plan` 统一消费，避免另建平行LayoutPlan通道。

`_path_first_audit` 新增：声明端口的原脚点与label anchor必须由一条本net实际segment连接；缺段、零长度、连错脚/锚点即拒绝。既有fallback-at-pin语义不变。相同输入replay必须labels与segments都一致。

只在文档显式写 `localLabelObligations` 时启用；不写、非path-first、generic fallback均保持旧行为。不要改公共schema、drawapply兜底、near/reach、旗位/排名/硬闸、参考坐标、userLocks、P42或冻结电气输入。

## 真实输入

复制H6脚本到 `evidence/548D/host-binding/port-column-p1/`，不改H3/H6。PresentationSpec在现有localSeats上增加一个 `localLabelObligations` 条目，nets为KEY1/KEY2/KEY3/KEY4/LED1/LED2，note说明它们是MCU与独立KEY/LED功能岛的信号边界、每脚以名称跨岛连接；这是语义声明，生产算法不得读这些名字。`labelPolicy.stubMin=40` 是这份规格的首选桩长，不是生产常量。真实64脚本须重新输出JSON/SVG及per_pin/readability/grammar。

## 文件域与验收

- `src/boardwise/engines/drawcompiler.py`
- 新 `tests/test_548d_host_port_columns.py`
- 新 `evidence/548D/host-binding/port-column-p1/`

测试≤6条高价值几何合同：同侧等长同列、原脚→far→label、首选长度与整组换档、未声明不变、audit缺段负例、replay一致。真实候选主代理视觉后才可签；profile的pinTexts为空不得伪造已实测数据，预览与宿主尺差异如实披露。

聚焦含现有43条，`-n 0`独立basetemp；加path-first/local-label/CH34邻域，不跑全量、不真机、不git写、不删除。≤40模型步骤或30分钟，交卷≤2000字，超预算带实测状态交回。主代理负责diff、变异、视觉、全量与P43。

## P1A 主代理裁决（依据实现实测更正触发合同）

原方案借用 `localLabelObligations` 被真实校验否决：KEY/LED在MCU切片里是单脚网，该键只接受岛内的局部连接，不能为绕过校验而改它。**不改该键、不改parser/schema。** 新触发改为 `_service_layout_page(ctx.presentation)` 且 `labelPolicy.stubMin > 0`；处理对象为 `_seat_first_label_map` 已经产生的、非generic-fallback的label-style网。未写stubMin的页面继续逐字节旧行为，真实规格写40作为首选，不是生产常量。`BOOT0` 是wire-style服务通道，不得进入moves；上一版以BOOT0做探针得出的“被R1脚顶死”与本次KEY/LED标签无关，不据此放宽pin-tip规则。

上一版 `6d18cd30…` 仅作半成品起点，必须修正：①按上述触发改 `_seat_first_port_columns` 与 `_path_first_carrier_failures`，不写localLabelObligations也覆盖真实KEY/LED；②初次 `again_labels` 应与port转换前的base labels比较，否则转换后必然误报non-deterministic，完整terminal replay另核carriers；③共享组级router/格点测量，避免每脚每档重建整页router的16.68秒回归，不能删碰撞检查；④port生成的label须携带规格的stub_min，plan/apply读同一首选，不改drawapply；⑤补任务书要求的真实几何测试与真实64成功SVG/JSON，43条保持绿。若下一红属于KEY/LED真实几何再逐项报告，不拿BOOT0拒绝代替。

## P1B 主代理视觉拒收：候选必须查实际导体跨度

P1A真实64虽已出列，主代理放大 `out/p1-zoom.png` 发现LED1/2短桩与既有3V3/GND引线交叉（soft crossings=2），不签视觉。根因接点：`_seat_first_port_columns` 的 `_local_label_candidate` 只量格点/name row/taken，未像 `_local_label_carriers` 的未预留分支那样对整条候选调用 `_span_free`；其router的seek已含 `_seat_first_path_walls`，但没有被用于跨度拒绝。

续批只在同一函数/测试/证据域：对每脚每档直桩用该脚已建router与blocked补 `_span_free`（保持原脚起点豁免和既有墙体语义），失败则整组换档；首选40不再是必须照画的距离，碰撞时可共同退到更短合法列。不得通过删除path walls、允许跨网交叉或调soft排名闯关。新增负例须放一条真实导体墙挡住首选档，断言整组换档且所有段与该导体无交，旧未声明行为不变。修正 `_path_first_carrier_failures` docstring仍写localLabelObligations的旧描述。真实64重新生成，机器三关+crossing读数+主代理放大视觉分别验收。若所有档均被旗位列挡住，具名交回，不能省略 `_span_free`。

## P1C 端口与旗位必须消费同一完整场景

P1B机器crossings=0，但LED1盒近边=-128、LED2=-151.5，阅读列仍不齐，主代理不签。原因：初始旗位按裸label场景决定，port生成最终label后没有重跑旗位联合分配；LED2只能为3V3旗单独退到更远的box rung。仅把两个盒统一推到rung2是局部化妆，不做。

有carrier时，保留最终labels和carriers，把label盒与carrier实际跨度墙加入scene，调用既有 `_seat_first_plans` 重新联合分配旗位；再以新 `_seat_first_path_walls` 重跑signal preflight并做全部既有label/signal/channel/fixed/determinism检查。carrier跨度对旗位为真实障碍，不许只在事后忽略交叉。terminal.scene/plans/path_walls/signals须一致，final plan继续只从该terminal生成。未启用stubMin或无carrier不进入重排，旧几何不变。

新增断言同 `(part,side)` 的label阅读盒近边也同列，不能只钉anchor；现有缺段/跨度墙/首选/旧行为合同保持。真实64期望KEY/LED名字都贴近自己的短桩终点且同组齐边，旗位可换合法候选但不能交叉/压字。若重排导致fallback集合改变，当前批次应具名拒绝并报告，不能悄悄丢掉原generic fallback。生产仍不读网名/实例坐标，不改公共schema或drawapply。
