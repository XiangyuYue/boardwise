# 任务书：577 / W-D1 — 写锁内的实时工程身份闸（shared 集成锁）

- 日期：2026-11-24
- 范围：仅 **566-D-1**，shared bridge/daemon 独立批；D-2/D-3/D-4 不在本批。
- 执行：一个 coder；主代理独立复验。离线，不真机、不全量。

## ① 前因后果

`outputs/hole566/d/REPRO.md` D-1 与主代理独立复现证明：设计写闸读 `window.project_name`（hello/上次响应的滞后副本），同窗口切工程后第一条设计写会按旧工程名过闸。闸与转发之间没有现读，且当前闸还在写锁外，锁等待期间也存在竞态。

修复必须同时做到：

1. 对每个 design write，在**目标窗口写锁内、实际写帧前**用既有 `_forward("sys.identity")` 只读现读；
2. 以返回的 focusedProject / activeDocument.project 更新当前身份后再过 `_check_design_write`；
3. 活动文档存在时要求 `consistent=true`；无活动文档时可用 focusedProject（新建首页合法）；
4. 旧 Connector 不支持、身份不可读、两层不一致、项目 name 与 uuid 同时缺失均 fail closed；name 或 uuid 任一非空即可识别，保持 537A3 原合同；TIMEOUT/DISCONNECTED 等技术错误不伪装成白名单错误；
5. 拒绝时 `routed` 不标记，且文案只能是“没有**设计写**被转发”，因为 sys.identity 只读探测允许先行。

569–576 已验收改动必须保留。shared、全量与真机串行，本批不夹绘制算法。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `bridge/daemon.py` 当前 SHA `4e414557c69779c30282492ca923cec8f7214d546e476d32cc6aa8e31cffbb80`，为 HEAD 原样。
- `tests/test_537a_daemon_write_policy.py` SHA `0f43166f8e63ea208d475dac363bc99882d10cd14df0993c941e4e2b52ef3431`。
- `tests/test_page_delete_guard.py` SHA `5924359187475d53444e571f419b441db1b51e3746314c0f7d9c7a8446a2b442`。
- `docs/bridge.md` 含 570 的 geometry 行更新，当前 SHA `8ed729229bcfe9623f861dcc6f8048bb989a89842ab7c098216b01327d05e52e`，只许改设计写相关段。
- 当前调用序：`handle_request` route → `_check_design_write` → routed 标记 → read 直接 forward / write_lock 后 forward。需要把 design-write 的新鲜读与检查移入 write_lock，且只有检查通过才标 routed。
- `sys.identity` 返回 focusedProject、activeDocument.project、consistent/consistentBasis；`apply_response_context` 是既有响应更新通道，可复用但不得替代本次返回值的显式校验。
- 563/568、569–576 其它文件与临时件禁触。

实施前 cp 备份生产文件到 `.tmp_577/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/bridge/daemon.py`
- `tests/test_537a_daemon_write_policy.py`
- `tests/test_page_delete_guard.py`（仅设计写 fake/调用序适配，不放宽）
- `tests/test_577_fresh_write_gate.py`（新 stale/race/identity 回归）
- `docs/bridge.md`（仅设计写与 WRITE_PROJECT_FORBIDDEN 相关段）
- 本任务书、`.tmp_577/`、`.tmp_pt_577/`、`evidence/577/`

禁止：connector 源码、protocol 动作目录/返回合同、CLI/DSH、contracts、绘制引擎、563/568、569–576 其它文件、outputs 历史证据、真实工程。

如 `test_bridge.py` / `test_bridge_cli.py` 的假宿主因新只读探测失败，先交具体名单；只有确认是同一 sys.identity 合同才可续批小修，不得放宽生产闸。

## ④ 交付物与兼容矩阵

| 维度 | 必须达到 | negative control / 不得声称 |
|---|---|---|
| 读动作 / navigation / self_update | 不增加 sys.identity 探测，原调用序/结果不变 | 不得把读或无设计写导航误拦 |
| design write（test/test2） | 写锁内先 sys.identity，再检查，再实际写；允许项目两个动作按序发生 | 不得再用上次响应的旧名放行 |
| `*` 全放开 | 保持 legacy，可不增加新鲜读 | 不得给旧测试/全放开调用强加新动作 |
| stale project switch | stale window 为 test、现读为 REAL_TARGET 时第一条设计写即拒，只有 sys.identity 先行 | 不得转发 delete/place/NC 等设计写，routed 不标记 |
| consistent=false / null / 缺字段 / UNKNOWN_ACTION | 拒绝并无设计写；不支持旧 Connector 不得放行 | 不得把 UNKNOWN_ACTION 当“身份不明但可写” |
| 无活动文档 | focusedProject 身份完整时可创建首页 | 不得要求必须有活动页才能写 |
| 多窗口 | 只探测 route 选中的窗口 | 另一窗口不得被读取/改名/写 |
| 锁内竞态 | 新鲜读与检查在 write_lock 内，锁等待不消费旧身份 | 不得把检查移回锁外 |
| V3/V4、`.epro2/.eprj2/.eprj3`、在线/离线、单/多板、普通器件/CBB | 本批仅离线 fake，格式与器件维度不变 | **全部真机/容器/多板/CBB 未覆盖**；重复 PCB 双审、分歧库串板与本批无关，不得宣称兼容验收 |

### 先红回归（生产改动前真实运行）

新建 `tests/test_577_fresh_write_gate.py` 并适配 537A fake：

1. **原洞复现**：window 的 stale context=test，live sys.identity=REAL_TARGET。第一条 `doc.delete_page(confirm=true)` 立即 WRITE_PROJECT_FORBIDDEN；只转发 sys.identity，无 delete，routed={}。错误文案含“没有设计写被转发”，不再说“零读取”。
2. **锁内顺序**：记录 write_lock 进入、sys.identity、实际写；身份探测与检查必须在锁内，且在 write 前。等待锁期间改 live 身份，必须以锁内新值判定。
3. **允许路径**：test/test2 项目按 sys.identity→设计写顺序；`doc.delete_page`、`sch.place_component`、`sch.set_pin_no_connected` 至少各一例。
4. **失败关闭**：consistent=false、null、缺 project、UNKNOWN_ACTION 各例无设计写；无活动文档但 focused 完整的正控制可写；技术错误保持原码。
5. **兼容**：读/navigation/self_update 无新增探测；`*` 不多读；多窗口只读目标窗；537A 的现有 whitelist 全部行为按新“设计写未转发”口径更新，不删负例。

### 实施口径

- 新鲜读使用现有 `_forward`，不新增 action 或 connector handler；在 write_lock 内执行并消费响应。明确写 helper 的字段映射/失败条件，不读另一个窗口。
- `consistent=true` 时 activeDocument.project 优先，focusedProject 兜底；无 activeDocument 时 focusedProject 可用。成功才覆盖 window.project_name/project_uuid，缺失不得沿用旧值冒充新值。
- `sys.identity` 的 UNKNOWN_ACTION 转 WRITE_PROJECT_FORBIDDEN（身份能力缺失）；其它异常保持原码。`_check_design_write` 文案改为“没有设计写被转发”。
- 只有检查通过才写 `routed["windowKey"]`；读/非设计写分支保持原行为。`*` 可绕过新鲜读以冻结 legacy。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_577_fresh_write_gate.py tests/test_537a_daemon_write_policy.py tests/test_page_delete_guard.py -q --basetemp=.tmp_pt_577/new
.venv/Scripts/python.exe -m pytest tests/test_bridge.py tests/test_bridge_cli.py tests/test_action_catalogue.py tests/test_doc_claims.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_577/neighborhood
```

至少三项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. 去掉新鲜读、恢复旧 window.project_name 判定 → stale 用例红；
2. 把新鲜读/检查移到 write_lock 外 → 锁内顺序用例红；
3. 接受 consistent=false/缺身份或 UNKNOWN_ACTION → 失败关闭用例红。

交回动作顺序、stale/允许/失败读数、兼容矩阵逐项、测试汇总、三变异与最终 SHA。证据 `evidence/577/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机/daemon/编辑器/真实工程；不跑全量 pytest；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail，不通过吞掉 sys.identity 调用伪造“零动作”。
- 不新增 bridge action，不放宽白名单，不碰 `毕设FOC驱动板`、`CH340G.eprj2`、`ROBOT ctrl FOC.eprj2` 或任何真实工程。
- 本批是 shared 集成锁，禁止夹带绘制算法/connector 改动；真机可达性明确未覆盖，不写“已上机”。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **40 步或 30 分钟**，不派下一级代理。
- 正文 ≤2000 字：`实际改动` → `先红/修后绿` → `三变异与 SHA` → `兼容矩阵与未覆盖项`。
- 有本批红项、缺锁内顺序或失败关闭证据，只能交「停止/未完成」；不得用减少必要测试来赶预算。
