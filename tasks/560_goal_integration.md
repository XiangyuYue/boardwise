# 560：目标 1/2/4/5 总集成与验收

## 1. 收尾范围

556 shared 合同/page_y、557 主要台账、558 手册义务、559 在线连通均已实现并分别父验；558B 处理 EST026 精确判型。总目标明确不推送、不部署 DSH、不发布、不擅自 Git 写，不把 machine_verified 自行升 verified。本批真机只做既有接口预验和原生激活拒因记录，不偷偷热更；**激活在 2026-11-20 由用户另行授权后一次做成（daemon 重启 + connector 写入 + 完整重启 EDA），与本批验收分开记**。

本批只做剩余文档/状态与最终验收，不再扩功能。

## 2. 必收文档尾巴

- `docs/review-sop.md:701`、`docs/pits.md:30` 的 #87“工作树实现”改已落 `3d4a0d5`（origin/main）、未发布；同步 `tests/test_doc_claims.py` token 与测试 docstring，历史读数不动。
- `tasks/TASKMAP.md` 550B 行尾“未提交未发布”改“未推送、未发布”；555 行末 CLI 合同待集成改 556 已同步，559 新命令由本批合同再核。
- `bridge/protocol.py` 与 connector `connectionEnd` 注释的 last-dot 用途改为 designator 可含点；protocol returns 的 direct 示例键与 TS 实际返回对齐（TS direct 无 status 键，不新增生产字段）。
- `tasks/review-line.md`、`tasks/TASKMAP.md`、`docs/handoff.md` 增加 556–560 实际状态：各批聚焦/父验读数、558B 真实分类、559 的 550B 真实预验与 native `unknown action` 阻断；不得把 native action 写成已激活，也不得把预验写成完整宿主兼容。
- `tasks/556…560` 补实际完成段；本批不改旧 PROGRESS 混合 hunk。
- DSH 不新增 connection 工具的理由写明：typed CLI 底座先验收，原生激活另授权后再裁适配；检查既有 DSH 全套不回归即可，不擅自 bump/pack。

## 3. 文件域与禁触

上述文档、`tests/test_doc_claims.py` 的必要状态钉、`evidence/560/`、`.tmp_560/`、`.tmp_pt_560/` 与最终验收日志。不得改生产源码、connector/DSH 源、绘制线、fixtures、真实工程、货架/trust、发布件。零 Git 写、零 rm/unlink、零部署发布。

## 4. 最终验收

- 文档/owner/layer/CLI 合同及 556/558/559 聚焦恢复全绿；无 558 开始时那两条 core/connection owner 红。
- 下一轮必要全量前，确认所有生产与文档改动已定格。只跑一轮：
  `.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_560_full --durations=50 --durations-min=1.0 --junitxml=.tmp_perf_pytest/junit-560.xml`
  （先建 `.tmp_perf_pytest/`；日志 `.tmp_560/full-pytest.log`）。
- 随后 connector 全量 + typecheck、DSH typecheck/test/build、Rust fmt/clippy/test。真实读数逐项记录，不拿 beta2 旧全绿替代。
- 其他线红项按归属披露，不越线修、不隐藏；本批新红必须定位后才允许一次完整复跑，第三轮先向岳说明。
- 保密/卫生检查、限定 diff-check、真实容器未入暂存区核对。全程不 add/commit/push/release。

## 5. 交卷

汇总目标①–⑤逐项证据；明确 native action 激活路径（2026-11-20 已成立：实例 `inst-015644463-2wuenu0j`，正例 CONNECTED / 反例 NOT_PROVEN，`evidence/559/native-activation-success.json`；激活前的 `unknown action` / `no handler` 留档），三份机器档仍待人工签核，U8/EST026 身份没有伪造，机械件退出 hunt 不等于审查通过。交真实命令、计数、失败项和剩余边界，不把“目标收尾”写成“全部板卡 GREEN”。

## 6. 实际完成（本批交卷，2026-11-19）

本批只做文档/状态收尾，生产逻辑与既有 hunks 未改；零 Git 写、零 rm/unlink、零全量 pytest、零 bridge/EDA、零部署发布。
详细证据与逐文件 SHA 见 `evidence/560/README.md`。

**§2 尾巴逐项**

1. `docs/review-sop.md`、`docs/pits.md` 的 #87 改“已落 `3d4a0d5`（`origin/main`）、未发布”；`tests/test_doc_claims.py` 两处状态 token 与两条 docstring 同步，历史在线读数不动。`git branch -r --contains 3d4a0d5` → 只有 `origin/main`/`origin/HEAD`，所以记已落、不记已推送。
2. `tasks/TASKMAP.md` 550B 行尾删“未提交”，只留“未推送、未发布”。
3. 555 行末改“CLI 合同快照已由 556 生成同步，559 新增命令的合同由 560 再核”；本批实核 `tools/cli_contract.py` check 通过。
4. `bridge/protocol.py` `params_schema` 与 connector `connectionEnd` 注释的 last-dot 用途改为 **designator 可含点**（pad 恒为末段、含点的 pad 号无法表达），删掉写反的“pad number contains dots”。
5. `bridge/protocol.py` summary 与 `returns` 的 `direct` 示例删除 TS 无有的 `status` 键（TS 实键 `{ok,count,ids,items,truncated,unreadable?,error?}`）；未新增生产字段。
6. `tasks/review-line.md`、`tasks/TASKMAP.md`、`docs/handoff.md` 加入 556–560 实况：明确 native action 于 2026-11-20 激活成立（激活前为 `unknown action` / `no handler`）、预验不等于完整兼容、direct-only 范围不变、三份机器档待签、U8/EST026 身份未伪造、机械件退出 hunt 不等于审查通过。
7. 任务书 556/557/558/558B/559 补实际完成段，本文件补本段；未改旧 PROGRESS 混合 hunk。
8. DSH 不新增 connection 工具的理由已写明：typed CLI 底座先验收，原生 action 当时连宿主都没加载，此时适配会把“未激活”包成可用；待另授权的激活成立后再裁，本批只核既有 DSH 不回归、不 bump/pack。（2026-11-20 激活已成立，但 DSH 适配仍未做、仍不 bump/pack，属另裁项。）

**测试（真实读数）**

- 首跑聚焦 5 文件 → **4 failed, 130 passed in 29.17s**（4 红全在 `test_540c_contracts`，因合同快照内嵌 protocol 文字）。
- `tools/cli_contract.py --write` 重生成后：`contracts/cli/v1.json` `0561be51…` → `3fe8b4f6…`，与改前快照逐行只差 4 行。
- 复跑同集 → **134 passed in 26.62s**（`.tmp_pt_560b`）。
- 559 CLI + 558 义务邻域 → **34 passed in 0.70s**（`.tmp_pt_560c`）。
- 限定 `git diff --check`（本批 9 文件）→ exit 0。

## 7. 最终验收（2026-11-19，真实读数）

全量 Python 共三轮：首轮在 463 秒因真实缺陷主动停止（不计通过），第二轮 **19 failed / 11913 passed**，第三轮确认轮结果如下。第三轮启动原因已提前向岳说明（只修本批 9 处审查/shared 红、不碰绘制线）。

- 第三轮命令：`.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_560_full_r3 --durations=50 --durations-min=1.0 --junitxml=.tmp_perf_pytest/junit-560-r3.xml` → **11 failed / 11921 passed / 26 skipped / 2 xfailed in 2593.86s (0:43:13)**。日志 `.tmp_560/full-pytest-r3.log`，UTF-8 快照 `.tmp_560/full-r3-final-utf8.log`。
- 二轮 19 failed 分解：**9 处审查/shared**（537A 2、540 4、038 3）+ **10 处绘制线**（548c7 4、548m/543h2/548d_wifi_ground/543h3b/draw_plain_carrier/548k 各 1）。第三轮里 537A/540/038 三组**全部消失**，说明 `review-red-parent.md` 的 243 passed 聚焦修复真实生效；**无 537A/540/038 红**。
- 第三轮剩余 11 处全部落到绘制线：`test_116_ordinal_consumption` 1（`test_098_scene08_refusal_is_byte_identical_to_the_recorded_baseline`）、`test_548m_rail_clustering` 1、`test_543h2_final_label_positions` 1、`test_548c7_library_flags` 4、`test_548d_wifi_ground` 1、`test_543h3b_stated_text_lane` 1、`test_draw_plain_carrier_contract` 1、`test_548k_stub_lane` 1。相对二轮名单：10 处同名延续，116 一条为本轮名单内的第 11 条；两者均按绘制线归属披露，本批未改绘制算法，也不为其编造因果。
- 其余三线（同树）：connector **864 passed / 0 failed** + typecheck 通过；DSH **207 passed / 1 skipped** + typecheck + build 通过；Rust `fmt --check`/`clippy -D warnings` 通过、**177 passed / 4 ignored**。
- 合同父变异（第三轮之后执行，不与全量交叉）：①移除 `pcb.connection_probe` 的 `NOT_DESIGN_WRITES` 例外 → **2 failed**；②owner 行数 159 回退 157 → **4 failed**；③038 三处 PRE_EXISTING hash 回退旧值 → **3 failed**；每轮 `cp` 备份 + `sha256` 恢复，恢复后该 6 文件聚焦 **119 passed**。
- 本批文档自检：`.venv/Scripts/python.exe -m pytest tests/test_doc_claims.py tests/test_workspace_conventions.py -q --basetemp=.tmp_pt_560_finaldocs` → **67 passed in 3.14s**；限定 `git diff --check`（本批 9 文件）→ **exit 0**（仅 CRLF 提醒，非空白错误）。改前 SHA-256 见 `.tmp_560/backup_finaldocs/pre-edit-sha256.txt`。

**结论口径**：第三轮只证明「本批 9 处审查/shared 红已消失」，**不证明全仓全绿**——11 处绘制线红按归属披露、不越线修，也不安排第四次全量。native action 已于 2026-11-20 另行授权激活成立（direct-only，正例 CONNECTED / 反例 NOT_PROVEN，`evidence/559/native-activation-success.json`），激活前未激活的读数照原样留档；三份机器档待签、U8/EST026 身份未伪造、**不声称板卡 GREEN**。逐项汇总见 `evidence/560/final-validation.md`。

**未决**：多跳铜仍需 `getAdjacentPrimitives` 图合同（direct-only 不覆盖，`NOT_PROVEN` 不是开路）；558 三份 `machine_verified` 待人工签核，U8/EST026 身份未伪造；全量四线由主代理统一跑，本批不预支读数，也不写成“全部板卡 GREEN”。原生激活前的 `unknown action`（旧 daemon exit 3 / stdout 空）与旧 connector `no handler` 作为失败史保留在 `evidence/559/native-activation.json`。
