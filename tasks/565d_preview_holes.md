# 565d — svgpreview 自洽三条洞（S6-H1 / S6-H2 / S6-H4）

- 批号 **565d**　日期 2026-11-25　owner：绘制线/预览　状态：**待派**
- 来源：`outputs/hole565/s6/holes.json` 的 `H1`/`H2`/`H4`（= TRIAGE 的 S6-H1/H2/H4）；`H3`（`--bodies` 形状）主代理重放已修（包装形解包、坏形状 exit 2），**本批不修只关单**。
- 文件域：`src/boardwise/engines/svgpreview.py`、`src/boardwise/core/textmetrics.py`、新建 `tests/test_565d_preview_holes.py`、`evidence/565d/`

## ① 前因后果

2026-11-24 的 565-S6 在预览器上审出三条：盒与字不同源（H1）、控制字符写出非法 XML 且不校验自己的输出（H2）、一个 label 落两条同网线只画一行且竖排 carrier 静默退回假位置（H4）。三条都会让「预览」与「图上实际会印什么」不一致——正是交付红线里「渲染后自己用视觉看」依赖的那张图。

主代理 2026-11-25 重放（子代理开工必须自己复跑，原文存 `.tmp_565d/repro/`）：

```
p1: box_w 按 Arial@7.1483；SVG font-family="DejaVu Sans, Consolas, monospace" font-size 继承 11；RENDER_TEXT_PX=7.006
    IIII: box 15.898 vs cons@7.006 30.815（画宽 194%）；WWWW: 53.984 vs cons 30.815
p2: NUL/STX/VT/0x1F → write_preview 写出 1447 B 文件，ET.parse → ParseError；函数仍返回路径
p4: vertical-first → label_wire_indices=[0,1] 但 preview row=None；horizontal-first 只画 1 行、caption 不提第二载体
```

## ② 当前树状态

- 混合未提交工作树；`svgpreview.py`、`textmetrics.py` 的既有未提交差量属其它批（**不许回退**）。
- 相关位置：`svgpreview.py:95` `NATIVE_TEXT_FONT_SIZE=7.006`、`:154` `_anchor_on_run`、`:180` `_label_carrier_row`、`:232` `render_svg`、`:316` font-family、`:460` `write_preview`、`:582` `_caption_lines`；`textmetrics.py` 的 `advance()`/`RENDER_TEXT_PX`/`render_width()`。
- 开工前：`cp` 两个源文件到 `.tmp_565d/backup/` 并记 SHA-256。

## ③ 文件域与禁触清单

**允许：** `src/boardwise/engines/svgpreview.py`、`src/boardwise/core/textmetrics.py`、新建 `tests/test_565d_preview_holes.py`、`evidence/565d/`、`.tmp_565d/**`。

**禁触：** `cli.py`、`engines/drawlint.py`、`core/circuitsemantics.py`、`core/netlist.py`、`core/presentationspec.py`、`commands/draw.py`（属 565b/565e/565f/565g）、`contracts/`、`tests/fixtures/`、任何既有测试断言。

## ④ 交付物与验收（先红后绿）

新建 `tests/test_565d_preview_holes.py`（纯内存构造 LayoutPlan/Sheet 夹具，**不用 `tmp_path`**，写盘用 `.tmp_565d/`）。父级裁决：

| 洞 | 期望行为 | 先红断言 |
|---|---|---|
| **S6-H1** | 虚线盒宽度 = 这串字在 SVG 上**实际**占的宽度：`font-family` 与 `textmetrics` 的计算族同源（一个常量，如 `Arial, Helvetica, sans-serif`），字号同源（盒子按 `RENDER_TEXT_PX`，不再用 7.1483）。同一份 SVG 在任何机器上宽度一致（不依赖本机是否装 DejaVu） | `advance(text,"Arial",7.006)` 与盒宽差 >0.5；SVG 根 `font-family` 与度量族不一致 |
| **S6-H2** | 所有进 SVG 的文字先过 `_text_safe()`（剔除 C0 控制字符，保留 `\t\n\r`），`write_preview` 写盘前 `ET.fromstring(render_svg(...))` 自检，失败抛 `ValueError` 且**不落盘**、不返回路径 | `ET.fromstring(render_svg(plan_with("A\x01B")))` 当前 ParseError；`write_preview` 当前写出坏文件仍返回 |
| **S6-H4** | 图上名字行数 = landing 真正命名的 horizontal carrier 数（每条一行，返回 `list[WireNameRow]` 并逐个绘制）；竖排 carrier 不静默退回 bbox 中心，而是在 caption/notes 里显式披露「竖排载体未建模」 | 同名 `<text>` 数量当前 1 ≠ `len(label_wire_indices)`=2；vertical-first 当前 row=None 且 caption 无 note |

**验收读数：**

```
.venv\Scripts\python.exe -m pytest tests/test_565d_preview_holes.py -q --basetemp=.tmp_pt_565d
.venv\Scripts\python.exe -m pytest tests/test_565d_preview_holes.py tests/test_580_svgpreview.py tests/test_svgpreview_label_carrier.py tests/test_svgpreview_native_text.py tests/test_575_text_metrics.py tests/test_548p44_native_art_preview.py -q --basetemp=.tmp_pt_565d
```

- 先红 ≥3 failed；后绿全 passed。
- **逐洞变异**：H1 把族/字号其一改回旧值 → H1 用例红；H2 去掉 `_text_safe` 或自检 → H2 用例红；H4 让 `_label_carrier_row` 只回第一行 → H4 用例红；各自 `cp` 还原 + SHA-256 核对。
- **钉死输出类测试的处理**：H1 会让盒宽/坐标有 ~2% 级变化。若 `test_580_svgpreview`/`test_svgpreview_label_carrier` 等**既有**用例因合法几何变化变红，**停下报告**（贴失败断言与差量），不自改既有断言、不批量重录 golden；由主代理裁决。

## ⑤ 纪律与红线

1. 零 git 写；零删除（禁 `rm`/`Remove-Item`）。
2. 不跑全量 pytest、不 `-n auto`、不碰 bridge/EDA、不联网。
3. 不改他人未提交差量；不新建第二套渲染器；只修这三条。
4. 不得放宽既有断言、skip/xfail、改夹具；「机器绿」不等于视觉通过——本批只出机器闸与解析自检，不签视觉验收。
5. 有红项或无读数，写「停止/未验收」。

## ⑥ 预算与交卷格式

- 上限 **40 步 / 30 分钟**。
- `evidence/565d/REPORT.md`：开工哈希、先红原文、三洞修复点、三次变异读数、后绿原文、H3 关单反证（包装形/坏形状 exit 2）、既有钉死测试的影响面、未做项。
- 最终回复 ≤2000 字：结论 + 关键读数 + 证据路径 + 需裁决项。
