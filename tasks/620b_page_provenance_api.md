# 任务书：620B（shared）— PageLayoutPlan provenance API 兼容

## ① 前因后果

全量新增 `tests/test_590_plan_provenance.py::test_real_candidates_state_their_route_and_a_seal_of_their_own`：`PageLayoutPlan` 只有 `page_provenance_sha256()`，而 590 的统一合同调用 `document.provenance_sha256()`，导致 AttributeError。当前 HEAD `76e0806` 已含这个命名分歧，不是本轮新算法回归；596 的最终全量发生在该提交之前。

本批只补 API 兼容：保留 `page_provenance_sha256()`，增加 `provenance_sha256()` 别名，沿用 LayoutPlan 的统一调用形状，返回值必须仍是 page geometry + route + `PAGE_PROVENANCE_DOMAIN` 的既有 seal，不改变 route、geometry、provenance 字节或候选。不能修改 590 测试来迁就缺失方法，也不能用 `__getattr__` 隐藏其它属性错误。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–620C 改动保留。
- `src/boardwise/core/pagelayoutplan.py` 当前 `page_provenance_sha256` 在 237–241 行，调用共享 `layoutplan.provenance_sha256(self.route, self.page_geometry_sha256(), PAGE_PROVENANCE_DOMAIN)`。
- `LayoutPlan.provenance_sha256` 是同类公开方法；`PageLayoutPlan.to_jsonable` 在 346–349 已使用 page 专用名。
- 全量其余 9 条为既有基线；534z 由 620C 处理，本批不碰。
- shared 文件需单独集成，至少验证 LayoutPlan 与 PageLayoutPlan 两个消费者、JSON round-trip 和 owner/layer。开始 cp 备份 pagelayoutplan 到 `.tmp_620b/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/core/pagelayoutplan.py`（兼容别名与必要注释）
- `tests/test_620b_page_provenance_api.py`（新）
- 本任务书、`.tmp_620b/`、`.tmp_pt_620b/`、`evidence/620b/`

禁止：layoutplan.py、pagecompiler/drawcompiler、其它 shared/parser/model、CLI/connector/DSH、fixtures、既有测试和他人文件。不得改 provenance/domain、route 默认、geometry digest、JSON 字段名或页面候选，不添加第二套 seal。

## ④ 交付物与验收

1. 新增 `PageLayoutPlan.provenance_sha256()`，实现只委托 `page_provenance_sha256()`，docstring 明确是 LayoutPlan 同形 API 的兼容别名。旧 page 专用方法保持原样，所有现有调用点不改。
2. 新测试用 `_page()` 或现有最小 PageLayoutPlan，断言别名与 page 专用方法相等，且与独立 `layoutplan.provenance_sha256(route,page_geometry,PAGE_PROVENANCE_DOMAIN)` 相等；LayoutPlan 同名方法行为不变。验证 to_jsonable 的 provenanceSha256 也一致，pre-590 仍无 route/seal。
3. 真实跑 `tests/test_590_plan_provenance.py`（应恢复全绿）、590B/590C/599/582/583/540 CLI 和 owner/layer 邻域，保存完整汇总。先红可用当前 API 缺失作基线，修后不重写历史。
4. 至少两项生产变异：① 删除别名，590 的 original failure 必须红；② 别名错用 LayoutPlan 的 `PROVENANCE_DOMAIN` 或嵌套 plan digest，page seal 独立断言必须红。每项 cp+SHA 恢复并复绿。

兼容矩阵：LayoutPlan 与 PageLayoutPlan、自动/pre-590 文档、JSON round-trip。V3/V4、真实容器、多板/CBB、真机未覆盖。negative control 为旧 page 专用调用、route/geometry/字段字节不变，590 测试不改。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量复跑（集成轮统一）、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得把页面 seal 改为嵌套 LayoutPlan 的 seal，不修改测试、候选或旧文档，不实现 `__getattr__` 掩盖其它错误。

## ⑥ 预算与交卷格式

一个 coder，最多 30 步或 20 分钟；不派下级。交卷 ≤1500字，含 API 缺失基线、修后命令汇总、两项变异与 SHA 恢复、两个消费者/兼容矩阵和未覆盖项。证据落 `evidence/620b/`。缺 590 全绿或变异只能写「停止/未完成」。

---

## 交卷记录（620B，2026-11-25）

- 改动：`src/boardwise/core/pagelayoutplan.py` 增加 `PageLayoutPlan.provenance_sha256()`，只委托 `page_provenance_sha256()`；新测试 `tests/test_620b_page_provenance_api.py`。
- 基线（修前）：`pytest tests/test_590_plan_provenance.py` → `1 failed, 28 passed`，失败即 `test_real_candidates_state_their_route_and_a_seal_of_their_own` 的 `AttributeError`（test_590:398）。
- 修后：同批 590 + 620B 新测试 + 599/582/583/owner/layer/540 CLI 三件套 → `230 passed in 43.58s`（exit 0）。
- 变异①删别名：590 原失败红 + 新测试 7 红（8 failed）；cp 恢复，sha256 `5b4cc29f…e60e97a`，cmp 一致，复绿 36 passed。
- 变异②别名错用 drawing 域：独立 seal 断言红（7 failed, 29 passed）；cp 恢复，同上 sha256/复绿。
- 真实候选 `outputs/054_drawcompile/cand{1,2,3}.page.json` 读→写字节一致，别名==page 专用==共享 helper。
- 证据：`evidence/620b/`（README + baseline/final/mutation 日志）。
- 未覆盖：V3/V4、真实容器、多板/CBB、真机；未跑全量（按任务书留给集成轮）。
