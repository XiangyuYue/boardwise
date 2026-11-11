# 038R3：有效板框下零可测量器件不得静默通过

日期：2026-11-11。审查线 BoardOffEdge 单规则小批，紧接 038R2，但与宿主 DRC completion 改动分开。

## 已核实缺口

- `BoardOffEdge.check` 在描边碎片时会给 WARN；正常路径用 `_measurable_designators` 筛选有焊盘的器件。
- 当板框闭合且角点足够，但器件存在、没有任何器件带可测量焊盘时，`_outside_outline` 返回 []；`checksRun` 仍记录规则，旧 `outlineNote` 因板框有效而消失。报告表现为从未运行提示变成静默通过。
- 不能把「没量到」写成 ERROR，也不能改既有无板框/开放板框/退化板框的语义。

## 合同

- 仅在板框 `closed`、角点达到既有 `MIN_OUTLINE_CORNERS`、且存在带位号器件，但 `_measurable_designators` 为空时，返回**一条聚合 WARN**。
- 文案明确「板框已读出，但本次没有任何带焊盘的器件可判定，出板框检查未运行（不是全过）」，并给出涉及位号/数量；不得写成无违规或通过。
- WARN 进入既有待分诊/open-items 链，不新造 coverage schema，不制造 ERROR，不影响正常有焊盘器件的逐件 ERROR 判定。
- 描边碎片既有一 WARN 优先，不能叠加成两条。无器件/无位号器件、无板框、开放/退化板框继续既有行为；其他 spacing/off-edge 规则不变。
- 本批不声称所有无焊盘器件都是设计错误：机械/特殊器件由工程师分诊，WARN 的含义是本次无法判定。

## 文件域

- `src/boardwise/rules/pcb/distance.py`：仅 BoardOffEdge 正常路径的零可测量分支与注释。
- `tests/test_126b_pcb_distance_rules.py`：新增 fake 回归，必要时最小更新明确依赖旧静默的用例并记录。
- `tests/test_188a_slender_outline.py`：仅允许给 `_board` 合成夹具补真实的 FOOTPRINT/PAD，使原有「规则照跑且为 ERROR」断言继续测量原主题；不得把断言放宽成「无抑制行」。
- 本任务书；日志/备份 `.tmp_038r3/`，pytest 独立 `--basetemp=.tmp_pt_038r3`。

不改 `pcbreview.py`、cli/completion、FOC、038Q4、038R2、bridge/Connector/DSH/Rust、绘制线、package/version/TASKMAP；零 git 写、零删除、零真机。

## 验收

- fake：闭合 4 角点板框 + 至少一个有位号器件 + pads=[]，修复前 findings=[]；修后恰一条 WARN，message/evidence 明确未运行、不是全过、涉及位号。
- 反向：无器件不新增 WARN；正常有焊盘器件保持原 ERROR/空结果；无板框、单点/开放框、描边碎片维持既有合同。
- 跑 `test_126b_pcb_distance_rules.py`、`test_126a_pcb_review_plumbing.py`、`test_164c_silent_truth.py` 与板框碎片邻域，记录计数。
- 两处变异：①删除零可测量 WARN；②去掉器件存在守卫导致空板也报。对应测试须红，cp+SHA-256 恢复复绿。
- 一个 coder，最多 25 步/20 分钟；主代理独立复验。集成全量另行串行。

## 交卷（coder，2026-11-11）

**实现**：`src/boardwise/rules/pcb/distance.py` — `BoardOffEdge._outside_outline` 在既有「无框/角点不足/未闭合 → `[]`」守卫**之后**新增一步：`designators` 为空时转 `_nothing_measurable(board)`；该方法只在 `board.components` 至少有一个带位号器件时返回**一条** WARN（`rule_id` 不变、`target=None`），文案写明「检查未运行（不是全过）」+ 位号数量，evidence 列出位号（>12 个时截断并给总数）与判据「没焊盘≠设计错误，机械件/特殊件由工程师分诊」。无器件 → `[]`。描边碎片仍由 `_frame_is_a_piece` 在 `check()` 里先返回，**不叠加**。类 docstring 与 `_outside_outline` docstring 同步补「第四态」一段。

**fake 前后**：`.tmp_038r3/probe_fake.py`（闭合 4 角点 500×500 框 + J1/MH1 + `pads=[]`）修复前 `findings=0`；修后 `findings=1`、severity=WARN、rule=`pcb-component-off-board`。

**测试**：`tests/test_126b_pcb_distance_rules.py` 新增 5 条（fake 一条聚合 WARN / 空板不新增 / 有焊盘器件走原逐件 ERROR 且不叠加 / 无框+单点+未闭合仍静默 / 描边碎片仍恰一条且不叠加）。计数：126b 29 passed；164c 17 passed；126a 14 passed + **1 failed**（见下）；邻域 187a+183+bug98a+188a+164c 77 passed + **1 failed**（见下）。

**变异**（cp + SHA 还原，脚本落 `.tmp_038r3/`）：①`return self._nothing_measurable(board)` → `return []`：fake 红（`len([])==0`），cp 还原后 `cmp` 字节一致、复绿；②`if not named:` → `if False:`：空板用例红，同样还原字节一致复绿。两轮变异在预变异快照 `fb9622b0…` 上做；随后只改了一处 docstring 措辞（message/evidence 未动），**最终文件 sha256 `1c6614f9f35e1ea593f840f11d7f9d5244ae2c585f9fc770d61fb788dff0dbd6`**，变异①在最终文件上重跑一次仍红、cp 还原后 `cmp` 字节一致、三点复绿。test_126b sha256 `ca2e583f…9b9c2`。

**未覆盖 / 需集成方处理（按文件域未改）**：
- `tests/test_126a_pcb_review_plumbing.py::test_the_rulebody_digest_covers_the_pcb_subpackage` 红：`distance.py` 在 `rules/pcb/` 下，按配方只进 recursive 摘要 —— direct 仍 `626e16ef`，recursive `424e2fd2` → **`f30b1163`**；`contracts/differential/manifest.json` 与 `inputs/review-report.json` 的 `rulebody` 需官方 `tools.build_differential_fixtures` 重生成（两者都不在本批文件域）。
- `tests/test_188a_slender_outline.py::test_the_degenerate_ring_187a_left_standing_is_disclosed` —— **已按主代理裁定①修复（夹具，断言未动）**：`_board()` 只写 COMPONENT/ATTR、无 FOOTPRINT 文档，R1 原本没有焊盘，旧断言靠空结果真空成立；038R3 后它正是「有效框 + 有带位号器件 + 零可测量」→ 出聚合 WARN，撞上 `all(severity == "ERROR")`。现给合成夹具补真实的 FOOTPRINT/PAD（复用 `test_183` 的 `_line`/`_component` 构造器：FOOTPRINT 文档 `fp1` + 40×40 RECT PAD +两条 LAYER，空行/记录顺序照 183 的 `board_text`），`COMPONENT.Footprint` 本来就指向 `fp1`，器件坐标不变。实测 R1 现在有 1 个焊盘（pad1 @ 1000, -0.45），在 2000×0.9 的环上量出 **ERROR 19.6 mil 出板框**——「规则照跑」不再靠空结果成立，原断言原样通过，`outlineNote` 仍只有细长披露一句。重跑：188a 4 passed；126b+164c 46 passed；碎片邻域（187a+183+bug98a+188a+164c）78 passed、零红。


## 主代理验收与集成（2026-11-11）

- 主代理核心 **50 passed**；碎片邻域 **78 passed**。
- 188a 采用裁定①：合成 `_board` 只补真实 FOOTPRINT/PAD/LAYER，原断言不改；R1 实测量出 19.6 mil 出框 ERROR，不再以空结果真空通过。全文件 4 passed。
- 两处变异均 cp+SHA-256 恢复复绿。最终 distance.py SHA-256 `1c6614f9f35e1ea593f840f11d7f9d5244ae2c585f9fc770d61fb788dff0dbd6`。
- 与 038R1 合并后 rulebody 实算 d2ff8ae4，官方生成器已同步 manifest/input；无关版本元数据按生成前保留，其他绘制生成物零变化。`test_126a` 已记录原因并同步断言。
- 证据 `outputs/review/038r3/ACCEPTANCE.md` 与 `outputs/review/038r4/ACCEPTANCE.md`；全量结果待集成批补记。
