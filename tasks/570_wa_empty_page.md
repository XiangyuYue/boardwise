# 任务书：570 / W-A — 空页证明、图元覆盖与复用写前闸

- 日期：2026-11-24
- 范围：TRIAGE **566-A-1 / A-2 / A-3**，只修空页证明与复用，不处理 A-4 suspect。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不跑全量 pytest。

## ① 前因后果

`outputs/hole566/a/REPRO.md` 已用流程探针证明三条洞：

1. **A-1 会造假结果**：`_draw_geometry_readable` 只拒 `available.components=False`，`wires/pins/netlabels` 读失败仍被当成全零空页。P3 中有 1 根导线的页被复用，11 次写含保存，报告同时写 `provably empty`、`reused=true`、`censusBefore.wireCount=1`。
2. **A-2 会漏**：`sch.geometry` 只 dump components/wires/pins/netlabels，文字及其他绘图 primitive 不在响应与空页判据中。宿主类型面没有独立 `sch_PrimitiveLine`；实际可读类别包括 `sch_PrimitiveText/Bus/Circle/Rectangle/Arc/Polygon`，不得虚构 `lines` 接口。
3. **A-3 会漏**：写前 `page_not_empty` 仅 `if report["page"]["created"]`，复用页绕过第二道闸。必须让扫描和写前共用同一非空判据，复用后、首次写前再拒一次非空页。

569 W-T 已验收并在工作树，不能回退其标题栏改动。A-4（geometry 无页身份）仍是 suspect，本批不冒充已复现、不顺手扩成真机任务。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`；混合未提交，零 git 写。
- 569 已落：`src/boardwise/cli.py` 当前 SHA `e06e1a90422cf91ddb24857ae628f82241a198a5e2db6a9aa774461d859b2340`；`core/pageframe.py`、`tests/test_057_draw_page_cli.py`、`tests/test_569_title_block.py` 也有 569 改动，必须保留。
- 本批其余关键文件开工为 HEAD 原样：
  - `engines/drawapply.py` SHA `9523b43309a86a5afffcc1762c4efa16a2653410a813c17294c6a86a15c3f5ae`
  - `connector/src/actions.ts` SHA `a57154c3f2e12e6f529b461064ca6d6dc7bdd7c71cc2efe9d032919dc0b2c971`
  - `tests/test_054_draw_cli.py` SHA `18a4bd3266f2be16de409d8931af4de7061e24ca3f539b907c4b3f81aa4d1d18`
  - `connector/tests/actions006.test.mjs` SHA `a187d9be0ab58f201a87bf78f72d5bec687da615b4ac575c06cc2d254af94173`
- 他人的 563 文件、`tasks/568_draw_holes_wave3.md`、PROGRESS/handoff/roadmap/TASKMAP/review-line 与临时件继续禁触。
- 现状锚：`cli.py:12019-12039` 可读性闸；`:13559-13617` 扫描/复用；`:13791-13810` 写前 census；`drawapply.py:4614-4647` census，`:6144-6156` 四个电气 section；`actions.ts:5110-5157 geometryOf`、`:5175-5245 schGeometry`。

实施前 `cp` 备份所有本批生产文件到 `.tmp_570/backup/`，记录修前/修后 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/cli.py`（空页扫描、复用写前闸及报告）
- `src/boardwise/engines/drawapply.py`（几何 section 常量与非空辅助；不改布局算法）
- `connector/src/actions.ts`（`sch.geometry` 的加性 namespace dump）
- `src/boardwise/bridge/protocol.py`（仅 `sch.geometry` summary/returns 与新字段一致）
- `docs/bridge.md`（仅 `sch.geometry` 行）
- `docs/draw.md`、`docs/pits.md`、`src/boardwise/core/changeplan.py`（主代理续审授权：仅同步四类电气 baseline 与六类绘图 section 的现行口径，不改行为）
- `tests/test_570_empty_page.py`（新聚焦回归）
- `tests/test_054_draw_cli.py`、`tests/test_057_draw_page_cli.py`（只更新假宿主几何能力/加性报告，不放宽断言）
- `connector/tests/actions006.test.mjs`（新 namespace 的生产 dispatch 合同）
- 本任务书、`.tmp_570/`、`.tmp_pt_570/`、`evidence/570/`

禁止：

- ②中他人文件、569 的 `core/pageframe.py` 与 `tests/test_569_title_block.py`（只能跑，不能改）。
- `core/changeplan.py` / `PlanDrawBaseline` 公开版本化形状、`core/candidate.py`、pagecompiler/drawcompiler/readability、daemon、DSH、contracts、fixtures。
- `outputs/hole566/` 及其他历史证据；`tasks/568_draw_holes_wave3.md`。
- 不新增 bridge action，不改 action 名/参数/退出码，不 bump/package/release。

## ④ 交付物与验收

### 先红断言（生产改动前真实跑出）

新建 `tests/test_570_empty_page.py`，复用 054/057 的真流程 fake 与 566-A 探针形态，至少钉住：

1. **逐 namespace 失败关闭**：components/wires/pins/netlabels/texts/buses/circles/rectangles/arcs/polygons 每项 `available=False`、缺少 meta/available、缺少 section 都不得 `readable=True`。尤其 `available.wires=False` 的完整 unbound apply 必须 `page_required` exit 5、零写、不得 `reused=true`。
2. **文字/图形不是空白**：只含 Text，以及分别只含 Bus/Circle/Rectangle/Arc/Polygon 的 geometry 不得被选为空页；空 section 全空的正控制仍可复用。旧 Connector 形状（没有新增 section 或 availability）只能拒证，不得视为空页。
3. **复用写前第二闸**：扫描时为空、写前出现 wire/text/任一新类别的复用页必须 exit 4 `page_not_empty`、零写；created 页既有非空拒绝不退化。拒因/报告须列出新增 section 的计数，不能一边报全零一边说非空。
4. **Connector 加性合同**：`sch.geometry` 返回上述六个新 section，保留 primitiveId 与 `meta.available.<section>`；任一 namespace getAll 失败只把该项标 unavailable，不伪造内容。既有四 section、bboxIds 与 sheets 行为不变。

### 实施口径

- `schGeometry` 复用现有 `geometryOf` 加六个真实 namespace；返回 key 用 `texts/buses/circles/rectangles/arcs/polygons`，不发明 `sch_PrimitiveLine`。
- `_draw_geometry_readable` 对全部十类要求：section 是 list、`meta.available` 是 dict、对应 availability 明确为 true。旧 Connector 缺新键时 fail closed，仅失去“自动证明空页并复用”的能力；不得影响显式 `--page` 的正常读取。
- `drawapply` 保留原四个电气 census section 的公开 baseline 形状，另命名六个 drawing section；提供统一的附加 section 计数/非空辅助，禁止把文字/图形硬塞进 netlabelCount。
- `_census_is_not_empty` 或新共用 helper 必须同时消费电气 census 与六类附加 section；扫描和 `created or reused` 写前闸都走它。`censusBefore`/拒因增加附加 section 计数。
- 同步更新 protocol/docs/源码注释中“只有四类”的旧描述；无新增公开 CLI 参数或 DSH 工具。

### 修后测试与变异

至少运行并留存汇总行：

```bash
.venv/Scripts/python.exe -m pytest tests/test_570_empty_page.py -q --basetemp=.tmp_pt_570/new
.venv/Scripts/python.exe -m pytest tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_143d_page_and_census.py tests/test_569_title_block.py tests/test_540_cli_draw.py tests/test_action_catalogue.py tests/test_doc_claims.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_570/neighborhood
cd connector && npm test && npm run typecheck
```

- 至少三项生产变异，各自 cp 备份、变异后指定测试必须红、cp 恢复并核 SHA：
  1. 可读性闸退回只看 components → A-1 用例红；
  2. `created or reused` 退回 `created` → A-3 流程用例红；
  3. 去掉一个新增 Connector namespace（Text 或 Rectangle）→ Node 合同红。
- 交回前后 exit/写入次数、逐 section 结果、Node/Python 汇总、三项变异、修后 SHA 与未覆盖项。日志 `.tmp_570/`，长期证据 `evidence/570/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机/daemon/编辑器/真实工程；connector 测试只用 fake host。
- 不跑全量 pytest；Python 单进程，前台带 timeout；pytest 必须独立 basetemp，禁 `-n auto`/`-n >4`。
- 不改既有断言/夹具来凑绿，不用 skip/xfail 遮洞，不新增第二套 builder/router/几何引擎。
- 不修改 569 已验收生产 hunk；发现冲突先停止交证据。
- 本批不交付新原理图，真机逐脚与视觉为「不适用，未做」；不得声称当前 Connector 已在真机激活。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **40 步或 30 分钟**，不派下一级代理；同一缺口续跑须带新证据。
- 正文 ≤2000 字：`实际改动` → `先红/修后绿命令与汇总` → `三变异与 SHA` → `未做/红项`。
- 有本批红项、缺完整流程证据或缺变异，只能交「停止/未完成」。相同拒因两轮无新证据即停，不扩阈值、页框或预算续命。
