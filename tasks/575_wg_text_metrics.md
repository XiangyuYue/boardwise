# 任务书：575 / W-G — 非 ASCII 前进宽与渲染声明字号

- 日期：2026-11-24
- 范围：TRIAGE **567-G-1 / G-2**，只修文本度量；G-3 suspect 不处理。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole567/g/REPRO.md` 证明两条独立但同域的问题：

1. **G-1 会漏**：`TEXT_ADVANCE_EM_FALLBACK=0.9` 低于全角 1.0 em，20 字全角名少量 14.297 单位，超过 L1 的 10.0 穿透阈。最小安全修法是把未知字符 fallback 提高到 **1.1 em**（保守覆盖全角/emoji），不改任何表内 ASCII advance；不引入复杂的字族探测。
2. **G-2 会漏**：`_svg_text_nodes` 解析每个节点自己的 `font-size` 后丢弃，`render_box` 恒按 `RENDER_TEXT_PX`；2 倍声明字号得到同一盒宽。必须把 size 传到盒构造，按 `size / RENDER_TEXT_PX` 缩放盒宽，并同步缩放盒高；未声明 size 保持旧行为。

G-3（同名同 run 双 label）在 234 个真实 plan 零命中，仍 suspect，本批不做。

569–574 已验收改动必须保留；本批不改布局算法、阈值或绘制几何。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `core/textmetrics.py` 当前 SHA `4206307d3c575c669cd754310c6d78a765d66ae2e1be9bb823144288fda3f71d`，为 HEAD 原样。
- `engines/drawlint.py` 当前 SHA `cce5f8891e935e27033d0aa51da69baeeeda4fda12749b2d43fc17e0a930ea5c`，为 HEAD 原样。
- 当前 `textmetrics.py:113` fallback=0.9；`drawlint.py:695-775` 返回五元组但丢 size，`:633-677` 盒宽/高只读常量。
- 563/568、569–574 其它文件、PROGRESS/handoff/roadmap/TASKMAP/review-line 与临时件禁触。

实施前 cp 备份两个生产文件到 `.tmp_575/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/core/textmetrics.py`
- `src/boardwise/engines/drawlint.py`
- `tests/test_575_text_metrics.py`（新聚焦回归）
- 本任务书、`.tmp_575/`、`.tmp_pt_575/`、`evidence/575/`

禁止：drawcompiler/readability/svgpreview/pagecompiler、CLI、contracts、connector、dsh-plugin、fixtures、563/568、569–574 其它文件、outputs 历史证据。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

新建 `tests/test_575_text_metrics.py`：

1. **G-1 安全下界**：`render_width("电容") >= 2 * RENDER_TEXT_PX`；全角拉丁、CJK、emoji 每码位至少 1.0 em；20 字全角名不再短于 `20 * RENDER_TEXT_PX`。ASCII（如 ABCD、网名、数字）必须逐值等于旧表计算结果，不能借修非 ASCII 改几何。
2. **G-2 声明字号**：同一 SVG annotation 分别声明基准 `RENDER_TEXT_PX`、2 倍、7.006200555911909；`_svg_text_nodes` 保留各 size，盒宽按比例（2 倍与 7.0062/RENDER_TEXT_PX），盒高同步按比例。start/middle/end 锚点仍按缩放后的宽度定位。
3. **缺省控制**：没有 font-size 时盒宽/高与旧实现相同；基准字号比例恰为 1，不产生浮点漂移之外的改变。

### 实施口径

- `TEXT_ADVANCE_EM_FALLBACK = 1.1`，更新“宽估以留净空”的注释；表内字符不变。
- `_svg_text_nodes` 返回值附 size；`render_box` 增加可选 size，按声明比例缩放 width 与 height，size 缺省/0 走原常量。调用点全部同步，不保留“解析后丢弃”的路径。
- 不改 RENDER_TEXT_PX、CANVAS_TEXT_UNITS、RENDER_PIN_PX、L1/L2 阈值或文本角色分类。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_575_text_metrics.py -q --basetemp=.tmp_pt_575/new
.venv/Scripts/python.exe -m pytest tests/test_111_draw_lint.py tests/test_111a_draw_lint_addendum.py tests/test_163b_gate_truth.py tests/test_531_text_ruler.py tests/test_534_label_stub_typography.py tests/test_146_host_text.py tests/test_147_host_rows_and_pins.py tests/test_525_pin_text_row.py tests/test_lock_p1_delivery_gates.py -q --basetemp=.tmp_pt_575/neighborhood
```

至少两项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. fallback 退回 0.9 → CJK/全角用例红、ASCII 控制仍绿；
2. render_box 忽略声明 size → 2 倍盒宽/高用例红。

交回 CJK/ASCII 数值、三种字号盒尺寸与锚点、测试汇总、两变异与最终 SHA。证据 `evidence/575/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不扩大页框/布局间距来消化新宽度，不改 ASCII 几何，不处理 G-3。
- 本批无新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **30 步或 20 分钟**，不派下一级代理。
- 正文 ≤1500 字：`实际改动` → `先红/修后绿` → `两变异与 SHA` → `未做/红项`。
- 有本批红项、缺 ASCII 控制或缺字号比例证据，只能交「停止/未完成」。
