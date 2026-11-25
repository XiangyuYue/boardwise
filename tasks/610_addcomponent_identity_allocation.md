# 任务书：610 — add-component 位号解析与分配不得撞名

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的两个身份缺口：

- **D6**：同页两个 R1 时 `primitive_id_of` 返回首个 p1，而同仓 `resolve_on_page` 判 ambiguous；小写 r1 又查不到。返回值可能让后续读脚/写线落到错误器件。
- **D7**：`allocate_designator(["C11"],"C1")` 返回池内已有的 C11。根因是把 prefix 含数字的非法输入与解析出的纯字母前缀比较；不能返回撞名，也不能悄悄改变位号语法。

本批只修身份解析/分配，不动 609 的落点几何。复用 `core.changeplan.resolve_on_page` 的大小写和歧义判据，不复制第三套解析；保留 addcomponent 既有 `state.PrimitiveId` 回退。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- `src/boardwise/engines/addcomponent.py` 开工 SHA `5168ea888a3535e24b96e1e10d345f14153e5fe5257dc63bc2d61f651577b3f5`（609 若已落，以其修后 hash 为准）。
- 194–210 行 primitive_id_of 只精确匹配 `state.Designator`；`core.changeplan.resolve_on_page` 在 3618 起支持 Designator/OtherProperty、大小写折叠和 matching>1，但其 PageComponent id 只取顶层 primitiveId，本批须兼容 addcomponent 原有的 state fallback。
- 664–683 行 allocate_designator 假定 prefix 纯字母。`_DESIGNATOR_RE` 为 `^([A-Za-z]+)(\d+)$`，现有合法大小写池应不变。
- 他人 563/review-line/router/临时文件禁触。开始 cp 备份 addcomponent 到 `.tmp_610/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/addcomponent.py`（primitive_id_of、allocate_designator 及对应注释）
- `tests/test_610_addcomponent_identity.py`（新）
- 本任务书、`.tmp_610/`、`.tmp_pt_610/`、`evidence/610/`

禁止：core.changeplan/shared/CLI/connector/DSH、609 的几何 hunk、其它 engines、fixtures 和他人文件。不得给 resolve_on_page 加全局行为，不得按坐标或输入顺序挑重复位号，不自动改名池中现有器件。既有测试不得删改宽。

## ④ 交付物与验收

### 合同

1. primitive_id_of 调 `resolve_on_page`：`ambiguous` 或找不到一律返回 `""`；大小写与 host 相同，r1 能唯一命中 R1，OtherProperty.Designator 也命中。唯一命中优先返回 PageComponent.primitive_id；若为空，允许从同一唯一匹配 entry 的 `state.PrimitiveId` 回退，不能因换 helper 丢掉既有能力。重复位号即使一个有顶层 id 另一个只有 state id 也必须拒绝。
2. allocate_designator 对非纯字母 prefix（包括 C1、空串、含数字/空白/下划线）具名 ValueError，说明 `<prefix><n>` 的 prefix 必须字母；绝不返回 names 中已有位号。合法 prefix 保持大小写输出形式与原实现（wanted 只用于比较）、最低自由编号和名称大小写折叠；可再加分配后全名 casefold 防碰撞防线，但不改变合法返回。
3. 不引入新异常类型到 primitive_id_of，保持 `""` 表示不能唯一解析，由现有调用方拒绝。

### 先红与修后

新增测试先跑未改生产：重复 R1、大小写 r1、C1 非字母 prefix 用例红；唯一 R1、OtherProperty、state.PrimitiveId、合法 C/c prefix 为控制。必须断言重复时**不返回 p1/p2**，不是只接受任意异常；D7 不仅断言“不是 C11”，还要断言明确拒绝。

修后跑新测试、029a/036/subcircuit/changeplan resolve 邻域、owner/layer；保存完整汇总。至少两项变异：① primitive_id_of 恢复首个精确匹配/忽略 ambiguous；② 允许 prefix=C1 走旧循环。每项新测试必须红，cp+SHA 恢复并复绿。

兼容矩阵：sch.geometry 字典与内存名称池；真实 host、多板、CBB、bridge 未覆盖。negative control 为唯一器件 id、state fallback、合法最低自由编号不变；无真机/写设计声明。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得在重复位号中取最近/首个，不得把 C1 解释成“C 系列从 1 开始”而返回撞名，不修改 fixtures 或既有断言。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含先红、修后命令汇总、两项变异与 SHA 恢复、唯一/重复/大小写/回退矩阵和未覆盖项。证据落 `evidence/610/`。缺有效负控或变异只能写「停止/未完成」。
