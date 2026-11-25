# 任务书：620D — 本器件引脚引线与真正外来导线的分级净距

## ① 前因后果

617D 为修 543d 的 RXD 误读，把 `_native_label_seat` 对**所有**他网导线的净距从 10 降为 5，导致全量新增 `test_534z_label_carriers.py::test_a_candidate_seat_clears_a_foreign_conductor` 红。620C 已恢复 `NATIVE_LABEL_CARRIER_LIMIT=10`，534z 全文件 14 passed，但 617D/617E 分别因 RXD 落入 U1 体内、stub 40>20 而红。证据 `evidence/620c/REPORT.md` 与穷举显示，在 10 单位引脚节距下，RXD 20 单位座位距 U1 自己的相邻 V3 引线为 5.5，理论最大也小于 10；在 `stub<96` 与 C3 gap>=2 下，所有导线一律 10 的最早可行座位为 97。此结论不是继续全局降 5 的理由。

本批依据现有 `readability._check_text`（1618–1626）对**引脚网络标签属于该器件自己的文字**的归属规则，细分两种几何：仍可证明属于其它器件、跨岛或无归属的导线严格 10；只有从当前页面真实 `LayoutPart` 与 SymbolProfile 姿态算出、实际终止于 `label.part_id` 该器件引脚末端的同器件引脚引线，才使用已有 `FLAG_BODY_CLEARANCE=5` 作为最小不擦碰距离。穿线仍一律拒绝，文字/器件体/标题栏等其它约束不变。这不是针对 RXD/U1 的特判，也不降低 534z 的无归属 10 合同。

620C 服务座位穷举已证明单纯挪 C3 无法解决相邻引脚引线距离，因此不再重复服务件移动或新增座位器；本批是在既有 `_native_label_seat` 内补充来源明确的导线分类。

## ② 当前树状态

HEAD/origin 均为 `76e08060ded403793bc6fb0eb64b38f9e140c765`。工作树混合：602–620C 的绘制线改动未提交；`circuitsemantics.py`、563 文档/测试、`tasks/review-line.md` 属另一线；`router.py`、`test_201f_admissible_heuristic.py`、`tasks/600_router_unreachable_fast_refusal.md` 及它们已写的 PROGRESS/handoff/TASKMAP/draw-line 属 600R，均不得改或还原。

当前 `pagecompiler.py` SHA-256 为 `7d91d6602cb4ed916aae64a67c3f9ac8a5889039d093dedecf451a6117e23aef`，`_native_label_seat` 在 5368 起；`_reseat_native_labels` 在 3019 起，标签已有 `LayoutLabel.part_id`；`_Context.book` 是真实 profile map。`_plan_wires` 当前只返回 `(net, points)`，无 owner 的调用必须保留严格 10。`drawcompiler.py` 为 `c5c6da702f9c1c83eaab665705c4a6a27e43bbb098c7496fabe6326a415f5b11`，本批不改。

开始先 `mkdir -p .tmp_620d/backup evidence/620d`，`cp` 备份所有允许修改的既有文件，记 SHA；保留 620C 原始证据与 stopping report，不覆盖。620B 在独立 `pagelayoutplan.py` 文件域可能并行，不能碰它。

## ③ 文件域与禁触清单

只允许：
- `src/boardwise/engines/pagecompiler.py`：复用现有座位梯级，增加窄的、可验证的同器件引脚引线分类与注释。
- `tests/test_620d_owned_pin_lead_clearance.py`：新增因果回归。
- `tests/test_617d_rxd_label_carrier.py`：**只允许更新文件顶端说明文字**，把“所有 foreign ink 都读 5”的旧解释改为有证明的同器件引脚引线 5、其它导线 10；所有断言行、常量、imports、helper 和测试逻辑逐字不变，交卷附 executable diff 为空。
- 本任务书、`.tmp_620d/`、`.tmp_pt_620d/`、`evidence/620d/`。

禁止改 534z/617E/543K 及所有既有测试断言；禁止改 `readability.py`、NATIVE_LABEL_CARRIER_LIMIT、FLAG_BODY_CLEARANCE、drawcompiler、规格/library、fixtures、shared/parser/model、CLI/connector/DSH/router/placement 与他人文件。不得识别特定 part id/net/坐标，不得仅凭调用者传入 owner 字符串就放宽；不得将同器件任意他网段、跨岛线或“网名相同”的导线视作自有引脚引线。无真实 part/profile/pin 证明时走原 10 路径。不得新建第二套 builder/router/seater 或扩大页框、预算、文本尺寸。

## ④ 交付物与验收

1. 默认/无归属合成调用保持原样：534z 的近座因他网导线 <10 被拒绝而选下一档；即便利测试伪造 `part_id`，没有真实几何归属也不能得到 5。
2. 在真实重座路径，从 `plan.parts` + `ctx.book` 的实际姿态定位 pin tip，只把实际终止于 label 所属 part 的引脚末端、且电气网与该 pin 一致的 run 归为同器件引脚引线。可选参数必须保持旧调用签名兼容；未知/不完整数据严格 10。不得把邻件、其它器件同点线、跨岛线归入 5。
3. 新增测试必须覆盖：
   - 无归属外来导线 5.5 仍拒绝、10 以上可选（534z 原尺）。
   - 有真实器件/pin 证明的同器件相邻引脚引线可按 5，但 cross/contact 仍拒。
   - 同样距离 5.5 的**另一器件**引脚引线仍拒绝；跨岛/任意他网段即使器件包含该 net 也不因 part 名而放宽。
   - 543d 与 617E 真实编译 `ok=True`、4 候选、每候选 RXD stub<=20、引脚外侧、C3 gap>=2、无器件体覆盖；逐候选报告严格 foreign gap>=10 与 same-part lead gap>=5 的证据，不能靠 0 候选/隐藏文字通过。
   - 543d/617E 58 脚/17 网、逐脚落地及 net 连通不退化，617E backflow=0 与 `moduleColumns` 单字段差不变。
4. 跑 `tests/test_534z_label_carriers.py tests/test_617d_rxd_label_carrier.py tests/test_617e_reading_flow.py tests/test_620d_owned_pin_lead_clearance.py`，再跑 617C、543K、543D/G/I 的相关既有测试；按 owner/layer 规则加受影响邻域。每轮 pytest 独立 basetemp，不全量。
5. 真实 `boardwise draw compile` 使用 `blocklib/specs/ch343_uart_534a.circuit.json`、`evidence/617e/effective.presentation.json`、既有 library 和 PAGE_BOX，输出到 `.tmp_620d/`，要求 ok=True、4 候选、0 failure，保存 stdout/stderr 与真实 page JSON。真实调用离线即可，不真机、不落画布。
6. 从真实 page JSON 渲染四候选 SVG/PNG 至 `evidence/620d/render/`，优先复用 620C/617E 的现有离线渲染脚本与 renderer，不另造渲染器；留命令、路径、P44 四项数与逐脚报告。
7. 至少两项生产变异：① 全局恢复 5 或无归属也走 5，534z/新负控必须红；② 同器件引线不再识别或错误把所有 foreign 当 10，真实 RXD stub/外向断言必须红。每项先 `cp` 备份，变异跑红后恢复并 SHA-256/cmp 字节一致，再复绿；不得用 git checkout/restore。
8. 交卷清楚区分：编译闸、逐脚连通、视觉待主代理复验；不得自称视觉通过。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink、git add/commit/checkout/restore；不碰历史证据、fixtures 和他人未提交改动。删除只能经岳同意后回收站，本批不删。单进程探针，不 fan-out，不全量 pytest，不真机/部署/发布。pytest 必须 `--basetemp=.tmp_pt_620d`（邻域可另用 `.tmp_pt_620d_neighbours`），命令有 timeout。不得删改宽测试、skip/xfail、调参凑绿、把 native 文本隐藏、改规格/输入或保留 0 候选。append 落盘后立即 grep -c 检查双执行。两轮同拒无新证据即停并交接。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟，先到先停，不派下级。交卷 <=2000 字：先红/修后实测命令与汇总行、同器件与外来导线的判定依据、四候选 RXD/净距/C3/58脚/17网读数、真实 CLI 和渲染路径、两项变异与 SHA 恢复、未跑项。详细日志落 `evidence/620d/REPORT.md`，原始输出在 evidence 或 `.tmp_620d/`。缺任一严格负控、真实候选、渲染或变异只能写「停止/未完成」，不能把本批写成视觉验收通过。
