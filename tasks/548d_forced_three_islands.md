# 548D3D-T1：强制 topology 三岛组合

## 当前实测（不是推断）

生产 `drawcompiler=1c7c93b9766e842c266458617dbced1caea666b7e6a6edcf6517efd09302bd2a`，`drawapply=f713895fe5e92688e0d84330e3ff30f0aa4dee7bda706f50a7493808ea8b5daf`。

`evidence/548D/host-binding/three-island/probe_forced.py` 将 `_variants` 与 `_widened_variants` 都置空，禁止base兜底，分别编译既有三岛规格和stubMin40+native-attr规格。两例均为：mcu=true、led=true、keys=false；KEY首个硬错为 `segments[2]` 穿过 `powerSymbols[1]` 的drawn extent（box [-46,-85,-34,-67] near(-40,-77.5)），`wire-through-body`。原始读数 `report.json`。这不是完整三岛通过，也不是真实SmartMedicineBox整页。

## 完成条件

先比较同一KEY冻结输入的base合法几何与强制topology被拒几何，确定是座位、旗位、共同power bank或回放分叉，禁止只调搜索次数/排名/near/reach或删检查。修复必须保持既有base三岛、MCU/P43、CH34与未启用新能力页面的行为，不改语义分岛、冻结电气、页框、userLocks或参考坐标。

- 强制topology下 `_variants`/`_widened_variants` 均空，mcu/keys/led都真实出候选；`baseline` 与 `port-native` 两例均ok。
- `t._per_pin_problems` 空、`readability.check_page` 空，独立分区/短路/NC按既有helper补核；跨岛只以名称连接。
- 生成两例SVG/LayoutPlan，主代理逐岛视觉签收；失败候选只留evidence，不落画布。
- 新测试 `tests/test_548d_forced_three_islands.py` 钉禁止base兜底的真实产物，不能只测布尔或私有模板；加回归后原548D/P43邻域不红。
- 生产文件域优先drawcompiler及既有coreless helper；若确需placement/shared，先交集成边界，不顺手改。测试/证据上述命名域；不真机、不git写、不删除。

## 复验

主代理抽diff、独立变异（禁用修复必须先红后cp+SHA恢复）、真实渲染和CH34邻域；全量与其他四线另记。后续真实整页仍独立，不借三岛合成合同关闭。

## T1A 根因裁决（只读分析后）

证据 `three-island/analysis/README.md`：base四支100节距同pose；forced四支0/180/90混姿，联合旗长从10退为None，随后同网预占S3/S4同锚(-45,-120)。H6/P1不在这条路径，不能拿它们当根因。

采用**现有coreless规则的topology投影**，不调用base梯子兜底：topology结果返回后、锚定/lattice与最终回放量刑前，对 `_coreless_return_column` 声明的组应用 `_place_coreless_column` 的同一共同端共线/真实盒节距规则，并用组内公共合法pose保证共同return方向一致。此投影只对该显式left/right组生效，其他模块原样。保持base构图函数不调用，forced仍由placement.place+topology回放真实产图。实现若证明需要改placement.py，先停止交shared锁，不直接扩域。

必备第二道防线：同网兄弟旗的预占和回放不得共用/重叠真实glyph盒；`_take_lane` 的同网豁免服务的是同网导线连通，不是两面旗重复占位。回放检查除router.boxes外还要核本次已画兄弟旗occupied/solids；不合法时丢弃预占并走普通梯，仍不合法则具名拒绝，不能把重旗交给readability收尾。base合法几何/CH34不变。

测试除任务书三条外，增加base digest不变、同网预占重盒负例；不能只修成“无硬错但四支散姿”，视觉仍要求同向/同节距/旗阵一致。

## T1B 主代理授权：P1C 普通信号与旗位同场景（文件域不变）

T1实现者已证 BOOT0 交叉来自 `_seat_first_path_first_terminal`，不是coreless投影或共享binder。主代理明确该修复仍属本三岛文件域，不需要改placement/shared。

当前P1C把carrier walls加入旗位场景，却漏了 `signals.walls`；`_seat_first_signal_failures` 又只查顶点，不查普通信号与旗lead/member path的跨度交叉。按以下闭环修：
1. 有carriers的迭代中，旗位分配场景加入**上一轮**普通信号跨度墙；信号预飞使用不含旧自身信号墙的另一scene，避免自己的旧线把自己拒掉。names场景继续排除旧carriers。
2. 收敛除labels/carriers相等外，还要signals.segment_map相等；最终scene/plans/signals确实同一轮。
3. 仅在port-carrier模式新增独立拒绝：普通信号跨度与旗lead/member path交叉即拒，不能只查vertex。无stubMin的旧路径保持原行为和旧已知视觉边界，不借本批宣称裸标签基线可交付。
4. port-native强制三岛新增BOOT0与3V3/GND零交叉断言；P43真实64几何/三读数保持，CH34和60+6聚焦不红。若仍不收敛，具名拒绝并保留证据，不放宽交叉。

这属于已完成P1C的互检缺漏，不新增公共schema、页框、搜索上限、排名或实例常量。
