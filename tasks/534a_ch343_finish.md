# 534A — CH343 USB 转 UART 小板交付收口

日期：2026-10-31 起 · 接续 `tasks/534_ch343_uart.md` · 授权：岳「把 CH343 的
UART 转 USB 模块原理图做好」+ 0.6.0 绘制线规划

> **2026-11-01 交付状态（V4 重画后）：以 V4 为准。** 页 `40091c5d26a5db27`
> （`/test V4`，`.eprj3`，宿主名 **P2**）；11 件 / 54 段计划线 / 15 旗标；
> `draw lint` **0 ERROR / 2 WARN**；独立逐脚 **17 网 / 58 脚 / 3 NC PASS**；
> apply exit 0、已保存、`saved_unverified`。详见 `evidence/534a_v4/report.md`。
>
> 历史 V3 落图（`/test` P4，`26e6a63bae878c44`，17 网 / 53 脚）仍在，但**已被
> V4 P2 取代，不再作为交付页**；两页使用同一份 `ch343_uart_534a.*`，V3 页未删除。
> 旧 `ch343_uart.*` 保持 0.6.0 四岛示例，不混改。checkup 整工程仍 `incomplete`
> （11 颗新件不在 PCB2，另有宿主 warning），不是板级通过。
>
> **回归**：全量 pytest **8826 passed / 23 skipped / 2 failed**（两条均为环境：
> `pytest-slots` ACL、MSYS `0xC0000022`）；connector **542 passed** + typecheck；
> DSH **127 passed / 1 skipped** + typecheck/build；Rust **47 passed / 4 ignored** +
> fmt/clippy。534A 相关 64 项测试全绿。

## 0. 为什么重开

`a8613c5` 已落四岛版到 `test Board2 P3`，`draw compile` 可出 `ok=True`，但当前源码重编译
仍有 3 处 soft-floor（`S-09` 30 弯/29 根、单根 5 弯、`S-21` 文字净距 0），
且 `usb_c` 岛内 USB-C 16 脚符号与 5 个外围件挤在一起，视觉上仍是“线团 + 大片空白”。
0.6.0 文档里的“CH343 示例已入库”只说明 spec 和落图存在，不说明这页达到交付标准。

## 1. 不可改变的设计裁定（继承 534）

- CH343G（SOP-16，C2844153）；Type-C 16P（C165948）；2×5P 2.54 排针（C49056209）。
- CC1/CC2 各 5.1kΩ 下拉到 GND；D+/D− 直连，不串阻；VBUS 5V → VDD5。
- VDD5：100nF + 10µF；V3：100nF；VIO/VCC 由排针对端供电，C4 100nF 到 GND。
- UART 侧 10 脚全部引出：TXD/RXD/RTS/CTS/DTR/DSR/DCD/RI/VCC/GND。
- 电源灯 VBUS → LED 红 → 1kΩ → GND。
- 地/电源一律旗标；网络标签只用于跨岛信号边界。D+/D− 保留每脚独立短载体 + 同名标签。

## 2. 当前可复现基线

```bash
.venv/Scripts/boardwise.exe draw compile \
  --circuit blocklib/specs/ch343_uart_534a.circuit.json \
  --presentation blocklib/specs/ch343_uart_534a.presentation.json \
  --profiles blocklib/specs/ch343_uart.library.json \
  --page-box 0,0,1170,825 --out .tmp_534a/compile_final8
```

最终读数：5 candidates / 0 failures；cand1 `legality=0 findings=0 crossings=0`，
`bends=28`、`wire_length=2235`、`unaligned_part_pairs=6`、`area=666622`；
`min_text_gap=0` 仍在（ref/value 边贴边 + Type-C 镜像对），作为已知软项披露。

## 3. 开发路线（先改 presentation，不先重写布局器）

1. **拆岛，不拆电气**：把 `usb_c` 的 6 件拆成
   `usb_connector`（USB1）/ `cc_term`（R1、R2）/ `vbus`（C2、D1、R3），
   与现存的 `ch343`、`ch343_power`、`hdr` 组成 6 岛；跨岛信号用标签，电源/地用旗标。
   目标：让每个岛只回答一个视觉问题（座子、CC、VBUS 灯、桥、去耦、排针）。
2. **只认三关，不认“机器 ok”**：每版先 `draw compile`，看 `soft floor` 与 SVG；
   不过就换岛划分/端口角色/流顺序，不把失败候选落到画布。
3. **必要时才动引擎**：若 6 岛仍在同一处软指标失败，只开一个窄修（一个文件域、
   有回归、≥2 变异），不在本批重写布线器；宽修另立批。
4. **真机落图**：优先在 `test` 新建专用页（不复用旧 P3 作为唯一证据），
   `bridge status` + `doc.list` 核对工程名逐字为 `test`；若用 V4，必须先确认
   `test V4` 在线并单独记录。
5. **三关**：`draw lint`（0 ERROR；WARN/INFO 逐条解释）→ 逐脚连通回验（对照 circuit
   17 网 / 53 脚 / 3 NC）→ 渲染 PNG/SVG 视觉自审（逐岛说清“是什么、怎么接、
   和网表对不对”）。
6. **审查线 dogfood**：对最终页跑 `checkup`，把发现记入报告；能修的修，不能修的
   记为管线缺口，不假绿。

## 4. 完成定义

- 一页 CH343 原理图，三关全过，渲染图端得出手；页名/工程名/证据路径写清。
- 报告：设计裁定落地、datasheet 四核对、soft 指标前后、每岛视觉说明、lint 明细、
  连通逐脚结果、checkup 发现、管线缺口。
- 文档同步：本文件、534 状态、TASKMAP、roadmap、handoff 四处一致；
  不把 `a8613c5` 的示例写成最终交付。
- 全量测试不因本批 spec 变红；改引擎则跑聚焦 + 全量，附变异证据。

## 5. 证据落点

`evidence/534a_v4/`：V4 P2 的 `render_final.png`、`apply.json`、`plan.json`、
`lint.json`、`netlist.json`、`geometry.json`、`connectivity.json`、`report.md`、
`SHA256SUMS`。V3 历史证据仍在 `evidence/534a/`，只作对照，不再作为交付页。
一次性中间态放 `.tmp_534a/`（V3）与 `.tmp_534v4/`（V4）。
